"""Recursos narrativos acumulados (RF-05.5; spec técnica §17.2): la capa semántica de la antirrepetición.

El extractor, que ya lee el capítulo entero, reporta en su delta las imágenes, gestos y giros recurrentes que ve.
Aquí se acumulan por capítulo en `04_estado/recursos_narrativos.json`, y `preparar-capitulo` inyecta los más usados
al escritor como recursos **agotados**, no prohibidos. Todas las funciones devuelven un objeto nuevo.
"""

from __future__ import annotations

import re
import unicodedata

from app.schemas.recursos import RecursoAcumulado, RecursoNarrativo, RecursosNarrativos

LIMITE_INYECCION = 20  # cuántos recursos entran al prompt del escritor: los más usados, empate por el más reciente


def clave(recurso: str) -> str:
    """Dos descripciones del mismo recurso con distinta mayúscula, acento o puntuación son el mismo recurso."""
    texto = unicodedata.normalize("NFKD", recurso.casefold())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"[^\w\s]", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def fusionar(nuevos: list[RecursoNarrativo]) -> list[RecursoNarrativo]:
    """Dentro de un mismo delta, el mismo recurso dos veces se suma en vez de duplicarse."""
    por_clave: dict[str, RecursoNarrativo] = {}
    for r in nuevos:
        k = clave(r.recurso)
        if not k:
            continue
        if k in por_clave:
            por_clave[k] = por_clave[k].model_copy(update={"veces": por_clave[k].veces + r.veces})
        else:
            por_clave[k] = r.model_copy()
    return list(por_clave.values())


def acumular(estado: RecursosNarrativos, nuevos: list[RecursoNarrativo], n: int, *, reextraccion: bool = False) -> RecursosNarrativos:
    """Suma las apariciones del capítulo N. En reextracción (RF-07.6) primero se retira lo que ese capítulo había aportado."""
    resultado: list[RecursoAcumulado] = []
    for r in estado.root:
        apariciones = dict(r.apariciones)
        if reextraccion:
            apariciones.pop(str(n), None)
        if apariciones:
            resultado.append(r.model_copy(update={"apariciones": apariciones}))
    indice = {clave(r.recurso): i for i, r in enumerate(resultado)}
    for nuevo in fusionar(nuevos):
        k = clave(nuevo.recurso)
        if k in indice:
            actual = resultado[indice[k]]
            apariciones = dict(actual.apariciones)
            apariciones[str(n)] = apariciones.get(str(n), 0) + nuevo.veces
            resultado[indice[k]] = actual.model_copy(update={"apariciones": apariciones})
        else:
            indice[k] = len(resultado)
            resultado.append(RecursoAcumulado(recurso=nuevo.recurso, apariciones={str(n): nuevo.veces}))
    return RecursosNarrativos(resultado)


def mas_usados(estado: RecursosNarrativos, limite: int = LIMITE_INYECCION) -> list[RecursoAcumulado]:
    """Los que más se repitieron; a igual conteo, el que apareció más recientemente."""
    ordenados = sorted(estado.root, key=lambda r: (-r.veces, -(max(r.caps) if r.caps else 0), clave(r.recurso)))
    return ordenados[:limite]


def formatear_agotados(estado: RecursosNarrativos, limite: int = LIMITE_INYECCION) -> str:
    """El bloque que entra al prompt del escritor: recurso, conteo y capítulos (RF-05.5)."""
    seleccion = mas_usados(estado, limite)
    if not seleccion:
        return "(todavía no hay recursos registrados: este es el primer capítulo con extracción)"
    lineas = []
    for r in seleccion:
        caps = ", ".join(str(c) for c in r.caps)
        lineas.append(f"- {r.recurso} · {r.veces} {'vez' if r.veces == 1 else 'veces'} · cap. {caps}")
    return "\n".join(lineas)
