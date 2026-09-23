"""Comparacion de terminos en texto libre (RF3-BRF-03).

La usan el analisis del brief, para saber si un termino vetado aparece en un elemento
personal, y la usara el guardrail de palabras prohibidas del bloque 5. Por eso vive aqui y
no en ninguno de los dos: tienen que normalizar exactamente igual, o lo que uno deja pasar el
otro lo bloquea.

La normalizacion es la de los nombres del grafo (`normalizar`: sin mayusculas ni acentos,
con la ene) mas un plural simple. El castellano forma el plural con -s tras vocal («nave»,
«naves») y con -es tras consonante («motor», «motores»), y desde el plural no se sabe cual de
las dos quitar. Por eso cada palabra lleva sus formas singulares posibles, y dos palabras son
el mismo termino si comparten alguna.
"""

from __future__ import annotations

import re

from compartido.grafo.escritura import normalizar

# Letras y cifras: «41» tambien es una palabra, y una cita con la edad tiene que casar.
_PALABRA = re.compile(r"[^\W_]+", re.UNICODE)
_MINIMO = 2


def formas(palabra: str) -> frozenset[str]:
    """La palabra y sus singulares simples posibles, sin bajar de dos letras («las», «la»)."""
    salida = {palabra}
    if palabra.endswith("s") and len(palabra) - 1 >= _MINIMO:
        salida.add(palabra[:-1])
    if palabra.endswith("es") and len(palabra) - 2 >= _MINIMO:
        salida.add(palabra[:-2])
    return frozenset(salida)


def palabras(texto: str) -> list[frozenset[str]]:
    """Las palabras del texto, normalizadas, cada una con sus formas, en orden."""
    return [formas(p) for p in _PALABRA.findall(normalizar(texto))]


def contiene_termino(texto: str, termino: str) -> bool:
    """Si el termino aparece en el texto como palabra o secuencia de palabras completas.

    «Laura» no aparece en «Laurana»; «la nave» aparece en «Las naves ardian».
    """
    buscadas = palabras(termino)
    if not buscadas:
        return False
    presentes = palabras(texto)
    n = len(buscadas)
    return any(
        all(presentes[i + k] & buscadas[k] for k in range(n))
        for i in range(len(presentes) - n + 1)
    )
