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
from compartido.vectores import Indice
from orquestador import cola, estados, fallo, pipeline

log = logging.getLogger("worker")

MAX_NOVELAS_POR_CICLO = 1


class Worker:
    def __init__(self, cfg: config.Config) -> None:
        self.cfg = cfg
        self.con: sqlite3.Connection = db.preparar(cfg.db_path)
        self.puerto = construir_puerto(cfg, self.con)
        self.indice = Indice(
            self.con, modelo=cfg.embedding_modelo, activo=cfg.vectores_activos
        )
        self.parar = False
        self._novela_en_curso: int | None = None

    # -- ciclo de vida ---------------------------------------------------------------------

    def arrancar(self) -> None:
        cola.tomar_cerrojo(
            self.con, poll_segundos=self.cfg.poll_segundos
        )
        self.recuperar()
        log.info("Worker en marcha. Sondeo cada %s s.", self.cfg.poll_segundos)
        try:
            self.bucle()
        finally:
            cola.soltar_cerrojo(self.con)
            log.info("Worker detenido.")

    def detener(self, *_: Any) -> None:
        log.info("Senal recibida: terminando el ciclo en curso.")
        self.parar = True
        interrumpir = getattr(self.puerto, "interrumpir", None)
        if callable(interrumpir):
            interrumpir()

    def recuperar(self) -> None:
        """Al arrancar, deja el mundo consistente (RF-FALLO-06).

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
            violaciones = db.verificar_integridad(self.con)
            with transaccion(self.con):
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
            cola.latir(self.con)
            intencion = cola.tomar(self.con)
            if intencion is None:
                time.sleep(self.cfg.poll_segundos)
                continue
            try:
                self.atender(intencion)
            except Exception as exc:  # noqa: BLE001 - el worker no puede morir por una intencion
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
            for tipo, valor in (p.get("restricciones") or {}).items():
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
        if str(ejecucion.get("estado")) == "parada":
            cola.cerrar(
                self.con, intencion.id, "rechazada",
                motivo="hay una parada abierta: resuelvela o relanza",
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

        tope = lectura.ultimo_capitulo_completado(self.con, novela_id) + 1
        if desde > tope:
            cola.cerrar(
                self.con, intencion.id, "rechazada",
                motivo=f"no se puede relanzar desde {desde}: el ultimo completado es {tope - 1}",
            )
            return

        with transaccion(self.con):
            borrado = fallo.revertir_a(self.con, novela_id, desde)
        if self.indice.disponible:
            with transaccion(self.con):
                self.indice.purgar(novela_id, desde)
        cola.cerrar(self.con, intencion.id, "hecha", resultado={"borrado": borrado})
        self._correr(novela_id)

    def _resolver_parada(self, intencion: cola.Intencion) -> None:
        novela_id = intencion.novela_id
        p = intencion.payload
        parada_id = int(p.get("parada_id") or 0)
        accion = str(p.get("accion") or "")

        if novela_id is None or not parada_id:
            cola.cerrar(self.con, intencion.id, "rechazada", motivo="parametros invalidos")
            return

        abiertas = {int(x["id"]) for x in fallo.paradas_abiertas(self.con, novela_id)}
        if parada_id not in abiertas:
            cola.cerrar(self.con, intencion.id, "rechazada", motivo="la parada no esta abierta")
            return

        if accion == "aceptar_retcon":
            capitulo = int(
                self.con.execute(
                    "SELECT COALESCE(capitulo, 1) AS c FROM parada WHERE id = ?", (parada_id,)
                ).fetchone()["c"]
            )
            with transaccion(self.con):
                revocados = fallo.aceptar_retcon(self.con, novela_id, parada_id)
                fallo.revertir_a(self.con, novela_id, capitulo)
                fallo.cerrar_parada(self.con, novela_id, parada_id, "aceptar_retcon")
            cola.cerrar(
                self.con, intencion.id, "hecha", resultado={"hechos_revocados": revocados}
            )
        elif accion == "relanzar":
            desde = int(p.get("desde_capitulo") or 1)
            with transaccion(self.con):
                fallo.revertir_a(self.con, novela_id, desde)
                fallo.cerrar_parada(self.con, novela_id, parada_id, "relanzar")
            cola.cerrar(self.con, intencion.id, "hecha")
        else:
            cola.cerrar(self.con, intencion.id, "rechazada", motivo=f"accion '{accion}' invalida")
            return

        self._correr(novela_id)

    # -- ejecucion --------------------------------------------------------------------------

    def _correr(self, novela_id: int) -> None:
        self._novela_en_curso = novela_id
        ctx = pipeline.Contexto(
            con=self.con, puerto=self.puerto, cfg=self.cfg, novela_id=novela_id,
            indice=self.indice,
        )
        try:
            final = pipeline.avanzar(ctx)
            log.info("Novela %s: %s", novela_id, final)
        except Exception as exc:  # noqa: BLE001
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
        except Exception:  # noqa: BLE001 - ya estabamos en el camino de error
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


def _manejador(worker: Worker):  # noqa: ANN202 - firma impuesta por signal
    def manejar(_num: int, _frame: FrameType | None) -> None:
        worker.detener()

    return manejar


if __name__ == "__main__":
    raise SystemExit(main())
