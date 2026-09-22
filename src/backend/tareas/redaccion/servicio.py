"""El paquete del redactor y la escritura de su prosa en el grafo.

Este es el paquete que la arquitectura describe bloque a bloque. Todo lo que entra, entra
porque el orquestador lo selecciono; el agente no busca canon por su cuenta y no tiene
herramientas con las que hacerlo.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from compartido.contexto import Paquete, ajustar
from compartido.grafo import insertar, lectura

from .esquemas import SalidaRedaccion

AGENTE = "redaccion"


def _instrucciones(con: sqlite3.Connection, novela_id: int, capitulo: int) -> str:
    n = lectura.novela(con, novela_id) or {}
    e = lectura.estilo(con, novela_id) or {}
    tics = lectura.tics_prohibidos(con, novela_id)
    lineas = [
        f"Escribes el capitulo {capitulo} de «{n.get('titulo', '')}».",
        f"Punto de vista por defecto: {n.get('pov_por_defecto', '')}. "
        f"Tiempo verbal: {n.get('tiempo_verbal', '')}.",
        "",
        "ESTILO NARRATIVO (constante en toda la obra):",
        f"- Registro: {e.get('registro', '')}",
        f"- Ritmo de prosa: {e.get('ritmo_prosa', '')}",
        f"- Densidad sensorial: {e.get('densidad_sensorial', '')}",
        f"- Distancia psiquica por defecto: {e.get('distancia_psiquica', '')}",
    ]
    if e.get("convenciones_formato"):
        lineas.append(f"- Convenciones de formato: {e['convenciones_formato']}")
    if tics:
        lineas += ["", "TICS PROHIBIDOS (una sola aparicion devuelve el capitulo entero):"]
        lineas.extend(f"- {t}" for t in tics)
    return "\n".join(lineas)


def _escaleta(escenas: list[dict[str, Any]]) -> str:
    bloques: list[str] = []
    for e in escenas:
        partes = [
            f"### Escena {e['orden']}"
            + (" (ANALEPSIS: ocurre antes en la cronologia)" if e["analepsis"] else ""),
            f"- POV: {e['pov_nombre']}",
            f"- Lugar: {e['lugar_nombre']}",
            f"- Reparto: {', '.join(e['reparto'])}",
            f"- Objetivo: {e['objetivo']}",
            f"- Conflicto: {e['conflicto']}",
            f"- Resultado: {e['resultado']}",
            f"- Valor en juego: {e['valor_inicial']} -> {e['valor_final']}",
            f"- Tension: {e['tension']}/10",
            f"- Longitud prevista: {e['longitud_prevista']} palabras",
        ]
        if e.get("gancho_salida"):
            partes.append(f"- Gancho de salida: {e['gancho_salida']}")
        if e.get("objetos"):
            partes.append(f"- Objetos presentes: {', '.join(e['objetos'])}")
        if e.get("beats"):
            partes.append("- Beats: " + " | ".join(b["cambio"] for b in e["beats"]))
        if e.get("secuela"):
            s = e["secuela"]
            partes.append(
                f"- Secuela: reacciona {s['reaccion']}; duda entre {s['dilema']}; "
                f"decide {s['decision']}"
            )
        bloques.append("\n".join(partes))
    return "\n\n".join(bloques)


def _canon(canon: dict[str, list[dict[str, Any]]]) -> str:
    partes: list[str] = []

    if canon["personajes"]:
        partes.append("### Personajes")
        for p in canon["personajes"]:
            partes.append(
                f"**{p['nombre']}** ({p['rol_narrativo']}). Desea {p['deseo']}. "
                f"Necesita {p['necesidad_interna']}. Defecto visible: {p['defecto']}. "
                f"Cree que {p['mentira']}.\nIdiolecto: {p['idiolecto']}"
                + (f"\nGuarda: {p['secreto']}" if p.get("secreto") else "")
            )
    if canon["lugares"]:
        partes.append("### Lugares")
        partes.extend(
            f"**{lugar['nombre']}** ({lugar['tipo']}). {lugar['descripcion']}"
            for lugar in canon["lugares"]
        )
    if canon["objetos"]:
        partes.append("### Objetos")
        partes.extend(
            f"**{o['nombre']}**: {o['funcion_narrativa']}" for o in canon["objetos"]
        )
    if canon["sistemas"]:
        partes.append("### Sistemas tecnicos (sus limites no se rompen)")
        partes.extend(
            f"**{s['nombre']}**. Puede: {s['capacidades']}. Cuesta: {s['costes']}. "
            f"Limites: {s['limites']}"
            for s in canon["sistemas"]
        )
    for a in canon["amenaza"]:
        try:
            reglas = json.loads(a.get("reglas") or "[]")
        except json.JSONDecodeError:
            reglas = []
        partes.append("### La amenaza (sus reglas no se rompen nunca)")
        partes.append(a["naturaleza"])
        partes.extend(
            f"- Puede {r.get('capacidad', '')}. No puede {r.get('limite', '')}. "
            f"Se activa con {r.get('activacion', '')}."
            for r in reglas if isinstance(r, dict)
        )
    return "\n\n".join(partes)


def _hechos(hechos: list[dict[str, Any]], conocimiento: list[dict[str, Any]]) -> str:
    partes: list[str] = []
    if hechos:
        partes.append("### Hechos ya establecidos (no los contradigas)")
        partes.extend(
            f"- {h['sujeto_nombre']} · {h['atributo']}: {h['valor']} (cap. "
            f"{h['capitulo_origen']})"
            for h in hechos
        )
    if conocimiento:
        partes.append(
            "### Quien sabe que (nadie puede actuar sobre lo que no ha recibido)"
        )
        partes.extend(
            f"- {c['personaje']} {c['postura']} que {c['sujeto_nombre']} · {c['atributo']}: "
            f"{c['valor']} (desde cap. {c['capitulo']}, {c['via']})"
            for c in conocimiento
        )
    return "\n".join(partes)


def paquete(
    con: sqlite3.Connection,
    novela_id: int,
    capitulo: int,
    *,
    criterios_incumplidos: list[dict[str, str]] | None = None,
    recuperado: list[Any] | None = None,
) -> Paquete:
    """Monta el paquete del capitulo y lo ajusta al presupuesto (RF-CTX-01)."""
    escenas = lectura.escenas_del_capitulo(con, novela_id, capitulo)
    canon = lectura.canon_del_capitulo(con, novela_id, capitulo)
    cap = lectura.capitulo(con, novela_id, capitulo) or {}

    p = Paquete(agente=AGENTE, capitulo=capitulo)
    p.anadir("instrucciones", _instrucciones(con, novela_id, capitulo), "TU ENCARGO Y EL ESTILO")

    cabecera = [
        f"Objetivo del capitulo: {cap.get('objetivo', '')}",
        f"Gancho de apertura: {cap.get('gancho_apertura', '')}",
        f"Gancho de cierre: {cap.get('gancho_cierre', '')}",
    ]
    p.anadir(
        "escaleta",
        "\n".join(cabecera) + "\n\n" + _escaleta(escenas),
        f"ESCALETA DEL CAPITULO {capitulo}",
    )
    p.anadir("canon", _canon(canon), "CANON DE ESTE CAPITULO")
    p.anadir(
        "hechos",
        _hechos(
            lectura.hechos_del_reparto(con, novela_id, capitulo),
            lectura.conocimiento_del_reparto(con, novela_id, capitulo),
        ),
        "ESTADO ESTABLECIDO",
    )

    siembras = lectura.siembras_vivas(con, novela_id, capitulo)
    if siembras:
        p.anadir(
            "siembras",
            "\n".join(
                f"- [{s['estado']}] {s['elemento']}"
                + (f" (pago previsto hacia el cap. {s['capitulo_pago_previsto']})"
                   if s["capitulo_pago_previsto"] else "")
                for s in siembras
            ),
            "SIEMBRAS VIVAS",
        )

    p.anadir(
        "estado_rodante",
        lectura.estado_rodante(con, novela_id, capitulo),
        "LO QUE HA PASADO HASTA AQUI",
    )
    if capitulo > 1:
        p.anadir(
            "capitulo_anterior",
            lectura.texto_capitulo(con, novela_id, capitulo - 1),
            f"TEXTO DEL CAPITULO {capitulo - 1}",
        )

    if recuperado:
        p.anadir(
            "recuperado",
            "\n\n".join(
                f"[cap. {f.capitulo}, escena {f.orden}, {f.lugar}]\n{f.texto}"
                for f in recuperado
            ),
            "COMO SE DESCRIBIO ESTO ANTES (no lo repitas ni lo contradigas)",
        )

    if criterios_incumplidos:
        p.anadir(
            "criterios_incumplidos",
            "\n\n".join(
                f"**{c['criterio']}** (principio {c.get('principio', '')}): "
                f"{c.get('sugerencia', '')}\nEvidencia del intento anterior: "
                f"«{c.get('evidencia', '')}»"
                for c in criterios_incumplidos
            ),
            "LO QUE FALLO EN EL INTENTO ANTERIOR. Reescribe desde la escaleta, no parchees",
        )

    return ajustar(p)


def aplicar(
    con: sqlite3.Connection,
    novela_id: int,
    capitulo: int,
    salida: SalidaRedaccion,
    *,
    intento: int = 1,
    llamada_id: int | None = None,
) -> dict[int, int]:
    """Guarda una version nueva del texto de cada escena. Nunca hace UPDATE (RF-PER-05).

    Devuelve {orden de escena: escena_id}, que es lo que el extractor necesita para referirse
    a las escenas por su numero.
    """
    escenas = lectura.escenas_del_capitulo(con, novela_id, capitulo)
    salida.comprobar_contra_escaleta([e["orden"] for e in escenas])
    por_orden = {int(e["orden"]): int(e["id"]) for e in escenas}

    for escrita in salida.escenas:
        escena_id = por_orden[escrita.orden]
        # Las versiones anteriores dejan de ser vigentes; no se borran, son historia legible.
        con.execute(
            "UPDATE escena_texto SET estado = 'descartada' WHERE escena_id = ? "
            "AND estado = 'vigente'",
            (escena_id,),
        )
        version = int(con.execute(
            "SELECT COALESCE(MAX(version), 0) + 1 FROM escena_texto WHERE escena_id = ?",
            (escena_id,),
        ).fetchone()[0])
        insertar(
            con, "escena_texto", novela_id=novela_id, escena_id=escena_id, version=version,
            texto=escrita.texto, palabras=escrita.palabras, origen="redaccion",
            intento=intento, estado="vigente", llamada_modelo_id=llamada_id,
        )
    return por_orden


def compilar(con: sqlite3.Connection, novela_id: int, capitulo: int) -> int:
    """Concatena las versiones vigentes en orden y guarda el capitulo compilado."""
    filas = con.execute(
        """
        SELECT et.texto FROM escena_texto et
        JOIN escena e   ON e.id = et.escena_id
        JOIN capitulo c ON c.id = e.capitulo_id
        WHERE et.novela_id = ? AND c.numero = ? AND et.estado = 'vigente'
        ORDER BY e.orden
        """,
        (novela_id, capitulo),
    ).fetchall()
    texto = "\n\n* * *\n\n".join(str(f["texto"]) for f in filas)
    cap = lectura.capitulo(con, novela_id, capitulo) or {}
    capitulo_id = int(cap["id"])

    con.execute(
        "UPDATE capitulo_compilado SET estado = 'descartada' WHERE capitulo_id = ? "
        "AND estado = 'vigente'",
        (capitulo_id,),
    )
    version = int(con.execute(
        "SELECT COALESCE(MAX(version), 0) + 1 FROM capitulo_compilado WHERE capitulo_id = ?",
        (capitulo_id,),
    ).fetchone()[0])
    return insertar(
        con, "capitulo_compilado", novela_id=novela_id, capitulo_id=capitulo_id,
        version=version, texto=texto, palabras=len(texto.split()), estado="vigente",
    )
