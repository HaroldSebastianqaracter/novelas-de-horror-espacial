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

import logging
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ValidationError

from compartido.contexto import Paquete, Presupuesto, PresupuestoExcedido
from compartido.db import transaccion
from compartido.grafo import emitir_evento, lectura
from compartido.puerto import AgenteInterrumpido, PuertoAgente
from config import MAX_INTENTOS_CAPITULO, Config
from tareas.arquitecto import servicio as s_arquitecto
from tareas.arquitecto.esquemas import SalidaArquitecto
from tareas.continuidad import puerta as p_continuidad
from tareas.elenco import servicio as s_elenco
from tareas.elenco.esquemas import SalidaElenco
from tareas.escaleta import puerta as p_escaleta
from tareas.escaleta import servicio as s_escaleta
from tareas.escaleta.esquemas import SalidaEscaleta
from tareas.estructura import puerta as p_estructura
from tareas.estructura import servicio as s_estructura
from tareas.estructura.esquemas import SalidaEstructura
from tareas.extraccion import servicio as s_extraccion
from tareas.extraccion.esquemas import SalidaExtraccion
from tareas.mundo import servicio as s_mundo
from tareas.mundo.esquemas import SalidaMundo
from tareas.oficio import puerta as p_oficio
from tareas.oficio import servicio as s_oficio
from tareas.oficio.esquemas import SalidaOficio
from tareas.redaccion import servicio as s_redaccion
from tareas.redaccion.esquemas import SalidaRedaccion

