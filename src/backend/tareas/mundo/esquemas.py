"""Entrada y salida del constructor de mundo (RF-PIPE-04).

Termina cuando toda regla que la trama vaya a usar esta escrita, incluidos limites y costes.
Por eso `costes` y `limites` son obligatorios y `Amenaza.reglas` pide capacidad, limite y
condicion de activacion: un sistema o una amenaza infraespecificados son la primera fuente
de agujeros de guion (definitions.md, principio 44).
"""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from compartido.tipos import Dureza, nombres_repetidos


class SistemaSalida(BaseModel):
    nombre: str = Field(min_length=2)
    capacidades: str = Field(min_length=10)
    costes: str = Field(min_length=5, description="Que cuesta usarlo. No puede quedar vacio")
    limites: str = Field(min_length=5, description="Donde deja de funcionar. No puede quedar vacio")
    acceso: str = ""
    dureza: Dureza = "duro"


class LugarSalida(BaseModel):
    nombre: str = Field(min_length=2)
    tipo: str = ""
    descripcion: str = Field(min_length=10)
    sistemas_criticos: list[str] = Field(default_factory=list)


class FaccionSalida(BaseModel):
    nombre: str = Field(min_length=2)
    proposito: str = ""
    objetivos: str = ""
    recursos: str = ""


class ReglaAmenaza(BaseModel):
    capacidad: str = Field(min_length=5, description="Que puede hacer")
    limite: str = Field(min_length=5, description="Que no puede hacer")
    activacion: str = Field(min_length=5, description="Que la dispara")


class AmenazaSalida(BaseModel):
    naturaleza: str = Field(min_length=10)
    origen: str = ""
    reglas: list[ReglaAmenaza] = Field(min_length=3)
    encarna_tema: str = Field(
        default="", description="De que ansiedad concreta es cuerpo (principio 53)"
    )


class EventoPrevio(BaseModel):
    fecha_interna: str = Field(min_length=1)
    descripcion: str = Field(min_length=5)
    tipo: str = ""


class MundoSalida(BaseModel):
    nombre: str = Field(min_length=2)
    geografia: str = ""
    historia: str = ""
    culturas: str = ""
    reglas_fisicas: str = Field(min_length=10)


class SalidaMundo(BaseModel):
    mundo: MundoSalida
    sistemas: list[SistemaSalida] = Field(min_length=1)
    lugares: list[LugarSalida] = Field(min_length=3)
    facciones: list[FaccionSalida] = Field(min_length=1)
    amenaza: AmenazaSalida
    linea_de_tiempo_origen: str = Field(min_length=1)
    linea_de_tiempo_unidad: str = Field(min_length=1)
    eventos_previos: list[EventoPrevio] = Field(min_length=1)

    @model_validator(mode="after")
    def _nombres_unicos(self) -> SalidaMundo:
        for que, nombres in (
            ("sistemas", [s.nombre for s in self.sistemas]),
            ("lugares", [x.nombre for x in self.lugares]),
            ("facciones", [f.nombre for f in self.facciones]),
        ):
            repetidos = nombres_repetidos(nombres)
            if repetidos:
                raise ValueError(
                    f"Hay {que} cuyo nombre solo difiere en tildes o mayusculas: "
                    + ", ".join(repetidos)
                )
        return self
