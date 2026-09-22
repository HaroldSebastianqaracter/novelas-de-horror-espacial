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
hechos pero sin marcar como completado. Eso no lo ve ningun lector como capitulo terminado, y
si el worker muere ahi, la recuperacion revierte al ultimo capitulo integro.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ValidationError

from compartido.contexto import PresupuestoExcedido
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

from . import cola, estados, fallo
from .puerta_global import evaluar as evaluar_puerta_global


class Detenido(Exception):
    """Llego una intencion de parar. No es un error: es el autor tomando el control."""


class Parado(Exception):
    """Se abrio una parada y el pipeline espera a un humano."""

    def __init__(self, parada_id: int, tipo: str) -> None:
        super().__init__(f"Parada {tipo} ({parada_id})")
        self.parada_id = parada_id
        self.tipo = tipo


@dataclass
class Contexto:
    con: sqlite3.Connection
    puerto: PuertoAgente
    cfg: Config
    novela_id: int
    indice: Any | None = None
    #: Informe de la puerta 2 cuando hay que rehacer la escaleta.
    eventos: list[str] = field(default_factory=list)
    #: Criterios de oficio incumplidos, que vuelven al redactor en el reintento.
    eventos_criterios: list[dict[str, Any]] = field(default_factory=list)

    @property
    def cfg_max_intentos(self) -> int:
        return MAX_INTENTOS_CAPITULO


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
    if cola.hay_parada_pendiente(ctx.con, ctx.novela_id):
        raise Detenido()


def _registrar_puerta(ctx: Contexto, resultado: Any, capitulo: int | None = None,
                      intento: int | None = None) -> None:
    with transaccion(ctx.con):
        resultado.registrar(ctx.con, ctx.novela_id, capitulo=capitulo, intento=intento)
        emitir_evento(
            ctx.con, ctx.novela_id, "puerta_evaluada", puerta=resultado.puerta,
            veredicto=resultado.veredicto, capitulo=capitulo,
            conflictos=[str(c) for c in resultado.conflictos[:10]],
        )


def _abrir_parada(ctx: Contexto, tipo: str, informe: dict[str, Any],
                  capitulo: int | None = None, intento: int | None = None) -> None:
    with transaccion(ctx.con):
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
    """Escaleta y puerta 2. Un fallo de puerta 2 se reintenta una vez con el informe."""
    _asegurar_activa(ctx, "arrancar_escaleta")
    for intento in (1, 2):
        if ctx.con.execute(
            "SELECT 1 FROM capitulo WHERE novela_id = ?", (ctx.novela_id,)
        ).fetchone() is None:
            with transaccion(ctx.con):
                estados.fijar_fase(ctx.con, ctx.novela_id, "escaleta", intento=intento)
            texto = s_escaleta.paquete(ctx.con, ctx.novela_id)
            if intento == 2 and ctx.eventos:
                texto += "\n\n## LA ESCALETA ANTERIOR FALLO POR ESTO\n\n" + "\n".join(ctx.eventos)
            salida, _ = _invocar(ctx, "escaleta", texto, SalidaEscaleta, intento=intento)
            with transaccion(ctx.con):
                s_escaleta.aplicar(ctx.con, ctx.novela_id, salida)

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

        ctx.eventos = [str(c) for c in resultado.bloqueantes]
        if intento == 2:
            _abrir_parada(ctx, "escaleta", resultado.informe(), intento=intento)
        # Se borra la escaleta fallida para que el segundo intento la rehaga entera.
        with transaccion(ctx.con):
            ctx.con.execute("DELETE FROM capitulo WHERE novela_id = ?", (ctx.novela_id,))
            ctx.con.execute("DELETE FROM secuencia WHERE novela_id = ?", (ctx.novela_id,))


# --- Bucle de capitulo -------------------------------------------------------------------------


