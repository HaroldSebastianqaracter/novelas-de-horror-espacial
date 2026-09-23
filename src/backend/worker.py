"""El worker: el unico proceso que escribe. Aqui vive el orquestador.

Se arranca aparte de la API, con `python -m worker`. Son dos comandos y no uno para poder
reiniciar la API sin matar una generacion en curso, que puede durar horas.
"""

from __future__ import annotations

import logging
import signal
import sqlite3
import sys
import time
from types import FrameType
from typing import Any

import config
from compartido import db
from compartido.db import transaccion
from compartido.grafo import emitir_evento, insertar, lectura
from compartido.puerto import construir as construir_puerto
from compartido.tipos import como_dict
from compartido.vectores import Indice
from orquestador import cola, estados, fallo, pipeline, vigencia

log = logging.getLogger("worker")

MAX_NOVELAS_POR_CICLO = 1


class Worker:
    def __init__(self, cfg: config.Config, con: sqlite3.Connection | None = None) -> None:
        self.cfg = cfg
        # `con` solo lo pasan los tests que exploran la maquina de estados en memoria.
        self.con: sqlite3.Connection = con if con is not None else db.conectar(cfg.db_path)
        # La unica escritura antes del cerrojo: la tabla del cerrojo vive en el esquema.
        db.crear_esquema(self.con)
        self.puerto = construir_puerto(cfg, self.con)
        self._indice: Indice | None = None
        self.latido: cola.Latido | None = None
        self.parar = False
        self._novela_en_curso: int | None = None

    @property
    def indice(self) -> Indice:
        """Se construye la primera vez que se usa: construirlo escribe en `indice_estado`, y
        el worker no escribe nada antes de tomar el cerrojo (RF2-PROC-03)."""
        if self._indice is None:
            self._indice = Indice(
                self.con, modelo=self.cfg.embedding_modelo, activo=self.cfg.vectores_activos
            )
        return self._indice

    # -- ciclo de vida ---------------------------------------------------------------------

    def arrancar(self) -> None:
        """Cerrojo, latido, migraciones, indice y recuperacion, en ese orden (RF2-PROC-03)."""
        cola.tomar_cerrojo(self.con, poll_segundos=self.cfg.poll_segundos)
        # Desde aqui, toda transaccion de esta conexion comprueba que el cerrojo sigue siendo
        # nuestro antes de escribir (RF2-WK-08).
        db.fijar_guardia(self.con, cola.exigir_cerrojo)
        self.latido = cola.Latido(self.cfg.db_path, self.cfg.poll_segundos).iniciar()
        try:
            aplicadas = db.migrar(self.con)
            if aplicadas:
                log.info("Migraciones aplicadas: %s", aplicadas)
            _ = self.indice
            self.recuperar()
            log.info("Worker en marcha. Sondeo cada %s s.", self.cfg.poll_segundos)
            self.bucle()
        finally:
            self.latido.detener()
            cola.soltar_cerrojo(self.con)
            log.info("Worker detenido.")

    def vigilar(self) -> None:
        """Punto de comprobacion del pipeline: aborta si ya no se puede o no se debe seguir."""
        if self.latido is not None and self.latido.perdido.is_set():
            raise cola.CerrojoPerdido(
                "El latido descubrio que otro proceso tiene el cerrojo del worker."
            )
        if self.parar:
            raise pipeline.Detenido()

    def detener(self, *_: Any) -> None:
        """Lo que hace una senal de terminar (RF2-WK-09).

        El pipeline se detiene en el siguiente punto de comprobacion, y el puerto queda cerrado:
        ninguna llamada posterior se lanza, aunque la senal llegue entre dos llamadas.
        """
        log.info("Senal recibida: terminando el ciclo en curso.")
        self.parar = True
        self.puerto.interrumpir(definitivo=True)

    def recuperar(self) -> None:
        """Al arrancar, deja el mundo consistente (RF2-FALLO-06).

        No reanuda solo. El autor decide con `arrancar`: si el worker se cayo a mitad de un
        capitulo, lo prudente es detenerse y dejar que alguien mire, no adivinar.
        """
        with transaccion(self.con):
            llamadas = self.con.execute(
                "UPDATE llamada_modelo SET estado = 'interrumpida', "
                "terminado_en = datetime('now') WHERE estado = 'en_curso'"
            ).rowcount
            intenciones = self.con.execute(
                "UPDATE intencion SET estado = 'interrumpida', motivo = 'worker_caido', "
                "actualizado_en = datetime('now') WHERE estado = 'en_curso'"
            ).rowcount

        activas = [
            dict(f) for f in self.con.execute(
                "SELECT novela_id, estado FROM ejecucion WHERE estado IN "
                "('planificando','escaletando','generando')"
            )
        ]
        for e in activas:
            novela_id = int(e["novela_id"])
            completados = lectura.ultimo_capitulo_completado(self.con, novela_id)
            with transaccion(self.con):
                # Con tres tramos por capitulo, el grafo puede haberse quedado con el texto y
                # los hechos de un capitulo sin cerrar. Se revierte antes de nada (RF2-FALLO-06).
                fallo.revertir_grafo(
                    self.con, novela_id, completados + 1, motivo="worker_caido"
                )
                self.con.execute(
                    """
                    UPDATE ejecucion
                       SET estado = 'detenida', fase = NULL, capitulo_actual = ?,
                           intento_actual = 1, capitulos_completados = ?,
                           ultimo_error = 'interrumpida_por_caida',
                           actualizado_en = datetime('now')
                     WHERE novela_id = ?
                    """,
                    (completados + 1, completados, novela_id),
                )
                # Ya revertida y detenida, la regla del capitulo a medias aplica: si sale algo,
                # la recuperacion no ha dejado el grafo integro y queda en la traza.
                violaciones = db.verificar_integridad(self.con)
                emitir_evento(
                    self.con, novela_id, "worker_recuperado",
                    capitulos_completados=completados,
                    integridad=[v.regla for v in violaciones],
                )
            log.warning(
                "Novela %s recuperada en el capitulo %s. Arranca tu cuando quieras.",
                novela_id, completados,
            )

        if llamadas or intenciones or activas:
            log.info(
                "Recuperacion: %s llamada(s) y %s intencion(es) interrumpidas, "
                "%s ejecucion(es) detenidas.", llamadas, intenciones, len(activas),
            )

    # -- bucle ------------------------------------------------------------------------------

    def bucle(self) -> None:
        while not self.parar:
            self.vigilar()
            intencion = cola.tomar(self.con)
            if intencion is None:
                time.sleep(self.cfg.poll_segundos)
                continue
            try:
                self.atender(intencion)
            except Exception as exc:  # el worker no puede morir por una intencion
                log.exception("Fallo atendiendo la intencion %s", intencion.id)
                cola.cerrar(self.con, intencion.id, "rechazada", motivo=str(exc)[:500])
                if intencion.novela_id:
                    self._marcar_error(intencion.novela_id, exc)

    def atender(self, intencion: cola.Intencion) -> None:
        log.info("Intencion %s: %s", intencion.id, intencion.tipo)
        with transaccion(self.con):
            emitir_evento(
                self.con, intencion.novela_id, "intencion_recibida",
                intencion_id=intencion.id, tipo=intencion.tipo,
            )

        manejador = {
            "crear_novela": self._crear_novela,
            "arrancar": self._arrancar,
            "parar": self._parar,
            "relanzar": self._relanzar,
            "resolver_parada": self._resolver_parada,
        }.get(intencion.tipo)

        if manejador is None:
            cola.cerrar(self.con, intencion.id, "rechazada", motivo="tipo desconocido")
            return
        manejador(intencion)

    # -- intenciones -------------------------------------------------------------------------

    def _crear_novela(self, intencion: cola.Intencion) -> None:
        p = intencion.payload
        with transaccion(self.con):
            novela_id = insertar(
                self.con, "novela",
                titulo=p.get("titulo") or "Sin titulo",
                genero=p.get("genero") or "terror_espacial",
                semilla_premisa=p.get("semilla_premisa"),
            )
            for tipo, valor in como_dict(p.get("restricciones")).items():
                insertar(
                    self.con, "restriccion", novela_id=novela_id, tipo=tipo, valor=str(valor)
                )
            insertar(self.con, "ejecucion", novela_id=novela_id, estado="configurada")
            emitir_evento(self.con, novela_id, "fase_cambiada", fase="configurada")
        cola.cerrar(self.con, intencion.id, "hecha", resultado={"novela_id": novela_id})
        log.info("Novela %s creada.", novela_id)

    def _arrancar(self, intencion: cola.Intencion) -> None:
        novela_id = intencion.novela_id
        if novela_id is None:
            cola.cerrar(self.con, intencion.id, "rechazada", motivo="falta novela_id")
            return

        activa = self.con.execute(
            "SELECT novela_id FROM ejecucion WHERE estado IN "
            "('planificando','escaletando','generando') AND novela_id <> ?",
            (novela_id,),
        ).fetchone()
        if activa is not None:
            cola.cerrar(
                self.con, intencion.id, "rechazada", motivo="otra_ejecucion_activa"
            )
            return

        ejecucion = lectura.ejecucion(self.con, novela_id) or {}
        estado = str(ejecucion.get("estado"))
        if estado == "parada":
            cola.cerrar(
                self.con, intencion.id, "rechazada",
                motivo="hay una parada abierta: resuelvela o relanza",
            )
            return
        if estado not in estados.ESTADOS_QUE_ADMITEN_ARRANCAR | estados.ESTADOS_ACTIVOS:
            cola.cerrar(
                self.con, intencion.id, "rechazada",
                motivo=f"la novela esta {estado}: para rehacer capitulos, relanza",
            )
            return

        cola.cerrar(self.con, intencion.id, "hecha")
        self._correr(novela_id)

    def _parar(self, intencion: cola.Intencion) -> None:
        # El pipeline ya se entera por `hay_parada_pendiente` mientras corre; si no habia
        # nada corriendo, esto solo deja constancia.
        novela_id = intencion.novela_id
        interrumpir = getattr(self.puerto, "interrumpir", None)
        if callable(interrumpir):
            interrumpir()
        if novela_id is not None:
            ejecucion = lectura.ejecucion(self.con, novela_id) or {}
            if str(ejecucion.get("estado")) in estados.ESTADOS_ACTIVOS:
                with transaccion(self.con):
                    estados.transicion(self.con, novela_id, "parar", fase=None)
                    emitir_evento(self.con, novela_id, "detenida")
        cola.cerrar(self.con, intencion.id, "hecha")

    def _relanzar(self, intencion: cola.Intencion) -> None:
        novela_id = intencion.novela_id
        desde = int(intencion.payload.get("desde_capitulo") or 1)
        if novela_id is None or desde < 1:
            cola.cerrar(self.con, intencion.id, "rechazada", motivo="parametros invalidos")
            return
        motivo = self._motivo_para_no_relanzar(novela_id, desde, "relanzar")
        if motivo:
            cola.cerrar(self.con, intencion.id, "rechazada", motivo=motivo)
            return

        with transaccion(self.con):
            borrado = fallo.relanzar(self.con, novela_id, desde)
        cola.cerrar(self.con, intencion.id, "hecha", resultado={"borrado": borrado})
        self._correr(novela_id)

    def _motivo_para_no_relanzar(self, novela_id: int, desde: int, suceso: str) -> str | None:
        """Todo lo que impide relanzar, comprobado ANTES de tocar el grafo (RF2-WK-06)."""
        estado, tipo = fallo.estado_y_parada(self.con, novela_id)
        try:
            estados.siguiente(estado, suceso, tipo_parada=tipo)
        except estados.TransicionInvalida as exc:
            return str(exc)
        for puerta in (1, 2):
            if not vigencia.puerta_vigente(self.con, novela_id, puerta):
                return (
                    f"la puerta {puerta} no esta vigente: no hay escaleta aprobada desde la que "
                    "relanzar capitulos"
                )
        tope = lectura.ultimo_capitulo_completado(self.con, novela_id) + 1
        if desde > tope:
            return f"no se puede relanzar desde {desde}: el ultimo completado es {tope - 1}"
        return None

    def _resolver_parada(self, intencion: cola.Intencion) -> None:
        """Resuelve una parada con una accion de la tabla cerrada de RF2-FALLO-03.

        Cualquier combinacion que no este en la tabla se rechaza con motivo y sin tocar nada:
        una parada de estructura no se arregla relanzando capitulos, y un retcon sin hecho
        que revocar repetiria el mismo conflicto.
        """
        novela_id = intencion.novela_id
        p = intencion.payload
        parada_id = int(p.get("parada_id") or 0)
        accion = str(p.get("accion") or "")

        if novela_id is None or not parada_id:
            cola.cerrar(self.con, intencion.id, "rechazada", motivo="parametros invalidos")
            return

        parada = next(
            (x for x in fallo.paradas_abiertas(self.con, novela_id) if int(x["id"]) == parada_id),
            None,
        )
        if parada is None:
            cola.cerrar(self.con, intencion.id, "rechazada", motivo="la parada no esta abierta")
            return

        tipo = str(parada["tipo"])
        if accion not in estados.acciones_validas(tipo):
            cola.cerrar(
                self.con, intencion.id, "rechazada",
                motivo=(
                    f"una parada de {tipo} no se resuelve con '{accion}'. Acciones validas: "
                    f"{', '.join(estados.acciones_validas(tipo))}"
                ),
            )
            return

        if accion == "rehacer":
            rehacer = fallo.rehacer_estructura if tipo == "estructura" else fallo.rehacer_escaleta
            with transaccion(self.con):
                destino = rehacer(self.con, novela_id, parada_id)
            cola.cerrar(self.con, intencion.id, "hecha", resultado={"estado": destino})

        elif accion == "aceptar_retcon":
            capitulo = parada["capitulo"]
            if capitulo is None or not fallo.hechos_a_revocar(self.con, parada_id):
                cola.cerrar(
                    self.con, intencion.id, "rechazada",
                    motivo="ningun conflicto de la parada senala un hecho establecido que revocar",
                )
                return
            with transaccion(self.con):
                revocados = fallo.aceptar_retcon(self.con, novela_id, parada_id)
                fallo.relanzar(self.con, novela_id, int(capitulo), suceso="aceptar_retcon")
            cola.cerrar(
                self.con, intencion.id, "hecha", resultado={"hechos_revocados": revocados}
            )

        elif accion == "dar_por_sabido":
            capitulo = parada["capitulo"]
            if capitulo is None or not fallo.conocimientos_a_dar_por_sabidos(
                self.con, novela_id, parada_id
            ):
                cola.cerrar(
                    self.con, intencion.id, "rechazada",
                    motivo=(
                        "ningun conflicto de la parada es un conocimiento no adquirido sobre "
                        "un hecho de un capitulo anterior"
                    ),
                )
                return
            with transaccion(self.con):
                sabidos = fallo.dar_por_sabido(self.con, novela_id, parada_id)
                fallo.relanzar(self.con, novela_id, int(capitulo), suceso="dar_por_sabido")
            cola.cerrar(
                self.con, intencion.id, "hecha", resultado={"conocimientos_dados": sabidos}
            )

        else:  # relanzar
            desde = int(p.get("desde_capitulo") or parada["capitulo"] or 1)
            motivo = self._motivo_para_no_relanzar(novela_id, desde, "relanzar")
            if motivo:
                cola.cerrar(self.con, intencion.id, "rechazada", motivo=motivo)
                return
            with transaccion(self.con):
                fallo.relanzar(self.con, novela_id, desde)
            cola.cerrar(self.con, intencion.id, "hecha")

        self._correr(novela_id)

    # -- ejecucion --------------------------------------------------------------------------

    def _correr(self, novela_id: int) -> None:
        self._novela_en_curso = novela_id
        ctx = pipeline.Contexto(
            con=self.con, puerto=self.puerto, cfg=self.cfg, novela_id=novela_id,
            indice=self.indice, vigilar=self.vigilar,
        )
        try:
            final = pipeline.avanzar(ctx)
            log.info("Novela %s: %s", novela_id, final)
        except Exception as exc:
            log.exception("Fallo no controlado en la novela %s", novela_id)
            self._marcar_error(novela_id, exc)
        finally:
            self._novela_en_curso = None

    def _marcar_error(self, novela_id: int, exc: BaseException) -> None:
        import traceback

        detalle = "".join(traceback.format_exception(exc))[-4000:]
        try:
            with transaccion(self.con):
                estados.transicion(self.con, novela_id, "error", fase=None, error=detalle)
                emitir_evento(self.con, novela_id, "error", mensaje=str(exc)[:500])
        except Exception:  # ya estabamos en el camino de error
            log.exception("No se pudo registrar el error de la novela %s", novela_id)


def main() -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s: %(message)s"
    )
    try:
        cfg = config.cargar()
    except config.ConfiguracionInvalida as exc:
        print(f"Configuracion invalida: {exc}", file=sys.stderr)
        return 2

    worker = Worker(cfg)
    for senal in (signal.SIGINT, signal.SIGTERM):
        signal.signal(senal, _manejador(worker))
    try:
        worker.arrancar()
    except cola.OtroWorkerVivo as exc:
        print(str(exc), file=sys.stderr)
        return 3
    return 0


def _manejador(worker: Worker):  # firma impuesta por signal
    def manejar(_num: int, _frame: FrameType | None) -> None:
        worker.detener()

    return manejar


if __name__ == "__main__":
    raise SystemExit(main())
