"""El orquestador: que fase toca, que paquete se monta y que puerta se aplica.

El orquestador **no es un agente, es codigo**. Decide, ensambla y verifica; quien escribe,
extrae y juzga es Claude Code a traves del puerto.

## Por que las llamadas al agente caen FUERA de la transaccion

La spec pedia una sola transaccion por capitulo con las llamadas dentro. No se puede: una
transaccion de escritura en SQLite retiene el cerrojo, un capitulo tarda minutos, y la API
necesita escribir para insertar una intencion. El efecto seria que pulsar «parar» en mitad de
un capitulo devolveria «database is locked», justo cuando mas falta hace.

Asi que el capitulo se ejecuta en tres tramos, con las llamadas al agente entre transacciones
y no dentro:

1. **Sin transaccion** — se llama al redactor y al extractor y se guarda lo que devuelven en
   memoria. Nada toca la base todavia.
2. **Transaccion corta** — entran el texto y los hechos JUNTOS y se ejecuta la puerta 3, que
   es SQL y tarda milisegundos. Si hay conflicto, revierte entera y no queda nada.
3. **Sin transaccion, y luego otra corta** — se juzga el oficio y, si pasa, una segunda
   transaccion marca el capitulo completado y lo compila.

Lo que la regla original protegia se conserva: **texto y hechos entran juntos o no entra
ninguno**, que es lo que impide que exista un capitulo escrito cuyos hechos no se capturaron.
Lo que cambia es que entre el tramo 2 y el 3 puede quedar un capitulo con su texto y sus
hechos pero sin marcar como completado. Es el unico estado intermedio legitimo, y solo
mientras la ejecucion esta activa (RF2-PER-07). Si el capitulo sale del bucle por cualquier
otro camino que no sea cerrarse, `generar_capitulo` lo revierte antes de propagar; y si el
worker muere ahi, sin ocasion de revertir, la recuperacion lo hace al arrancar
(RF2-FALLO-06).
"""

from __future__ import annotations

import json
import logging
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import partial
from typing import Any

from pydantic import BaseModel, ValidationError

from compartido import politica
from compartido.cambio import Cambio
from compartido.contexto import Paquete, Presupuesto, PresupuestoExcedido
from compartido.db import simulacion, transaccion
from compartido.grafo import emitir_evento, lectura, normalizar
from compartido.puerta_base import ResultadoPuerta
from compartido.puerto import AgenteInterrumpido, PuertoAgente
from compartido.tipos import como_dict, como_lista
from compartido.vectores import purgar_descartes
from config import (
    MAX_INTENTOS_CAPITULO,
    OFICIO_MUESTRAS,
    OFICIO_MUESTRAS_SI_DISCREPAN,
    Config,
)
from tareas.arquitecto import servicio as s_arquitecto
from tareas.arquitecto.esquemas import SalidaArquitecto
from tareas.continuidad import puerta as p_continuidad
from tareas.continuidad import servicio as s_continuidad
from tareas.continuidad.esquemas import SalidaContinuidad
from tareas.elenco import servicio as s_elenco
from tareas.elenco.esquemas import SalidaElenco
from tareas.escaleta import puerta as p_escaleta
from tareas.escaleta import servicio as s_escaleta
from tareas.escaleta.esquemas import SalidaEscaleta
from tareas.estructura import puerta as p_estructura
from tareas.estructura import servicio as s_estructura
from tareas.estructura.esquemas import SalidaEstructura
from tareas.extraccion import servicio as s_extraccion
from tareas.extraccion.esquemas import (
    PALABRAS_RESUMEN,
    PALABRAS_RESUMEN_BREVE,
    SalidaExtraccion,
)
from tareas.interprete import servicio as s_interprete
from tareas.interprete.esquemas import SalidaInterprete
from tareas.mundo import servicio as s_mundo
from tareas.mundo.esquemas import SalidaMundo
from tareas.oficio import puerta as p_oficio
from tareas.oficio import servicio as s_oficio
from tareas.oficio.esquemas import SalidaOficio
from tareas.redaccion import servicio as s_redaccion
from tareas.redaccion.esquemas import SalidaRedaccion
from tareas.revision import puerta as p_revision
from tareas.revision import servicio as s_revision
from tareas.revision.esquemas import SalidaRevision

from . import cambios as o_cambios
from . import cola, estados, fallo, versiones, vigencia
from .puerta_global import evaluar as evaluar_puerta_global
from .seudonimo import Mascara

log = logging.getLogger("orquestador")


class Detenido(Exception):
    """Llego una intencion de parar. No es un error: es el autor tomando el control."""


class Parado(Exception):
    """Se abrio una parada y el pipeline espera a un humano."""

    def __init__(self, parada_id: int, tipo: str) -> None:
        super().__init__(f"Parada {tipo} ({parada_id})")
        self.parada_id = parada_id
        self.tipo = tipo


class PuertasNoVigentes(Exception):
    """Se intento generar un capitulo sin las puertas 1 y 2 vigentes (RF2-PIPE-00b).

    No es una parada: si llega aqui, el orquestador ha derivado mal lo que tocaba, y eso es un
    error del sistema que acaba en `error`, nunca en un capitulo.
    """


@dataclass
class Contexto:
    con: sqlite3.Connection
    puerto: PuertoAgente
    cfg: Config
    novela_id: int
    indice: Any | None = None
    #: Lo llama cada punto de comprobacion. El worker lo usa para abortar si perdio el
    #: cerrojo (RF2-WK-07) o si recibio una senal de terminar.
    vigilar: Callable[[], None] | None = None
    #: Criterios de oficio incumplidos, que vuelven al redactor en el reintento.
    eventos_criterios: list[dict[str, Any]] = field(default_factory=list[dict[str, Any]])
    #: Exportador a Langfuse (spec3, RF3-OBS-08), o None si no hay claves.
    exportador: Any | None = None

    @property
    def cfg_max_intentos(self) -> int:
        return MAX_INTENTOS_CAPITULO

    @property
    def presupuesto(self) -> Presupuesto:
        """El presupuesto de contexto, siempre desde la configuracion (RF2-CTX-12)."""
        return Presupuesto(
            bloques=self.cfg.presupuesto_bloques, techo=self.cfg.presupuesto_paquete
        )


# --- Invocacion con validacion ---------------------------------------------------------------


