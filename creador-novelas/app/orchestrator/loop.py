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

from app import registro, validacion
from app.agents import escritor, extractor, qa
from app.agents.escritor import Contexto
from app.agents.qa import PreparacionQA
from app.config import VERSION_SPECS, HarnessConfig, hash_prompts
from app.errores import (
    AutovalidacionFallidaError, CapituloCerradoError, ContextoExcedidoError, ContratoRetornoError, EstadoInvalidoError,
    LongitudFueraDeRangoAviso, ManifiestoInconsistenteError, PersonajeNoPrevistoError,
)
from app.orchestrator import checkpoint, cursor as cur
from app.orchestrator.cursor import Cursor
from app.rutas import Rutas
from app.schemas import DeltaExtraccion, ReporteQA
from app.state import continuidad as cont
from app.state import personajes as pers
from app.state import recursos as rec
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
    cur.borrar(raiz, "huerfano: la tanda anterior murio a mitad y esta la recalcula desde el manifiesto")
    hashes = hash_prompts(raiz)
    carpeta = registro.iniciar_tanda(raiz, {  # §5.1: una carpeta por tanda; tanda.json lleva lo que la traza necesita (§16.2)
        "prompts_hash": hashes, "total_capitulos": config.total_capitulos, "capitulos_por_tanda": tope,
        "cadencia_qa": config.cadencia_qa, "palabras_por_capitulo": config.palabras_por_capitulo,
        "max_llamadas_por_tanda": config.max_llamadas_por_tanda, "version_specs": VERSION_SPECS,
        "inicio": m.ultimo_capitulo_cerrado + 1,
    })
    cursor = Cursor(inicio=m.ultimo_capitulo_cerrado + 1, tope=tope, max_llamadas=config.max_llamadas_por_tanda,
                    registro=carpeta.relative_to(raiz).as_posix())
    cur.escribir(raiz, cursor)
    checkpoint.actualizar_prompts_hash(raiz, hashes)
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
        cur.borrar(raiz, resultado.motivo)
    return resultado


def feedback_de_qa(raiz: Path, n: int) -> str:
    """Las contradicciones que el revisor encontró en el capítulo n, tal como se las damos al escritor.

    Solo las contradicciones. Las repeticiones ya las ataja el validador con su propia realimentación,
    y meterlas aquí distraería del único fallo que obliga a rehacer el capítulo.
    """
    ruta = Rutas(raiz).reporte_qa_json(n)
    if not ruta.is_file():
        raise EstadoInvalidoError(f"no existe {ruta.as_posix()}: no hay revisión de la que corregir")
    reporte = ReporteQA.model_validate_json(ruta.read_text(encoding="utf-8"))
    contradicciones = [h for h in reporte.hallazgos if h.tipo == "contradiccion"]
    if not contradicciones:
        raise EstadoInvalidoError(f"qa_cap_{n} no tiene contradicciones: no hay nada que corregir")
    lineas = [f"- {h.descripcion.strip()} (el hecho contradicho viene del capítulo {h.cap_origen})"
              for h in contradicciones]
    return chr(10).join(lineas)


