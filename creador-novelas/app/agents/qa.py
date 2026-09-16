"""Agente QA, lado determinista (RF-07.1 a RF-07.5, RF-08.1, §12.4).

Único módulo de `agents/` que importa `leer_muestra_manuscrito` (INV-05): la usa para las métricas
computables del corte (entropía de bigramas), no para el prompt, que el subagente resuelve leyendo con `Read`.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from app.agents import plantillas
from app.config import HarnessConfig
from app.errores import ContratoRetornoError
from app.rutas import Rutas
from app.schemas import LogContinuidad, ReporteQA
from app.state import repository as repo
from app.state.repository import leer_muestra_manuscrito

MAX_LINEAS_RETORNO = 5
_BANDERA = re.compile(r"tiene_contradicciones\s*[:=]\s*(true|false|sí|si|no|verdadero|falso)", re.IGNORECASE)

ESQUEMA_REPORTE = """{
  "cap_corte": <NUM>,
  "hallazgos": [
    { "tipo": "contradiccion", "descripcion": "qué afirma el capítulo y qué hecho contradice", "cap_origen": <k> },
    { "tipo": "repeticion", "descripcion": "recurso repetido y dónde", "cap_origen": null }
  ],
  "tiene_contradicciones": true | false
}

recursos_usados.json: [ { "recurso": "descripción", "veces": <entero>, "caps": [<capítulos>] } ]"""


@dataclass
class PreparacionQA:
    n: int
    caps_muestra: list[int]
    rutas_muestra: list[str]
    prompt: str


@dataclass
class RetornoQA:
    tiene_contradicciones: bool
    lineas: list[str]


def capitulos_muestra(n: int, cadencia_qa: int) -> list[int]:
    """RF-07.1: los últimos `cadencia_qa` capítulos hasta N inclusive."""
    return list(range(max(1, n - cadencia_qa + 1), n + 1))


def _formatear_log(log: LogContinuidad) -> str:
    if not log.root:
        return "(log vacío)"
    return json.dumps([h.model_dump() for h in log.root], ensure_ascii=False, indent=2)


def preparar_corte(n: int, config: HarnessConfig, raiz: Path) -> PreparacionQA:
    rutas = Rutas(raiz)
    caps = capitulos_muestra(n, config.cadencia_qa)
    rutas_muestra = [rutas.capitulo(k).as_posix() for k in caps]
    recursos = repo.leer_recursos_usados(raiz)
    valores = {
        "NUM": str(n),
        "CAPS_MUESTRA": ", ".join(str(k) for k in caps),
        "RUTAS_MUESTRA": "\n".join(f"- {r}" for r in rutas_muestra),
        "LOG_CONTINUIDAD": _formatear_log(repo.leer_continuidad(raiz)),
        "RECURSOS_USADOS": json.dumps([r.model_dump() for r in recursos.root], ensure_ascii=False, indent=2),
        "IDIOMA": config.idioma,
        "PERSONA_NARRATIVA": config.persona_narrativa,
        "TIEMPO_VERBAL": config.tiempo_verbal,
        "ESQUEMA_REPORTE": ESQUEMA_REPORTE.replace("<NUM>", str(n)),
        "RUTA_REPORTE_MD": rutas.reporte_qa_md(n).as_posix(),
        "RUTA_REPORTE_JSON": rutas.reporte_qa_json(n).as_posix(),
        "RUTA_RECURSOS": rutas.recursos_usados.as_posix(),
    }
    prompt = plantillas.rellenar(plantillas.cargar_plantilla(raiz, "qa"), valores)
    return PreparacionQA(n=n, caps_muestra=caps, rutas_muestra=rutas_muestra, prompt=prompt)


def parsear_retorno_qa(texto: str) -> RetornoQA:
    """RF-08.1: hasta cinco líneas con `tiene_contradicciones` y el conteo de hallazgos por tipo."""
    lineas = [l.strip() for l in texto.strip().splitlines() if l.strip()]
    if not lineas:
        raise ContratoRetornoError("RF-08.1: el retorno de QA está vacío")
    if len(lineas) > MAX_LINEAS_RETORNO:
        raise ContratoRetornoError(f"RF-08.1: el retorno de QA tiene {len(lineas)} líneas; el máximo es {MAX_LINEAS_RETORNO}")
    m = _BANDERA.search(texto)
    if not m:
        raise ContratoRetornoError("RF-08.1: el retorno de QA debe declarar `tiene_contradicciones: true|false`")
    return RetornoQA(tiene_contradicciones=m.group(1).lower() in ("true", "sí", "si", "verdadero"), lineas=lineas)


def entropia_bigramas(texto: str) -> float:
    """§12.4 (Ent-2): entropía de Shannon de los bigramas de palabras, en bits."""
    palabras = re.findall(r"\w+", texto.lower())
    if len(palabras) < 2:
        return 0.0
    conteo = Counter(zip(palabras, palabras[1:]))
    total = sum(conteo.values())
    return -sum((c / total) * math.log2(c / total) for c in conteo.values())


def metricas_corte(raiz: Path, caps: list[int], reporte: ReporteQA, log: LogContinuidad) -> dict:
    """§12.4: entropía de bigramas de la muestra y tasa de conflicto (contradicciones / hechos vigentes)."""
    muestra = leer_muestra_manuscrito(raiz, caps)
    vigentes = len(log.vigentes())
    contradicciones = reporte.conteo_por_tipo()["contradiccion"]
    return {
        "cap_corte": reporte.cap_corte,
        "caps_muestra": caps,
        "entropia_bigramas": round(entropia_bigramas("\n".join(muestra.values())), 4),
        "hechos_vigentes": vigentes,
        "contradicciones": contradicciones,
        "tasa_conflicto": round(contradicciones / vigentes, 4) if vigentes else 0.0,
    }


def ejecutar_corte(prep: PreparacionQA, *, invocar: Callable[[str], str]) -> ReporteQA:
    """Invocación del subagente QA, inyectada. Devuelve el ReporteQA. Solo la usa el loop con dobles (§9)."""
    return repo.validar_texto(invocar(prep.prompt), ReporteQA, "ReporteQA")
