"""La rubrica: paquete, registro y comparacion con la revision humana (LLM-as-judge).

El juez lee la novela entera al terminar la generacion y pone una nota de 1 a 5 a seis
criterios, cada una con su justificacion y una cita literal. No bloquea: una nota de 2 o menos
deja un evento `rubrica_baja` para que el autor lo mire. La misma tabla guarda la revision
humana (`origen = 'humano'`), para comparar las dos con `evals/rubrica_humana.py`.
"""

from __future__ import annotations

import re
import sqlite3
from typing import Any

from compartido.contexto import Paquete, Presupuesto, ajustar
from compartido.grafo import lectura, normalizar
from compartido.tipos import CRITERIOS_RUBRICA

from .esquemas import SalidaRubrica

AGENTE = "rubrica"

#: Una nota igual o menor deja el evento `rubrica_baja`.
NOTA_BAJA = 2

#: Una cita de menos palabras no prueba nada: «el» esta en cualquier novela.
PALABRAS_MINIMAS_DE_CITA = 3

# La tipografia que el modelo no copia igual: la cursiva del redactor (*...*), las comillas y
# las rayas. Se quitan en los dos lados antes de comparar.
_TIPOGRAFIA = re.compile(r"[*_«»“”„\"'‘’`]")
_RAYAS = re.compile(r"[—–‒―-]")
_NO_PALABRA = re.compile(r"[^\w\s]")


def _para_comparar(texto: str) -> str:
    sin_marcas = _RAYAS.sub(" ", _TIPOGRAFIA.sub("", texto))
    return " ".join(normalizar(_NO_PALABRA.sub(" ", sin_marcas)).split())


def es_cita_literal(evidencia: str, texto_normalizado: str) -> bool:
    """La evidencia aparece en la novela, sin mirar cursivas, comillas, rayas ni puntuacion,
    y tiene al menos `PALABRAS_MINIMAS_DE_CITA` palabras."""
    cita = _para_comparar(evidencia)
    return len(cita.split()) >= PALABRAS_MINIMAS_DE_CITA and f" {cita} " in texto_normalizado


#: Que mide cada criterio. La skill los explica; el paquete los repite, para que la rubrica
#: que usa el juez y la plantilla del humano sean la misma.
DESCRIPCIONES: dict[str, str] = {
    "continuidad": "Hechos, nombres, cifras y tiempos no se contradicen de un capitulo a otro.",
    "tono": "El tono y la intensidad pedidos se sostienen de principio a fin.",
    "arco": "La novela plantea una pregunta dramatica y la cierra; la protagonista cambia.",
    "coherencia_personajes": "Cada personaje actua segun lo que se ha contado de el, y su voz "
                             "se distingue de las demas.",
    "ritmo": "La tension crece y alterna con respiros; ninguna parte sobra ni va con prisa.",
    "personalizacion_natural": "Los datos del destinatario (nombre, allegados, recuerdos) "
                               "estan integrados en la historia y no pegados.",
}


def texto_de_la_novela(con: sqlite3.Connection, novela_id: int) -> str:
    """Los capitulos completados, en orden, con su numero."""
    partes: list[str] = []
    for f in con.execute(
        "SELECT numero FROM capitulo WHERE novela_id = ? AND estado = 'completado' "
        "ORDER BY numero", (novela_id,),
    ):
        texto = lectura.texto_capitulo(con, novela_id, int(f[0]))
        if texto:
            partes.append(f"## Capitulo {f[0]}\n\n{texto}")
    return "\n\n".join(partes)


def paquete(con: sqlite3.Connection, novela_id: int, *, presupuesto: Presupuesto) -> Paquete:
    novela = con.execute("SELECT * FROM novela WHERE id = ?", (novela_id,)).fetchone()
    p = Paquete(agente=AGENTE)
    instrucciones = [
        "Puntua la novela entera, de 1 a 5, en cada uno de estos criterios:",
        *(f"- `{c}`: {DESCRIPCIONES[c]}" for c in CRITERIOS_RUBRICA),
        "",
        f"Titulo: {novela['titulo'] if novela else ''}",
    ]
    if novela is not None:
        for campo in ("premisa", "pregunta_dramatica", "tema_central", "tipo_final"):
            if novela[campo]:
                instrucciones.append(f"{campo.replace('_', ' ').capitalize()}: {novela[campo]}")
    brief = lectura.brief(con, novela_id)
    if brief is not None:
        instrucciones.append(f"Intensidad pedida: {brief.intensidad}. Tono pedido: {brief.tono}.")
    p.anadir("instrucciones", "\n".join(instrucciones), "TU ENCARGO")

    fichas = [
        f"- **{x['nombre']}** ({x['rol_narrativo']}): deseo «{x['deseo'] or ''}», "
        f"necesidad «{x['necesidad_interna'] or ''}», arco {x['tipo_arco'] or 'sin declarar'}"
        for x in con.execute(
            "SELECT nombre, rol_narrativo, deseo, necesidad_interna, tipo_arco FROM personaje "
            "WHERE novela_id = ? ORDER BY id", (novela_id,))
    ]
    if fichas:
        p.anadir("canon", "\n".join(fichas), "PERSONAJES (lo que prometio el elenco)")
    elementos = [f"- {e['tipo']}: {e['texto']}"
                 for e in lectura.elementos_personales(con, novela_id)]
    if elementos:
        p.anadir("escaleta", "\n".join(elementos),
                 "DATOS DEL DESTINATARIO QUE LA NOVELA TENIA QUE INTEGRAR")
    p.anadir("prosa", texto_de_la_novela(con, novela_id), "LA NOVELA")
    return ajustar(p, presupuesto)


