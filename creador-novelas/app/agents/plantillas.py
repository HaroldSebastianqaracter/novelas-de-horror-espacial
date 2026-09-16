"""Plantillas de prompt por rol (config/prompts/<rol>.md, spec técnica §11.5) con marcadores {{NOMBRE}}."""

from __future__ import annotations

import re
from pathlib import Path

from app.errores import ConfiguracionInvalidaError
from app.rutas import Rutas

_MARCADOR = re.compile(r"\{\{([A-Z_]+)\}\}")

# Checklist de contenido obligatorio de §11.5, expresado como marcadores que la plantilla debe usar.
MARCADORES_OBLIGATORIOS: dict[str, tuple[str, ...]] = {
    "escritor": (
        "IDIOMA", "PERSONA_NARRATIVA", "TIEMPO_VERBAL",  # RF-CFG-05
        "TITULO", "OBJETIVO_NARRATIVO", "PERSONAJES", "LOCACION", "INFORMACION_NUEVA",  # RF-03.1
        "TENSION",  # RF-05.1, con el vocabulario de ritmo de style_guide
        "HECHOS",  # RF-05.1, ya filtrados por el harness
        "RESUMEN_RODANTE",  # RF-06.4
        "FICHAS",  # RF-04.1
        "PALABRAS", "PALABRAS_MIN", "PALABRAS_MAX",  # RF-05.2
        "PERSONAJES_PERMITIDOS",  # RF-05.2, EX-08
        "FEEDBACK_LONGITUD",  # EX-07
        "STYLE_GUIDE", "TRES_ACTOS", "RUTA_CAPITULO", "NUM",
        "COMANDO_VALIDACION",  # RF-08.4: la forma canónica exacta que H-11 deja pasar
        "RECURSOS_AGOTADOS",  # RF-05.5 / §17.2: recursos narrativos ya usados, con su conteo; agotados, no prohibidos
    ),
    "extractor": (
        "RUTA_CAPITULO", "NUM",  # INV-02: un solo capítulo
        "REGISTRO_PERSONAJES", "REGISTRO_LOCACIONES",  # RF-06.1
        "ESQUEMA",  # §4 con sujeto y categoria
        "MAX_HECHOS",  # §11.6
        "RUTA_DELTA", "COMANDO_VALIDACION",  # RF-08.4: escribe y valida su propio delta
    ),
    "qa": (
        "LOG_CONTINUIDAD",  # RF-07.2, con superado_por visible
        "RECURSOS_USADOS",  # RF-07.5
        "CAPS_MUESTRA", "RUTAS_MUESTRA",  # RF-07.1
        "IDIOMA", "PERSONA_NARRATIVA", "TIEMPO_VERBAL",  # RF-CFG-05
        "ESQUEMA_REPORTE", "RUTA_REPORTE_MD", "RUTA_REPORTE_JSON", "RUTA_RECURSOS", "NUM",
        "COMANDO_VALIDACION",  # RF-08.4
    ),
}


def cargar_plantilla(raiz: Path, rol: str) -> str:
    path = Rutas(raiz).prompts_config / f"{rol}.md"
    if not path.exists():
        raise ConfiguracionInvalidaError(f"falta la plantilla de prompt {path.as_posix()} (§11.5)")
    texto = path.read_text(encoding="utf-8")
    faltantes = verificar_checklist(texto, rol)
    if faltantes:
        raise ConfiguracionInvalidaError(
            f"la plantilla config/prompts/{rol}.md omite marcadores del checklist §11.5: {', '.join(faltantes)}"
        )
    return texto


def verificar_checklist(texto: str, rol: str) -> list[str]:
    presentes = set(_MARCADOR.findall(texto))
    return [m for m in MARCADORES_OBLIGATORIOS[rol] if m not in presentes]


def rellenar(plantilla: str, valores: dict[str, str]) -> str:
    def _sustituir(m: re.Match) -> str:
        clave = m.group(1)
        if clave not in valores:
            raise ConfiguracionInvalidaError(f"la plantilla usa el marcador {{{{{clave}}}}} y el harness no lo provee")
        return valores[clave]

    return _MARCADOR.sub(_sustituir, plantilla)
