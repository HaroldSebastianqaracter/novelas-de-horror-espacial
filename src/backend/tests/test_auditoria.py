"""Las reproducciones de la auditoria del 23 de septiembre de 2026, como tests.

Cada test afirma el comportamiento CORRECTO y lleva el numero de hallazgo del informe en el
nombre. Mientras el fallo exista, el test falla y la marca `xfail(strict=True)` lo cuenta sin
romper la suite. El dia que el fallo desaparezca, `strict` convierte el pase inesperado en un
error: la fase que lo arregle tiene que quitar la marca a conciencia, y asi se sabe que el test
miraba donde estaba el problema (specs/spec2-plan.md, regla «rojo antes que verde»).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

import worker
from compartido.contexto import Paquete, Presupuesto, PresupuestoExcedido, ajustar
from compartido.grafo import lectura
from compartido.puerta_base import Conflicto, ResultadoPuerta
from compartido.puerto import demo as agentes_falsos
from orquestador import cola, fallo, pipeline
from tareas.continuidad import puerta as p3
from tests.entorno import (
    cfg_de,
    contar,
    contexto,
    crear_novela,
    hechos_del_capitulo,
    nueva_bd,
    puerto_falso,
    textos_vigentes_del_capitulo,
)
from tests.fabrica import hecho, novela_minima

RAIZ = Path(__file__).resolve().parents[1]


def _falla(puerta: int):  # sustituto de un evaluar de puerta
    def evaluar(*_: object) -> ResultadoPuerta:
        return ResultadoPuerta(puerta=puerta, conflictos=[Conflicto("forzado", "falla forzada")])

    return evaluar


def _intencion(con, tipo: str, novela_id: int, **payload: object) -> cola.Intencion:
    iid = cola.encolar(con, tipo, novela_id, **payload)
    con.execute("UPDATE intencion SET estado = 'en_curso' WHERE id = ?", (iid,))
    return cola.Intencion(id=iid, tipo=tipo, novela_id=novela_id, payload=dict(payload))


# --- Fase 1: el capitulo a medias ---------------------------------------------------------------


def test_hallazgo_05_parar_durante_el_oficio_no_deja_el_capitulo_a_medias() -> None:
    con, ruta = nueva_bd()
    novela_id = crear_novela(con)
    puerto = puerto_falso(con)
    avisado = {"ya": False}

    def extraccion(entrada: str, agente: str) -> dict:
        salida = agentes_falsos.extraccion(entrada, agente)
        if "capitulo 2" in entrada.lower() and not avisado["ya"]:
            avisado["ya"] = True
            cola.encolar(con, "parar", novela_id)  # llega como lo haria la API
        return salida

    puerto.registrar("extraccion", extraccion)
    assert pipeline.avanzar(contexto(con, puerto, ruta, novela_id)) == "detenida"
    assert hechos_del_capitulo(con, novela_id, 2) == 0
    assert textos_vigentes_del_capitulo(con, novela_id, 2) == 0


def test_hallazgo_06_el_worker_caido_no_deja_hechos_del_capitulo_a_medias() -> None:
    """La caida es de verdad: el subproceso sale con os._exit y no corre ningun finally."""
    con, ruta = nueva_bd()
    con.close()
    guion = f"""
import os, sys
sys.path.insert(0, r"{RAIZ}")
from compartido import db
from compartido.puerto import demo
from orquestador import pipeline
from tests.entorno import contexto, crear_novela, puerto_falso
con = db.preparar(r"{ruta}")
novela_id = crear_novela(con)
puerto = puerto_falso(con)
def oficio(entrada, agente):
    if "capitulo 2" in entrada.lower():
        os._exit(3)
    return demo.oficio(entrada, agente)
