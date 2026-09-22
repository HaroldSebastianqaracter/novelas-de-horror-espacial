"""Entrada y salida del estructurador (RF-PIPE-04).

Termina cuando los hilos abren y cierran en orden y el climax responde la pregunta
dramatica. Los cuatro puntos de giro obligatorios del hilo principal son lo que la puerta 1
comprueba despues con una consulta (RF-PIPE-05).
"""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from compartido.tipos import TipoHilo, TipoPuntoDeGiro

OBLIGATORIOS_HILO_PRINCIPAL: tuple[TipoPuntoDeGiro, ...] = (
    "incidente_incitador", "punto_medio", "climax", "resolucion",
)


class ActoSalida(BaseModel):
    numero: int = Field(ge=1)
    funcion_narrativa: str = Field(min_length=10)


class PuntoDeGiroSalida(BaseModel):
    tipo: TipoPuntoDeGiro
    posicion: float = Field(ge=0.0, le=100.0, description="Porcentaje aproximado de la obra")
    descripcion: str = ""


class HiloSalida(BaseModel):
    nombre: str = Field(min_length=2, description="Identificador legible del hilo")
    tipo: TipoHilo
    conflicto_central: str = Field(min_length=10)
    personajes: list[str] = Field(default_factory=list)
    dramatiza_tema: bool = False
    puntos_de_giro: list[PuntoDeGiroSalida] = Field(min_length=2)

    @model_validator(mode="after")
    def _principal_completo(self) -> HiloSalida:
        tipos = [p.tipo for p in self.puntos_de_giro]
        if len(set(tipos)) != len(tipos):
            raise ValueError(f"El hilo '{self.nombre}' repite un tipo de punto de giro.")
        if self.tipo == "principal":
            faltan = [t for t in OBLIGATORIOS_HILO_PRINCIPAL if t not in tipos]
            if faltan:
                raise ValueError(
                    f"Al hilo principal le faltan puntos de giro obligatorios: {faltan}"
                )
            posiciones = {p.tipo: p.posicion for p in self.puntos_de_giro}
            orden = [posiciones[t] for t in OBLIGATORIOS_HILO_PRINCIPAL]
            if orden != sorted(orden):
                raise ValueError(
                    "En el hilo principal, incidente incitador, punto medio, climax y "
                    "resolucion tienen que ir en ese orden."
                )
        return self


class SiembraSalida(BaseModel):
    elemento: str = Field(min_length=5)
    hilo: str = ""
    capitulo_pago_previsto: int | None = Field(default=None, ge=1)


class ObjetoSalida(BaseModel):
    nombre: str = Field(min_length=2)
    funcion_narrativa: str = Field(min_length=5)


class SalidaEstructura(BaseModel):
    actos: list[ActoSalida] = Field(min_length=3)
    hilos: list[HiloSalida] = Field(min_length=1)
    siembras: list[SiembraSalida] = Field(default_factory=list)
    objetos: list[ObjetoSalida] = Field(default_factory=list)

    @model_validator(mode="after")
    def _un_solo_principal(self) -> SalidaEstructura:
        principales = [h for h in self.hilos if h.tipo == "principal"]
        if len(principales) != 1:
            raise ValueError(
                f"Tiene que haber exactamente un hilo principal, hay {len(principales)}."
            )
        numeros = [a.numero for a in self.actos]
        if sorted(numeros) != list(range(1, len(numeros) + 1)):
            raise ValueError(f"Los actos tienen que numerarse 1..n sin huecos: {numeros}")
        nombres = {h.nombre for h in self.hilos}
        for s in self.siembras:
            if s.hilo and s.hilo not in nombres:
                raise ValueError(f"La siembra '{s.elemento}' cuelga de un hilo inexistente.")
        return self
