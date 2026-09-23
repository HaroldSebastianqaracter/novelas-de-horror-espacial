"""Un solo escritor, de verdad (spec2, fase 3: RF2-WK-07, RF2-WK-08, RF2-PROC-03).

Cierra la fila 34 de spec1-verification: dos procesos reales compiten por el cerrojo, un
ladron se lo queda a mitad del pipeline y el worker original no escribe ni una fila mas.
"""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import pytest

import worker
from compartido import db
from compartido.db import transaccion
from compartido.puerto import demo as agentes_falsos
from orquestador import cola
from tests.entorno import cfg_de, crear_novela, nueva_bd

RAIZ = Path(__file__).resolve().parents[1]


def _filas_totales(ruta: Path) -> dict[str, int]:
    con = db.conectar(ruta, solo_lectura=True)
    try:
        tablas = [
            f[0] for f in con.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            )
        ]
        return {t: int(con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]) for t in tablas}
    finally:
        con.close()


def _esperar(condicion, segundos: float = 5.0) -> bool:  # noqa: ANN001
    limite = time.monotonic() + segundos
    while time.monotonic() < limite:
        if condicion():
            return True
        time.sleep(0.05)
    return condicion()


# --- Dos procesos reales ------------------------------------------------------------------------


def test_dos_procesos_reales_no_tienen_el_cerrojo_a_la_vez() -> None:
    """El proceso A no late desde su bucle principal y aun asi conserva el cerrojo pasada la
    gracia: late su hilo. El proceso B no puede entrar hasta que A lo suelta."""
    con, ruta = nueva_bd()
    guion = f"""
import sys, time
sys.path.insert(0, r"{RAIZ}")
from compartido import db
from orquestador import cola
con = db.conectar(r"{ruta}")
cola.tomar_cerrojo(con, poll_segundos=1)
latido = cola.Latido(r"{ruta}", 0.5).iniciar()
print("listo", flush=True)
time.sleep(5)          # una llamada larga al agente: el bucle principal no vuelve a latir
latido.detener()
cola.soltar_cerrojo(con)
"""
    a = subprocess.Popen(
        [sys.executable, "-c", guion], cwd=RAIZ, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert a.stdout is not None
        assert a.stdout.readline().strip() == "listo", a.stderr.read() if a.stderr else ""
        time.sleep(4)  # mas que la gracia de tres ciclos de un segundo
        with pytest.raises(cola.OtroWorkerVivo):
            cola.tomar_cerrojo(con, poll_segundos=1)
    finally:
        a.wait(timeout=30)
    assert a.returncode == 0, a.stderr.read() if a.stderr else ""
    cola.tomar_cerrojo(con, poll_segundos=1)  # A lo solto: ahora si
    assert int(con.execute("SELECT pid FROM worker_lock").fetchone()[0]) == os.getpid()


def test_crear_el_esquema_a_la_vez_desde_varios_procesos() -> None:
    """BEGIN IMMEDIATE y relectura de la version: nadie aplica el esquema dos veces."""
    _, ruta = nueva_bd()
    ruta = ruta.with_name("carrera.db")
    guion = f"""
import sys
sys.path.insert(0, r"{RAIZ}")
from compartido import db
db.preparar(r"{ruta}").close()
"""
    procesos = [
        subprocess.Popen([sys.executable, "-c", guion], cwd=RAIZ, stderr=subprocess.PIPE,
                         text=True)
        for _ in range(8)
    ]
    errores = [p.communicate(timeout=60)[1] for p in procesos]
    assert all(p.returncode == 0 for p in procesos), errores
    con = db.conectar(ruta)
    versiones = [f[0] for f in con.execute("SELECT version FROM esquema_version ORDER BY 1")]
    # Cada version una sola vez, hasta la ultima: nadie la aplico dos veces.
    assert versiones == [db.VERSION_ESQUEMA, *(m.numero for m in db._migraciones())]  # noqa: SLF001
    assert versiones[-1] == db.version_objetivo()


# --- Fencing ----------------------------------------------------------------------------------


def test_una_transaccion_sin_el_cerrojo_se_revierte_sin_escribir() -> None:
    con, _ = nueva_bd()
    cola.tomar_cerrojo(con, poll_segundos=1)
    db.fijar_guardia(con, cola.exigir_cerrojo)
    with transaccion(con):
        con.execute("INSERT INTO novela (titulo) VALUES ('mientras es mio')")

    con.execute("UPDATE worker_lock SET pid = pid + 1")  # otro proceso se lo queda
    with pytest.raises(cola.CerrojoPerdido), transaccion(con):
        con.execute("INSERT INTO novela (titulo) VALUES ('ya no es mio')")
    assert [f[0] for f in con.execute("SELECT titulo FROM novela")] == ["mientras es mio"]


def test_el_worker_que_pierde_el_cerrojo_a_mitad_no_escribe_nada_mas() -> None:
    con, ruta = nueva_bd()
    novela_id = crear_novela(con)
    con.close()
    w = worker.Worker(cfg_de(ruta))
    cola.tomar_cerrojo(w.con, poll_segundos=1)
    db.fijar_guardia(w.con, cola.exigir_cerrojo)
    en_el_robo: dict[str, int] = {}

    def redaccion(entrada: str, agente: str) -> dict:
        if "CAPITULO 2" in entrada:
            ladron = db.conectar(ruta)
            ladron.execute("UPDATE worker_lock SET pid = 999999")
            ladron.close()
            en_el_robo.update(_filas_totales(ruta))
        return agentes_falsos.redaccion(entrada, agente)

    w.puerto.registrar("redaccion", redaccion)  # type: ignore[attr-defined]
    with pytest.raises(cola.CerrojoPerdido):
        w._correr(novela_id)

    assert en_el_robo, "el ladron no llego a actuar"
    assert _filas_totales(ruta) == en_el_robo


def test_el_latido_descubre_que_perdio_el_cerrojo() -> None:
    con, ruta = nueva_bd()
    cola.tomar_cerrojo(con, poll_segundos=1)
    latido = cola.Latido(ruta, 0.05).iniciar()
    try:
        assert not latido.perdido.wait(0.3), "con el cerrojo propio no debe darse por perdido"
        con.execute("UPDATE worker_lock SET pid = 999999")
        assert _esperar(latido.perdido.is_set)
    finally:
        latido.detener()


def test_el_pipeline_aborta_en_cuanto_el_latido_pierde_el_cerrojo() -> None:
    """La bandera del latido basta para parar, aunque ninguna escritura haya fallado aun."""
    con, ruta = nueva_bd()
    novela_id = crear_novela(con)
    w = worker.Worker(cfg_de(ruta))
    w.latido = cola.Latido(ruta, 60)  # sin arrancar: la bandera se levanta a mano
    w.latido.perdido.set()
    with pytest.raises(cola.CerrojoPerdido):
        w._correr(novela_id)
    assert w.con.execute("SELECT COUNT(*) FROM llamada_modelo").fetchone()[0] == 0


# --- Orden de arranque ------------------------------------------------------------------------


def test_el_worker_no_escribe_nada_antes_de_tomar_el_cerrojo() -> None:
    con, ruta = nueva_bd()
    con.execute("INSERT INTO worker_lock (id, pid) VALUES (1, 999999)")
    con.execute("INSERT INTO intencion (tipo, estado) VALUES ('crear_novela', 'en_curso')")
    antes = _filas_totales(ruta)

    w = worker.Worker(cfg_de(ruta))
    with pytest.raises(cola.OtroWorkerVivo):
        w.arrancar()

    # Ni la recuperacion, ni el indice, ni la traza: nada se escribio.
    assert _filas_totales(ruta) == antes
    assert con.execute("SELECT estado FROM intencion").fetchone()[0] == "en_curso"


def test_aplicar_una_version_ya_aplicada_no_hace_nada() -> None:
    """La relectura dentro de la transaccion: si otro proceso ya migro, este no repite."""
    con, _ = nueva_bd()
    assert db.crear_esquema(con) is False
    esquema = db.RUTA_ESQUEMA.read_text(encoding="utf-8")
    assert db._aplicar_version(con, db.VERSION_ESQUEMA, esquema) is False  # noqa: SLF001
    assert not con.in_transaction


def test_sentencias_parte_el_esquema_entero() -> None:
    esquema = db.RUTA_ESQUEMA.read_text(encoding="utf-8")
    partes = db.sentencias(esquema)
    assert all(sqlite3.complete_statement(p) for p in partes)
    creadas = sum(1 for p in partes if "CREATE " in p.upper())
    assert creadas == esquema.upper().count("CREATE ")
