"""La traza dice la verdad y el extractor deja rastro (spec2, fase 6).

RF2-PIPE-13 (la puerta 4 registra mecanica y juicio), RF2-PIPE-16 (los descartes del
extractor se cuentan), RF2-PIPE-17 (busquedas dirigidas sobre la prosa), RF2-PUERTO-10 (el
agente no usa herramientas) y RF2-WK-09 (una senal entre llamadas para).
"""

from __future__ import annotations

import json
import sqlite3

import pytest

import config
import worker
from compartido.puerto import AgenteInterrumpido, AgenteUsoHerramientas, PuertoTerminal
from compartido.puerto import demo as agentes_falsos
from orquestador import fallo, pipeline
from tareas.continuidad import puerta as p3
from tests import claude_falso
from tests.entorno import cfg_de, contexto, crear_novela, nueva_bd, puerto_falso
from tests.fabrica import Grafo, hecho, novela_minima


def _puerta_4(con: sqlite3.Connection, novela_id: int, capitulo: int) -> list[dict]:
    return [
        {"veredicto": f["veredicto"], **json.loads(f["detalle"])}
        for f in con.execute(
            "SELECT veredicto, detalle FROM resultado_puerta WHERE novela_id = ? AND puerta = 4 "
            "AND capitulo = ? ORDER BY id", (novela_id, capitulo),
        )
    ]


# --- RF2-PIPE-13: la puerta 4 entera ------------------------------------------------------------


def test_un_juicio_en_contra_queda_registrado_con_su_evidencia() -> None:
    """El juez falla el primer intento y aprueba el segundo: la traza dice las dos cosas."""
    con, ruta = nueva_bd()
    novela_id = crear_novela(con)
    puerto = puerto_falso(con)
    intentos = {"n": 0}

    def oficio(entrada: str, agente: str) -> dict:
        salida = agentes_falsos.oficio(entrada, agente)
        if "capitulo 1" in entrada.lower():
            intentos["n"] += 1
            if intentos["n"] <= config.OFICIO_MUESTRAS:  # las muestras del primer intento
                salida["veredictos"][2] = {
                    "criterio": salida["veredictos"][2]["criterio"], "veredicto": "falla",
                    "evidencia": "Sintio miedo.", "sugerencia": "Muestralo en el cuerpo.",
                }
        return salida

    puerto.registrar("oficio", oficio)
    pipeline.avanzar(contexto(con, puerto, ruta, novela_id))

    registros = _puerta_4(con, novela_id, 1)
    assert [r["veredicto"] for r in registros][0] == "falla"
    assert registros[-1]["veredicto"] != "falla"
    juicios = [c for c in registros[0]["conflictos"] if c["comprobacion"].startswith("juicio:")]
    assert juicios and juicios[0]["datos"]["evidencia"] == "Sintio miedo."


def test_si_la_mecanica_falla_el_juez_corre_igual_y_el_redactor_recibe_todo() -> None:
    """RF3-PAS-14: la mecanica y el juez a la vez, para no descubrir los fallos de uno en uno."""
    con, ruta = nueva_bd()
    novela_id = crear_novela(con)
    puerto = puerto_falso(con)
    tic = agentes_falsos.TICS[0]

    def redaccion(entrada: str, agente: str) -> dict:
        salida = agentes_falsos.redaccion(entrada, agente)
        for e in salida["escenas"]:
            e["texto"] = f"{e['texto']} Y {tic}, todo se apago."
        return salida

    def oficio(entrada: str, agente: str) -> dict:
        salida = agentes_falsos.oficio(entrada, agente)
        for v in salida["veredictos"]:
            if v["criterio"] == "cuentas_cuadran":
                v.update(veredicto="falla", evidencia="Nueve de siete.",
                         sugerencia="Cuadra el censo.")
        return salida

    puerto.registrar("redaccion", redaccion)
    puerto.registrar("oficio", oficio)
    assert pipeline.avanzar(contexto(con, puerto, ruta, novela_id)) == "parada"
    assert [i for i in puerto.invocaciones if i["agente"] == "oficio"]
    registros = _puerta_4(con, novela_id, 1)
    assert registros and all(r["veredicto"] == "falla" for r in registros)
    comprobaciones = {c["comprobacion"] for c in registros[0]["conflictos"]}
    assert {"tic_prohibido", "juicio:cuentas_cuadran"} <= comprobaciones
    assert "juicio_no_invocado" not in comprobaciones
    segundo = [i for i in puerto.invocaciones if i["agente"] == "redaccion"][1]["entrada"]
    assert "tic_prohibido" in segundo and "Cuadra el censo." in segundo


