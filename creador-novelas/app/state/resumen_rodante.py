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


def agregar(texto: str, n: int, resumen: str) -> str:
    """RF-06.4: incorpora el resumen del capítulo N y conserva todos los anteriores.

    X-02.3: el almacenamiento ya no descarta los resúmenes viejos. Lo que se recorta es lo que se le
    entrega al escritor (`para_escritor`), no lo que se guarda: así el arco completo sigue disponible y
    una reextracción (RF-07.6) puede regenerar la sección de cualquier capítulo, no solo los recientes.
    """
    secciones = [(k, r) for k, r in parsear(texto) if k != n]
    secciones.append((n, resumen.strip()))
    secciones.sort(key=lambda s: s[0])
    return serializar(secciones)


def _primera_frase(resumen: str) -> str:
    """La primera oración del resumen, para la línea única de los capítulos fuera de la ventana."""
    texto = " ".join(resumen.split())
    corte = texto.find(". ")
    return texto[: corte + 1] if corte != -1 else texto


def para_escritor(texto: str, ventana: int) -> str:
    """X-02.3: los últimos `ventana` capítulos completos; los anteriores, una línea cada uno.

    El escritor ve así todo el arco por menos del 1 % del contexto, sin recibir prosa literal de la novela
    (lo que dispararía RF-05.5): un resumen es paráfrasis, no manuscrito.
    """
    secciones = parsear(texto)
    if not secciones:
        return ""
    if ventana < 1:
        ventana = 1
    completos = secciones[-ventana:]
    anteriores = secciones[:-ventana]
    partes = []
    if anteriores:
        partes.append("### Capítulos anteriores, en una línea cada uno")
        partes.append("\n".join(f"- Capítulo {n}: {_primera_frase(r)}" for n, r in anteriores))
    partes.append(serializar(completos).rstrip("\n"))
    return "\n\n".join(partes) + "\n"


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
