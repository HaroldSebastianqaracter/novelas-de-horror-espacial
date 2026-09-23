"""Entrada y salida del revisor de oficio: la parte de juicio de la puerta 4 (RF-PIPE-13).

Exige un veredicto por cada criterio de la lista cerrada, con su principio de
docs/domain-knowledge.md, su evidencia citada y una sugerencia. Sin esos cuatro campos el
veredicto no sirve para reescribir: el redactor necesita saber QUE incumplio y DONDE.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from config import CRITERIOS_OFICIO

# Criterio -> principio de docs/domain-knowledge.md contra el que se puntua.
PRINCIPIO_POR_CRITERIO: dict[str, str] = {
    "voz_constante": "28-30",
    "distancia_psiquica": "29",
    "emocion_no_nombrada": "31",
    "dialogo_con_subtexto": "33",
    "voces_distinguibles": "25",
    "escena_se_gana_su_lugar": "10, 19",
    "cliche": "38",
    "tropos_con_causalidad": "55",
    "cuentas_cuadran": "48",
}


class VeredictoCriterio(BaseModel):
    criterio: str
    principio: str = ""
    veredicto: str = Field(pattern="^(pasa|falla)$")
    evidencia: str = Field(default="", description="Cita literal del texto que lo demuestra")
    sugerencia: str = Field(default="", description="Que cambiar; se le pasa al redactor")

    @model_validator(mode="after")
    def _falla_con_evidencia(self) -> VeredictoCriterio:
        if self.criterio not in CRITERIOS_OFICIO:
            raise ValueError(
                f"'{self.criterio}' no es un criterio de la puerta 4. Validos: {CRITERIOS_OFICIO}"
            )
        if self.veredicto == "falla" and not self.evidencia.strip():
            raise ValueError(
                f"El criterio '{self.criterio}' falla sin citar evidencia: no se puede reescribir."
            )
        if not self.principio:
            self.principio = PRINCIPIO_POR_CRITERIO.get(self.criterio, "")
        return self


class SalidaOficio(BaseModel):
    veredictos: list[VeredictoCriterio] = Field(min_length=len(CRITERIOS_OFICIO))

    @model_validator(mode="after")
    def _todos_los_criterios(self) -> SalidaOficio:
        dados = {v.criterio for v in self.veredictos}
        faltan = sorted(set(CRITERIOS_OFICIO) - dados)
        if faltan:
            raise ValueError(f"Faltan veredictos de estos criterios: {faltan}")
        return self

    @property
    def incumplidos(self) -> list[VeredictoCriterio]:
        return [v for v in self.veredictos if v.veredicto == "falla"]

    @property
    def pasa(self) -> bool:
        return not self.incumplidos