from . import cola, estados, fallo, vigencia
from .puerta_global import evaluar as evaluar_puerta_global

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

    ultimo: ValidationError | None = None
    for vuelta in (1, 2):
        resultado = ctx.puerto.invocar(
            agente, entrada, modelo.model_json_schema(),
            timeout_s=ctx.cfg.timeout_agente_segundos, novela_id=ctx.novela_id,
            capitulo=capitulo, intento=intento, tokens_por_bloque=por_bloque,
        )
        try:
            validado = modelo.model_validate(resultado.salida)
        except ValidationError as exc:
            ultimo = exc
            if vuelta == 2:
                break
            entrada = (
                f"{entrada}\n\n## ERROR DEL INTENTO ANTERIOR\n\n"
                f"Tu respuesta no cumplia estas reglas. Corrigelas:\n{exc}"
            )
            continue

        emitir_traza(
            ctx, "agente_terminado", agente=agente, capitulo=capitulo,
            tokens_salida=resultado.tokens_salida, coste=resultado.coste_usd,
            compactacion=resultado.hubo_compactacion,
        )
        return validado, resultado

    raise ValueError(f"El agente '{agente}' no produjo una salida valida: {ultimo}")


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
                  *, antes: Callable[[], None] | None = None) -> None:
    """Abre la parada y lleva la ejecucion a `parada`, en una transaccion.

    `antes` corre dentro de esa misma transaccion: es lo que permite borrar la escaleta
    rechazada y abrir la parada de forma atomica (RF2-FALLO-03).
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
        if agente == "estructura":
            rechazo = vigencia.informe_de_rechazo(ctx.con, ctx.novela_id, 1)
            if rechazo:
                texto += (
                    "\n\n## LA ESTRUCTURA ANTERIOR NO PASO LA PUERTA 1, POR ESTO\n\n"
                    + "\n".join(rechazo)
                )
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
            hechos, _ = _invocar(
                ctx, "extraccion", paquete_extraccion, SalidaExtraccion,
                capitulo=numero, intento=intento,
            )

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
                        ctx.con, ctx.novela_id, numero, hechos, por_orden
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
                _abrir_parada(ctx, "continuidad", informe, capitulo=numero, intento=intento)
                return

            a_medias = True
            _trazar_descartes(ctx, numero, intento, descartes)
            _registrar_puerta(ctx, continuidad, capitulo=numero, intento=intento)

            # --- Tramo 3: oficio, y si pasa, cierre del capitulo -------------------------
            texto_completo = "\n\n".join(textos[k] for k in sorted(textos))
            mecanica = p_oficio.evaluar(ctx.con, ctx.novela_id, numero, texto_completo)

            juicio: SalidaOficio | None = None
            if mecanica.pasa:
                with transaccion(ctx.con):
                    estados.fijar_fase(ctx.con, ctx.novela_id, "puerta_4", capitulo=numero,
                                       intento=intento)
                paquete_oficio = _paquete_o_parada(
                    ctx, numero, intento, s_oficio.paquete,
                    ctx.con, ctx.novela_id, numero, texto_completo, mecanica,
                    presupuesto=ctx.presupuesto,
                )
                juicio, _ = _invocar(
                    ctx, "oficio", paquete_oficio, SalidaOficio, capitulo=numero,
                    intento=intento,
                )

            # La puerta 4 se registra entera, mecanica y juicio (RF2-PIPE-13).
            oficio = p_oficio.combinar(mecanica, juicio)
            pasa_oficio = oficio.pasa
            _registrar_puerta(ctx, oficio, capitulo=numero, intento=intento)

            if pasa_oficio:
                with transaccion(ctx.con):
                    _cerrar_capitulo(ctx, numero)
                a_medias = False
                _indexar(ctx, numero)
                return

            # Falla el oficio: se descarta lo escrito y se vuelve a redaccion con el criterio.
            ctx.eventos_criterios = (
                [v.model_dump() for v in juicio.incumplidos] if juicio is not None
                else [{"criterio": c.comprobacion, "sugerencia": c.descripcion,
                       "evidencia": "", "principio": "38"} for c in mecanica.bloqueantes]
            )
            with transaccion(ctx.con):
                fallo.revertir_grafo(ctx.con, ctx.novela_id, numero, motivo="oficio")
            a_medias = False

            if intento == ctx.cfg_max_intentos:
                informe: dict[str, Any] = {
                    "motivo": (
                        f"Tres intentos sin pasar la puerta de oficio en el capitulo {numero}. "
                        "Si el capitulo no se puede escribir bien, el problema probablemente "
                        "esta en la escaleta y no en la prosa."
                    ),
                    "mecanica": mecanica.informe(),
                    "criterios_incumplidos": ctx.eventos_criterios,
                }
                _abrir_parada(ctx, "oficio", informe, capitulo=numero, intento=intento)
                return
    finally:
        if a_medias:
            _revertir_a_medias(ctx, numero)


def _trazar_descartes(
    ctx: Contexto, numero: int, intento: int, descartes: Any
) -> None:
    """Lo que el extractor dijo y no se pudo registrar, a la traza (RF2-PIPE-16)."""
    if descartes is not None and descartes.total:
        emitir_traza(ctx, "extraccion_descartes", capitulo=numero, intento=intento,
                     recuento=descartes.recuento, usos=descartes.usos)


def _paquete_o_parada(
    ctx: Contexto, numero: int, intento: int, fabricar: Callable[..., Paquete],
    *args: Any, **kwargs: Any,
) -> Paquete:
    """Monta un paquete o, si lo obligatorio no cabe, abre una parada de presupuesto.

    Vale para los tres paquetes del capitulo (RF2-CTX-03). Si ocurre despues del tramo 2, la
    parada sale por el `finally` de `generar_capitulo`, que revierte el capitulo a medias.
    """
    try:
        return fabricar(*args, **kwargs)
    except PresupuestoExcedido as exc:
        _abrir_parada(ctx, "presupuesto", exc.informe(), capitulo=numero, intento=intento)
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


def avanzar(ctx: Contexto) -> str:
    """Lleva la ejecucion tan lejos como pueda desde donde este. Devuelve su estado final.

    Que toca se DERIVA DEL GRAFO, no del estado de `ejecucion` (RF2-PIPE-00): agentes de
    planificacion que faltan, puerta 1 no vigente, escaleta ausente, puerta 2 no vigente,
    capitulos pendientes y puerta 5, en ese orden. El estado puede mentir tras una parada o una
    caida; el grafo, con la vigencia de cada puerta, no.
    """
    try:
        nid = ctx.novela_id
        if _fase_pendiente_de_planificacion(ctx) or not vigencia.puerta_vigente(ctx.con, nid, 1):
            planificar(ctx)

        if lectura.total_capitulos(ctx.con, nid) == 0 or not vigencia.puerta_vigente(
            ctx.con, nid, 2
        ):
            escaletar(ctx)

        _asegurar_activa(ctx, "arrancar_generacion")

        total = lectura.total_capitulos(ctx.con, ctx.novela_id)
        siguiente = lectura.ultimo_capitulo_completado(ctx.con, ctx.novela_id) + 1
        while siguiente <= total:
            generar_capitulo(ctx, siguiente)
            siguiente = lectura.ultimo_capitulo_completado(ctx.con, ctx.novela_id) + 1

        with transaccion(ctx.con):
            estados.fijar_fase(ctx.con, ctx.novela_id, "puerta_5")
        global_ = evaluar_puerta_global(ctx.con, ctx.novela_id)
        _registrar_puerta(ctx, global_)
        with transaccion(ctx.con):
            suceso = "terminado_limpio" if not global_.conflictos else "terminado_con_avisos"
            final = estados.transicion(ctx.con, ctx.novela_id, suceso, fase=None)
            emitir_evento(ctx.con, ctx.novela_id, "completada", avisos=len(global_.conflictos))
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
