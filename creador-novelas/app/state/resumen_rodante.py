"""Resumen rodante: ventana deslizante por capítulo (RF-06.4, EX-04, RF-07.6).

Formato del archivo: una sección `## Capítulo N` por capítulo cubierto, en orden ascendente. Guardar cada
capítulo en su propia sección es lo que permite regenerar solo la afectada tras una corrección (RF-07.6).
"""

from __future__ import annotations

import re

_ENCABEZADO = re.compile(r"^## Capítulo (\d+)\s*$", re.MULTILINE)


def parsear(texto: str) -> list[tuple[int, str]]:
    """Devuelve [(n, resumen)] en el orden del archivo."""
    if not texto.strip():
        return []
    secciones: list[tuple[int, str]] = []
    marcas = list(_ENCABEZADO.finditer(texto))
    for i, m in enumerate(marcas):
        fin = marcas[i + 1].start() if i + 1 < len(marcas) else len(texto)
        secciones.append((int(m.group(1)), texto[m.end():fin].strip()))
    return secciones


def serializar(secciones: list[tuple[int, str]]) -> str:
    if not secciones:
        return ""
    return "\n\n".join(f"## Capítulo {n}\n\n{resumen.strip()}" for n, resumen in secciones) + "\n"


def agregar(texto: str, n: int, resumen: str, ventana: int) -> str:
    """RF-06.4: incorpora el resumen del capítulo N y descarta los más antiguos si se excede la ventana."""
    secciones = [(k, r) for k, r in parsear(texto) if k != n]
    secciones.append((n, resumen.strip()))
    secciones.sort(key=lambda s: s[0])
    return serializar(secciones[-ventana:])


def reemplazar(texto: str, n: int, resumen: str) -> str:
    """RF-07.6: regenera la sección del capítulo N si está en la ventana; si no está, no la agrega."""
    secciones = parsear(texto)
    if not any(k == n for k, _ in secciones):
        return texto
    return serializar([(k, resumen.strip() if k == n else r) for k, r in secciones])


def recortar_a_minimo(texto: str) -> str:
    """EX-04: el mínimo del resumen rodante es la sección del capítulo más reciente."""
    secciones = parsear(texto)
    return serializar(secciones[-1:]) if secciones else ""


def capitulos_cubiertos(texto: str) -> list[int]:
    return [n for n, _ in parsear(texto)]