def _invocar[T: BaseModel](
    ctx: Contexto,
    agente: str,
    paquete: Any,
    modelo: type[T],
    *,
    capitulo: int | None = None,
    intento: int | None = None,
    mascara: Mascara | None = None,
) -> tuple[T, Any]:
    """Invoca al agente y valida su salida contra el modelo de su tarea.

    El puerto ya reintenta una vez si la respuesta no cumple el esquema JSON. Aqui se
    reintenta una vez mas si falla una regla que el esquema no puede expresar —«exactamente un
    protagonista», «ninguna escena repite valor»— porque esas solo las ve Pydantic.
    """
    _comprobar_parada(ctx)
    recortes = getattr(paquete, "recortes", None)
    if recortes:
        # Ningun recorte es silencioso, aunque el paquete quepa (RF2-CTX-03).
        emitir_traza(ctx, "paquete_recortado", agente=agente, capitulo=capitulo,
                     intento=intento, bloques=recortes)
    emitir_traza(ctx, "agente_iniciado", agente=agente, capitulo=capitulo, intento=intento)

    entrada = paquete.render() if hasattr(paquete, "render") else str(paquete)
    por_bloque = paquete.tokens_por_bloque if hasattr(paquete, "tokens_por_bloque") else None
    # Los nombres del encargo no salen de la maquina (spec3, RF3-SEU-01): el agente ve
    # etiquetas, y su respuesta vuelve con los nombres antes de validarla.
    # La correccion del lector trae la suya, hecha dentro de la simulacion con el brief ya
    # cambiado (validador de cd8ab12): aqui el brief leido seria el de antes del cambio.
    mascara = mascara or Mascara(lectura.brief(ctx.con, ctx.novela_id))
    entrada = mascara.ocultar(entrada)
    if not mascara.vacia:
        entrada = f"{mascara.leyenda()}\n\n{entrada}"

    ultimo: ValidationError | None = None
    for vuelta in (1, 2):
        resultado = ctx.puerto.invocar(
            agente, entrada, modelo.model_json_schema(),
            timeout_s=ctx.cfg.timeout_agente_segundos, novela_id=ctx.novela_id,
            capitulo=capitulo, intento=intento, tokens_por_bloque=por_bloque,
        )
        try:
            validado = modelo.model_validate(mascara.restaurar(resultado.salida))
        except ValidationError as exc:
            ultimo = exc
            if vuelta == 2:
                break
            # El error cita la respuesta ya restaurada: vuelve a salir con etiquetas.
            entrada = (
                f"{entrada}\n\n## ERROR DEL INTENTO ANTERIOR\n\n"
                f"Tu respuesta no cumplia estas reglas. Corrigelas:\n{mascara.ocultar(str(exc))}"
            )
            continue

        emitir_traza(
            ctx, "agente_terminado", agente=agente, capitulo=capitulo,
            tokens_salida=resultado.tokens_salida, coste=resultado.coste_usd,
            compactacion=resultado.hubo_compactacion,
        )
        return validado, resultado

    raise ValueError(f"El agente '{agente}' no produjo una salida valida: {ultimo}")


def _trazar_resumenes_recortados(
    ctx: Contexto, capitulo: int, intento: int, cruda: dict[str, Any]
) -> None:
    """El validador recorta los resumenes largos; aqui queda que lo hizo (RF2-PIPE-20)."""
    campos = {
        campo: len(str(cruda.get(campo, "")).split())
        for campo, limite in (("resumen", PALABRAS_RESUMEN),
                              ("resumen_breve", PALABRAS_RESUMEN_BREVE))
        if len(str(cruda.get(campo, "")).split()) > limite
    }
    if campos:
        emitir_traza(ctx, "resumen_recortado", capitulo=capitulo, intento=intento,
                     palabras=campos)


def emitir_traza(ctx: Contexto, tipo: str, **payload: Any) -> None:
    with transaccion(ctx.con):
        emitir_evento(ctx.con, ctx.novela_id, tipo, **payload)


def _comprobar_parada(ctx: Contexto) -> None:
    if ctx.vigilar is not None:
        ctx.vigilar()
    if cola.hay_parada_pendiente(ctx.con, ctx.novela_id):
        raise Detenido()


def _registrar_puerta(ctx: Contexto, resultado: Any, capitulo: int | None = None,
                      intento: int | None = None) -> None:
    with transaccion(ctx.con):
        _registrar_puerta_en(ctx, resultado, capitulo=capitulo, intento=intento)


def _registrar_puerta_en(ctx: Contexto, resultado: Any, capitulo: int | None = None,
                         intento: int | None = None) -> None:
    """`_registrar_puerta` dentro de la transaccion del llamante."""
    resultado.registrar(
        ctx.con, ctx.novela_id, capitulo=capitulo, intento=intento,
        huella=vigencia.huella(ctx.con, ctx.novela_id, resultado.puerta),
    )
    emitir_evento(
        ctx.con, ctx.novela_id, "puerta_evaluada", puerta=resultado.puerta,
        veredicto=resultado.veredicto, capitulo=capitulo,
        conflictos=[str(c) for c in resultado.conflictos[:10]],
    )


def _abrir_parada(ctx: Contexto, tipo: str, informe: dict[str, Any],
                  capitulo: int | None = None, intento: int | None = None,
                  *, antes: Callable[[], object] | None = None,
                  despues: Callable[[int], None] | None = None) -> None:
    """Abre la parada y lleva la ejecucion a `parada`, en una transaccion.

    `antes` corre dentro de esa misma transaccion: es lo que permite borrar la escaleta
    rechazada y abrir la parada de forma atomica (RF2-FALLO-03). `despues` corre con la parada
    ya abierta y recibe su id: lo que haga no puede impedir que exista (spec3, RF3-JUE-01).
    """
    with transaccion(ctx.con):
        if antes is not None:
            antes()
        parada_id = fallo.abrir_parada(
            ctx.con, ctx.novela_id, tipo, informe, capitulo=capitulo, intento=intento
        )
        estados.transicion(
            ctx.con, ctx.novela_id, "conflicto", fase=None, capitulo=capitulo,
            parada_id=parada_id,
        )
    if despues is not None:
        despues(parada_id)
    raise Parado(parada_id, tipo)


# --- Planificacion ----------------------------------------------------------------------------

_PLANIFICACION = (
    ("arquitecto", s_arquitecto, SalidaArquitecto),
    ("mundo", s_mundo, SalidaMundo),
    ("elenco", s_elenco, SalidaElenco),
    ("estructura", s_estructura, SalidaEstructura),
)


