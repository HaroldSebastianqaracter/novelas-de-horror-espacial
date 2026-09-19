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

from app.agents import plantillas
from app.config import HarnessConfig, comando_validador
from app.errores import AutovalidacionFallidaError, ContratoRetornoError, OutlineFaltanteError
from app.rutas import Rutas
from app.schemas.continuidad import HechoContinuidad
from app.state import continuidad as cont
from app.state import personajes as pers
from app.state import recursos as rec
from app.state import repository as repo
from app.state import resumen_rodante as rr
from app.tokens import estimar_tokens

MAX_PALABRAS_RETORNO = 40
_RETORNO = re.compile(
    r"^(?:05_manuscrito/)?cap_(?P<n>\d+)\.md\s*[·|\-–,]\s*(?P<palabras>[\d.,\s]+?)\s*palabras\s*[·|\-–,]\s*"
    r"personajes\s*:\s*(?P<personajes>.*?)\s*[·|\-–,]\s*validado\s*$",
    re.IGNORECASE,
)
_NO_VALIDADO = re.compile(r"^(?:[\w/]+/)?(?P<artefacto>[\w.]+)\s*[·|\-–,]\s*NO VALIDADO\s*[·|\-–,]?\s*(?P<detalle>.*)$", re.IGNORECASE | re.DOTALL)


def detectar_ex10(texto: str, rol: str) -> None:
    """EX-10: el agente terminó informando que agotó sus intentos de autovalidación (RF-08.4)."""
    m = _NO_VALIDADO.match(texto.strip())
    if m:
        n = re.search(r"(\d+)", m.group("artefacto"))
        raise AutovalidacionFallidaError(rol, int(n.group(1)) if n else None, m.group("detalle").strip() or "sin detalle")


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
    recursos_inyectados: int = 0  # RF-05.5: recursos narrativos agotados que entraron al prompt
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


# X-05: lo que se deja libre sobre el tope del escritor al repartir el presupuesto de los hechos. El
# prompt se mide antes de escribirlo, pero el modelo no cuenta exactamente igual que tiktoken; apurar
# el tope al token cambiaría un recorte silencioso por un prompt rechazado.
MARGEN_TOKENS_HECHOS = 500


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
        posicion = f.posicion.strip() or "sin registrar"  # X-02.2
        bloques.append(
            f"### {nombre}\n- Estado físico: {f.estado_fisico}\n- Estado psicológico: {f.estado_psicologico}\n"
            f"- Secretos que conoce: {secretos}\n- Dónde quedó: {posicion}\n- Última aparición: {ultima}"
        )
    return "\n\n".join(bloques)


def ensamblar_contexto(n: int, config: HarnessConfig, raiz: Path, *, feedback_longitud: str | None = None,
                       feedback_qa: str | None = None, resumen_minimo: bool = False) -> Contexto:
    """RF-05.1: construye el prompt del escritor desde el estado persistente, sin el manuscrito."""
    rutas = Rutas(raiz)
    entrada = repo.leer_outline_entry(raiz, n)
    if entrada is None:
        raise OutlineFaltanteError(n)

    fichas = repo.leer_personajes(raiz)
    log = repo.leer_continuidad(raiz)
    minimo, maximo = config.rango_palabras()
    permitidos = list(dict.fromkeys(list(entrada.personajes) + list(fichas.root.keys())))
    # X-02.1: los hechos y las fichas de TODOS los personajes permitidos, no solo los de la escaleta. La
    # escaleta es una previsión; si el escritor mueve una escena, un personaje permitido pero no previsto
    # llegaba sin ficha ni continuidad y escribía sobre él a ciegas.
    hechos = cont.filtrar_para_capitulo(log, entrada, set(permitidos))
    resumen = repo.leer_resumen_rodante(raiz)
    resumen = (rr.recortar_a_minimo(resumen) if resumen_minimo
               else rr.para_escritor(resumen, config.ventana_resumen_rodante))  # X-02.3
    recursos = repo.leer_recursos_narrativos(raiz)  # RF-05.5 / §17.2: estado acumulado por el extractor, no manuscrito
    agotados = rec.mas_usados(recursos)
    # X-02.4b: del capítulo siguiente, solo su locación y el encargo de dejar la escena para que continúe
    # allí. Nunca su `informacion_nueva`, que es justo lo que el escritor no debe adelantar.
    siguiente = repo.leer_outline_entry(raiz, n + 1)
    if siguiente is None:
        relevo = "Este es el último capítulo de la novela: cerrá el arco, no dejes nada abierto para un capítulo posterior."
    else:
        relevo = (f"El capítulo siguiente ({n + 1}) transcurre en: {siguiente.locacion}. "
                  "Dejá esta escena de modo que la acción pueda continuar allí (los personajes que sigan "
                  "en juego, en camino o ya en esa locación), sin narrar lo que ocurrirá en él ni adelantar "
                  "su información nueva.")

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
        "FICHAS": _formatear_fichas(pers.fichas_presentes(fichas, permitidos)),  # X-02.1: todos los permitidos
        "RELEVO": relevo,
        "PALABRAS": str(config.palabras_por_capitulo),
        "PALABRAS_MIN": str(minimo),
        "PALABRAS_MAX": str(maximo),
        "PERSONAJES_PERMITIDOS": ", ".join(permitidos) if permitidos else "(ninguno)",
        "FEEDBACK_LONGITUD": feedback_longitud or "(primer intento: sin desvío previo)",
        "FEEDBACK_QA": feedback_qa or "(no hay revisión previa de este capítulo)",
        "COMANDO_VALIDACION": comando_validador("escritor", n, con_delta=config.escritor_emite_delta),
        "ENCARGO_DELTA": _encargo_delta(n, config, raiz),
        "RECURSOS_AGOTADOS": rec.formatear_agotados(recursos),
    }
    plantilla = plantillas.cargar_plantilla(raiz, "escritor")
    if config.aristas_en_continuidad:
        # X-05: el presupuesto de los hechos no es un número inventado, es lo que sobra. Se mide el
        # prompt sin ellos y se les da el resto menos un margen, así el recorte solo actúa cuando de
        # verdad no caben: en una novela corta, donde cabe todo, no cambia absolutamente nada.
        base, _ = estimar_tokens(plantillas.rellenar(plantilla, {**valores, "HECHOS": ""}))
        tope = max(0, config.max_tokens_contexto_escritor - base - MARGEN_TOKENS_HECHOS)
        hechos = cont.recortar_a_presupuesto(
            hechos, entrada, set(permitidos), n, tope_tokens=tope,
            coste=lambda h: estimar_tokens(_formatear_hechos([h]))[0])
        valores["HECHOS"] = _formatear_hechos(hechos)
    texto = plantillas.rellenar(plantilla, valores)
    tokens, metodo = estimar_tokens(texto)
    return Contexto(
        n=n, texto=texto, tokens_estimados=tokens, limite=config.max_tokens_contexto_escritor,
        metodo_estimacion=metodo, hechos_inyectados=hechos, resumen_recortado=resumen_minimo,
        feedback_longitud=feedback_longitud, recursos_inyectados=len(agotados), _config=config, _raiz=raiz,
    )


