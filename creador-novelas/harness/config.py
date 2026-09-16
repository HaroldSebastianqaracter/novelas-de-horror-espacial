"""Carga y validación de la carpeta `config/` (spec técnica §8.1, §11.1-11.5; EX-05)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from harness.errores import ConfiguracionInvalidaError
from harness.rutas import Rutas

ROLES = ("escritor", "extractor", "qa")
SKILL_DE_DOMINIO = {"escritor": "prosa-terror-espacial", "extractor": "formato-delta", "qa": "criterios-qa"}

CAMPOS_NOVELA = (
    "total_capitulos", "palabras_por_capitulo", "idioma", "persona_narrativa", "tiempo_verbal",
    "ventana_resumen_rodante", "cadencia_qa", "max_tokens_contexto_escritor", "max_hechos_por_capitulo",
)
CAMPOS_EJECUCION = ("capitulos_por_tanda", "max_llamadas_por_tanda", "registrar_uso")


class HarnessConfig(BaseModel):
    """§8.1. Se valida antes de cualquier llamada al modelo (EX-05)."""

    model_config = ConfigDict(extra="forbid")

    total_capitulos: int = Field(ge=30, le=50)  # RF-CFG-01, acotado por RF-03.1
    capitulos_por_tanda: int | None = Field(default=None, ge=1)  # RF-CFG-02; None = sin tope
    max_llamadas_por_tanda: int | None = Field(default=None, ge=1)  # RF-CFG-06
    registrar_uso: bool = True  # RF-CFG-06
    palabras_por_capitulo: int = Field(gt=0)  # RF-CFG-01
    idioma: str = Field(min_length=2)  # RF-CFG-05
    persona_narrativa: Literal["primera", "tercera_limitada", "tercera_omnisciente"]
    tiempo_verbal: Literal["presente", "pasado"]
    ventana_resumen_rodante: int = Field(ge=1)
    cadencia_qa: int = Field(ge=1)
    max_tokens_contexto_escritor: int = Field(gt=0)
    max_hechos_por_capitulo: int = Field(gt=0)  # §11.6

    def rango_palabras(self) -> tuple[int, int]:
        """RF-05.2: palabras_por_capitulo +-20 %."""
        return int(round(self.palabras_por_capitulo * 0.8)), int(round(self.palabras_por_capitulo * 1.2))

    def a_novela_json(self) -> dict[str, Any]:
        return {c: getattr(self, c) for c in CAMPOS_NOVELA}

    def a_ejecucion_json(self) -> dict[str, Any]:
        return {c: getattr(self, c) for c in CAMPOS_EJECUCION}


def _leer_json(path: Path, nombre: str) -> dict[str, Any]:
    if not path.exists():
        raise ConfiguracionInvalidaError(f"EX-05: falta {nombre} ({path})")
    try:
        datos = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ConfiguracionInvalidaError(f"EX-05: {nombre} no es JSON válido: {e}") from e
    if not isinstance(datos, dict):
        raise ConfiguracionInvalidaError(f"EX-05: {nombre} debe ser un objeto JSON")
    return datos


def _formatear_errores(e: ValidationError) -> str:
    partes = []
    for err in e.errors():
        campo = ".".join(str(p) for p in err["loc"]) or "<raíz>"
        partes.append(f"{campo}: {err['msg']}")
    return "; ".join(partes)


def construir_config(novela: dict[str, Any], ejecucion: dict[str, Any]) -> HarnessConfig:
    """Une los dos archivos y valida. Es lo que usan el CLI y el frontend (§15.2)."""
    for clave in novela:
        if clave in CAMPOS_EJECUCION:
            raise ConfiguracionInvalidaError(f"EX-05: `{clave}` pertenece a ejecucion.json, no a novela.json")
    for clave in ejecucion:
        if clave in CAMPOS_NOVELA:
            raise ConfiguracionInvalidaError(f"EX-05: `{clave}` pertenece a novela.json (INV-04), no a ejecucion.json")
    try:
        return HarnessConfig(**novela, **ejecucion)
    except ValidationError as e:
        raise ConfiguracionInvalidaError(f"EX-05: configuración inválida: {_formatear_errores(e)}") from e
    except TypeError as e:
        raise ConfiguracionInvalidaError(f"EX-05: configuración inválida: {e}") from e


def cargar_config(raiz: Path, capitulos_por_tanda: int | None = None) -> HarnessConfig:
    """Lee config/novela.json + config/ejecucion.json. Solo `capitulos_por_tanda` admite override (RF-CFG-03)."""
    rutas = Rutas(raiz)
    novela = _leer_json(rutas.novela_json, "config/novela.json")
    ejecucion = _leer_json(rutas.ejecucion_json, "config/ejecucion.json")
    config = construir_config(novela, ejecucion)
    if capitulos_por_tanda is not None:
        if capitulos_por_tanda < 1:
            raise ConfiguracionInvalidaError("EX-05: capitulos_por_tanda por línea de comandos debe ser >= 1")
        config = config.model_copy(update={"capitulos_por_tanda": capitulos_por_tanda})
    return config


def cargar_proveedores(raiz: Path) -> dict[str, Any]:
    """config/proveedores.json (§11.4). Documental en esta ruta: los alias los resuelve Claude Code (§3.2)."""
    rutas = Rutas(raiz)
    if not rutas.proveedores_json.exists():
        return {}
    return _leer_json(rutas.proveedores_json, "config/proveedores.json")


def hash_prompts(raiz: Path) -> dict[str, str]:
    """§11.5 y §11.8: sha256 de config/prompts/<rol>.md + la skill de dominio del rol."""
    rutas = Rutas(raiz)
    resultado: dict[str, str] = {}
    for rol in ROLES:
        h = hashlib.sha256()
        for path in (rutas.prompts_config / f"{rol}.md", rutas.skills / SKILL_DE_DOMINIO[rol] / "SKILL.md"):
            h.update(path.name.encode("utf-8"))
            h.update(path.read_bytes() if path.exists() else b"<ausente>")
        resultado[rol] = h.hexdigest()[:16]
    return resultado