def planificar(ctx: Contexto) -> None:
    """Arquitecto, mundo, elenco y estructurador, una vez y en ese orden. Puerta 1 al final.

    Deja el estado en su sitio por su cuenta: cada fase es autosuficiente, para que se pueda
    invocar tanto desde `avanzar` como sola.
    """
    _asegurar_activa(ctx, "arrancar_planificacion")
    for agente, servicio, modelo in _PLANIFICACION:
        if _fase_ya_hecha(ctx, agente):
            continue
        with transaccion(ctx.con):
            estados.fijar_fase(ctx.con, ctx.novela_id, agente)
        texto = servicio.paquete(ctx.con, ctx.novela_id)
        rechazo = vigencia.informe_de_rechazo(ctx.con, ctx.novela_id, 1)
        if rechazo:
            # Quien vuelve a correr tras un rechazo de la puerta 1 lo recibe: el estructurador
            # siempre, y el arquitecto o el elenco cuando lo rechazado era suyo (spec3, RF3-PER-04).
            titulo = (
                "LA ESTRUCTURA ANTERIOR NO PASO LA PUERTA 1, POR ESTO" if agente == "estructura"
                else "LA PLANIFICACION ANTERIOR NO PASO LA PUERTA 1, POR ESTO"
            )
            texto += f"\n\n## {titulo}\n\n" + "\n".join(rechazo)
        salida, _ = _invocar(ctx, agente, texto, modelo)
        # Una transaccion por agente: su parte del canon entra entera o no entra.
        with transaccion(ctx.con):
            servicio.aplicar(ctx.con, ctx.novela_id, salida)
            emitir_evento(ctx.con, ctx.novela_id, "fase_cambiada", fase=agente, hecho=True)

    with transaccion(ctx.con):
        estados.fijar_fase(ctx.con, ctx.novela_id, "puerta_1")
    resultado = p_estructura.evaluar(ctx.con, ctx.novela_id)
    _registrar_puerta(ctx, resultado)
    if not resultado.pasa:
        _abrir_parada(ctx, "estructura", resultado.informe())

    with transaccion(ctx.con):
        estados.transicion(ctx.con, ctx.novela_id, "puerta_1_ok", fase="escaleta")


def _fase_ya_hecha(ctx: Contexto, agente: str) -> bool:
    """Permite reanudar la planificacion sin repetir lo que ya se escribio."""
    consultas = {
        "arquitecto": "SELECT 1 FROM estilo_narrativo WHERE novela_id = ?",
        "mundo": "SELECT 1 FROM mundo WHERE novela_id = ?",
        "elenco": "SELECT 1 FROM personaje WHERE novela_id = ?",
        "estructura": "SELECT 1 FROM acto WHERE novela_id = ?",
    }
    return ctx.con.execute(consultas[agente], (ctx.novela_id,)).fetchone() is not None


# --- Escaleta ---------------------------------------------------------------------------------


def escaletar(ctx: Contexto) -> None:
    """Escaleta y puerta 2. Un fallo de puerta 2 se reintenta una vez con el informe.

    La escaleta rechazada se borra siempre antes de seguir, tambien la segunda vez: se borra
    en la misma transaccion que abre la parada, y el informe la lleva resumida para que el
    autor pueda leer que se rechazo (RF2-FALLO-03).
    """
    _asegurar_activa(ctx, "arrancar_escaleta")
    for intento in (1, 2):
        if lectura.total_capitulos(ctx.con, ctx.novela_id) == 0:
            with transaccion(ctx.con):
                estados.fijar_fase(ctx.con, ctx.novela_id, "escaleta", intento=intento)
            texto = s_escaleta.paquete(ctx.con, ctx.novela_id)
            rechazo = vigencia.informe_de_rechazo(ctx.con, ctx.novela_id, 2)
            if rechazo:
                texto += "\n\n## LA ESCALETA ANTERIOR FALLO POR ESTO\n\n" + "\n".join(rechazo)
            salida, _ = _invocar(ctx, "escaleta", texto, SalidaEscaleta, intento=intento)
            with transaccion(ctx.con):
                s_escaleta.aplicar(ctx.con, ctx.novela_id, salida)
                emitir_evento(ctx.con, ctx.novela_id, "fase_cambiada", fase="escaleta",
                              hecho=True)

        with transaccion(ctx.con):
            estados.fijar_fase(ctx.con, ctx.novela_id, "puerta_2", intento=intento)
        resultado = p_escaleta.evaluar(ctx.con, ctx.novela_id)
        _registrar_puerta(ctx, resultado, intento=intento)
        if resultado.pasa:
            with transaccion(ctx.con):
                estados.transicion(
                    ctx.con, ctx.novela_id, "puerta_2_ok", fase="paquete", capitulo=1, intento=1
                )
            return

        if intento == 2:
            informe = resultado.informe()
            informe["escaleta_rechazada"] = _resumen_escaleta(ctx)
            _abrir_parada(ctx, "escaleta", informe, intento=intento,
                          antes=lambda: _borrar_escaleta(ctx))
        # Se borra la escaleta fallida para que el segundo intento la rehaga entera.
        with transaccion(ctx.con):
            _borrar_escaleta(ctx)


def _borrar_escaleta(ctx: Contexto) -> None:
    """Capitulos y secuencias; escenas, beats, secuelas y reparto caen en cascada."""
    fallo.borrar_escaleta(ctx.con, ctx.novela_id)


def _resumen_escaleta(ctx: Contexto) -> list[dict[str, Any]]:
    """La escaleta rechazada, legible sin abrir la base de datos (RF-FALLO-02)."""
    capitulos: list[dict[str, Any]] = []
    for f in ctx.con.execute(
        "SELECT numero, objetivo FROM capitulo WHERE novela_id = ? ORDER BY numero",
        (ctx.novela_id,),
    ).fetchall():
        escenas = [
            {
                "orden": e["orden"], "pov": e["pov_nombre"], "lugar": e["lugar_nombre"],
                "objetivo": e["objetivo"], "conflicto": e["conflicto"],
                "valor": f"{e['valor_inicial']} -> {e['valor_final']}",
                "longitud_prevista": e["longitud_prevista"],
            }
            for e in lectura.escenas_del_capitulo(ctx.con, ctx.novela_id, int(f["numero"]))
        ]
        capitulos.append({"numero": f["numero"], "objetivo": f["objetivo"], "escenas": escenas})
    return capitulos


# --- Bucle de capitulo -------------------------------------------------------------------------


