"""Entrada y salida del disenador de elenco (RF-PIPE-04).

Termina cuando ningun personaje duplica la funcion de otro y el oponente tiene argumento
propio. `posicion_tematica` existe para que esa segunda condicion sea comprobable con una
consulta y no con un juicio: dos personajes con el mismo rol narrativo y la misma posicion
ante el tema son el mismo personaje escrito dos veces (principio 24).
"""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from compartido.grafo.escritura import normalizar
from compartido.tipos import RolNarrativo, SubtipoArco, TipoArco, nombres_repetidos


class RelacionSalida(BaseModel):
    destino: str = Field(min_length=1, description="Nombre del otro personaje")
    tipo: str = Field(pattern="^(se_opone_a|aliado_con)$")


class PersonajeSalida(BaseModel):
    nombre: str = Field(min_length=2)
    rol: str = Field(default="", description="Su oficio a bordo, no su funcion narrativa")
    rol_narrativo: RolNarrativo
    deseo: str = Field(min_length=5, description="Objetivo externo y consciente")
    necesidad_interna: str = Field(min_length=5, description="Carencia que debe resolver")
    fantasma: str = Field(min_length=5, description="El suceso del pasado")
    herida: str = Field(min_length=5, description="El dano que dejo")
    mentira: str = Field(min_length=5, description="La creencia protectora")
    defecto: str = Field(min_length=5, description="La conducta observable")
    tipo_arco: TipoArco
    subtipo_arco: SubtipoArco | None = None
    idiolecto: str = Field(min_length=5, description="Su huella verbal")
    secreto: str = ""
    posicion_tematica: str = Field(
        min_length=5, description="Que responde este personaje a la pregunta central"
    )
    faccion: str = ""
    relaciones: list[RelacionSalida] = Field(default_factory=list)

    @model_validator(mode="after")
    def _subtipo_solo_si_negativo(self) -> PersonajeSalida:
        if self.subtipo_arco is not None and self.tipo_arco != "negativo":
            raise ValueError("subtipo_arco solo aplica a un tipo_arco negativo.")
        if self.tipo_arco == "negativo" and self.subtipo_arco is None:
            raise ValueError("Un arco negativo tiene que precisar su subtipo.")
        return self


class SalidaElenco(BaseModel):
    personajes: list[PersonajeSalida] = Field(min_length=3)

    @model_validator(mode="after")
    def _reparto_sin_duplicados(self) -> SalidaElenco:
        protagonistas = [p for p in self.personajes if p.rol_narrativo == "protagonista"]
        if len(protagonistas) != 1:
            raise ValueError(
                f"Tiene que haber exactamente un protagonista, hay {len(protagonistas)}."
            )
        if not any(p.rol_narrativo == "oponente" for p in self.personajes):
            raise ValueError("Falta el oponente.")

        repetidos = nombres_repetidos(p.nombre for p in self.personajes)
        if repetidos:
            raise ValueError(
                "Hay personajes cuyo nombre solo difiere en tildes o mayusculas: "
                + ", ".join(repetidos)
            )

        vistos: set[tuple[str, str]] = set()
        for p in self.personajes:
            clave = (p.rol_narrativo, p.posicion_tematica.strip().lower())
            if clave in vistos:
                raise ValueError(
                    f"'{p.nombre}' duplica rol narrativo y posicion tematica de otro personaje: "
                    "uno de los dos es decorado."
                )
            vistos.add(clave)

        conocidos = {normalizar(p.nombre) for p in self.personajes}
        for p in self.personajes:
            for r in p.relaciones:
                if normalizar(r.destino) not in conocidos:
                    raise ValueError(
                        f"'{p.nombre}' se relaciona con '{r.destino}', que no esta en el elenco."
                    )
        return self