def preparar_correccion(raiz: Path, config: HarnessConfig, n: int) -> Contexto:
    """Contexto para rehacer un capítulo que el revisor tumbó (RF-07.6, paso 2).

    El escritor no recibe el texto del capítulo --INV-01 vale también aquí-- y no le hace falta: lo
    reescribe desde el mismo estado con el que lo escribió la primera vez, más el hallazgo de QA.
    Es la misma mecánica con la que ya corrige un desvío de longitud, aplicada a la contradicción,
    que hasta ahora era el único fallo que nadie le contaba nunca.
    """
    m = checkpoint.exigir_manifest(raiz)
    if n not in (m.reextraccion_pendiente or []):
        raise EstadoInvalidoError(
            f"el capítulo {n} no está pendiente de corrección; pendientes: {m.reextraccion_pendiente}")
    contexto = escritor.ensamblar_contexto(n, config, raiz, feedback_qa=feedback_de_qa(raiz, n))
    if contexto.excede_limite():
        contexto = escritor.recortar_resumen_rodante(contexto)
    escritor.persistir_contexto(contexto, raiz)
    registro.guardar_prompt(raiz, "escritor", n, contexto.texto)
    registro.evento(raiz, "agente_inicio", rol="escritor", capitulo=n, agent_id=None,
                    intento=1, tokens=contexto.tokens_estimados, motivo="correccion_qa")
    return contexto


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
            registro.evento_error(raiz, error, capitulo=n)
            cur.borrar(raiz, "EX-04")
            raise error
    escritor.persistir_contexto(contexto, raiz)
    registro.guardar_prompt(raiz, "escritor", n, contexto.texto)  # §5.1: la copia del contexto exacto entregado
    registro.evento(raiz, "agente_inicio", rol="escritor", capitulo=n, agent_id=None,
                    intento=2 if feedback_longitud else 1, tokens=contexto.tokens_estimados)
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
    texto = extractor.preparar_prompt_extractor(n, config, raiz)
    rutas.prompt_extractor(n).write_text(texto, encoding="utf-8")
    registro.guardar_prompt(raiz, "extractor", n, texto)
    if config.escritor_emite_delta:
        # X-04: el prompt se deja preparado por si hay que caer al extractor, pero anunciar su
        # arranque dejaba un agente abierto que no cerraba nunca: el plano de la nave enseñaba
        # extractores fantasma y el resumen contaba invocaciones que no ocurrieron.
        return rutas.prompt_extractor(n)
    registro.evento(raiz, "agente_inicio", rol="extractor", capitulo=n, agent_id=None,
                    reextraccion=n in m.reextraccion_pendiente)
    return rutas.prompt_extractor(n)


def evaluar_borrador(raiz: Path, config: HarnessConfig, n: int) -> ResultadoEscritor:
    """EX-07 sobre el archivo en disco, con el mismo validador que corre el agente (RF-08.4): decide si toca el único reintento."""
    if not repo.existe_capitulo(raiz, n):
        raise ContratoRetornoError(f"RF-05.4: no existe 05_manuscrito/cap_{n}.md")
    v = validacion.validar_capitulo(raiz, config, n)
    palabras = v.datos["palabras"]
    ok, mensaje = escritor.evaluar_longitud(palabras, config)
    otros = [e for e in v.errores if e != mensaje]
    if otros:  # lo que no es longitud (encabezados, personajes en escena ausentes) no tiene reintento EX-07: es EX-01
        raise EstadoInvalidoError(f"el borrador del capítulo {n} no valida: " + "; ".join(otros))
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
    registro.guardar_retorno(raiz, "escritor", n, linea)
    try:
        retorno = escritor.parsear_retorno_escritor(linea)
    except AutovalidacionFallidaError as e:  # EX-10: el borrador va a descartados; el fallo se trata como EX-07/EX-08
        registro.descartar(raiz, "escritor", n, Rutas(raiz).capitulo(n), str(e))
        raise
    if retorno.n != n:
        raise ContratoRetornoError(f"RF-08.1: el escritor declaró cap_{retorno.n}.md y el capítulo en curso es {n}")
    resultado = evaluar_borrador(raiz, config, n)
    resultado.personajes_declarados = retorno.personajes
    return resultado


