"""Loop principal fases 5-7 (spec técnica §6), partido en tramos (§8.2).

Cada tramo es una función determinista que la skill `/escribir-tanda` invoca por CLI entre dos invocaciones
de subagente. `ejecutar_tanda` encadena los mismos tramos con las tres invocaciones inyectadas (dobles en
`pytest`, §9). Ninguna excepción de §7 se captura en silencio: todas dejan el manifiesto consistente.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from app.agents import escritor, extractor, qa
from app.agents.escritor import Contexto
from app.agents.qa import PreparacionQA
from app.config import HarnessConfig, hash_prompts
from app.errores import (
    CapituloCerradoError, ContextoExcedidoError, ContratoRetornoError, EstadoInvalidoError,
    LongitudFueraDeRangoAviso, ManifiestoInconsistenteError, PersonajeNoPrevistoError,
)
from app.orchestrator import checkpoint, cursor as cur
from app.orchestrator.cursor import Cursor
from app.rutas import Rutas
from app.schemas import DeltaExtraccion, ReporteQA
from app.state import continuidad as cont
from app.state import personajes as pers
from app.state import repository as repo
from app.state import resumen_rodante as rr

MOTIVOS_FIN = ("tope_de_tanda", "pausado_por_qa", "novela_completa", "tope_de_llamadas", "completo")


@dataclass
class ResultadoTanda:
    cerrados: int
    motivo: str  # uno de MOTIVOS_FIN, o "seguir" con el próximo capítulo en `siguiente`
    siguiente: int | None = None
    avisos: list[str] = field(default_factory=list)


@dataclass
class ResultadoEscritor:
    n: int
    palabras: int
    dentro_de_rango: bool
    mensaje: str
    reintentar: bool  # EX-07: True solo tras el primer fallo
    personajes_declarados: list[str]


@dataclass
class ResultadoDelta:
    n: int
    regenerar: bool  # EX-08 primer fallo
    claves_no_previstas: list[str]
    sujetos_no_validados: list[str]
    hechos_agregados: int
    cerrado: bool
    toca_qa: bool


@dataclass
class ResultadoQA:
    reporte: ReporteQA
    pausado: bool
    metricas: dict


class Agentes(Protocol):
    """Las tres invocaciones de subagente, inyectadas (§6). Devuelven texto: borrador, JSON del delta, JSON del reporte."""

    def generar_capitulo(self, prompt: str) -> str: ...

    def extraer(self, cap_n: str) -> str: ...

    def ejecutar_corte(self, prompt: str) -> str: ...


# ---------- tramos ----------

def iniciar_tanda(raiz: Path, config: HarnessConfig, capitulos_por_tanda: int | None = None,
                  hasta_el_final: bool = False) -> Cursor:
    """Verifica que se pueda reanudar (EX-02, EX-06, §5), crea el cursor (descartando uno huérfano) y registra prompts_hash."""
    m = checkpoint.verificar_reanudable(raiz, config)
    tope = None if hasta_el_final else (capitulos_por_tanda or config.capitulos_por_tanda)  # RF-CFG-03
    cursor = Cursor(inicio=m.ultimo_capitulo_cerrado + 1, tope=tope, max_llamadas=config.max_llamadas_por_tanda)
    cur.borrar(raiz)
    cur.escribir(raiz, cursor)
    checkpoint.actualizar_prompts_hash(raiz, hash_prompts(raiz))
    if m.ultimo_error:
        checkpoint.limpiar_error(raiz)
    return cursor


def evaluar_siguiente(raiz: Path, config: HarnessConfig, cursor: Cursor) -> ResultadoTanda:
    """Decide entre seguir con el próximo capítulo o terminar limpio (RF-CFG-02, RF-CFG-06, §6)."""
    m = checkpoint.exigir_manifest(raiz)
    if m.ultimo_capitulo_cerrado >= config.total_capitulos:
        if m.estado != "completo":
            checkpoint.marcar_completo(raiz)
        return ResultadoTanda(cursor.cerrados, "novela_completa" if cursor.cerrados > 0 else "completo", avisos=cursor.avisos)
    if cursor.tope_alcanzado():
        return ResultadoTanda(cursor.cerrados, "tope_de_tanda", avisos=cursor.avisos)
    if cursor.llamadas_agotadas():
        return ResultadoTanda(cursor.cerrados, "tope_de_llamadas", avisos=cursor.avisos)
    return ResultadoTanda(cursor.cerrados, "seguir", siguiente=m.ultimo_capitulo_cerrado + 1, avisos=cursor.avisos)


def tanda_siguiente(raiz: Path, config: HarnessConfig) -> ResultadoTanda:
    """Verbo `tanda siguiente`: avanza el cursor; si la tanda termina, lo borra."""
    cursor = cur.exigir(raiz)
    resultado = evaluar_siguiente(raiz, config, cursor)
    if resultado.motivo != "seguir":
        cur.borrar(raiz)
    return resultado


def preparar_capitulo(raiz: Path, config: HarnessConfig, n: int, feedback_longitud: str | None = None) -> Contexto:
    """RF-05.1 con EX-03 y EX-04. Deja el prompt en 04_estado/prompts/ y anota el capítulo en curso."""
    m = checkpoint.exigir_manifest(raiz)
    if n != m.ultimo_capitulo_cerrado + 1:
        raise ManifiestoInconsistenteError(
            f"INV-07: el próximo capítulo es {m.ultimo_capitulo_cerrado + 1}, no {n}"
        )
    contexto = escritor.ensamblar_contexto(n, config, raiz, feedback_longitud=feedback_longitud)
    if contexto.excede_limite():
        contexto = escritor.recortar_resumen_rodante(contexto)
        if contexto.excede_limite():
            error = ContextoExcedidoError(n, contexto.tokens_estimados, contexto.limite)
            checkpoint.registrar_error(raiz, str(error))
            cur.borrar(raiz)
            raise error
    escritor.persistir_contexto(contexto, raiz)
    preparar_extractor(raiz, config, n)  # el prompt del extractor no depende del texto del capítulo
    cursor = cur.leer(raiz)
    if cursor is not None and cursor.capitulo_en_curso != n:
        cursor.capitulo_en_curso = n
        cursor.intentos_longitud = 0
        cursor.intentos_personaje = 0
        cur.escribir(raiz, cursor)
    return contexto


def preparar_extractor(raiz: Path, config: HarnessConfig, n: int) -> Path:
    """Deja el prompt de invocación del extractor en 04_estado/prompts/extractor_cap_N.md (RF-06.1, §12.2)."""
    m = checkpoint.exigir_manifest(raiz)
    if n != m.ultimo_capitulo_cerrado + 1 and n not in m.reextraccion_pendiente:
        raise ManifiestoInconsistenteError(
            f"el extractor solo se prepara para el capítulo en curso ({m.ultimo_capitulo_cerrado + 1}) o uno en reextracción {m.reextraccion_pendiente}; se pidió {n}"
        )
    rutas = Rutas(raiz)
    rutas.prompts_trabajo.mkdir(parents=True, exist_ok=True)
    rutas.prompt_extractor(n).write_text(extractor.preparar_prompt_extractor(n, config, raiz), encoding="utf-8")
    return rutas.prompt_extractor(n)


def evaluar_borrador(raiz: Path, config: HarnessConfig, n: int) -> ResultadoEscritor:
    """EX-07 sobre el archivo en disco: cuenta palabras y decide si toca el único reintento."""
    if not repo.existe_capitulo(raiz, n):
        raise ContratoRetornoError(f"RF-05.4: no existe 05_manuscrito/cap_{n}.md")
    palabras = escritor.contar_palabras(repo.leer_manuscrito(raiz, n))
    ok, mensaje = escritor.evaluar_longitud(palabras, config)
    reintentar = False
    if not ok:
        m = checkpoint.exigir_manifest(raiz)
        cursor = cur.leer(raiz)
        intentos_previos = max(m.intentos_por_capitulo.get(str(n), 0), cursor.intentos_longitud if cursor else 0)
        if intentos_previos == 0:
            reintentar = True
            if cursor is not None:
                cursor.intentos_longitud = 1
                cur.escribir(raiz, cursor)
        else:
            warnings.warn(mensaje, LongitudFueraDeRangoAviso)
            checkpoint.registrar_intentos(raiz, n, 2)
            if cursor is not None:
                cursor.intentos_longitud = 2
                cursor.avisos.append(f"EX-07 cap. {n}: {mensaje}")
                cur.escribir(raiz, cursor)
    return ResultadoEscritor(n=n, palabras=palabras, dentro_de_rango=ok, mensaje=mensaje, reintentar=reintentar,
                             personajes_declarados=[])


def registrar_escritor(raiz: Path, config: HarnessConfig, n: int, linea: str) -> ResultadoEscritor:
    """Verbo `registrar-escritor`: parser de RF-08.1 y evaluación EX-07 del archivo escrito."""
    retorno = escritor.parsear_retorno_escritor(linea)
    if retorno.n != n:
        raise ContratoRetornoError(f"RF-08.1: el escritor declaró cap_{retorno.n}.md y el capítulo en curso es {n}")
    resultado = evaluar_borrador(raiz, config, n)
    resultado.personajes_declarados = retorno.personajes
    return resultado


def aplicar_delta(raiz: Path, config: HarnessConfig, n: int, delta: DeltaExtraccion | str | None = None,
                  reextraccion: bool = False) -> ResultadoDelta:
    """RF-06.1 a RF-06.4 (y RF-07.6 paso 2 con `reextraccion`). Nada se escribe si algo no valida (EX-01)."""
    rutas = Rutas(raiz)
    m = checkpoint.exigir_manifest(raiz)
    if reextraccion:
        if n not in m.reextraccion_pendiente:
            raise ManifiestoInconsistenteError(f"RF-07.6: el capítulo {n} no está en reextraccion_pendiente {m.reextraccion_pendiente}")
    elif n != m.ultimo_capitulo_cerrado + 1:
        raise ManifiestoInconsistenteError(f"INV-07: se intentó aplicar el delta del capítulo {n} y el siguiente es {m.ultimo_capitulo_cerrado + 1}")

    if delta is None:
        path = rutas.delta(n)
        if not path.exists():
            raise EstadoInvalidoError(f"no existe {path.as_posix()}: el orquestador debe dejar ahí el JSON del extractor")
        delta = path.read_text(encoding="utf-8")
    if isinstance(delta, str):
        delta = extractor.parsear_delta(delta)

    fichas = repo.leer_personajes(raiz)
    mundo = repo.leer_mundo(raiz)
    registro = pers.sujetos_conocidos(fichas, mundo)
    validado = extractor.validar_delta(delta, registro, config, n)

    cursor = cur.leer(raiz)
    if validado.claves_no_previstas:
        # EX-08: primer fallo regenera; segundo detiene.
        intentos = (cursor.intentos_personaje if cursor else 0) + 1
        if cursor is not None:
            cursor.intentos_personaje = intentos
            cur.escribir(raiz, cursor)
        checkpoint.registrar_intentos(raiz, n, 2)
        if intentos >= 2:
            error = PersonajeNoPrevistoError(n, validado.claves_no_previstas)
            checkpoint.registrar_error(raiz, str(error))
            cur.borrar(raiz)
            raise error
        return ResultadoDelta(n=n, regenerar=True, claves_no_previstas=validado.claves_no_previstas,
                              sujetos_no_validados=validado.sujetos_no_validados, hechos_agregados=0,
                              cerrado=False, toca_qa=False)

    d = validado.delta
    nuevas_fichas = pers.aplicar_delta(fichas, d.personajes, n)
    if reextraccion:  # la última aparición no retrocede por corregir un capítulo viejo
        for clave in d.personajes:
            previa = fichas.root.get(clave)
            if previa and previa.ultima_aparicion > n:
                nuevas_fichas.root[clave] = nuevas_fichas.root[clave].model_copy(update={"ultima_aparicion": previa.ultima_aparicion})
    log = cont.agregar(repo.leer_continuidad(raiz), d.hechos_nuevos, n, registro)
    resumen_actual = repo.leer_resumen_rodante(raiz)
    resumen = (rr.reemplazar(resumen_actual, n, d.resumen_corto) if reextraccion
               else rr.agregar(resumen_actual, n, d.resumen_corto, config.ventana_resumen_rodante))

    repo.escribir_personajes(raiz, nuevas_fichas)  # RF-06.2
    repo.escribir_continuidad(raiz, log)  # RF-06.3
    repo.escribir_resumen_rodante(raiz, resumen)  # RF-06.4

    if reextraccion:
        checkpoint.quitar_reextraccion(raiz, n)
        return ResultadoDelta(n=n, regenerar=False, claves_no_previstas=[], sujetos_no_validados=validado.sujetos_no_validados,
                              hechos_agregados=len(d.hechos_nuevos), cerrado=False, toca_qa=False)

    checkpoint.marcar_capitulo_cerrado(raiz, n)
    if cursor is not None:
        cursor.cerrados += 1
        cursor.capitulo_en_curso = None
        cursor.intentos_longitud = 0
        cursor.intentos_personaje = 0
        cur.escribir(raiz, cursor)
    return ResultadoDelta(n=n, regenerar=False, claves_no_previstas=[], sujetos_no_validados=validado.sujetos_no_validados,
                          hechos_agregados=len(d.hechos_nuevos), cerrado=True, toca_qa=(n % config.cadencia_qa == 0))


def descartar_borrador(raiz: Path, n: int) -> None:
    """EX-08: elimina el borrador para regenerar. Nunca un capítulo cerrado (INV-07)."""
    m = checkpoint.exigir_manifest(raiz)
    repo.descartar_borrador(raiz, n, m.ultimo_capitulo_cerrado)


def preparar_qa(raiz: Path, config: HarnessConfig, n: int) -> PreparacionQA:
    """RF-07.1: el corte corre sobre el último capítulo cerrado, que debe ser múltiplo de cadencia_qa."""
    m = checkpoint.exigir_manifest(raiz)
    if n != m.ultimo_capitulo_cerrado:
        raise ManifiestoInconsistenteError(f"RF-07.1: el corte de QA corre sobre el último cerrado ({m.ultimo_capitulo_cerrado}), no sobre {n}")
    prep = qa.preparar_corte(n, config, raiz)
    rutas = Rutas(raiz)
    rutas.prompts_trabajo.mkdir(parents=True, exist_ok=True)
    rutas.prompt_qa(n).write_text(prep.prompt, encoding="utf-8")
    return prep


def cerrar_qa(raiz: Path, config: HarnessConfig, n: int) -> ResultadoQA:
    """RF-07.4, RF-07.5: lee qa_cap_N.json y recursos_usados.json, registra métricas y pausa si hay contradicciones."""
    rutas = Rutas(raiz)
    reporte = repo.leer_reporte_qa(raiz, n)
    if reporte is None:
        raise EstadoInvalidoError(f"RF-07.2: QA no escribió {rutas.reporte_qa_json(n).as_posix()}")
    if reporte.cap_corte != n:
        raise EstadoInvalidoError(f"RF-07.2: el reporte dice cap_corte = {reporte.cap_corte} y el corte es {n}")
    if not rutas.reporte_qa_md(n).exists():
        raise EstadoInvalidoError(f"RF-07.2: QA no escribió {rutas.reporte_qa_md(n).as_posix()}")
    if not rutas.recursos_usados.exists():
        raise EstadoInvalidoError(f"RF-07.5: QA no escribió {rutas.recursos_usados.as_posix()}")
    repo.leer_recursos_usados(raiz)  # valida el esquema (EX-01)

    metricas = qa.metricas_corte(raiz, qa.capitulos_muestra(n, config.cadencia_qa), reporte, repo.leer_continuidad(raiz))
    import json as _json
    with rutas.metricas_qa.open("a", encoding="utf-8") as f:
        f.write(_json.dumps(metricas, ensure_ascii=False) + "\n")

    if reporte.tiene_contradicciones:
        checkpoint.pausar_por_qa(raiz, n)
        cur.borrar(raiz)
        return ResultadoQA(reporte=reporte, pausado=True, metricas=metricas)
    checkpoint.registrar_qa(raiz, n)
    return ResultadoQA(reporte=reporte, pausado=False, metricas=metricas)


# ---------- loop completo con agentes inyectados (§6, §9) ----------

def ejecutar_tanda(config: HarnessConfig, raiz: Path, agentes: Agentes, capitulos_por_tanda: int | None = None,
                   hasta_el_final: bool = False) -> ResultadoTanda:
    rutas = Rutas(raiz)
    cursor = iniciar_tanda(raiz, config, capitulos_por_tanda, hasta_el_final)
    while True:
        cursor = cur.exigir(raiz)
        decision = evaluar_siguiente(raiz, config, cursor)
        if decision.motivo != "seguir":
            cur.borrar(raiz)
            return decision
        n = decision.siguiente
        assert n is not None

        feedback: str | None = None
        while True:
            contexto = preparar_capitulo(raiz, config, n, feedback)  # RF-05.1, EX-03, EX-04
            borrador = escritor.generar_capitulo(contexto, invocar=agentes.generar_capitulo)  # RF-05.2
            cur.sumar_llamada(raiz)
            m = checkpoint.exigir_manifest(raiz)
            if n <= m.ultimo_capitulo_cerrado:
                raise CapituloCerradoError(f"INV-07: el capítulo {n} ya está cerrado")
            repo.guardar_capitulo(raiz, n, borrador, reemplazar_borrador=True)  # RF-05.4
            evaluacion = evaluar_borrador(raiz, config, n)  # EX-07
            if evaluacion.reintentar:
                feedback = evaluacion.mensaje
                continue
            feedback = None
            delta = extractor.extraer(rutas.capitulo(n).as_posix(), invocar=agentes.extraer)  # RF-06.1
            cur.sumar_llamada(raiz)
            resultado = aplicar_delta(raiz, config, n, delta)  # RF-06.2-06.4, EX-01, EX-08
            if resultado.regenerar:
                descartar_borrador(raiz, n)
                continue
            break

        if resultado.toca_qa:  # RF-07.1, antes de evaluar el tope (RF-CFG-02)
            prep = preparar_qa(raiz, config, n)
            reporte = qa.ejecutar_corte(prep, invocar=agentes.ejecutar_corte)
            cur.sumar_llamada(raiz)
            if not rutas.reporte_qa_json(n).exists():
                repo.guardar_reporte_qa(raiz, reporte, texto_md=_reporte_md(reporte))
            resultado_qa = cerrar_qa(raiz, config, n)
            if resultado_qa.pausado:
                cursor = cur.leer(raiz)
                return ResultadoTanda(cerrados=cursor.cerrados if cursor else decision.cerrados + 1, motivo="pausado_por_qa")


def _reporte_md(reporte: ReporteQA) -> str:
    lineas = [f"# Reporte de QA · corte en el capítulo {reporte.cap_corte}", "",
              f"tiene_contradicciones: {'true' if reporte.tiene_contradicciones else 'false'}", ""]
    for h in reporte.hallazgos:
        origen = f" (cap_origen {h.cap_origen})" if h.cap_origen is not None else ""
        lineas.append(f"- [{h.tipo}]{origen} {h.descripcion}")
    return "\n".join(lineas) + "\n"
