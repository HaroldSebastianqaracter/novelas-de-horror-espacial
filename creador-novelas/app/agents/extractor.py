"""Agente extractor, lado determinista (RF-06.1, RF-08.1, EX-08, §3.4).

`extraer(cap_n: str, ...)` acepta un único capítulo (INV-02). El extractor devuelve el JSON del
`DeltaExtraccion` en su mensaje final; este módulo lo parsea y lo valida contra el registro de sujetos.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from app.agents import plantillas
from app.agents.escritor import detectar_ex10
from app.config import HarnessConfig, comando_validador
from app.errores import ContratoRetornoError, EstadoInvalidoError
from app.rutas import Rutas
from app.schemas import DeltaExtraccion
from app.schemas.continuidad import HechoContinuidad
from app.state import continuidad as cont
from app.state import personajes as pers
from app.state import recursos as rec
from app.state import repository as repo

_FENCE = re.compile(r"^```[a-zA-Z]*\s*\n(.*?)\n```\s*$", re.DOTALL)
_RETORNO = re.compile(
    r"^(?:04_estado/deltas/)?delta_cap_(?P<n>\d+)\.json\s*[·|\-–,]\s*(?P<hechos>\d+)\s*hechos?\s*[·|\-–,]\s*"
    r"(?P<personajes>\d+)\s*personajes?\s*[·|\-–,]\s*validado\s*$",
    re.IGNORECASE,
)


@dataclass
class RetornoExtractor:
    n: int
    hechos: int
    personajes: int
    linea: str


def parsear_retorno_extractor(texto: str) -> RetornoExtractor:
    """RF-08.1: una sola línea `delta_cap_N.json · 4 hechos · 2 personajes · validado`. Nunca el JSON."""
    detectar_ex10(texto, "extractor")
    lineas = [l for l in texto.strip().splitlines() if l.strip()]
    if len(lineas) != 1:
        raise ContratoRetornoError(f"RF-08.1: el extractor debe devolver exactamente una línea; devolvió {len(lineas)}")
    linea = lineas[0].strip()
    if linea.startswith("{") or linea.startswith("```"):
        raise ContratoRetornoError("RF-08.1: el extractor no devuelve el JSON: lo escribe en disco y devuelve la línea de confirmación")
    m = _RETORNO.match(linea)
    if not m:
        raise ContratoRetornoError(
            "RF-08.1: la línea no tiene la forma `delta_cap_N.json · <hechos> hechos · <personajes> personajes · validado`"
        )
    return RetornoExtractor(n=int(m.group("n")), hechos=int(m.group("hechos")), personajes=int(m.group("personajes")), linea=linea)

ESQUEMA_DELTA = """{
  "personajes": {
    "<clave del registro>": {
      "estado_fisico": "string",
      "estado_psicologico": "string",
      "secretos_que_conoce": ["string"],
      "ultima_aparicion": <NUM>
    }
  },
  "hechos_nuevos": [
    {
      "sujeto": "<clave del registro, locación del registro o \\"mundo\\">",
      "categoria": "personaje | locacion | mundo",
      "hecho": "una oración en prosa, atómica y verificable",
      "cap_origen": <NUM>
    }
  ],
  "resumen_corto": "3 a 5 líneas",
  "recursos_narrativos": [
    {
      "recurso": "imagen, gesto, muletilla o giro recurrente, descrito en pocas palabras (no la cita entera)",
      "veces": <apariciones en este capítulo>
    }
  ]
}"""


@dataclass
class DeltaValidado:
    delta: DeltaExtraccion  # con cap_origen, ultima_aparicion y sujeto_validado ya fijados por el harness
    claves_no_previstas: list[str]  # EX-08 si no está vacía
    sujetos_no_validados: list[str]  # hechos con sujeto fuera del registro (se conservan)

    @property
    def requiere_regeneracion(self) -> bool:
        return bool(self.claves_no_previstas)


def registro_de_sujetos(raiz: Path) -> tuple[list[str], list[str]]:
    fichas = repo.leer_personajes(raiz)
    mundo = repo.leer_mundo(raiz)
    return list(fichas.root.keys()), (mundo.nombres_locaciones() if mundo else [])


def preparar_prompt_extractor(n: int, config: HarnessConfig, raiz: Path) -> str:
    """Prompt de invocación: la ruta del único capítulo permitido y el registro de sujetos, sin memoria (§12.2)."""
    rutas = Rutas(raiz)
    personajes, locaciones = registro_de_sujetos(raiz)
    valores = {
        "NUM": str(n),
        "RUTA_CAPITULO": rutas.capitulo(n).as_posix(),
        "REGISTRO_PERSONAJES": ", ".join(personajes) if personajes else "(vacío)",
        "REGISTRO_LOCACIONES": ", ".join(locaciones) if locaciones else "(vacío)",
        "ESQUEMA": ESQUEMA_DELTA.replace("<NUM>", str(n)),
        "MAX_HECHOS": str(config.max_hechos_por_capitulo),
        "RUTA_DELTA": rutas.delta(n).as_posix(),
        "COMANDO_VALIDACION": comando_validador("extractor", n),
    }
    return plantillas.rellenar(plantillas.cargar_plantilla(raiz, "extractor"), valores)


def parsear_delta(texto: str) -> DeltaExtraccion:
    """RF-08.1: el retorno es el JSON del delta y nada más. Se tolera un único bloque ``` alrededor."""
    limpio = texto.strip()
    m = _FENCE.match(limpio)
    if m:
        limpio = m.group(1).strip()
    if not limpio.startswith("{"):
        raise EstadoInvalidoError("RF-08.1: el extractor debe devolver solo el JSON del DeltaExtraccion, sin texto alrededor")
    return repo.validar_texto(limpio, DeltaExtraccion, "DeltaExtraccion")


def validar_delta(delta: DeltaExtraccion, registro: set[str], config: HarnessConfig, n: int) -> DeltaValidado:
    """Fija cap_origen = N y ultima_aparicion = N, marca sujeto_validado y detecta EX-08 y el tope de hechos (§11.6)."""
    if len(delta.hechos_nuevos) > config.max_hechos_por_capitulo:
        raise EstadoInvalidoError(
            f"§11.6: el delta trae {len(delta.hechos_nuevos)} hechos y el tope es {config.max_hechos_por_capitulo}; "
            "quedate con los que más condicionan capítulos futuros"
        )
    lineas_resumen = [l for l in delta.resumen_corto.strip().splitlines() if l.strip()]
    if not lineas_resumen:
        raise EstadoInvalidoError("RF-06.1: resumen_corto no puede estar vacío")
    hechos: list[HechoContinuidad] = []
    no_validados: list[str] = []
    for h in delta.hechos_nuevos:
        h2 = cont.validar_sujeto(h.model_copy(update={"cap_origen": n, "superado_por": None}), registro)
        if not h2.sujeto_validado:
            no_validados.append(h2.sujeto)
        hechos.append(h2)
    personajes = {
        clave: p.model_copy(update={"ultima_aparicion": n}) for clave, p in delta.personajes.items()
    }
    # RF-05.5 / §17.3: los recursos narrativos no entran en el tope de hechos; el mismo recurso dos veces se funde.
    normalizado = DeltaExtraccion(personajes=personajes, hechos_nuevos=hechos, resumen_corto=delta.resumen_corto,
                                  recursos_narrativos=rec.fusionar(delta.recursos_narrativos))
    return DeltaValidado(
        delta=normalizado,
        claves_no_previstas=pers.claves_no_previstas(delta.personajes, registro),
        sujetos_no_validados=no_validados,
    )


def extraer(cap_n: str, *, invocar: Callable[[str], str]) -> DeltaExtraccion:
    """Invocación del subagente extractor sobre UN capítulo (INV-02). Solo la usa el loop con dobles (§9)."""
    return parsear_delta(invocar(cap_n))


def serializar_delta(delta: DeltaExtraccion) -> str:
    return json.dumps(delta.model_dump(), ensure_ascii=False, indent=2) + "\n"