def generar_capitulo(ctx: Contexto, numero: int) -> None:
    """Paquete, redaccion, extraccion, puerta 3 y puerta 4 para un capitulo (RF2-PIPE-08).

    Toda salida que no sea «capitulo cerrado» ni «parada de continuidad» revierte el
    capitulo antes de propagarse: un `parar` durante el oficio, un agente interrumpido, una
    salida invalida o cualquier excepcion. Sin eso, el texto y los hechos del tramo 2 se
    quedarian en el grafo de un capitulo que nadie termino.
    """
    # Guardarrail (RF2-PIPE-00b): la misma propiedad que `avanzar` garantiza por
    # construccion, comprobada aqui en ejecucion.
    faltan = [p for p in (1, 2) if not vigencia.puerta_vigente(ctx.con, ctx.novela_id, p)]
    if faltan:
        raise PuertasNoVigentes(
            f"El capitulo {numero} no puede generarse: la puerta "
            f"{' y la '.join(str(p) for p in faltan)} no esta vigente."
        )
    _asegurar_activa(ctx, "arrancar_generacion")
    # Verdadero desde que el tramo 2 confirma hasta que el capitulo se cierra o se revierte.
    a_medias = False
    try:
        for intento in range(1, ctx.cfg_max_intentos + 1):
            with transaccion(ctx.con):
                estados.fijar_fase(ctx.con, ctx.novela_id, "paquete", capitulo=numero,
                                   intento=intento)

            criterios = ctx.eventos_criterios if intento > 1 else None
            recuperado = _recuperar(ctx, numero)

            paquete_redaccion = _paquete_o_parada(
                ctx, numero, intento, s_redaccion.paquete,
                ctx.con, ctx.novela_id, numero, presupuesto=ctx.presupuesto,
                criterios_incumplidos=criterios, recuperado=recuperado,
            )

            # --- Tramo 1: llamadas al agente, sin transaccion ----------------------------
            with transaccion(ctx.con):
                estados.fijar_fase(ctx.con, ctx.novela_id, "redaccion", capitulo=numero,
                                   intento=intento)
            prosa, resultado_redaccion = _invocar(
                ctx, "redaccion", paquete_redaccion, SalidaRedaccion,
                capitulo=numero, intento=intento,
            )
            textos = {e.orden: e.texto for e in prosa.escenas}

            with transaccion(ctx.con):
                estados.fijar_fase(ctx.con, ctx.novela_id, "extraccion", capitulo=numero,
                                   intento=intento)
            paquete_extraccion = _paquete_o_parada(
                ctx, numero, intento, s_extraccion.paquete,
                ctx.con, ctx.novela_id, numero, textos, presupuesto=ctx.presupuesto,
            )
            hechos, resultado_extraccion = _invocar(
                ctx, "extraccion", paquete_extraccion, SalidaExtraccion,
                capitulo=numero, intento=intento,
            )
            _trazar_resumenes_recortados(ctx, numero, intento, resultado_extraccion.salida)

            # --- Tramo 2: texto y hechos entran juntos, y la puerta 3 decide -------------
            descartes: s_extraccion.Descartes | None = None
            try:
                with transaccion(ctx.con):
                    estados.fijar_fase(ctx.con, ctx.novela_id, "puerta_3", capitulo=numero,
                                       intento=intento)
                    por_orden = s_redaccion.aplicar(
                        ctx.con, ctx.novela_id, numero, prosa, intento=intento,
                        llamada_id=resultado_redaccion.llamada_id,
                    )
                    descartes = s_extraccion.aplicar(
                        ctx.con, ctx.novela_id, numero, hechos, por_orden, textos
                    )
                    continuidad = p_continuidad.evaluar(
                        ctx.con, ctx.novela_id, numero, textos=textos,
                        usos_descartados=descartes.usos,
                    )
                    if not continuidad.pasa:
                        raise _Rechazado(continuidad)
            except _Rechazado as rechazo:
                # La transaccion ya se revirtio entera: no hay nada a medias.
                _trazar_descartes(ctx, numero, intento, descartes)
                _registrar_puerta(ctx, rechazo.resultado, capitulo=numero, intento=intento)
                informe = rechazo.resultado.informe()
                informe["prosa_rechazada"] = textos
                informe["segunda_opinion"] = None
                _abrir_parada(
                    ctx, "continuidad", informe, capitulo=numero, intento=intento,
                    despues=partial(_segunda_opinion, ctx, numero, intento,
                                    rechazo.resultado, textos),
                )
                return

            a_medias = True
            _trazar_descartes(ctx, numero, intento, descartes)
            _registrar_puerta(ctx, continuidad, capitulo=numero, intento=intento)

            # --- Tramo 3: oficio, y si pasa, cierre del capitulo -------------------------
            texto_completo = "\n\n".join(textos[k] for k in sorted(textos))
            mecanica = p_oficio.evaluar(ctx.con, ctx.novela_id, numero, texto_completo)

            # El juez corre aunque la mecanica falle (spec3, RF3-PAS-14): si no, el redactor
            # descubre los fallos de uno en uno y el ultimo intento se gasta en el primero que
            # el juez ve (capitulo 3 de la novela de tres capitulos).
            with transaccion(ctx.con):
                estados.fijar_fase(ctx.con, ctx.novela_id, "puerta_4", capitulo=numero,
                                   intento=intento)
            try:
                paquete_oficio = _paquete_o_parada(
                    ctx, numero, intento, s_oficio.paquete,
                    ctx.con, ctx.novela_id, numero, texto_completo, mecanica,
                    presupuesto=ctx.presupuesto, revertir=True,
                )
            except Parado:
                a_medias = False  # la parada ya revirtio el capitulo en su transaccion
                raise
            juicio, votos = _juzgar(ctx, paquete_oficio, numero, intento)

            # La puerta 4 se registra entera, mecanica y juicio (RF2-PIPE-13).
            oficio = p_oficio.combinar(mecanica, juicio, votos)
            pasa_oficio = oficio.pasa
            _registrar_puerta(ctx, oficio, capitulo=numero, intento=intento)

            if pasa_oficio:
                with transaccion(ctx.con):
                    _cerrar_capitulo(ctx, numero)
                a_medias = False
                _indexar(ctx, numero)
                return

            # Falla el oficio: se descarta lo escrito y se vuelve a redaccion con TODO lo que
            # fallo, la mecanica y el juez juntos (RF3-PAS-14).
            ctx.eventos_criterios = [
                {"criterio": c.comprobacion, "sugerencia": c.descripcion,
                 "evidencia": "", "principio": "38"} for c in mecanica.bloqueantes
            ] + [v.model_dump() for v in juicio.incumplidos]
            ultimo = intento == ctx.cfg_max_intentos
            with transaccion(ctx.con):
                fallo.revertir_grafo(ctx.con, ctx.novela_id, numero, motivo="oficio")
                if not ultimo:
                    _registrar_politica(ctx, mecanica, numero, intento, texto_completo,
                                        "reintentar")
            a_medias = False

            if ultimo:
                informe: dict[str, Any] = {
                    "motivo": (
                        f"Tres intentos sin pasar la puerta de oficio en el capitulo {numero}. "
                        "Si el capitulo no se puede escribir bien, el problema probablemente "
                        "esta en la escaleta y no en la prosa."
                    ),
                    "mecanica": mecanica.informe(),
                    "criterios_incumplidos": ctx.eventos_criterios,
                }
                _abrir_parada(
                    ctx, "oficio", informe, capitulo=numero, intento=intento,
                    antes=partial(_registrar_politica, ctx, mecanica, numero, intento,
                                  texto_completo, "parar"),
                )
                return
    finally:
        if a_medias:
            _revertir_a_medias(ctx, numero)


