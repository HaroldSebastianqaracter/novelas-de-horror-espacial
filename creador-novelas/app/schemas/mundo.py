"""Biblia del mundo (spec técnica §4; RF-04.2). Solo `locaciones` la consume el sistema (registro de sujetos y filtro)."""

from __future__ import annotations

from pydantic import BaseModel


class Mundo(BaseModel):
    reglas: list[str]  # reglas del universo que condicionan la trama (RF-04.2)
    objetos: list[str]  # objetos relevantes
    linea_de_tiempo: list[str]  # hitos previos al capítulo 1
    locaciones: dict[str, str]  # clave canónica -> descripción; las claves alimentan RF-06.1 y RF-05.1

    def nombres_locaciones(self) -> list[str]:
        return list(self.locaciones.keys())