def test_toda_parada_de_oficio_tiene_la_puerta_4_en_falla() -> None:
    """Contrato: no puede haber una parada de oficio con la traza diciendo `pasa`."""
    con, ruta = nueva_bd()
    novela_id = crear_novela(con)
    puerto = puerto_falso(con)

    def siempre_falla(entrada: str, agente: str) -> dict:
        salida = agentes_falsos.oficio(entrada, agente)
        salida["veredictos"][0].update(veredicto="falla", evidencia="x", sugerencia="y")
        return salida

    puerto.registrar("oficio", siempre_falla)
    pipeline.avanzar(contexto(con, puerto, ruta, novela_id))
    for parada in fallo.paradas_abiertas(con, novela_id):
        if parada["tipo"] == "oficio":
            veredictos = [r["veredicto"] for r in _puerta_4(con, novela_id, parada["capitulo"])]
            assert veredictos and all(v == "falla" for v in veredictos)


# --- RF2-PIPE-16: los descartes del extractor ----------------------------------------------------


def test_los_descartes_del_extractor_van_a_la_traza_por_motivo() -> None:
    con, ruta = nueva_bd()
    novela_id = crear_novela(con)
    puerto = puerto_falso(con)

    def extraccion(entrada: str, agente: str) -> dict:
        salida = agentes_falsos.extraccion(entrada, agente)
        salida["estados_personaje"].append({
            "escena_orden": 1, "personaje_ref": "Dra. Kowalski", "condicion": "vivo",
        })
        salida["conocimiento"].append({
            "escena_orden": 99, "personaje_ref": agentes_falsos.PERSONAJES[0],
            "sujeto_ref": agentes_falsos.LUGARES[0], "atributo": "olor", "postura": "sabe",
            "via": "presencio",
        })
        return salida

    puerto.registrar("extraccion", extraccion)
    pipeline.avanzar(contexto(con, puerto, ruta, novela_id))
    eventos = [
        json.loads(f["payload"]) for f in con.execute(
            "SELECT payload FROM traza_evento WHERE tipo = 'extraccion_descartes'"
        )
    ]
    assert eventos
    recuento = eventos[0]["recuento"]
    assert recuento["estados_personaje"] == {"personaje_sin_resolver": 1}
    assert recuento["conocimiento"] == {"escena_desconocida": 1}


# --- RF2-PIPE-17: busquedas dirigidas sobre la prosa ---------------------------------------------


@pytest.fixture()
def grafo() -> tuple[sqlite3.Connection, Grafo]:
    con, _ = nueva_bd()
    con.execute("BEGIN")
    g = novela_minima(con)
    con.execute("COMMIT")
    return con, g


def _avisos(con: sqlite3.Connection, g: Grafo, textos: dict[int, str]) -> dict[str, dict]:
    resultado = p3.evaluar(con, g.novela_id, 2, textos=textos)
    return {c.comprobacion: c.datos for c in resultado.avisos}


def test_un_nombre_del_canon_sin_nada_registrado_es_aviso(
    grafo: tuple[sqlite3.Connection, Grafo],
) -> None:
    con, g = grafo
    avisos = _avisos(con, g, {1: "Reyes cruzo el Puente con la baliza en la mano."})
    # Reyes y la Baliza no tienen nada registrado en la escena 2.1; el Puente es donde ocurre.
    assert set(avisos["nombre_sin_registro"]["nombres"]) == {"Reyes", "Baliza"}
    # Una vez registrado algo sobre Reyes, deja de avisar por el.
    hecho(con, g, (2, 1), "Reyes", "herida", "brazo")
    avisos = _avisos(con, g, {1: "Reyes cruzo el Puente con la baliza en la mano."})
    assert avisos["nombre_sin_registro"]["nombres"] == ["Baliza"]


def test_una_cifra_sin_hecho_de_fecha_ni_distancia_es_aviso(
    grafo: tuple[sqlite3.Connection, Grafo],
) -> None:
    con, g = grafo
    assert "cifra_sin_hecho" in _avisos(con, g, {1: "Quedaban 42 metros hasta la esclusa."})
    from compartido.grafo import insertar_hecho

    insertar_hecho(
        con, novela_id=g.novela_id, escena_id=g.escenas[(2, 1)], sujeto_tipo="lugar",
        sujeto_id=g.lugares["Esclusa"], sujeto_nombre="Esclusa", atributo="distancia al puente",
        valor="42 metros", categoria="distancia",
    )
    assert "cifra_sin_hecho" not in _avisos(con, g, {1: "Quedaban 42 metros hasta la esclusa."})


def test_nombrar_a_un_muerto_fuera_de_una_analepsis_es_aviso(
    grafo: tuple[sqlite3.Connection, Grafo],
) -> None:
    con, g = grafo
    con.execute(
        "INSERT INTO estado_personaje (novela_id, personaje_id, escena_id, condicion) "
        "VALUES (?,?,?, 'muerto')", (g.novela_id, g.personajes["Reyes"], g.escenas[(1, 2)]),
    )
    texto = {1: "Kowalski penso en Reyes y en lo que dijo antes de caer."}
    assert _avisos(con, g, texto)["muerto_nombrado"]["nombres"] == ["Reyes"]
    con.execute("UPDATE escena SET analepsis = 1 WHERE id = ?", (g.escenas[(2, 1)],))
    assert "muerto_nombrado" not in _avisos(con, g, texto)