def _version_actual(con: sqlite3.Connection, novela_id: int) -> int | None:
    fila = con.execute("SELECT MAX(numero) FROM novela_version WHERE novela_id = ?",
                       (novela_id,)).fetchone()
    return int(fila[0]) if fila and fila[0] is not None else None


def registrar(
    con: sqlite3.Connection,
    novela_id: int,
    notas: list[dict[str, Any]],
    *,
    origen: str,
    llamada_id: int | None = None,
) -> list[str]:
    """Guarda una evaluacion completa. Devuelve los criterios con nota baja.

    En las del juez se anota si la evidencia es de verdad una cita de la novela: una cita
    inventada no invalida la nota, pero deja constancia (se compara sin tildes ni mayusculas).
    """
    version = _version_actual(con, novela_id)
    texto = (f" {_para_comparar(texto_de_la_novela(con, novela_id))} "
             if origen == "llm" else "")
    bajas: list[str] = []
    for n in notas:
        evidencia = str(n.get("evidencia") or "")
        literal = int(es_cita_literal(evidencia, texto)) if origen == "llm" else None
        con.execute(
            "INSERT INTO evaluacion_rubrica (novela_id, version, origen, criterio, nota, "
            "justificacion, evidencia, evidencia_literal, llamada_id) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (novela_id, version, origen, n["criterio"], int(n["nota"]),
             str(n.get("justificacion") or ""), evidencia, literal, llamada_id),
        )
        if int(n["nota"]) <= NOTA_BAJA:
            bajas.append(str(n["criterio"]))
    return bajas


def registrar_salida(con: sqlite3.Connection, novela_id: int, salida: SalidaRubrica,
                     *, llamada_id: int | None) -> list[str]:
    return registrar(con, novela_id, [n.model_dump() for n in salida.notas], origen="llm",
                     llamada_id=llamada_id)


def existe_la_tabla(con: sqlite3.Connection) -> bool:
    """Si la base ya tiene la migracion 015."""
    return con.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' "
                       "AND name = 'evaluacion_rubrica'").fetchone() is not None


def ultimas_notas(con: sqlite3.Connection, novela_id: int, origen: str) -> dict[str, int]:
    """La nota mas reciente de cada criterio para un origen."""
    salida: dict[str, int] = {}
    for f in con.execute(
        "SELECT criterio, nota FROM evaluacion_rubrica WHERE novela_id = ? AND origen = ? "
        "ORDER BY id", (novela_id, origen),
    ):
        salida[str(f[0])] = int(f[1])  # por posicion: vale con o sin row_factory
    return salida


def comparar(con: sqlite3.Connection, novela_id: int) -> str:
    """La tabla del juez frente a la revision humana, con el acuerdo."""
    llm = ultimas_notas(con, novela_id, "llm")
    humano = ultimas_notas(con, novela_id, "humano")
    filas = ["| Criterio | LLM | Humano | Diferencia |", "| --- | --- | --- | --- |"]
    diferencias: list[int] = []
    for c in CRITERIOS_RUBRICA:
        a, b = llm.get(c), humano.get(c)
        dif = "—" if a is None or b is None else f"{a - b:+d}"
        if a is not None and b is not None:
            diferencias.append(abs(a - b))
        filas.append(f"| {c} | {a if a is not None else '—'} | "
                     f"{b if b is not None else '—'} | {dif} |")
    if diferencias:
        media = sum(diferencias) / len(diferencias)
        exactos = sum(d == 0 for d in diferencias)
        cercanos = sum(d <= 1 for d in diferencias)
        filas += ["", f"Diferencia media absoluta: {media:.2f} sobre {len(diferencias)} "
                      f"criterios. Acuerdo exacto: {exactos}; a un punto o menos: {cercanos}."]
    else:
        filas += ["", "Falta una de las dos evaluaciones: no hay nada que comparar."]
    return "\n".join(filas)
