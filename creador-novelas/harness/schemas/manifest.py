"""Manifiesto de ejecución (spec técnica §5). Artefacto de control, no de memoria narrativa."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

ESTADOS = ("en_progreso", "pausado_por_qa", "completo")  # no hay "abortado" (§5)
Estado = Literal["en_progreso", "pausado_por_qa", "completo"]


class Manifest(BaseModel):
    ultimo_capitulo_cerrado: int = Field(ge=0)
    ultimo_qa_ejecutado: int = Field(default=0, ge=0)
    total_capitulos_esperado: int = Field(ge=1)
    estado: Estado = "en_progreso"
    reporte_qa_pendiente: str | None = None  # nombre del reporte sin resolver (RF-07.4)
    intentos_por_capitulo: dict[str, int] = {}  # solo capítulos que necesitaron reintento (EX-07/EX-08)
    prompts_hash: dict[str, str] = {}  # §11.5
    reextraccion_pendiente: list[int] = []  # RF-07.6 paso 1 -> paso 2
    resolucion_iniciada: bool = False  # True entre el paso 1 (`resolver --capitulos`) y el paso 3 (`--cerrar`)
    capitulo_activo: int | None = None  # null = ultimo_capitulo_cerrado + 1 (H-05)
    ultimo_error: str | None = None  # texto del último fallo que detuvo la tanda; lo muestra status

    @model_validator(mode="after")
    def _pausa_con_reporte(self) -> "Manifest":
        if self.estado == "pausado_por_qa" and not self.reporte_qa_pendiente:
            raise ValueError("§5: pausado_por_qa exige reporte_qa_pendiente")
        return self

    def capitulo_actual(self) -> int:
        """Capítulo que el escritor escribe y el extractor puede leer (H-05, H-06, H-07)."""
        return self.capitulo_activo if self.capitulo_activo is not None else self.ultimo_capitulo_cerrado + 1

    def editado_a_mano(self) -> bool:
        """§5: en_progreso con reporte_qa_pendiente no nulo solo lo produce una edición manual."""
        return self.estado == "en_progreso" and self.reporte_qa_pendiente is not None