def test_las_busquedas_dirigidas_avisan_pero_no_paran(
    grafo: tuple[sqlite3.Connection, Grafo],
) -> None:
    con, g = grafo
    resultado = p3.evaluar(con, g.novela_id, 2, textos={1: "Reyes conto 3 pasos."})
    assert resultado.pasa
    assert resultado.avisos


# --- RF2-PUERTO-10: el agente no usa herramientas -------------------------------------------------


def _puerto(respuesta: dict) -> tuple[PuertoTerminal, object]:
    ejecutable = claude_falso.ejecutable(respuesta)
    return PuertoTerminal(
        claude_bin=str(ejecutable), skills_dir=claude_falso.SKILLS, timeout_agente_segundos=60,
    ), ejecutable


def test_el_puerto_retira_las_herramientas_y_los_mcp() -> None:
    puerto, ejecutable = _puerto(claude_falso.sobre({"x": 1}))
    assert puerto.invocar("arquitecto", "entrada", {"type": "object"}).salida == {"x": 1}
    argv = claude_falso.argumentos(ejecutable)  # type: ignore[arg-type]
    assert "--tools" in argv and "--allowedTools" in argv and "--strict-mcp-config" in argv


def test_el_puerto_pide_el_modelo_configurado(monkeypatch: pytest.MonkeyPatch) -> None:
    """RF2-PUERTO-11: por defecto Opus 5.5, y NOVELAS_MODELO lo cambia."""
    from dataclasses import replace

    from compartido.puerto import construir

    monkeypatch.setenv("NOVELAS_DB_PATH", "x.db")
    monkeypatch.setenv("NOVELAS_PUERTO", "terminal")
    monkeypatch.delenv("NOVELAS_MODELO", raising=False)
    assert config.cargar().modelo == "claude-opus-5-5"
    monkeypatch.setenv("NOVELAS_MODELO", " claude-sonnet-5 ")
    cfg = config.cargar()
    assert cfg.modelo == "claude-sonnet-5"

    ejecutable = claude_falso.ejecutable(claude_falso.sobre({"x": 1}))
    cfg = replace(cfg, claude_bin=str(ejecutable), skills_dir=claude_falso.SKILLS)
    puerto = construir(cfg)
    assert isinstance(puerto, PuertoTerminal)
    puerto.invocar("arquitecto", "entrada", {"type": "object"})
    argv = claude_falso.argumentos(ejecutable)
    assert argv[argv.index("--model") + 1] == "claude-sonnet-5"


def test_sin_modelo_el_puerto_no_pasa_model() -> None:
    puerto, ejecutable = _puerto(claude_falso.sobre({"x": 1}))
    puerto.invocar("arquitecto", "entrada", {"type": "object"})
    assert "--model" not in claude_falso.argumentos(ejecutable)  # type: ignore[arg-type]


@pytest.mark.parametrize("turnos", [2, 3])
def test_el_numero_de_turnos_no_es_uso_de_herramientas(turnos: int) -> None:
    """Las dos cifras salieron de llamadas reales sin herramientas (CLI 2.1.274)."""
    puerto, _ = _puerto(claude_falso.sobre({"x": 1}, num_turns=turnos))
    assert puerto.invocar("arquitecto", "entrada", {"type": "object"}).salida == {"x": 1}


def test_un_permiso_denegado_es_un_error_y_no_se_reintenta() -> None:
    puerto, _ = _puerto(claude_falso.sobre(
        {"x": 1}, permission_denials=[{"tool_name": "Read", "tool_input": {"file": "x"}}],
    ))
    with pytest.raises(AgenteUsoHerramientas, match="Read"):
        puerto.invocar("arquitecto", "entrada", {"type": "object"})


# --- RF2-WK-09: una senal entre llamadas para ---------------------------------------------------


def test_una_senal_entre_llamadas_para_sin_llamar_a_ningun_agente() -> None:
    from compartido.grafo import lectura

    _, ruta = nueva_bd()
    w = worker.Worker(cfg_de(ruta))
    novela_id = crear_novela(w.con)
    w.detener()  # SIGTERM cuando no hay ninguna llamada en curso
    w._correr(novela_id)

    assert (lectura.ejecucion(w.con, novela_id) or {})["estado"] == "detenida"
    assert w.con.execute("SELECT COUNT(*) FROM llamada_modelo").fetchone()[0] == 0
    with pytest.raises(AgenteInterrumpido):
        w.puerto.invocar("arquitecto", "entrada", {"type": "object"})


def test_parar_por_intencion_solo_corta_una_llamada() -> None:
    """La interrupcion de un `parar` no es definitiva: la siguiente ejecucion puede llamar."""
    puerto, _ = _puerto(claude_falso.sobre({"x": 1}))
    puerto.interrumpir()
    assert puerto.invocar("arquitecto", "entrada", {"type": "object"}).salida == {"x": 1}
