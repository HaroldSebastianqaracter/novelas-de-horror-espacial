"""Texto no confiable: patrones de inyeccion conocidos y delimitacion (RF3-ENT-05, RF3-CAM-04).

Lo usan la entrevista, con el texto libre del comprador, y el cambio del lector, con su
peticion. Vive aqui para que las dos busquen exactamente lo mismo.
"""

from __future__ import annotations

import re

from compartido.grafo.escritura import normalizar

#: Patrones de inyeccion conocidos. Es una lista cerrada: un verde significa «ninguno de los
#: conocidos», no «texto limpio» (validators.md, puntos ciegos). La defensa de fondo de quien la
#: usa no depende de esta lista: el filtro de campos de la entrevista y los ids cerrados del
#: interprete.
PATRONES_INYECCION: tuple[tuple[str, str], ...] = (
    ("ignora_instrucciones",
     r"\b(ignora|olvida|descarta|salta)\w*\s+(\w+\s+){0,3}"
     r"(instrucciones|reglas|indicaciones|normas|restricciones)"),
    ("cambio_de_rol", r"\b(a partir de ahora|desde ahora)\s+(eres|seras|actua)"),
    ("prompt_del_sistema", r"\b(prompt|mensaje|instrucciones)\s+(del|de)\s+sistema\b"),
    ("marcador_de_rol",
     r"(<\|?\s*(system|assistant|im_start)|\[/?(inst|system)\]|^\s*(system|assistant)\s*:)"),
    ("orden_de_salida", r"\b(responde|devuelve|escribe)\s+(solo|unicamente)\b"),
    ("orden_de_contenido",
     r"\b(escribe|incluye|anade|pon|mete)\s+(\w+\s+){0,3}(contenido|escenas?|capitulos?)\b"),
)


def alertas_de_inyeccion(texto: str) -> list[str]:
    """Los patrones de inyeccion conocidos que aparecen en el texto (RF3-ENT-05)."""
    plano = normalizar(texto)
    return [
        nombre for nombre, patron in PATRONES_INYECCION
        if re.search(patron, plano, re.IGNORECASE | re.MULTILINE)
    ]


def delimitar(texto: str, etiqueta: str) -> str:
    """El texto entre dos marcas con la etiqueta, sin nada dentro que se parezca a una marca.

    Quien escribe el texto no puede cerrar el bloque antes de tiempo y seguir como si fuera el
    sistema: cualquier aparicion de la etiqueta se quita antes de envolverlo.
    """
    marca = re.compile(rf"<*\s*{re.escape(etiqueta)}\s*>*", re.IGNORECASE)
    return f"<<<{etiqueta}\n{marca.sub('', texto)}\n{etiqueta}>>>"
