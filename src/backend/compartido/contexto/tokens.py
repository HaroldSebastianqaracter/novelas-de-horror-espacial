"""Estimacion de tokens (RF-CTX-02).

Es una estimacion determinista a proposito, no un tokenizador real: tiene que dar el mismo
numero siempre, correr sin dependencias y ser barata, porque se llama una vez por bloque y
por llamada. El margen del 10 % y los 26.000 tokens que el paquete deja libres absorben el
error.

Si algun dia hace falta precision, se sustituye esta funcion y nada mas cambia.
"""

from __future__ import annotations

CARACTERES_POR_TOKEN = 3.5
MARGEN = 1.10


def estimar(texto: str) -> int:
    """Tokens aproximados de un texto. Siempre al alza."""
    if not texto:
        return 0
    return int(len(texto) / CARACTERES_POR_TOKEN * MARGEN) + 1


def recortar_a(texto: str, tokens: int) -> str:
    """Corta un texto para que quepa en ese presupuesto, por parrafos enteros.

    Corta por parrafos y no por caracteres porque medio parrafo es peor que ninguno: el
    agente lo leeria como una frase inacabada del canon.
    """
    if estimar(texto) <= tokens:
        return texto
    parrafos = texto.split("\n\n")
    acumulado: list[str] = []
    usados = 0
    for p in parrafos:
        coste = estimar(p) + 1
        if usados + coste > tokens:
            break
        acumulado.append(p)
        usados += coste
    return "\n\n".join(acumulado)
