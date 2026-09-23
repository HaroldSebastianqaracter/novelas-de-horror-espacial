"""Salida del entrevistador (specs/spec3.md, RF3-ENT-01, RF3-ENT-02).

El agente hace dos cosas: convertir la respuesta del comprador en campos del brief y
formular la siguiente pregunta. Que falta y que se contradice no lo decide el: lo calcula
`compartido.brief.analizar` y se lo da hecho.

Cada actualizacion lleva la `cita` literal de la que sale. El codigo la comprueba contra la
respuesta del comprador antes de aplicarla: un valor sin cita, o con una cita que el
comprador no escribio, se descarta.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

CampoBrief = Literal[
    "destinatario.nombre", "destinatario.edad", "destinatario.pronombres",
    "destinatario.rasgos", "recuerdos", "allegados", "ocasion", "ocasion_detalle",
    "quien_regala", "mensaje_dedicatoria", "intensidad", "tono", "subgenero", "capitulos",
    "vetados",
]


class Actualizacion(BaseModel):
    """Un dato que el comprador ha dado. En las listas (rasgos, recuerdos, vetados,
    allegados) cada actualizacion anade un elemento; en el resto, fija el valor."""

    campo: CampoBrief
    valor: str = Field(min_length=1, max_length=500)
    cita: str = Field(
        min_length=1, max_length=500,
        description="Fragmento literal de la respuesta del comprador del que sale el valor",
    )
    relacion: str = Field(
        default="", max_length=60,
        description="Solo en allegados: que es del destinatario (su perra, su hermano)",
    )
    rasgos: list[str] = Field(
        default_factory=list[str], max_length=5,
        description="Solo en allegados: como es",
    )


class SalidaEntrevistador(BaseModel):
    actualizaciones: list[Actualizacion] = Field(default_factory=list[Actualizacion])
    pregunta: str = Field(
        default="", max_length=600,
        description="La siguiente pregunta al comprador, sobre el primer pendiente. Vacia si "
                    "no queda nada pendiente",
    )
