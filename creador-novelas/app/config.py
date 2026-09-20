"""Carga y validación de la carpeta `config/` (spec técnica §8.1, §11.1-11.5; EX-05)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.errores import ConfiguracionInvalidaError
from app.rutas import Rutas

VERSION_SPECS = "v1.12"  # versión de las especificaciones que implementa este código; viaja en la traza (§16.2)
ROLES = ("escritor", "extractor", "qa")
SKILL_DE_DOMINIO = {"escritor": "prosa-terror-espacial", "extractor": "formato-delta", "qa": "criterios-qa"}

# RF-08.4 / §13.3 "Forma canónica del comando": el único comando de Bash que H-11 deja pasar a cada rol.
INTERPRETE = ".venv/Scripts/python.exe"  # solo el intérprete del entorno virtual; `python` a secas no se acepta
VERBO_POR_ROL = {"escritor": "validar-capitulo", "extractor": "validar-delta", "qa": "validar-reporte"}


def comando_validador(rol: str, n: int, *, con_delta: bool = False) -> str:
    """El único comando de terminal que H-11 le deja a cada rol.

    `con_delta` es para el escritor que además emite su propio delta (X-04): en vez de abrirle la
    valla a dos comandos --que es una puerta que luego no se cierra sola-- se le cambia el suyo por
    uno que valida las dos cosas de una vez.
    """
    sufijo = " --con-delta" if con_delta and rol == "escritor" else ""
    return f"{INTERPRETE} -m app {VERBO_POR_ROL[rol]} {n}{sufijo}"

CAMPOS_NOVELA = (
    "total_capitulos", "palabras_por_capitulo", "idioma", "persona_narrativa", "tiempo_verbal",
    "ventana_resumen_rodante", "cadencia_qa", "max_tokens_contexto_escritor", "max_hechos_por_capitulo",
)
CAMPOS_EJECUCION = ("capitulos_por_tanda", "max_llamadas_por_tanda", "registrar_uso", "exportar_trazas",
                    "exportar_para_juez", "escritor_emite_delta", "aristas_en_continuidad",
                    "variante_prompt_escritor")


class HarnessConfig(BaseModel):
    """§8.1. Se valida antes de cualquier llamada al modelo (EX-05)."""

    model_config = ConfigDict(extra="forbid")

    total_capitulos: int = Field(ge=1, le=200)  # RF-CFG-01; el maximo es un seguro de coste
    capitulos_por_tanda: int | None = Field(default=None, ge=1)  # RF-CFG-02; None = sin tope
    max_llamadas_por_tanda: int | None = Field(default=None, ge=1)  # RF-CFG-06
    registrar_uso: bool = True  # RF-CFG-06
    # La traza sale de la máquina hacia un servicio externo, así que se puede apagar. Con `False` el
    # registro se sigue escribiendo en disco: lo único que no ocurre es la publicación.
    exportar_trazas: bool = True  # RF-09
    # X-03.2: si la publicación automática incluye el capítulo y su escaleta en las generaciones del
    # escritor. Es lo que el evaluador de Langfuse necesita para puntuar; sin esto la traza llega completa
    # en todo menos en lo único que el juez lee, y la pestaña de scores se queda vacía sin decir por qué.
    # Va aparte de `exportar_trazas` porque decide algo distinto: no si se publica, sino si sale el texto
    # de la novela hacia un servicio externo y de ahí al modelo juez.
    exportar_para_juez: bool = False
    # X-04: el escritor entrega el capítulo y su delta en la misma invocación, y el extractor no se
    # llama. El miedo era que el delta contase lo que el escritor quiso escribir y no lo que escribió;
    # medido sobre tres premisas emparejadas pasa lo contrario, 0 contradicciones frente a 4 y la
    # mitad de reloj (19/09, ver HALLAZGOS.md). Por eso viene encendido; apagarlo devuelve el extractor.
    escritor_emite_delta: bool = True
    # X-05: el salto de vecindad y el recorte por puntuación en el filtro de continuidad. Apagado
    # arranca el filtro de siempre --solo el sujeto, y `mundo` entra completo-- que es el brazo de
    # control. Con 3 capítulos los dos dan lo mismo, porque todo cabe; la diferencia aparece a
    # partir del capítulo 10, que es donde hay que medirlo.
    aristas_en_continuidad: bool = False
    # X-06: qué variante de la plantilla del escritor se usa. Vacío es `escritor.md`, la de siempre.
    # El loop de prompts mide contra ella, así que el control tiene que seguir existiendo intacto:
    # una variante es un archivo nuevo al lado, nunca una edición de la original.
    variante_prompt_escritor: str = ""
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