def _corte_qa_sin_cerrar(m, config: HarnessConfig) -> bool:
    """¿El último capítulo cerrado tocaba auditoría y el corte todavía no se cerró?

    Con el corte solapado (§6) el revisor y el escritor del capítulo siguiente trabajan a la vez;
    esto es lo que impide que el segundo se cierre antes que el primero.
    """
    ultimo = m.ultimo_capitulo_cerrado
    return bool(ultimo) and ultimo % config.cadencia_qa == 0 and m.ultimo_qa_ejecutado < ultimo


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
    if not reextraccion and _corte_qa_sin_cerrar(m, config):
        # El corte de QA se solapa con la escritura del capítulo siguiente para no pagar su tiempo
        # dos veces, pero cerrar ese capítulo antes que el corte movería `ultimo_capitulo_cerrado`,
        # y de ahí sale el capítulo con el que los hooks resuelven a QA (§13.3): su `validar-reporte`
        # dejaría de casar con H-11 a media auditoría. El corte se cierra primero.
        raise ManifiestoInconsistenteError(
            f"RF-07.4: queda sin cerrar el corte de QA del capítulo {m.ultimo_capitulo_cerrado}; "
            f"corré `cerrar-qa {m.ultimo_capitulo_cerrado}` antes de cerrar el capítulo {n}"
        )

    fichas = repo.leer_personajes(raiz)
    mundo = repo.leer_mundo(raiz)
    registro_sujetos = pers.sujetos_conocidos(fichas, mundo)
    try:
        if isinstance(delta, DeltaExtraccion):  # solo el loop con dobles pasa el objeto ya parseado
            validado = extractor.validar_delta(delta, registro_sujetos, config, n)
        else:  # RF-08.4: el mismo parseo y la misma validación que `validar-delta`; el harness vuelve a validar
            validado = validacion.cargar_delta_validado(raiz, config, n, delta)
    except EstadoInvalidoError as e:  # EX-01 / EX-10: el delta rechazado va a descartados con su error (§5.1)
        registro.descartar(raiz, "extractor", n, rutas.delta(n), str(e))
        raise

    cursor = cur.leer(raiz)
    if validado.claves_no_previstas:
        # EX-08: primer fallo regenera; segundo detiene.
        intentos = (cursor.intentos_personaje if cursor else 0) + 1
        if cursor is not None:
            cursor.intentos_personaje = intentos
            cur.escribir(raiz, cursor)
        checkpoint.registrar_intentos(raiz, n, 2)
        registro.descartar(raiz, "extractor", n, rutas.delta(n), f"EX-08: personajes fuera del registro {validado.claves_no_previstas}")
        if intentos >= 2:
            error = PersonajeNoPrevistoError(n, validado.claves_no_previstas)
            checkpoint.registrar_error(raiz, str(error))
            registro.evento_error(raiz, error, capitulo=n)
            cur.borrar(raiz, "EX-08")
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
    log = cont.agregar(repo.leer_continuidad(raiz), d.hechos_nuevos, n, registro_sujetos)
    resumen_actual = repo.leer_resumen_rodante(raiz)
    resumen = (rr.reemplazar(resumen_actual, n, d.resumen_corto) if reextraccion
               else rr.agregar(resumen_actual, n, d.resumen_corto))  # X-02.3: se guardan todos; la ventana recorta al entregar

    recursos = rec.acumular(repo.leer_recursos_narrativos(raiz), d.recursos_narrativos, n, reextraccion=reextraccion)

    repo.escribir_personajes(raiz, nuevas_fichas)  # RF-06.2
    repo.escribir_continuidad(raiz, log)  # RF-06.3
    repo.escribir_resumen_rodante(raiz, resumen)  # RF-06.4
    repo.escribir_recursos_narrativos(raiz, recursos)  # RF-05.5 / §17.2: la capa semántica de la antirrepetición

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
    """EX-08: elimina el borrador para regenerar. Nunca un capítulo cerrado (INV-07). La copia queda en descartados (§5.1)."""
    m = checkpoint.exigir_manifest(raiz)
    registro.descartar(raiz, "escritor", n, Rutas(raiz).capitulo(n), "descartar-borrador: el capítulo se regenera (EX-08 / EX-10)")
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
    registro.guardar_prompt(raiz, "qa", n, prep.prompt)
    registro.evento(raiz, "agente_inicio", rol="qa", capitulo=n, agent_id=None, muestra=prep.caps_muestra)
    return prep