def _juzgar(
    ctx: Contexto, paquete_oficio: Any, numero: int, intento: int,
    mascara: Mascara | None = None,
) -> tuple[SalidaOficio, dict[str, tuple[int, int]]]:
    """El juez vota (spec3, RF3-JUE-02): con una muestra, el veredicto de un capitulo cambiaba
    de una llamada a otra. Tres muestras, y dos mas si discrepan."""
    juicios = [
        _invocar(ctx, "oficio", paquete_oficio, SalidaOficio, capitulo=numero,
                 intento=intento, mascara=mascara)[0]
        for _ in range(OFICIO_MUESTRAS)
    ]
    if p_oficio.discrepan(juicios):
        juicios += [
            _invocar(ctx, "oficio", paquete_oficio, SalidaOficio, capitulo=numero,
                     intento=intento, mascara=mascara)[0]
            for _ in range(OFICIO_MUESTRAS_SI_DISCREPAN - len(juicios))
        ]
    return p_oficio.votar(juicios)


def _segunda_opinion(
    ctx: Contexto, numero: int, intento: int, resultado: Any, textos: dict[int, str],
    parada_id: int,
) -> None:
    """El revisor de continuidad explica la parada ya abierta y opina si cada conflicto parece
    real (spec3, RF3-JUE-01), y la opinion se anade a su informe. Nunca la levanta ni impide que
    exista: la parada se abre antes de llamarlo, y cualquier fallo de la llamada, tambien una
    detencion pedida por el autor o una senal de terminar, solo deja la opinion vacia y el evento
    en la traza (validador de 9cc7972: con la llamada antes de abrirla, esos casos la perdian)."""
    try:
        paquete = s_continuidad.paquete(ctx.con, ctx.novela_id, numero, resultado, textos,
                                        presupuesto=ctx.presupuesto)
        salida, _ = _invocar(ctx, "continuidad", paquete, SalidaContinuidad,
                             capitulo=numero, intento=intento)
    except Exception as exc:
        emitir_traza(ctx, "segunda_opinion_fallida", capitulo=numero, intento=intento,
                     error=f"{type(exc).__name__}: {exc}"[:500])
        return
    with transaccion(ctx.con):
        fallo.anotar_informe(ctx.con, parada_id, "segunda_opinion", salida.model_dump())


def _registrar_politica(
    ctx: Contexto, mecanica: Any, numero: int, intento: int, texto: str, accion: str
) -> None:
    """Cada termino vetado que encontro la puerta 4, con lo que se hizo (spec3, RF3-GRD-04).

    Corre dentro de la transaccion que revierte el capitulo o abre la parada: si el worker cae
    antes, no queda escrita una accion que no ocurrio (validador de 66542ef)."""
    for c in mecanica.conflictos:
        if c.comprobacion == "termino_vetado":
            politica.registrar(ctx.con, ctx.novela_id, numero, intento, texto,
                               c.datos["hallazgos"], c.datos["politica"], accion=accion)


def _trazar_descartes(
    ctx: Contexto, numero: int, intento: int, descartes: Any
) -> None:
    """Lo que el extractor dijo y no se pudo registrar, a la traza (RF2-PIPE-16)."""
    if descartes is not None and (descartes.total or descartes.correcciones):
        emitir_traza(ctx, "extraccion_descartes", capitulo=numero, intento=intento,
                     recuento=descartes.recuento, usos=descartes.usos,
                     correcciones=descartes.correcciones)


def _paquete_o_parada(
    ctx: Contexto, numero: int, intento: int, fabricar: Callable[..., Paquete],
    *args: Any, revertir: bool = False, **kwargs: Any,
) -> Paquete:
    """Monta un paquete o, si lo obligatorio no cabe, abre una parada de presupuesto.

    Vale para los tres paquetes del capitulo (RF2-CTX-03). Despues del tramo 2 (`revertir`),
    la parada revierte el capitulo a medias en SU MISMA transaccion. Antes se revertia despues,
    en otra, desde el `finally` de `generar_capitulo`: si el worker caia entre las dos, quedaba
    una parada con un capitulo a medias que la recuperacion no tocaba (TLC, `CodigoActual.cfg`).
    """
    try:
        return fabricar(*args, **kwargs)
    except PresupuestoExcedido as exc:
        antes = partial(fallo.revertir_grafo, ctx.con, ctx.novela_id, numero,
                        motivo="presupuesto") if revertir else None
        _abrir_parada(ctx, "presupuesto", exc.informe(), capitulo=numero, intento=intento,
                      antes=antes)
        raise  # inalcanzable: _abrir_parada lanza Parado


def _revertir_a_medias(ctx: Contexto, numero: int) -> None:
    """Deshace el tramo 2 de un capitulo que sale del bucle sin cerrarse.

    Corre en su propia transaccion y no lanza: si la reversion falla, lo que tiene que
    llegar al llamante es la excepcion original, no la de la limpieza. La recuperacion del
    worker volvera a intentarlo al arrancar (RF2-FALLO-06).
    """
    try:
        with transaccion(ctx.con):
            fallo.revertir_grafo(ctx.con, ctx.novela_id, numero, motivo="salida_anomala")
    except Exception:  # no debe tapar la excepcion que nos trajo aqui
        log.exception("No se pudo revertir el capitulo %s a medias", numero)


class _Rechazado(Exception):
    """La puerta 3 encontro conflicto: revierte la transaccion del capitulo."""

    def __init__(self, resultado: Any) -> None:
        super().__init__("conflicto de continuidad")
        self.resultado = resultado


def _cerrar_capitulo(ctx: Contexto, numero: int) -> None:
    """Marca el capitulo completado, lo compila y avanza el contador (RF-PIPE-14)."""
    s_redaccion.compilar(ctx.con, ctx.novela_id, numero)
    ctx.con.execute(
        "UPDATE capitulo SET estado = 'completado' WHERE novela_id = ? AND numero = ?",
        (ctx.novela_id, numero),
    )
    completados = lectura.ultimo_capitulo_completado(ctx.con, ctx.novela_id)
    ctx.con.execute(
        """
        UPDATE ejecucion SET capitulos_completados = ?, capitulo_actual = ?, intento_actual = 1,
               actualizado_en = datetime('now')
         WHERE novela_id = ?
        """,
        (completados, numero + 1, ctx.novela_id),
    )
    emitir_evento(ctx.con, ctx.novela_id, "capitulo_completado", capitulo=numero)


def _indice_util(ctx: Contexto, operacion: str, capitulo: int) -> bool:
    """Si el indice se puede usar. Si no, por un fallo y no por configuracion, avisa."""
    if ctx.indice is None:
        return False
    if getattr(ctx.indice, "disponible", False):
        return True
    fallo = getattr(ctx.indice, "fallo", None)
    if fallo:
        emitir_traza(ctx, "indice_fallo", operacion=operacion, capitulo=capitulo, error=fallo)
    return False


