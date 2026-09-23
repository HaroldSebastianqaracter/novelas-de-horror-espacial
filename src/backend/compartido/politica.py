"""El guardrail de terminos vetados (specs/spec3.md, 3.5: RF3-GRD-01 a RF3-GRD-04).

Vive en `compartido/` por la misma razon que `texto.py`: el analisis del brief decide si un
termino vetado choca con un elemento personal, y este modulo decide si la prosa lo usa. Tienen
que normalizar exactamente igual, o lo que uno deja pasar el otro lo bloquea. Por eso parte las
palabras con `normalizar` y `formas` de alli.

La busqueda es por secuencias de palabras completas, nunca por subcadena, y guarda la posicion
de cada hallazgo sobre el texto ORIGINAL: el registro de decisiones tiene que poder senalar el
pasaje exacto aunque el texto llevara caracteres invisibles.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import unicodedata
from dataclasses import dataclass

from compartido.grafo import lectura
from compartido.grafo.escritura import normalizar
from compartido.texto import formas

#: Cambia si cambia la normalizacion (aqui o en compartido/texto.py): entra en la huella.
VERSION_NORMALIZACION = "texto-1"
NIVELES = ("atmosferico", "tension", "intenso")
_PALABRA = re.compile(r"[^\W_]+", re.UNICODE)
_CONTEXTO = 40


@dataclass(frozen=True)
class Regla:
    termino: str
    origen: str  # global, novela o brief
    excepciones: tuple[str, ...] = ()


@dataclass(frozen=True)
class Hallazgo:
    regla: Regla
    forma: str
    inicio: int
    fin: int
    fragmento: str


def reglas(con: sqlite3.Connection, novela_id: int) -> list[Regla]:
    """Los terminos que aplican a la novela: globales de su nivel, suyos y del brief."""
    brief = lectura.brief(con, novela_id)
    nivel = brief.intensidad if brief is not None else None
    # Sin intensidad, solo lo que se veta en todos los niveles.
    aplicables = NIVELES[NIVELES.index(nivel):] if nivel else ("intenso",)
    salida = [
        Regla(str(f["termino"]), "global" if f["novela_id"] is None else "novela",
              tuple(json.loads(f["excepciones"])))
        for f in con.execute(
            f"""
            SELECT termino, novela_id, excepciones FROM termino_vetado
            WHERE (novela_id IS NULL AND hasta_nivel IN ({",".join("?" * len(aplicables))}))
               OR novela_id = ?
            ORDER BY novela_id IS NOT NULL, id
            """,
            (*aplicables, novela_id),
        )
    ]
    if brief is not None:
        salida += [Regla(v, "brief") for v in brief.vetados]
    return salida


def huella(aplicadas: list[Regla]) -> str:
    """Lo que se aplico, para poder decir despues con que politica se decidio."""
    datos = json.dumps(
        [VERSION_NORMALIZACION, sorted((r.termino, r.origen, sorted(r.excepciones))
                                       for r in aplicadas)],
        ensure_ascii=False,
    )
    return hashlib.sha256(datos.encode("utf-8")).hexdigest()


def _tokens(texto: str) -> list[tuple[frozenset[str], int, int]]:
    """Las palabras del texto con sus formas y su posicion en el ORIGINAL.

    Los caracteres de formato invisibles (Cf: el espacio de ancho cero, el guion blando) se
    saltan sin partir la palabra: «san\\u200bgre» es «sangre».
    """
    limpio: list[str] = []
    origen: list[int] = []
    for i, c in enumerate(texto):
        if unicodedata.category(c) == "Cf":
            continue
        limpio.append(c)
        origen.append(i)
    plano = "".join(limpio)
    return [
        (formas(normalizar(m.group(0))), origen[m.start()], origen[m.end() - 1] + 1)
        for m in _PALABRA.finditer(plano)
    ]


def _secuencias(
    tokens: list[tuple[frozenset[str], int, int]], expresion: str
) -> list[tuple[int, int]]:
    buscadas = [formas(normalizar(p)) for p in _PALABRA.findall(expresion)]
    n = len(buscadas)
    if not n:
        return []
    return [
        (tokens[i][1], tokens[i + n - 1][2])
        for i in range(len(tokens) - n + 1)
        if all(tokens[i + k][0] & buscadas[k] for k in range(n))
    ]


def buscar(texto: str, aplicadas: list[Regla]) -> list[Hallazgo]:
    """Cada aparicion de un termino como palabras completas, fuera de sus excepciones."""
    tokens = _tokens(texto)
    salida: list[Hallazgo] = []
    for regla in aplicadas:
        excluidas = [s for e in regla.excepciones for s in _secuencias(tokens, e)]
        for inicio, fin in _secuencias(tokens, regla.termino):
            if any(a <= inicio and fin <= b for a, b in excluidas):
                continue
            salida.append(Hallazgo(
                regla=regla, forma=texto[inicio:fin], inicio=inicio, fin=fin,
                fragmento=texto[max(0, inicio - _CONTEXTO):fin + _CONTEXTO].replace("\n", " "),
            ))
    return sorted(salida, key=lambda h: (h.inicio, h.regla.termino))


def registrar(
    con: sqlite3.Connection, novela_id: int, capitulo: int, intento: int, texto: str,
    hallazgos: list[dict[str, object]], politica: str, *, accion: str,
) -> None:
    """Una fila de `decision_politica` por hallazgo (RF3-GRD-04). Quien llama abre la
    transaccion: el worker es el unico escritor."""
    huella_texto = hashlib.sha256(texto.encode("utf-8")).hexdigest()
    con.executemany(
        """
        INSERT INTO decision_politica (novela_id, capitulo, intento, termino, origen, forma,
            fragmento, inicio, fin, accion, huella_politica, huella_texto)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        [(novela_id, capitulo, intento, h["termino"], h["origen"], h["forma"], h["fragmento"],
          h["inicio"], h["fin"], accion, politica, huella_texto) for h in hallazgos],
    )
