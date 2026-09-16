"""Agente escritor, lado determinista (RF-05.1, RF-05.2, RF-08.1).

Este módulo es el ÚNICO que ensambla el contexto del escritor y NO importa ninguna función que lea el
manuscrito (INV-01, spec técnica §2). Trabaja solo con artefactos de estado.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from harness.agents import plantillas
from harness.config import HarnessConfig
from harness.errores import ContratoRetornoError, OutlineFaltanteError
from harness.rutas import Rutas
from harness.schemas.continuidad import HechoContinuidad
from harness.state import continuidad as cont
from harness.state import personajes as pers
from harness.state import repository as repo
from harness.state import resumen_rodante as rr
from harness.tokens import estimar_tokens

MAX_PALABRAS_RETORNO = 40
_RETORNO = re.compile(
    r"^(?:05_manuscrito/)?cap_(?P<n>\d+)\.md\s*[·|\-–,]\s*(?P<palabras>[\d.,\s]+?)\s*palabras\s*[·|\-–,]\s*"
    r"personajes\s*:\s*(?P<personajes>.*)$",
    re.IGNORECASE,
)


@dataclass
class Contexto:
    n: int
    texto: str
    tokens_estimados: int
    limite: int
    metodo_estimacion: str
    hechos_inyectados: list[HechoContinuidad]
    resumen_recortado: bool = False
    feedback_longitud: str | None = None
    _config: HarnessConfig | None = field(default=None, repr=False)
    _raiz: Path | None = field(default=None, repr=False)

    def excede_limite(self) -> bool:
        return self.tokens_estimados > self.limite


@dataclass
class RetornoEscritor:
    n: int
    palabras_declaradas: int
    personajes: list[str]
    linea: str


def _formatear_hechos(hechos: list[HechoContinuidad]) -> str:
    if not hechos:
        return "(todavía no hay hechos establecidos)"
    lineas = []
    for h in hechos:
        marca = "" if h.sujeto_validado else " [sujeto sin validar: tratar con cuidado]"
        lineas.append(f"- [{h.categoria} · {h.sujeto} · cap. {h.cap_origen}] {h.hecho}{marca}")
    return "\n".join(lineas)


def _formatear_fichas(fichas: dict) -> str:
    if not fichas:
        return "(ninguna ficha registrada para los personajes de este capítulo)"
    bloques = []
    for nombre, f in fichas.items():
        secretos = "; ".join(f.secretos_que_conoce) if f.secretos_que_conoce else "ninguno registrado"
        ultima = f"cap. {f.ultima_aparicion}" if f.ultima_aparicion > 0 else "todavía no apareció"
        bloques.append(
            f"### {nombre}\n- Estado físico: {f.estado_fisico}\n- Estado psicológico: {f.estado_psicologico}\n"
            f"- Secretos que conoce: {secretos}\n- Última aparición: {ultima}"
        )
    return "\n\n".join(bloques)


def ensamblar_contexto(n: int, config: HarnessConfig, raiz: Path, *, feedback_longitud: str | None = None,
                       resumen_minimo: bool = False) -> Contexto:
    """RF-05.1: construye el prompt del escritor desde el estado persistente, sin el manuscrito."""
    rutas = Rutas(raiz)
    entrada = repo.leer_outline_entry(raiz, n)
    if entrada is None:
        raise OutlineFaltanteError(n)

    fichas = repo.leer_personajes(raiz)
    log = repo.leer_continuidad(raiz)
    hechos = cont.filtrar_para_capitulo(log, entrada)
    resumen = repo.leer_resumen_rodante(raiz)
    if resumen_minimo:
        resumen = rr.recortar_a_minimo(resumen)
    minimo, maximo = config.rango_palabras()
    permitidos = list(dict.fromkeys(list(entrada.personajes) + list(fichas.root.keys())))

    valores = {
        "NUM": str(n),
        "RUTA_CAPITULO": rutas.capitulo(n).as_posix(),
        "IDIOMA": config.idioma,
        "PERSONA_NARRATIVA": config.persona_narrativa,
        "TIEMPO_VERBAL": config.tiempo_verbal,
        "TITULO": entrada.titulo,
        "OBJETIVO_NARRATIVO": entrada.objetivo_narrativo,
        "PERSONAJES": ", ".join(entrada.personajes) if entrada.personajes else "(ninguno en escena)",
        "LOCACION": entrada.locacion,
        "INFORMACION_NUEVA": entrada.informacion_nueva or "(ninguna)",
        "TENSION": str(entrada.tension),
        "STYLE_GUIDE": repo.leer_style_guide(raiz).strip() or "(sin guía de estilo)",
        "TRES_ACTOS": repo.leer_tres_actos(raiz).strip() or "(sin sinopsis)",
        "HECHOS": _formatear_hechos(hechos),
        "RESUMEN_RODANTE": resumen.strip() or "(este es el primer capítulo: no hay escena previa)",
        "FICHAS": _formatear_fichas(pers.fichas_presentes(fichas, entrada.personajes)),
        "PALABRAS": str(config.palabras_por_capitulo),
        "PALABRAS_MIN": str(minimo),
        "PALABRAS_MAX": str(maximo),
        "PERSONAJES_PERMITIDOS": ", ".join(permitidos) if permitidos else "(ninguno)",
        "FEEDBACK_LONGITUD": feedback_longitud or "(primer intento: sin desvío previo)",
    }
    texto = plantillas.rellenar(plantillas.cargar_plantilla(raiz, "escritor"), valores)
    tokens, metodo = estimar_tokens(texto)
    return Contexto(
        n=n, texto=texto, tokens_estimados=tokens, limite=config.max_tokens_contexto_escritor,
        metodo_estimacion=metodo, hechos_inyectados=hechos, resumen_recortado=resumen_minimo,
        feedback_longitud=feedback_longitud, _config=config, _raiz=raiz,
    )


def recortar_resumen_rodante(contexto: Contexto) -> Contexto:
    """EX-04: recorta el resumen rodante a su mínimo. Nunca toca continuidad ni personajes."""
    assert contexto._config is not None and contexto._raiz is not None
    return ensamblar_contexto(contexto.n, contexto._config, contexto._raiz,
                              feedback_longitud=contexto.feedback_longitud, resumen_minimo=True)


def persistir_contexto(contexto: Contexto, raiz: Path) -> Path:
    """Deja el prompt en 04_estado/prompts/ (artefacto de trabajo, §8.2) junto con los hechos inyectados."""
    rutas = Rutas(raiz)
    rutas.prompts_trabajo.mkdir(parents=True, exist_ok=True)
    rutas.prompt_escritor(contexto.n).write_text(contexto.texto, encoding="utf-8")
    rutas.hechos_inyectados(contexto.n).write_text(
        json.dumps([h.model_dump() for h in contexto.hechos_inyectados], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return rutas.prompt_escritor(contexto.n)


def contar_palabras(texto: str) -> int:
    return len(re.findall(r"\S+", texto))


def evaluar_longitud(palabras: int, config: HarnessConfig) -> tuple[bool, str]:
    """EX-07: (dentro de rango, mensaje de desvío para el reintento)."""
    minimo, maximo = config.rango_palabras()
    if minimo <= palabras <= maximo:
        return True, ""
    return False, (
        f"El borrador tiene {palabras} palabras; el objetivo es {config.palabras_por_capitulo} +-20 % "
        f"(entre {minimo} y {maximo}). "
        + ("Hay que alargarlo." if palabras < minimo else "Hay que acortarlo.")
    )


def parsear_retorno_escritor(texto: str) -> RetornoEscritor:
    """RF-08.1: una sola línea `cap_N.md · 2.940 palabras · personajes: A, B`. Rechaza prosa o varias líneas."""
    lineas = [l for l in texto.strip().splitlines() if l.strip()]
    if len(lineas) != 1:
        raise ContratoRetornoError(
            f"RF-08.1: el escritor debe devolver exactamente una línea; devolvió {len(lineas)}"
        )
    linea = lineas[0].strip()
    if contar_palabras(linea) > MAX_PALABRAS_RETORNO:
        raise ContratoRetornoError("RF-08.1: la línea de retorno del escritor excede 40 palabras; parece prosa")
    m = _RETORNO.match(linea)
    if not m:
        raise ContratoRetornoError(
            "RF-08.1: la línea no tiene la forma `cap_N.md · <palabras> palabras · personajes: A, B`"
        )
    palabras = int(re.sub(r"[^\d]", "", m.group("palabras")) or 0)
    personajes = [p.strip() for p in re.split(r"[,;]", m.group("personajes")) if p.strip()]
    return RetornoEscritor(n=int(m.group("n")), palabras_declaradas=palabras, personajes=personajes, linea=linea)


def generar_capitulo(contexto: Contexto, *, invocar: Callable[[str], str]) -> str:
    """Invocación del subagente escritor, inyectada. Devuelve el borrador. Solo lo usa el loop con dobles (§9)."""
    return invocar(contexto.texto)
