"""El pipeline completo, de punta a punta, con el puerto falso.

Es la propiedad 23 del plan de verificacion: el pipeline debe poder correr entero sin Claude
Code instalado y sin gastar dinero. Y es tambien donde se comprueban las propiedades que solo
se ven en conjunto: que un lector nunca vea un capitulo a medias, que revertir deje el grafo
como estaba, y que la puerta 3 pare la generacion en vez de dejar pasar el conflicto.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

import config
from compartido import db
from compartido.db import transaccion
from compartido.puerto import PuertoFalso
from compartido.puerto import demo as agentes_falsos
from orquestador import cola, fallo, pipeline


@pytest.fixture()
def entorno() -> Iterator[tuple[sqlite3.Connection, PuertoFalso, config.Config]]:
    ruta = Path(tempfile.mkdtemp()) / "novela.db"
    con = db.preparar(ruta)
    puerto = PuertoFalso(generadores=dict(agentes_falsos.TODOS), con=con)
    cfg = config.Config(
        db_path=ruta, claude_bin="claude", skills_dir=Path(".claude/skills"),
        poll_segundos=1, timeout_agente_segundos=60, presupuesto_tokens=100_000,
        puerto="falso", puerto_falso_dir=None, embedding_modelo="hash", vectores_activos=False,
    )
    yield con, puerto, cfg
    con.close()


def _crear_novela(con: sqlite3.Connection) -> int:
    from compartido.grafo import insertar

    with transaccion(con):
        novela_id = insertar(con, "novela", titulo="Cerro Quince", genero="terror_espacial")
        insertar(con, "restriccion", novela_id=novela_id,
                 tipo="longitud_objetivo_palabras", valor="5400")
        insertar(con, "ejecucion", novela_id=novela_id, estado="configurada")
    return novela_id


def _contexto(entorno, novela_id: int) -> pipeline.Contexto:
    con, puerto, cfg = entorno
    return pipeline.Contexto(con=con, puerto=puerto, cfg=cfg, novela_id=novela_id)


# --- El recorrido completo -------------------------------------------------------------------


def test_pipeline_completo_sin_claude_code(entorno) -> None:
    con, puerto, _ = entorno
    novela_id = _crear_novela(con)

    final = pipeline.avanzar(_contexto(entorno, novela_id))

    assert final in ("completada", "completada_con_avisos"), final
    assert db.verificar_integridad(con) == []

    capitulos = con.execute(
        "SELECT COUNT(*) FROM capitulo WHERE novela_id = ? AND estado = 'completado'",
        (novela_id,),
    ).fetchone()[0]
    assert capitulos == agentes_falsos.CAPITULOS

    # Cada capitulo completado tiene su texto compilado y sus hechos.
    compilados = con.execute(
        "SELECT COUNT(*) FROM capitulo_compilado WHERE novela_id = ? AND estado = 'vigente'",
        (novela_id,),
    ).fetchone()[0]
    assert compilados == agentes_falsos.CAPITULOS
    assert con.execute(
        "SELECT COUNT(*) FROM hecho WHERE novela_id = ?", (novela_id,)
    ).fetchone()[0] > 0

    # Se invoco a cada agente que la v1 usa.
    invocados = {i["agente"] for i in puerto.invocaciones}
    assert invocados == {
        "arquitecto", "mundo", "elenco", "estructura", "escaleta", "redaccion", "extraccion",
        "oficio",
    }


def test_las_puertas_quedan_registradas(entorno) -> None:
    con, _, _ = entorno
    novela_id = _crear_novela(con)
    pipeline.avanzar(_contexto(entorno, novela_id))

    puertas = {
        int(f["puerta"]) for f in con.execute(
            "SELECT DISTINCT puerta FROM resultado_puerta WHERE novela_id = ?", (novela_id,)
        )
    }
    assert puertas == {1, 2, 3, 4, 5}


def test_la_traza_permite_reconstruir_cada_llamada(entorno) -> None:
    """RNF-01: sistema, entrada y salida de cada invocacion quedan guardados."""
    con, _, _ = entorno
    novela_id = _crear_novela(con)
    pipeline.avanzar(_contexto(entorno, novela_id))

    eventos = {
        f["tipo"] for f in con.execute(
            "SELECT DISTINCT tipo FROM traza_evento WHERE novela_id = ?", (novela_id,)
        )
    }
    assert {"agente_iniciado", "agente_terminado", "puerta_evaluada",
            "capitulo_completado", "completada"} <= eventos


# --- La puerta 3 para el pipeline -------------------------------------------------------------


def test_un_conflicto_de_continuidad_para_y_no_deja_rastro(entorno) -> None:
    """La prosa rechazada no se guarda como texto vigente: va al informe de la parada."""
    con, puerto, _ = entorno
    novela_id = _crear_novela(con)

    # El extractor afirma en el capitulo 2 lo contrario de lo que fijo en el 1.
    original = agentes_falsos.extraccion

    def contradictorio(entrada: str, agente: str) -> dict:
        salida = original(entrada, agente)
        if "CAPITULO 2" in entrada or "capitulo 2" in entrada:
            salida["hechos"][0]["valor"] = "aire limpio y sin olor"
        return salida

    puerto.registrar("extraccion", contradictorio)
    final = pipeline.avanzar(_contexto(entorno, novela_id))

    assert final == "parada"
    abiertas = fallo.paradas_abiertas(con, novela_id)
    assert len(abiertas) == 1
    assert abiertas[0]["tipo"] == "continuidad"
    assert abiertas[0]["capitulo"] == 2

    informe = abiertas[0]["informe"]
    assert "prosa_rechazada" in informe

    # El capitulo 1 quedo entero; el 2 no existe para ningun lector.
    assert con.execute(
        "SELECT estado FROM capitulo WHERE novela_id = ? AND numero = 1", (novela_id,)
    ).fetchone()["estado"] == "completado"
    assert con.execute(
        "SELECT estado FROM capitulo WHERE novela_id = ? AND numero = 2", (novela_id,)
    ).fetchone()["estado"] == "planificado"
    assert con.execute(
        """
        SELECT COUNT(*) FROM escena_texto et JOIN escena e ON e.id = et.escena_id
        JOIN capitulo c ON c.id = e.capitulo_id
        WHERE c.numero = 2 AND et.estado = 'vigente' AND et.novela_id = ?
        """,
        (novela_id,),
    ).fetchone()[0] == 0
    assert db.verificar_integridad(con) == []


def _parar_en_el_capitulo_2(puerto: PuertoFalso) -> None:
    original = agentes_falsos.extraccion

    def contradictorio(entrada: str, agente: str) -> dict:
        salida = original(entrada, agente)
        if "CAPITULO 2" in entrada or "capitulo 2" in entrada:
            salida["hechos"][0]["valor"] = "aire limpio y sin olor"
        return salida

    puerto.registrar("extraccion", contradictorio)


def test_la_parada_de_continuidad_lleva_una_segunda_opinion(entorno) -> None:
    """spec3, RF3-JUE-01: el revisor explica y opina, y la parada sigue abierta."""
    con, puerto, _ = entorno
    novela_id = _crear_novela(con)
    _parar_en_el_capitulo_2(puerto)
    assert pipeline.avanzar(_contexto(entorno, novela_id)) == "parada"

    [parada] = fallo.paradas_abiertas(con, novela_id)
    informe = json.loads(parada["informe"])
    opinion = informe["segunda_opinion"]
    # Numerados sobre la lista entera del informe, como los ve el autor en el frontend.
    numeros = [n for n, c in enumerate(informe["conflictos"], start=1) if not c["aviso"]]
    assert [o["conflicto"] for o in opinion["opiniones"]] == numeros
    [entrada] = [i["entrada"] for i in puerto.invocaciones if i["agente"] == "continuidad"]
    assert "1. [continuidad_factual]" in entrada
    assert "PROSA RECHAZADA DEL CAPITULO 2" in entrada


def test_si_la_segunda_opinion_falla_la_parada_se_abre_igual(entorno) -> None:
    from compartido.puerto import TiempoAgotado

    con, puerto, _ = entorno
    novela_id = _crear_novela(con)
    _parar_en_el_capitulo_2(puerto)

    def caido(entrada: str, agente: str) -> dict:
        raise TiempoAgotado("sin respuesta")

    puerto.registrar("continuidad", caido)
    assert pipeline.avanzar(_contexto(entorno, novela_id)) == "parada"
    [parada] = fallo.paradas_abiertas(con, novela_id)
    assert parada["tipo"] == "continuidad"
    assert json.loads(parada["informe"])["segunda_opinion"] is None
    assert con.execute(
        "SELECT COUNT(*) FROM traza_evento WHERE novela_id = ? AND tipo = "
        "'segunda_opinion_fallida'", (novela_id,)).fetchone()[0] == 1


def test_una_opinion_de_falso_positivo_no_levanta_la_parada(entorno) -> None:
    con, puerto, _ = entorno
    novela_id = _crear_novela(con)
    _parar_en_el_capitulo_2(puerto)

    def todo_falso(entrada: str, agente: str) -> dict:
        salida = agentes_falsos.continuidad(entrada, agente)
        for o in salida["opiniones"]:
            o["parece"] = "falso_positivo"
        return salida

    puerto.registrar("continuidad", todo_falso)
    assert pipeline.avanzar(_contexto(entorno, novela_id)) == "parada"
    [parada] = fallo.paradas_abiertas(con, novela_id)
    assert parada["tipo"] == "continuidad"
    opiniones = json.loads(parada["informe"])["segunda_opinion"]["opiniones"]
    assert opiniones and {o["parece"] for o in opiniones} == {"falso_positivo"}


@pytest.mark.parametrize("error", ["interrumpido", "inesperado", "detenido"])
def test_nada_de_lo_que_pase_en_la_opinion_pierde_la_parada(entorno, error: str) -> None:
    """Validador de 9cc7972: con la llamada antes de abrir la parada, una interrupcion, una
    detencion pedida por el autor o un fallo imprevisto se la llevaban por delante."""
    from compartido.puerto import AgenteInterrumpido

    con, puerto, _ = entorno
    novela_id = _crear_novela(con)
    _parar_en_el_capitulo_2(puerto)

    def falla(entrada: str, agente: str) -> dict:
        if error == "interrumpido":
            raise AgenteInterrumpido("senal de terminar")
        if error == "inesperado":
            raise RuntimeError("algo que nadie espera")
        with transaccion(con):
            cola.encolar(con, "parar", novela_id)
        return agentes_falsos.continuidad(entrada, agente)

    puerto.registrar("continuidad", falla)
    pipeline.avanzar(_contexto(entorno, novela_id))
    [parada] = fallo.paradas_abiertas(con, novela_id)
    assert parada["tipo"] == "continuidad"


def test_el_revisor_numera_como_el_informe() -> None:
    from compartido.contexto import Presupuesto
    from compartido.puerta_base import Conflicto, ResultadoPuerta
    from tareas.continuidad import servicio as s_continuidad

    con = db.preparar(Path(tempfile.mkdtemp()) / "novela.db")
    resultado = ResultadoPuerta(puerta=3, conflictos=[
        Conflicto(comprobacion="habito_roto", descripcion="Un aviso.", aviso=True),
        Conflicto(comprobacion="continuidad_factual", descripcion="Un conflicto."),
    ])
    render = s_continuidad.paquete(con, 1, 2, resultado, {1: "Texto."}, presupuesto=Presupuesto(
        bloques=config.PRESUPUESTO_BLOQUES, techo=config.PRESUPUESTO_PAQUETE)).render()
    assert "2. [continuidad_factual]" in render and "habito_roto" not in render


def test_la_skill_de_continuidad_opina_y_no_levanta_la_parada() -> None:
    skill = (config.raiz_repo() / ".claude" / "skills" / "continuidad" / "SKILL.md").read_text(
        encoding="utf-8")
    assert "**Una opinión por conflicto**" in skill
    assert "`real`, `falso_positivo` o `dudoso`" in skill
    assert "**No levantas la parada.**" in skill
    assert "No decides si hay conflicto" not in skill


def test_la_puerta_4_reintenta_y_escala_a_parada(entorno) -> None:
    """Tres intentos sin pasar el oficio escalan a parada: el problema esta en la escaleta."""
    con, puerto, _ = entorno
    novela_id = _crear_novela(con)

    def siempre_falla(entrada: str, agente: str) -> dict:
        salida = agentes_falsos.oficio(entrada, agente)
        salida["veredictos"][0] = {
            "criterio": salida["veredictos"][0]["criterio"], "veredicto": "falla",
            "evidencia": "La compuerta cedio con un chasquido seco.",
            "sugerencia": "Acerca la distancia psiquica al abrir.",
        }
        return salida

    puerto.registrar("oficio", siempre_falla)
    final = pipeline.avanzar(_contexto(entorno, novela_id))

    assert final == "parada"
    abiertas = fallo.paradas_abiertas(con, novela_id)
    assert abiertas[0]["tipo"] == "oficio"
    assert abiertas[0]["intento"] == config.MAX_INTENTOS_CAPITULO

    redacciones = [i for i in puerto.invocaciones if i["agente"] == "redaccion"]
    assert len(redacciones) == config.MAX_INTENTOS_CAPITULO

    # El tercer intento llevaba el criterio incumplido en el paquete.
    assert "LO QUE FALLO EN EL INTENTO ANTERIOR" in redacciones[-1]["entrada"]


# --- Reanudacion --------------------------------------------------------------------------------


def test_revertir_deja_el_grafo_como_estaba(entorno) -> None:
    """Propiedad 9: revertir a N deja el grafo identico al que habia al terminar N-1."""
    con, _, _ = entorno
    novela_id = _crear_novela(con)
    ctx = _contexto(entorno, novela_id)

    pipeline.planificar(ctx)
    pipeline.escaletar(ctx)
    pipeline.generar_capitulo(ctx, 1)

    def foto() -> dict[str, int]:
        return {
            tabla: int(con.execute(f"SELECT COUNT(*) FROM {tabla}").fetchone()[0])
            for tabla in (
                "hecho", "estado_conocimiento", "uso_conocimiento", "estado_personaje",
                "estado_objeto", "evento", "siembra_estado", "capitulo_compilado",
            )
        }

    antes = foto()
    pipeline.generar_capitulo(ctx, 2)
    assert foto() != antes

    with transaccion(con):
        fallo.revertir_grafo(con, novela_id, 2)

    despues = foto()
    # El compilado no se borra, se descarta: es historia legible.
    assert despues.pop("capitulo_compilado") >= antes.pop("capitulo_compilado")
    assert despues == antes
    assert db.verificar_integridad(con) == []

    vigentes = con.execute(
        "SELECT COUNT(*) FROM capitulo_compilado WHERE novela_id = ? AND estado = 'vigente'",
        (novela_id,),
    ).fetchone()[0]
    assert vigentes == 1


def test_se_puede_reanudar_y_termina(entorno) -> None:
    """Tras revertir, avanzar vuelve a llevar la novela hasta el final."""
    con, _, _ = entorno
    novela_id = _crear_novela(con)
    ctx = _contexto(entorno, novela_id)
    pipeline.avanzar(ctx)

    with transaccion(con):
        fallo.relanzar(con, novela_id, 2)
    assert con.execute(
        "SELECT COUNT(*) FROM capitulo WHERE novela_id = ? AND estado = 'completado'",
        (novela_id,),
    ).fetchone()[0] == 1

    final = pipeline.avanzar(_contexto(entorno, novela_id))
    assert final in ("completada", "completada_con_avisos")
    assert con.execute(
        "SELECT COUNT(*) FROM capitulo WHERE novela_id = ? AND estado = 'completado'",
        (novela_id,),
    ).fetchone()[0] == agentes_falsos.CAPITULOS


# --- Parar ----------------------------------------------------------------------------------------


def test_parar_detiene_sin_dejar_capitulo_a_medias(entorno) -> None:
    con, _, _ = entorno
    novela_id = _crear_novela(con)
    ctx = _contexto(entorno, novela_id)

    pipeline.planificar(ctx)
    pipeline.escaletar(ctx)
    with transaccion(con):
        cola.encolar(con, "parar", novela_id)

    final = pipeline.avanzar(ctx)
    assert final == "detenida"
    assert con.execute(
        "SELECT COUNT(*) FROM capitulo WHERE novela_id = ? AND estado = 'completado'",
        (novela_id,),
    ).fetchone()[0] == 0
    assert db.verificar_integridad(con) == []