puerto.registrar("oficio", oficio)
pipeline.avanzar(contexto(con, puerto, r"{ruta}", novela_id))
"""
    salida = subprocess.run(
        [sys.executable, "-c", guion], cwd=RAIZ, capture_output=True, text=True, timeout=120
    )
    assert salida.returncode == 3, salida.stderr[-2000:]

    w = worker.Worker(cfg_de(ruta))
    w.recuperar()
    ejecucion = lectura.ejecucion(w.con, 1) or {}
    assert ejecucion["estado"] == "detenida"
    assert ejecucion["capitulos_completados"] == 1
    assert hechos_del_capitulo(w.con, 1, 2) == 0
    assert textos_vigentes_del_capitulo(w.con, 1, 2) == 0


# --- Fase 2: reanudar nunca se salta una puerta -------------------------------------------------


def test_hallazgo_01_resolver_una_parada_de_estructura_no_se_salta_las_puertas(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, ruta = nueva_bd()
    w = worker.Worker(cfg_de(ruta))
    novela_id = crear_novela(w.con)
    monkeypatch.setattr(pipeline.p_estructura, "evaluar", _falla(1))

    w._correr(novela_id)
    parada_id = int(fallo.paradas_abiertas(w.con, novela_id)[0]["id"])
    w._resolver_parada(_intencion(
        w.con, "resolver_parada", novela_id, parada_id=parada_id, accion="relanzar",
        desde_capitulo=1,
    ))

    puertas = [
        (int(f["puerta"]), str(f["veredicto"])) for f in w.con.execute(
            "SELECT puerta, veredicto FROM resultado_puerta WHERE novela_id = ? ORDER BY id",
            (novela_id,),
        )
    ]
    # Nunca una puerta 5 sin que el ultimo veredicto de las puertas 1 y 2 sea favorable.
    if any(p == 5 for p, _ in puertas):
        antes = puertas[: [p for p, _ in puertas].index(5)]
        for puerta in (1, 2):
            ultimo = [v for p, v in antes if p == puerta][-1:]
            assert ultimo and ultimo[0] != "falla", f"puerta 5 sin puerta {puerta}: {puertas}"
    estado = str((lectura.ejecucion(w.con, novela_id) or {})["estado"])
    assert not (estado.startswith("completada") and lectura.total_capitulos(w.con, novela_id) == 0)


def test_hallazgo_02_la_escaleta_rechazada_dos_veces_no_se_queda(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    con, ruta = nueva_bd()
    novela_id = crear_novela(con)
    monkeypatch.setattr(pipeline.p_escaleta, "evaluar", _falla(2))

    final = pipeline.avanzar(contexto(con, puerto_falso(con), ruta, novela_id))
    assert final == "parada"
    assert lectura.total_capitulos(con, novela_id) == 0


def test_hallazgo_12_aceptar_retcon_sobre_una_parada_de_estructura_se_rechaza(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, ruta = nueva_bd()
    w = worker.Worker(cfg_de(ruta))
    novela_id = crear_novela(w.con)
    monkeypatch.setattr(pipeline.p_estructura, "evaluar", _falla(1))
    w._correr(novela_id)
    parada_id = int(fallo.paradas_abiertas(w.con, novela_id)[0]["id"])

    intencion = _intencion(
        w.con, "resolver_parada", novela_id, parada_id=parada_id, accion="aceptar_retcon"
    )
    w._resolver_parada(intencion)
    estado = w.con.execute(
        "SELECT estado FROM intencion WHERE id = ?", (intencion.id,)
    ).fetchone()["estado"]
    assert estado == "rechazada"


# --- Fase 3: un solo escritor -------------------------------------------------------------------


def test_hallazgo_03_el_latido_sabe_si_perdio_el_cerrojo() -> None:
    con, _ = nueva_bd()
    cola.tomar_cerrojo(con, poll_segundos=1)
    # Otro proceso se queda la fila mientras este no latia.
    con.execute("UPDATE worker_lock SET pid = pid + 1 WHERE id = 1")
    assert cola.latir(con) is False


# --- Fase 4: el paquete no pierde canon en silencio ---------------------------------------------


def test_hallazgo_04_el_bloque_de_hechos_no_desaparece_en_silencio() -> None:
    """La reproduccion de la auditoria: 200 hechos y 700 posturas pasan de su presupuesto.

    Antes el bloque era un solo parrafo y desaparecia entero sin excepcion. Ahora se quitan
    los opcionales desde el final, lo obligatorio se queda entero y el recorte queda anotado.
    """
    import config
    from tareas.redaccion.servicio import _hechos

    hechos = [
        {"sujeto_nombre": f"Personaje{i % 6}", "atributo": f"atributo {i}", "valor": "x" * 40,
         "capitulo_origen": i // 20, "obligatorio": i < 50}
        for i in range(200)
    ]
    conocimiento = [
        {"personaje": f"P{i % 6}", "postura": "sabe", "sujeto_nombre": "S", "atributo": f"a{i}",
         "valor": "y" * 40, "capitulo": i // 30, "via": "presencio"}
        for i in range(700)
    ]
    p = Paquete(agente="redaccion", capitulo=30)
    p.anadir("instrucciones", "estilo")
    p.anadir("escaleta", "escenas")
    p.anadir_elementos("hechos", _hechos(hechos, conocimiento), "ESTADO ESTABLECIDO")
    presupuesto = Presupuesto(
        bloques=config.PRESUPUESTO_BLOQUES, techo=config.PRESUPUESTO_PAQUETE
    )
    try:
        ajustado = ajustar(p, presupuesto)
    except PresupuestoExcedido:
        return
    texto = ajustado.render()
    assert all(f"atributo {i}:" in texto for i in range(50))
    assert all(f"· a{i}:" in texto for i in range(700))
    assert ajustado.recortes["hechos"]["elementos"] == 150


def test_hallazgo_10_los_hechos_antiguos_del_reparto_entran_en_el_paquete() -> None:
    con, _ = nueva_bd()
    con.execute("BEGIN")
    g = novela_minima(con)
    con.execute("COMMIT")
    for i in range(250):
        hecho(con, g, (1, 2), "Estacion", f"atributo {i}", "v", sujeto_tipo="mundo")
    hechos = lectura.hechos_del_reparto(con, g.novela_id, 2)
    assert any(h["id"] == g.hechos["ojos"] for h in hechos)


# --- Fase 5: puerta 3 sin falsos positivos ------------------------------------------------------

def test_hallazgo_07_una_cadena_de_supersesiones_no_es_contradiccion() -> None:
    con, _ = nueva_bd()
    con.execute("BEGIN")
    g = novela_minima(con)
    con.execute("COMMIT")
    azules = hecho(con, g, (2, 1), "Ibarra", "color de ojos", "azules",
                   supersede_a=g.hechos["ojos"])
    hecho(con, g, (2, 2), "Ibarra", "color de ojos", "verdes", supersede_a=azules)
    bloqueantes = p3.evaluar(con, g.novela_id, 2).bloqueantes
    assert not [c for c in bloqueantes if c.comprobacion == "continuidad_factual"]


def test_hallazgo_08_valores_que_solo_difieren_en_tildes_no_se_contradicen() -> None:
    con, _ = nueva_bd()
    con.execute("BEGIN")
    g = novela_minima(con)
    con.execute("COMMIT")
    for escena, valor in (((1, 1), "Ámbar"), ((2, 1), "ámbar")):
        hecho(con, g, escena, "Reyes", "color de pelo", valor)
    bloqueantes = p3.evaluar(con, g.novela_id, 2).bloqueantes
    assert not [c for c in bloqueantes if c.comprobacion == "continuidad_factual"]


# --- Fase 6: la traza dice la verdad ------------------------------------------------------------


def test_hallazgo_09_una_parada_de_oficio_deja_la_puerta_4_en_falla() -> None:
    con, ruta = nueva_bd()
    novela_id = crear_novela(con)
    puerto = puerto_falso(con)

    def siempre_falla(entrada: str, agente: str) -> dict:
        salida = agentes_falsos.oficio(entrada, agente)
        salida["veredictos"][0] = {
            "criterio": salida["veredictos"][0]["criterio"], "veredicto": "falla",
            "evidencia": "La compuerta cedio.", "sugerencia": "Acerca la distancia.",
        }
        return salida

    puerto.registrar("oficio", siempre_falla)
    assert pipeline.avanzar(contexto(con, puerto, ruta, novela_id)) == "parada"
    assert contar(
        con, "SELECT COUNT(*) FROM resultado_puerta WHERE novela_id = ? AND puerta = 4 "
        "AND veredicto = 'falla'", novela_id,
    ) >= 1


def test_hallazgo_15_un_evento_dramatizado_sin_orden_interno_no_valida() -> None:
    from pydantic import ValidationError

    from tareas.extraccion.esquemas import EventoExtraido

    with pytest.raises(ValidationError):
        EventoExtraido(fecha_interna="dia 3", descripcion="Se abre la esclusa", dramatizado=True)


def test_hallazgo_16_casi_muerto_no_es_muerto() -> None:
    con, _ = nueva_bd()
    con.execute("BEGIN")
    g = novela_minima(con)
    con.execute("COMMIT")
    con.execute(
        "INSERT INTO estado_personaje (novela_id, personaje_id, escena_id, salud_fisica) "
        "VALUES (?,?,?, 'casi muerto, pero respira')",
        (g.novela_id, g.personajes["Ibarra"], g.escenas[(1, 2)]),
    )
    bloqueantes = p3.evaluar(con, g.novela_id, 2).bloqueantes
    assert not [c for c in bloqueantes if c.comprobacion == "presencia_imposible"]


def test_hallazgo_20_dos_personajes_con_el_mismo_nombre_se_rechazan() -> None:
    import sqlite3

    from compartido.grafo import insertar

    con, _ = nueva_bd()
    novela_id = crear_novela(con)
    insertar(con, "personaje", novela_id=novela_id, nombre="Reyes", rol_narrativo="aliado")
    with pytest.raises(sqlite3.IntegrityError):
        insertar(con, "personaje", novela_id=novela_id, nombre="reyes", rol_narrativo="espejo")


def test_hallazgo_21_un_hecho_no_se_modifica_se_revoca() -> None:
    import sqlite3

    con, _ = nueva_bd()
    con.execute("BEGIN")
    g = novela_minima(con)
    con.execute("COMMIT")
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("UPDATE hecho SET vigente = 0 WHERE id = ?", (g.hechos["ojos"],))


# --- Fase 6: la traza dice la verdad ----------------------------------------------------------


def test_hallazgo_11_un_uso_sobre_un_hecho_que_no_existe_deja_aviso() -> None:
    con, ruta = nueva_bd()
    novela_id = crear_novela(con)
    puerto = puerto_falso(con)

    def extraccion(entrada: str, agente: str) -> dict:
        salida = agentes_falsos.extraccion(entrada, agente)
        salida["usos_de_conocimiento"] = [{
            "escena_orden": 1, "personaje_ref": agentes_falsos.PERSONAJES[0],
            "sujeto_ref": "Dra. Kowalski", "atributo": "secreto",
        }]
        return salida

    puerto.registrar("extraccion", extraccion)
    pipeline.avanzar(contexto(con, puerto, ruta, novela_id))
    detalles = [
        f["detalle"] for f in con.execute(
            "SELECT detalle FROM resultado_puerta WHERE novela_id = ? AND puerta = 3",
            (novela_id,),
        )
    ]
    assert any("conocimiento_sin_comprobar" in d for d in detalles)


def _puerto_terminal(respuesta: dict):
    from compartido.puerto import PuertoTerminal
    from tests import claude_falso

    return PuertoTerminal(
        claude_bin=str(claude_falso.ejecutable(respuesta)), skills_dir=claude_falso.SKILLS,
        timeout_agente_segundos=60,
    )


def test_hallazgo_17_una_llamada_con_permisos_denegados_es_un_error_de_puerto() -> None:
    from compartido.puerto import ErrorDePuerto
    from tests import claude_falso

    puerto = _puerto_terminal(claude_falso.sobre(
        {"x": 1}, permission_denials=[{"tool_name": "Read", "tool_input": {}}],
    ))
    with pytest.raises(ErrorDePuerto):
        puerto.invocar("arquitecto", "entrada", {"type": "object"})


def test_hallazgo_18_una_senal_entre_llamadas_corta_la_siguiente() -> None:
    from compartido.puerto import AgenteInterrumpido
    from tests import claude_falso

    _, ruta = nueva_bd()
    w = worker.Worker(cfg_de(ruta))
    w.puerto = _puerto_terminal(claude_falso.sobre({"x": 1}))
    w.detener()  # SIGTERM mientras no hay ninguna llamada en curso
    with pytest.raises(AgenteInterrumpido):
        w.puerto.invocar("arquitecto", "entrada", {"type": "object"})
