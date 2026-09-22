"""Puerta 4, parte mecanica (RF-PIPE-13, punto 1).

Busquedas dirigidas sobre listas cerradas: lo que se puede comprobar contando, antes de
gastar una llamada de juicio. Corre primero porque es gratis.

Solo los tics prohibidos **fallan**. El resto son avisos que van al informe y al juez: que
haya tres palabras filtro no significa que la voz falle, y convertirlo en fallo automatico
produciria prosa timida en vez de prosa buena.
"""

from __future__ import annotations

import re
import sqlite3
import unicodedata

from compartido.grafo import lectura
from compartido.puerta_base import Conflicto, ResultadoPuerta
from config import PALABRAS_FILTRO

# «dijo secamente», «respondio friamente»: el adverbio que sostiene un verbo debil.
_ADVERBIO_ATRIBUCION = re.compile(
    r"\b(dijo|respondio|respondió|pregunto|preguntó|exclamo|exclamó|murmuro|murmuró|"
    r"susurro|susurró|anadio|añadió)\s+\w+mente\b",
    re.IGNORECASE,
)

# Verbos de habla expresivos: si hacen falta, la replica no es lo bastante dura por si sola.
_VERBOS_EXPRESIVOS = (
    "espeto", "espetó", "bramo", "bramó", "vocifero", "vociferó", "siseo", "siseó",
    "gruno", "gruñó", "chillo", "chilló", "ladro", "ladró", "escupio", "escupió",
)


def _sin_tildes(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    ).lower()


def _contar(texto_normalizado: str, expresion: str) -> int:
    return len(re.findall(rf"\b{re.escape(_sin_tildes(expresion))}\b", texto_normalizado))


def evaluar(
    con: sqlite3.Connection, novela_id: int, capitulo: int, texto: str
) -> ResultadoPuerta:
    conflictos: list[Conflicto] = []
    plano = _sin_tildes(texto)
    palabras = max(1, len(texto.split()))

    for tic in lectura.tics_prohibidos(con, novela_id):
        veces = _contar(plano, tic)
        if veces:
            conflictos.append(Conflicto(
                comprobacion="tic_prohibido", capitulo=capitulo,
                descripcion=(
                    f"«{tic}» aparece {veces} vez(ces). Esta en los tics prohibidos del estilo "
                    "narrativo de la obra."
                ),
                datos={"tic": tic, "veces": veces},
            ))

    filtro = {p: _contar(plano, p) for p in PALABRAS_FILTRO}
    total_filtro = sum(filtro.values())
    if total_filtro:
        por_mil = round(total_filtro * 1000 / palabras, 1)
        conflictos.append(Conflicto(
            comprobacion="palabras_filtro", aviso=True, capitulo=capitulo,
            descripcion=(
                f"{total_filtro} palabras filtro ({por_mil} por cada mil). En punto de vista "
                "limitado son tautologicas y alejan al lector un centimetro cada vez."
            ),
            datos={"total": total_filtro, "por_mil": por_mil,
                   "detalle": {k: v for k, v in filtro.items() if v}},
        ))

    adverbios = _ADVERBIO_ATRIBUCION.findall(texto)
    if adverbios:
        conflictos.append(Conflicto(
            comprobacion="adverbio_de_atribucion", aviso=True, capitulo=capitulo,
            descripcion=(
                f"{len(adverbios)} atribucion(es) sostenidas por un adverbio en -mente. Si hace "
                "falta el adverbio, la replica no dice lo que deberia."
            ),
            datos={"casos": len(adverbios)},
        ))

    expresivos = {v: _contar(plano, v) for v in _VERBOS_EXPRESIVOS}
    total_expresivos = sum(expresivos.values())
    if total_expresivos:
        conflictos.append(Conflicto(
            comprobacion="verbo_de_habla_expresivo", aviso=True, capitulo=capitulo,
            descripcion=(
                f"{total_expresivos} verbo(s) de habla expresivos. «Dijo» es invisible y casi "
                "siempre el correcto."
            ),
            datos={k: v for k, v in expresivos.items() if v},
        ))

    return ResultadoPuerta(puerta=4, conflictos=conflictos)