def _encargo_delta(n: int, config: HarnessConfig, raiz: Path) -> str:
    """X-04: el segundo archivo que el escritor entrega, cuando emite su propio delta.

    Va como un bloque entero del prompt en vez de como varias claves sueltas para que la
    plantilla siga leyéndose igual con el interruptor apagado, que es como corre la línea base.
    """
    if not config.escritor_emite_delta:
        return "(en esta corrida no escribís delta: de eso se encarga otro agente)"
    from app.agents.extractor import esquema_delta, registro_de_sujetos

    personajes, locaciones = registro_de_sujetos(raiz)
    rutas = Rutas(raiz)
    partes = [
        "Además del capítulo escribís su **delta de extracción**, que es lo que el harness usa "
        f"para armar el capítulo siguiente. Va en `{rutas.delta(n).as_posix()}` con Write, solo "
        "el objeto JSON, sin bloque de código ni texto alrededor.",
        "Describí **lo que quedó escrito en el capítulo**, no lo que pensabas escribir: si la "
        "escena se te fue por otro lado, manda el texto. Ese delta viaja a los capítulos "
        "siguientes y es lo único que sabrán de este.",
        f"Registro de sujetos, usá estos nombres exactos. Personajes: "
        f"{chr(44).join(personajes) if personajes else chr(40) + chr(41)}. "
        f"Locaciones: {chr(44).join(locaciones) if locaciones else chr(40) + chr(41)}. "
        "Y `mundo` para lo general.",
        f"Tope: {config.max_hechos_por_capitulo} hechos nuevos. Solo lo que este capítulo "
        "establece, no lo que reitera. Los `recursos_narrativos` no cuentan para el tope.",
        f"Esquema:{chr(10)}{esquema_delta(n, con_aristas=config.aristas_en_continuidad)}",
    ]
    return (chr(10) * 2).join(partes)

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
    """RF-08.1: una sola línea `cap_N.md · 2.940 palabras · personajes: A, B · validado`. Rechaza prosa o varias líneas."""
    detectar_ex10(texto, "escritor")
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
            "RF-08.1: la línea no tiene la forma `cap_N.md · <palabras> palabras · personajes: A, B · validado` "
            "(la confirmación `validado` es obligatoria, RF-08.4)"
        )
    palabras = int(re.sub(r"[^\d]", "", m.group("palabras")) or 0)
    personajes = [p.strip() for p in re.split(r"[,;]", m.group("personajes")) if p.strip()]
    return RetornoEscritor(n=int(m.group("n")), palabras_declaradas=palabras, personajes=personajes, linea=linea)


def generar_capitulo(contexto: Contexto, *, invocar: Callable[[str], str]) -> str:
    """Invocación del subagente escritor, inyectada. Devuelve el borrador. Solo lo usa el loop con dobles (§9)."""
    return invocar(contexto.texto)