def cerrar_qa(raiz: Path, config: HarnessConfig, n: int) -> ResultadoQA:
    """RF-07.4, RF-07.5: lee qa_cap_N.json y recursos_usados.json, registra métricas y pausa si hay contradicciones."""
    rutas = Rutas(raiz)
    reporte = validacion.exigir_reporte(raiz, n)  # RF-08.4: la misma comprobación que `validar-reporte`

    metricas = qa.metricas_corte(raiz, qa.capitulos_muestra(n, config.cadencia_qa), reporte, repo.leer_continuidad(raiz))
    import json as _json
    with rutas.metricas_qa.open("a", encoding="utf-8") as f:
        f.write(_json.dumps(metricas, ensure_ascii=False) + "\n")

    if reporte.tiene_contradicciones:
        checkpoint.pausar_por_qa(raiz, n)
        cur.borrar(raiz, "pausado_por_qa")
        return ResultadoQA(reporte=reporte, pausado=True, metricas=metricas)
    checkpoint.registrar_qa(raiz, n)
    return ResultadoQA(reporte=reporte, pausado=False, metricas=metricas)


# ---------- loop completo con agentes inyectados (§6, §9) ----------

def ejecutar_tanda(config: HarnessConfig, raiz: Path, agentes: Agentes, capitulos_por_tanda: int | None = None,
                   hasta_el_final: bool = False) -> ResultadoTanda:
    rutas = Rutas(raiz)
    cursor = iniciar_tanda(raiz, config, capitulos_por_tanda, hasta_el_final)

    def _fin_doble(rol: str, n: int, retorno: str) -> None:
        """Con dobles no hay SubagentStop: el loop deja el par agente_fin + retorno que dejaría H-10 (§5.1, §9)."""
        cur.sumar_llamada(raiz)
        registro.guardar_retorno(raiz, rol, n, retorno if len(retorno) < 4000 else retorno[:4000] + "\n[... doble: recortado]")
        registro.evento(raiz, "agente_fin", rol=rol, capitulo=n, agent_id=f"doble-{rol}-{n}", turnos=1, intentos_de_validacion=0)

    while True:
        cursor = cur.exigir(raiz)
        decision = evaluar_siguiente(raiz, config, cursor)
        if decision.motivo != "seguir":
            cur.borrar(raiz, decision.motivo)
            return decision
        n = decision.siguiente
        assert n is not None

        feedback: str | None = None
        while True:
            contexto = preparar_capitulo(raiz, config, n, feedback)  # RF-05.1, EX-03, EX-04
            borrador = escritor.generar_capitulo(contexto, invocar=agentes.generar_capitulo)  # RF-05.2
            m = checkpoint.exigir_manifest(raiz)
            if n <= m.ultimo_capitulo_cerrado:
                raise CapituloCerradoError(f"INV-07: el capítulo {n} ya está cerrado")
            repo.guardar_capitulo(raiz, n, borrador, reemplazar_borrador=True)  # RF-05.4
            _fin_doble("escritor", n, f"cap_{n}.md · {escritor.contar_palabras(borrador)} palabras · personajes: (doble) · validado")
            evaluacion = evaluar_borrador(raiz, config, n)  # EX-07
            if evaluacion.reintentar:
                feedback = evaluacion.mensaje
                continue
            feedback = None
            texto_delta = agentes.extraer(rutas.capitulo(n).as_posix())  # RF-06.1 (INV-02: un solo capítulo)
            rutas.deltas_trabajo.mkdir(parents=True, exist_ok=True)
            rutas.delta(n).write_text(texto_delta, encoding="utf-8")  # el extractor real lo escribe él (RF-08.4)
            _fin_doble("extractor", n, f"delta_cap_{n}.json · (doble) · validado")
            resultado = aplicar_delta(raiz, config, n)  # RF-06.2-06.4, EX-01, EX-08: lee y revalida el archivo
            if resultado.regenerar:
                descartar_borrador(raiz, n)
                continue
            break

        if resultado.toca_qa:  # RF-07.1, antes de evaluar el tope (RF-CFG-02)
            prep = preparar_qa(raiz, config, n)
            reporte = qa.ejecutar_corte(prep, invocar=agentes.ejecutar_corte)
            _fin_doble("qa", n, f"tiene_contradicciones: {str(reporte.tiene_contradicciones).lower()}\nvalidado")
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