def _recuperar(ctx: Contexto, numero: int) -> list[Any]:
    """Bloque recuperado del paquete (RF2-CTX-07). Sin indice, lista vacia y a seguir.

    Prescindible no es silencioso: todo fallo del indice queda en la traza (RF2-CTX-09).
    """
    if numero <= 1 or not _indice_util(ctx, "recuperar", numero):
        return []
    escenas = lectura.escenas_del_capitulo(ctx.con, ctx.novela_id, numero)
    if not escenas:
        return []
    consulta = " ".join(
        f"{e['objetivo']} {e['conflicto']} {e['lugar_nombre']}" for e in escenas
    )
    lugares = sorted({int(e["lugar_id"]) for e in escenas})
    try:
        return ctx.indice.recuperar(  # type: ignore[union-attr]
            ctx.novela_id, consulta, hasta_capitulo=numero, lugares=lugares, limite=8
        )
    except Exception as exc:  # el indice es prescindible, pero se avisa
        emitir_traza(ctx, "indice_fallo", operacion="recuperar", capitulo=numero,
                     error=f"{type(exc).__name__}: {exc}")
        return []


def _indexar(ctx: Contexto, numero: int) -> None:
    if not _indice_util(ctx, "indexar", numero):
        return
    try:
        with transaccion(ctx.con):
            ctx.indice.indexar_capitulo(ctx.novela_id, numero)  # type: ignore[union-attr]
    except Exception as exc:  # el indice es prescindible, pero se avisa
        emitir_traza(ctx, "indice_fallo", operacion="indexar", capitulo=numero,
                     error=f"{type(exc).__name__}: {exc}")


# --- Recorrido completo -------------------------------------------------------------------------


def exportar_a_langfuse(ctx: Contexto) -> None:
    """Envia a Langfuse lo nuevo de la novela (RF3-OBS-08). Nunca lanza.

    Un fallo de Langfuse no para, ni revierte, ni cambia el estado de nada: queda en la traza
    como `langfuse_fallo` y lo no enviado se reintenta en el siguiente envio.
    """
    if ctx.exportador is None:
        return
    try:
        ctx.exportador.exportar(ctx.con, ctx.novela_id)
    except Exception as exc:  # el exportador es prescindible, pero se avisa
        try:
            emitir_traza(ctx, "langfuse_fallo", error=f"{type(exc).__name__}: {exc}"[:500])
        except Exception:  # ni siquiera la traza: el pipeline sigue
            log.warning("No se pudo anotar el fallo de Langfuse", exc_info=True)


def avanzar(ctx: Contexto) -> str:
    """Lleva la ejecucion tan lejos como pueda desde donde este. Devuelve su estado final.

    Que toca se DERIVA DEL GRAFO, no del estado de `ejecucion` (RF2-PIPE-00): agentes de
    planificacion que faltan, puerta 1 no vigente, escaleta ausente, puerta 2 no vigente,
    capitulos pendientes y puerta 5, en ese orden. El estado puede mentir tras una parada o una
    caida; el grafo, con la vigencia de cada puerta, no.

    Al cerrar cada unidad (planificacion, escaleta, capitulo) y al salir por cualquier via,
    envia a Langfuse lo nuevo (RF3-OBS-08).
    """
    try:
        return _avanzar(ctx)
    finally:
        exportar_a_langfuse(ctx)


def _avanzar(ctx: Contexto) -> str:
    try:
        nid = ctx.novela_id
        if _fase_pendiente_de_planificacion(ctx) or not vigencia.puerta_vigente(ctx.con, nid, 1):
            planificar(ctx)
            exportar_a_langfuse(ctx)

        if lectura.total_capitulos(ctx.con, nid) == 0 or not vigencia.puerta_vigente(
            ctx.con, nid, 2
        ):
            escaletar(ctx)
            exportar_a_langfuse(ctx)

        _asegurar_activa(ctx, "arrancar_generacion")

        total = lectura.total_capitulos(ctx.con, ctx.novela_id)
        siguiente = lectura.ultimo_capitulo_completado(ctx.con, ctx.novela_id) + 1
        while siguiente <= total:
            generar_capitulo(ctx, siguiente)
            exportar_a_langfuse(ctx)
            siguiente = lectura.ultimo_capitulo_completado(ctx.con, ctx.novela_id) + 1

        final, _ = _completar(ctx)
        return final

    except Detenido:
        with transaccion(ctx.con):
            estados.transicion(ctx.con, ctx.novela_id, "parar", fase=None)
            emitir_evento(ctx.con, ctx.novela_id, "detenida")
        return "detenida"
    except Parado:
        return "parada"
    except AgenteInterrumpido:
        with transaccion(ctx.con):
            estados.transicion(ctx.con, ctx.novela_id, "parar", fase=None)
            emitir_evento(ctx.con, ctx.novela_id, "detenida")
        return "detenida"


def _completar(
    ctx: Contexto,
    *,
    motivo: versiones.Motivo | None = None,
    detalle: str | None = None,
    aplicar: Callable[[], None] | None = None,
) -> tuple[str, int | None]:
    """Puerta 5, la transicion a completada y la version, en UNA transaccion (RF3-BIB-12).

    Es el final de la generacion y el del cambio del lector. `aplicar` corre al principio de
    esa misma transaccion: el cambio escribe ahi su canon y sus textos (spec3, RF3-CAM-11), y si
    lanza, no queda nada. Devuelve el estado final y el numero de la version publicada, o None
    si el texto no cambio.
    """
    with transaccion(ctx.con):
        estados.fijar_fase(ctx.con, ctx.novela_id, "puerta_5")
    with transaccion(ctx.con):
        if aplicar is not None:
            aplicar()
        global_ = evaluar_puerta_global(ctx.con, ctx.novela_id)
        _registrar_puerta_en(ctx, global_)
        suceso = "terminado_limpio" if not global_.conflictos else "terminado_con_avisos"
        final = estados.transicion(ctx.con, ctx.novela_id, suceso, fase=None)
        emitir_evento(ctx.con, ctx.novela_id, "completada", avisos=len(global_.conflictos))
        # Lo que leera el lector, en la misma transaccion que la completa (RF3-BIB-12).
        numero = versiones.publicar(ctx.con, ctx.novela_id, motivo=motivo, detalle=detalle)
    return final, numero


def _fase_pendiente_de_planificacion(ctx: Contexto) -> bool:
    return any(not _fase_ya_hecha(ctx, agente) for agente, _, _ in _PLANIFICACION)


def _asegurar_activa(ctx: Contexto, suceso: str) -> None:
    ejecucion = lectura.ejecucion(ctx.con, ctx.novela_id) or {}
    estado = str(ejecucion.get("estado", ""))
    destino = {"arrancar_planificacion": "planificando", "arrancar_escaleta": "escaletando",
               "arrancar_generacion": "generando"}[suceso]
    if estado == destino:
        return
    with transaccion(ctx.con):
        if estado == "configurada":
            estados.transicion(ctx.con, ctx.novela_id, "arrancar", fase=None)
            if destino != "planificando":
                estados.transicion(
                    ctx.con, ctx.novela_id,
                    "puerta_1_ok" if destino == "escaletando" else "puerta_2_ok", fase=None,
                )
        else:
            estados.transicion(ctx.con, ctx.novela_id, suceso, fase=None)


