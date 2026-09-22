"""Entrada y salida del escaletador (RF-PIPE-06).

Termina cuando ninguna escena tiene valorInicial igual a valorFinal. Esa comprobacion la
repite despues la puerta 2 sobre el grafo entero (RF-PIPE-07); aqui esta para que el fallo
se detecte en la validacion de la llamada y cueste una repeticion, no una puerta.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from compartido.tipos import TipoPuntoDeGiro


def normalizar_valor(v: str) -> str:
    """Normaliza un valor en juego para compararlo: minusculas, sin tildes ni espacios."""
    tabla = str.maketrans("áéíóúüñÁÉÍÓÚÜÑ", "aeiouunAEIOUUN")
    return " ".join(v.translate(tabla).lower().split())


class BeatSalida(BaseModel):
    tipo: str = ""
    cambio: str = Field(min_length=3)


class SecuelaSalida(BaseModel):
    reaccion: str = Field(min_length=3)
    dilema: str = Field(min_length=3)
    decision: str = Field(min_length=3)


class EscenaSalida(BaseModel):
    orden: int = Field(ge=1)
    pov: str = Field(min_length=1, description="Nombre del personaje punto de vista")
    lugar: str = Field(min_length=1)
    reparto: list[str] = Field(min_length=1)
    objetivo: str = Field(min_length=5)
    conflicto: str = Field(min_length=5)
    resultado: str = Field(min_length=5)
    valor_inicial: str = Field(min_length=2)
    valor_final: str = Field(min_length=2)
    tension: int = Field(ge=1, le=10)
    gancho_salida: str = ""
    longitud_prevista: int = Field(ge=100)
    analepsis: bool = False
    secuencia: str = ""
    punto_de_giro: TipoPuntoDeGiro | None = None
    objetos: list[str] = Field(default_factory=list)
    beats: list[BeatSalida] = Field(default_factory=list)
    secuela: SecuelaSalida | None = None

    @model_validator(mode="after")
    def _cambia_un_valor(self) -> EscenaSalida:
        if normalizar_valor(self.valor_inicial) == normalizar_valor(self.valor_final):
            raise ValueError(
                f"La escena {self.orden} no cambia el valor en juego "
                f"('{self.valor_inicial}' -> '{self.valor_final}'): es relleno."
            )
        if self.pov not in self.reparto:
            raise ValueError(
                f"La escena {self.orden} tiene POV '{self.pov}', que no esta en su reparto."
            )
        return self


class CapituloSalida(BaseModel):
    numero: int = Field(ge=1)
    acto: int = Field(ge=1)
    objetivo: str = Field(min_length=5)
    pov: str = Field(min_length=1)
    gancho_apertura: str = Field(min_length=5)
    gancho_cierre: str = Field(min_length=5)
    escenas: list[EscenaSalida] = Field(min_length=1)

    @property
    def longitud_prevista(self) -> int:
        return sum(e.longitud_prevista for e in self.escenas)


class SecuenciaSalida(BaseModel):
    nombre: str = Field(min_length=1)
    acto: int = Field(ge=1)
    objetivo_intermedio: str = Field(min_length=5)
    orden: int = Field(ge=1)


class SalidaEscaleta(BaseModel):
    capitulos: list[CapituloSalida] = Field(min_length=1)
    secuencias: list[SecuenciaSalida] = Field(default_factory=list)

    @model_validator(mode="after")
    def _capitulos_correlativos(self) -> SalidaEscaleta:
        numeros = [c.numero for c in self.capitulos]
        if len(set(numeros)) != len(numeros):
            raise ValueError(f"Hay numeros de capitulo repetidos: {numeros}")
        for c in self.capitulos:
            ordenes = [e.orden for e in c.escenas]
            if sorted(ordenes) != list(range(1, len(ordenes) + 1)):
                raise ValueError(
                    f"Las escenas del capitulo {c.numero} tienen que ir 1..n sin huecos."
                )
        nombres_secuencia = {s.nombre for s in self.secuencias}
        for c in self.capitulos:
            for e in c.escenas:
                if e.secuencia and e.secuencia not in nombres_secuencia:
                    raise ValueError(
                        f"La escena {c.numero}.{e.orden} cuelga de una secuencia inexistente."
                    )
        return self
