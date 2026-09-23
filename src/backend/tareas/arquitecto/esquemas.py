"""Entrada y salida del arquitecto (RF-PIPE-04).

Produce: Novela (las tres compresiones, subgenero, tipo de final), Tema, Motivo y
EstiloNarrativo. Lee Restriccion, que no inventa: se la da el usuario.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from compartido.tipos import Pov, Subgenero, TiempoVerbal, TipoFinal


class TemaSalida(BaseModel):
    pregunta_central: str = Field(min_length=10)
    verdad_tematica: str = Field(min_length=10)


class MotivoSalida(BaseModel):
    simbolo: str = Field(min_length=2)
    significado_inicial: str = Field(min_length=3)
    significado_final: str = Field(min_length=3)


class EstiloSalida(BaseModel):
    registro: str = Field(min_length=3)
    ritmo_prosa: str = Field(min_length=3)
    densidad_sensorial: str = Field(min_length=3)
    distancia_psiquica: str = Field(min_length=3)
    tics_prohibidos: list[str] = Field(min_length=1)
    convenciones_formato: str = ""

    @field_validator("tics_prohibidos")
    @classmethod
    def _tics_no_vacios(cls, v: list[str]) -> list[str]:
        if any(not t.strip() for t in v):
            raise ValueError("Ningun tic prohibido puede estar vacio.")
        return v


class SalidaArquitecto(BaseModel):
    """Termina cuando las tres compresiones son coherentes y el estilo esta fijado."""

    premisa: str = Field(min_length=20, description="La proposicion causal que la obra demuestra")
    logline: str = Field(min_length=20, description="Protagonista, objetivo y antagonismo")
    pregunta_dramatica: str = Field(min_length=10, description="Pregunta de si o no del climax")
    tema_central: str = Field(min_length=5)
    subgenero_dominante: Subgenero
    tipo_final: TipoFinal
    pov_por_defecto: Pov = "tercera_limitada"
    tiempo_verbal: TiempoVerbal = "pasado"
    titulo_propuesto: str = ""
    dedicatoria: str = Field(
        default="", max_length=400,
        description="Solo si la novela es un regalo: la dedicatoria de la portada, con el "
                    "nombre del destinatario escrito exactamente como en el encargo",
    )
    temas: list[TemaSalida] = Field(min_length=1)
    motivos: list[MotivoSalida] = Field(min_length=1)
    estilo: EstiloSalida

    @field_validator("pregunta_dramatica")
    @classmethod
    def _es_pregunta(cls, v: str) -> str:
        if "?" not in v:
            raise ValueError("La pregunta dramatica tiene que estar formulada como pregunta.")
        return v