# --- El cambio del lector (specs/spec3.md, 3.8) ------------------------------------------------


class CambioImposible(Exception):
    """El paso final del cambio no se puede confirmar: su transaccion se deshace (RF3-CAM-12)."""

    def __init__(self, motivo: str, problemas: list[str]) -> None:
        super().__init__(motivo)
        self.problemas = problemas


def interpretar_cambio(
    ctx: Contexto, objetivo: dict[str, Any], peticion: str, cita: dict[str, Any] | None,
    candidatos: s_interprete.Candidatos,
) -> SalidaInterprete:
    """La llamada al interprete (RF3-CAM-03). Lo que devuelve lo valida `s_interprete.validar`."""
    paquete = s_interprete.paquete(objetivo, peticion, cita, candidatos)
    salida, _ = _invocar(ctx, "interprete", paquete, SalidaInterprete)
    return salida


def _planificacion_sin_vigencia(ctx: Contexto) -> list[tuple[int, ResultadoPuerta]]:
    """Las puertas 1 y 2 que el canon actual deja sin vigencia, evaluadas de nuevo."""
    salida: list[tuple[int, ResultadoPuerta]] = []
    for puerta, evaluar in ((1, p_estructura.evaluar), (2, p_escaleta.evaluar)):
        if not vigencia.puerta_vigente(ctx.con, ctx.novela_id, puerta):
            salida.append((puerta, evaluar(ctx.con, ctx.novela_id)))
    return salida


def _fallos(evaluadas: list[tuple[int, ResultadoPuerta]]) -> list[str]:
    return [f"puerta {puerta}: [{c.comprobacion}] {c.descripcion}"
            for puerta, r in evaluadas for c in r.bloqueantes]


def comprobar_planificacion(ctx: Contexto, cambio: Cambio) -> list[str]:
    """Antes de gastar nada: aplicado en simulacion, ¿el cambio deja pasar las puertas 1 y 2?

    Devuelve lo que fallaria, vacio si nada (spec3, RF3-CAM-04).
    """
    with simulacion(ctx.con):
        o_cambios.aplicar_canon(ctx.con, ctx.novela_id, cambio)
        return _fallos(_planificacion_sin_vigencia(ctx))


def aplicar_cambio(ctx: Contexto, cambio_id: int) -> str:
    """Reescribe los capitulos del alcance y, si todos pasan, confirma el cambio de una vez.

    La ejecucion ya esta en `generando` (la transicion `cambio_lector` la hace el worker al
    cerrar la intencion). Devuelve el estado final. Nada se aplica hasta el ultimo paso: un
    fracaso, un `parar` o una caida no dejan nada a medias (RF3-CAM-07, RF3-CAM-12).
    """
    try:
        return _aplicar_cambio(ctx, cambio_id)
    finally:
        exportar_a_langfuse(ctx)


def _marcar_cambio(ctx: Contexto, cambio_id: int, estado: str, **campos: Any) -> None:
    asignaciones = ", ".join(["estado = ?", *(f"{c} = ?" for c in campos),
                              "actualizado_en = datetime('now')"])
    valores = [estado, *(json.dumps(v, ensure_ascii=False) if isinstance(v, dict | list)
                         else v for v in campos.values())]
    ctx.con.execute(f"UPDATE cambio_lector SET {asignaciones} WHERE id = ?",
                    (*valores, cambio_id))


def _aplicar_cambio(ctx: Contexto, cambio_id: int) -> str:
    registro = lectura.cambio(ctx.con, ctx.novela_id, cambio_id) or {}
    cambio = Cambio.desde_dict(como_dict(registro.get("cambio")))
    capitulos = [int(c) for c in como_lista(registro.get("capitulos"))]
    corregidos: dict[int, SalidaRevision] = {}
    try:
        for numero in capitulos:
            revisado = _revisar_capitulo(ctx, cambio, numero)
            if not isinstance(revisado, SalidaRevision):
                return _fracasar(ctx, cambio_id, revisado)
            corregidos[numero] = revisado
        try:
            final, version = _completar(
                ctx, motivo="cambio_lector", detalle=str(registro.get("peticion") or ""),
                aplicar=partial(_confirmar_cambio, ctx, cambio, corregidos),
            )
        except CambioImposible as exc:
            return _fracasar(ctx, cambio_id, {"motivo": str(exc), "problemas": exc.problemas})
        with transaccion(ctx.con):
            _marcar_cambio(ctx, cambio_id, "aplicado", version=version)
            emitir_evento(ctx.con, ctx.novela_id, "cambio_aplicado", cambio_id=cambio_id,
                          version=version, capitulos=sorted(corregidos))
        for numero in sorted(corregidos):
            _indexar(ctx, numero)
        return final
    except (Detenido, AgenteInterrumpido):
        with transaccion(ctx.con):
            _marcar_cambio(ctx, cambio_id, "interrumpido")
            estados.transicion(ctx.con, ctx.novela_id, "parar", fase=None)
            emitir_evento(ctx.con, ctx.novela_id, "detenida")
        return "detenida"
    except Exception as exc:
        try:
            with transaccion(ctx.con):
                _marcar_cambio(ctx, cambio_id, "fallido",
                               informe={"motivo": f"{type(exc).__name__}: {exc}"[:500]})
        except Exception:  # ya estamos en el camino de error
            log.exception("No se pudo marcar el cambio %s como fallido", cambio_id)
        raise


def _fracasar(ctx: Contexto, cambio_id: int, informe: dict[str, Any]) -> str:
    """El cambio no se aplica: la novela vuelve a su estado completado sin version nueva."""
    with transaccion(ctx.con):
        _marcar_cambio(ctx, cambio_id, "fallido", informe=informe)
        emitir_evento(ctx.con, ctx.novela_id, "cambio_fallido", cambio_id=cambio_id,
                      informe=informe)
    final, _ = _completar(ctx)
    return final


def _nombre_anterior_del_encargo(ctx: Contexto, cambio: Cambio) -> str | None:
    """El nombre viejo, si el cambio renombra a una persona del encargo (RF3-SEU-01)."""
    if cambio.tipo != "renombrar":
        return None
    brief = lectura.brief(ctx.con, ctx.novela_id)
    if brief is None:
        return None
    del_encargo = [brief.destinatario.nombre, brief.quien_regala,
                   *(a.nombre for a in brief.allegados)]
    viejo = normalizar(cambio.antes)
    return cambio.antes if any(n and normalizar(n) == viejo for n in del_encargo) else None