def generar_capitulo(ctx: Contexto, numero: int) -> None:
    """Paquete, redaccion, extraccion, puerta 3 y puerta 4 para un capitulo."""
    _asegurar_activa(ctx, "arrancar_generacion")
    for intento in range(1, ctx.cfg_max_intentos + 1):
        with transaccion(ctx.con):
            estados.fijar_fase(ctx.con, ctx.novela_id, "paquete", capitulo=numero,
                               intento=intento)

        criterios = ctx.eventos_criterios if intento > 1 else None
        recuperado = _recuperar(ctx, numero)

        try:
            paquete_redaccion = s_redaccion.paquete(
                ctx.con, ctx.novela_id, numero,
                criterios_incumplidos=criterios, recuperado=recuperado,
            )
        except PresupuestoExcedido as exc:
            _abrir_parada(ctx, "presupuesto", exc.informe(), capitulo=numero, intento=intento)
            return

        # --- Tramo 1: llamadas al agente, sin transaccion --------------------------------
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
        paquete_extraccion = s_extraccion.paquete(ctx.con, ctx.novela_id, numero, textos)
        hechos, _ = _invocar(
            ctx, "extraccion", paquete_extraccion, SalidaExtraccion,
            capitulo=numero, intento=intento,
        )

        # --- Tramo 2: texto y hechos entran juntos, y la puerta 3 decide -----------------
        limpio = False
        try:
            with transaccion(ctx.con):
                estados.fijar_fase(ctx.con, ctx.novela_id, "puerta_3", capitulo=numero,
                                   intento=intento)
                por_orden = s_redaccion.aplicar(
                    ctx.con, ctx.novela_id, numero, prosa, intento=intento,
                    llamada_id=resultado_redaccion.llamada_id,
                )
                s_extraccion.aplicar(ctx.con, ctx.novela_id, numero, hechos, por_orden)
                continuidad = p_continuidad.evaluar(ctx.con, ctx.novela_id, numero)
                if not continuidad.pasa:
                    raise _Rechazado(continuidad)
                limpio = True
        except _Rechazado as rechazo:
            _registrar_puerta(ctx, rechazo.resultado, capitulo=numero, intento=intento)
            informe = rechazo.resultado.informe()
            informe["prosa_rechazada"] = textos
            _abrir_parada(ctx, "continuidad", informe, capitulo=numero, intento=intento)
            return

        if limpio:
            _registrar_puerta(ctx, continuidad, capitulo=numero, intento=intento)

        # --- Tramo 3: oficio, y si pasa, cierre del capitulo -----------------------------
        texto_completo = "\n\n".join(textos[k] for k in sorted(textos))
        mecanica = p_oficio.evaluar(ctx.con, ctx.novela_id, numero, texto_completo)

        juicio: SalidaOficio | None = None
        if mecanica.pasa:
            with transaccion(ctx.con):
                estados.fijar_fase(ctx.con, ctx.novela_id, "puerta_4", capitulo=numero,
                                   intento=intento)
            paquete_oficio = s_oficio.paquete(
                ctx.con, ctx.novela_id, numero, texto_completo, mecanica
            )
            juicio, _ = _invocar(
                ctx, "oficio", paquete_oficio, SalidaOficio, capitulo=numero, intento=intento
            )

        pasa_oficio = mecanica.pasa and juicio is not None and juicio.pasa
        _registrar_puerta(ctx, mecanica, capitulo=numero, intento=intento)

        if pasa_oficio:
            with transaccion(ctx.con):
                _cerrar_capitulo(ctx, numero)
            _indexar(ctx, numero)
            return

        # Falla el oficio: se descarta lo escrito y se vuelve a redaccion con el criterio.
        ctx.eventos_criterios = (
            [v.model_dump() for v in juicio.incumplidos] if juicio is not None
            else [{"criterio": c.comprobacion, "sugerencia": c.descripcion,
                   "evidencia": "", "principio": "38"} for c in mecanica.bloqueantes]
        )
        with transaccion(ctx.con):
            fallo.revertir_a(ctx.con, ctx.novela_id, numero)

        if intento == ctx.cfg_max_intentos:
            informe: dict[str, Any] = {
                "motivo": (
                    f"Tres intentos sin pasar la puerta de oficio en el capitulo {numero}. "
                    "Si el capitulo no se puede escribir bien, el problema probablemente esta "
                    "en la escaleta y no en la prosa."
                ),
                "mecanica": mecanica.informe(),
                "criterios_incumplidos": ctx.eventos_criterios,
            }
            _abrir_parada(ctx, "oficio", informe, capitulo=numero, intento=intento)
            return


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


def _recuperar(ctx: Contexto, numero: int) -> list[Any]:
    """Bloque recuperado del paquete (RF-CTX-07). Sin indice, lista vacia y a seguir."""
    if ctx.indice is None or not getattr(ctx.indice, "disponible", False) or numero <= 1:
        return []
    escenas = lectura.escenas_del_capitulo(ctx.con, ctx.novela_id, numero)
    if not escenas:
        return []
    consulta = " ".join(
        f"{e['objetivo']} {e['conflicto']} {e['lugar_nombre']}" for e in escenas
    )
    lugares = sorted({int(e["lugar_id"]) for e in escenas})
    try:
        return ctx.indice.recuperar(
            ctx.novela_id, consulta, hasta_capitulo=numero, lugares=lugares, limite=8
        )
    except Exception:  # noqa: BLE001 - el indice es prescindible por diseno
        return []


def _indexar(ctx: Contexto, numero: int) -> None:
    if ctx.indice is None or not getattr(ctx.indice, "disponible", False):
        return
    try:
        with transaccion(ctx.con):
            ctx.indice.indexar_capitulo(ctx.novela_id, numero)
    except Exception:  # noqa: BLE001
        pass


# --- Recorrido completo -------------------------------------------------------------------------


def avanzar(ctx: Contexto) -> str:
    """Lleva la ejecucion tan lejos como pueda desde donde este. Devuelve su estado final."""
    try:
        ejecucion = lectura.ejecucion(ctx.con, ctx.novela_id) or {}
        estado = str(ejecucion.get("estado", "configurada"))

        pendiente = estado in ("configurada", "detenida", "error", "planificando")
        if pendiente and _fase_pendiente_de_planificacion(ctx):
            planificar(ctx)

        ejecucion = lectura.ejecucion(ctx.con, ctx.novela_id) or {}
        estado = str(ejecucion.get("estado", ""))
        if estado in ("escaletando", "detenida", "error"):
            if lectura.total_capitulos(ctx.con, ctx.novela_id) == 0:
                _asegurar_activa(ctx, "arrancar_escaleta")
                escaletar(ctx)
            elif estado != "generando":
                _asegurar_activa(ctx, "arrancar_generacion")

        ejecucion = lectura.ejecucion(ctx.con, ctx.novela_id) or {}
        if str(ejecucion.get("estado", "")) != "generando":
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