def _revisar_capitulo(
    ctx: Contexto, cambio: Cambio, numero: int
) -> SalidaRevision | dict[str, Any]:
    """El revisor corrige el capitulo y la puerta 4 lo juzga, hasta tres veces (RF3-CAM-08/09).

    Devuelve la correccion aprobada, o el informe de por que no hubo ninguna.
    """
    viejo = o_cambios.textos_del_capitulo(ctx.con, ctx.novela_id, numero)
    criterios: list[dict[str, Any]] | None = None
    informe: dict[str, Any] = {}
    cap = lectura.capitulo(ctx.con, ctx.novela_id, numero) or {}
    aprobados = (str(cap.get("resumen") or ""), str(cap.get("resumen_breve") or ""))
    anterior = _nombre_anterior_del_encargo(ctx, cambio)
    for intento in range(1, ctx.cfg_max_intentos + 1):
        with transaccion(ctx.con):
            estados.fijar_fase(ctx.con, ctx.novela_id, "revision", capitulo=numero,
                               intento=intento)
        with simulacion(ctx.con):
            o_cambios.aplicar_canon(ctx.con, ctx.novela_id, cambio)
            paquete = s_revision.paquete(ctx.con, ctx.novela_id, numero, cambio, viejo,
                                         criterios_incumplidos=criterios)
            # RF3-SEU-01 en el cambio: el brief ya lleva el nombre nuevo, y el viejo, si era
            # de una persona del encargo, sale como [NOMBRE_ANTERIOR].
            mascara = Mascara(lectura.brief(ctx.con, ctx.novela_id), anterior=anterior)
        salida, _ = _invocar(ctx, "revision", paquete, SalidaRevision, capitulo=numero,
                             intento=intento, mascara=mascara)
        nuevo = salida.textos()
        comprobado = p_revision.comprobar(
            cambio, numero, viejo, nuevo, (salida.resumen, salida.resumen_breve), salida.citas,
            aprobados=aprobados,
        )
        texto = "\n\n".join(nuevo[k] for k in sorted(nuevo))
        mecanica = comprobado
        paquete_oficio = None
        if comprobado.pasa:
            try:
                with simulacion(ctx.con):
                    o_cambios.aplicar_canon(ctx.con, ctx.novela_id, cambio)
                    propia = p_oficio.evaluar(ctx.con, ctx.novela_id, numero, texto)
                    # La correccion no vuelve a extraer: `elemento_sin_integrar` leeria la
                    # extraccion del texto aprobado, o ninguna en una novela anterior a la
                    # migracion 013 (spec3, RF3-ELE-02; validador de 73d4723).
                    propia = ResultadoPuerta(puerta=4, conflictos=[
                        c for c in propia.conflictos if c.comprobacion != "elemento_sin_integrar"
                    ])
                    if propia.pasa:
                        paquete_oficio = s_oficio.paquete(
                            ctx.con, ctx.novela_id, numero, texto, propia,
                            presupuesto=ctx.presupuesto,
                        )
            except PresupuestoExcedido as exc:
                return {"motivo": f"El paquete del juez del capitulo {numero} no cabe.",
                        "capitulo": numero, "presupuesto": exc.informe()}
            mecanica = ResultadoPuerta(puerta=4, conflictos=[*comprobado.conflictos,
                                                             *propia.conflictos])
        juicio: SalidaOficio | None = None
        votos: dict[str, tuple[int, int]] | None = None
        if paquete_oficio is not None:
            with transaccion(ctx.con):
                estados.fijar_fase(ctx.con, ctx.novela_id, "puerta_4", capitulo=numero,
                                   intento=intento)
            juicio, votos = _juzgar(ctx, paquete_oficio, numero, intento, mascara)
        oficio = p_oficio.combinar(mecanica, juicio, votos)
        _registrar_puerta(ctx, oficio, capitulo=numero, intento=intento)
        ultimo = intento == ctx.cfg_max_intentos
        if not oficio.pasa:
            with transaccion(ctx.con):
                _registrar_politica(ctx, mecanica, numero, intento, texto,
                                    "parar" if ultimo else "reintentar")
        if oficio.pasa:
            return salida
        criterios = (
            [v.model_dump() for v in juicio.incumplidos] if juicio is not None
            else [{"criterio": c.comprobacion, "sugerencia": c.descripcion}
                  for c in mecanica.bloqueantes]
        )
        informe = {
            "motivo": (
                f"Tres intentos sin que la correccion del capitulo {numero} pasara las "
                "comprobaciones del cambio y la puerta de oficio."
            ),
            "capitulo": numero,
            "criterios_incumplidos": criterios,
            "mecanica": mecanica.informe(),
        }
    return informe


def _confirmar_cambio(ctx: Contexto, cambio: Cambio, corregidos: dict[int, SalidaRevision]
                      ) -> None:
    """El paso final, dentro de la transaccion de `_completar` (RF3-CAM-11).

    Un error de datos aqui (la base o un dato que ya no cuadra) deshace la transaccion y hace
    fracasar el cambio: la novela vuelve a su estado completado, como pide RF3-CAM-12
    (validador de 2fa0ee6). Un error de programacion no es del cambio: sube tal cual y la
    ejecucion acaba en `error` (validador de 58e70f0).
    """
    try:
        _escribir_cambio(ctx, cambio, corregidos)
    except (sqlite3.DatabaseError, o_cambios.CanonDesfasado) as exc:
        raise CambioImposible(
            "Un error de datos impidio aplicar el cambio.", [f"{type(exc).__name__}: {exc}"]
        ) from exc


def _escribir_cambio(ctx: Contexto, cambio: Cambio, corregidos: dict[int, SalidaRevision]
                     ) -> None:
    o_cambios.aplicar_canon(ctx.con, ctx.novela_id, cambio,
                            citas={n: s.citas for n, s in corregidos.items()})
    for numero, salida in sorted(corregidos.items()):
        if o_cambios.guardar_textos(ctx.con, ctx.novela_id, numero, salida.textos()):
            s_redaccion.compilar(ctx.con, ctx.novela_id, numero)
        ctx.con.execute(
            "UPDATE capitulo SET resumen = ?, resumen_breve = ? WHERE novela_id = ? "
            "AND numero = ?",
            (salida.resumen, salida.resumen_breve, ctx.novela_id, numero),
        )
    evaluadas = _planificacion_sin_vigencia(ctx)
    fallos = _fallos(evaluadas)
    if fallos:
        raise CambioImposible(
            "El cambio deja sin pasar la planificacion de la novela.", fallos
        )
    for _, resultado in evaluadas:
        _registrar_puerta_en(ctx, resultado)
    # Lo que acaba de quedar descartado sale del indice en esta misma transaccion.
    error = purgar_descartes(ctx.con)
    if error:
        emitir_evento(ctx.con, ctx.novela_id, "indice_fallo", operacion="purgar", error=error)
