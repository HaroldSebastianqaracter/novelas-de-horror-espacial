"""El guardrail de terminos vetados (specs/spec3.md, 3.5: RF3-GRD-01 a RF3-GRD-04).

Un caso por nivel de intensidad, las variantes que la normalizacion tiene que cubrir (tildes,
mayusculas, plural, caracteres invisibles), lo que no puede casar (subcadenas, excepciones) y el
recorrido entero: el capitulo vuelve al redactor y cada decision queda registrada.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pytest

from compartido import politica
from compartido.db import transaccion
from compartido.puerto import demo
from orquestador import fallo, pipeline
from tests import fabrica
from tests.entorno import cfg_de, contar, nueva_bd, puerto_falso
from tests.test_personalizacion import crear


def _novela(intensidad: str) -> tuple[sqlite3.Connection, Path, int]:
    con, ruta = nueva_bd()
    return con, ruta, crear(con, ruta, intensidad=intensidad)


def _terminos(con: sqlite3.Connection, novela_id: int, texto: str) -> list[str]:
    return [h.regla.termino for h in politica.buscar(texto, politica.reglas(con, novela_id))]


# --- RF3-GRD-01: un caso por nivel ----------------------------------------------------------------


@pytest.mark.parametrize(("intensidad", "vetados", "admitidos"), [
    ("atmosferico", ["sangre", "tortura", "sexo"], []),
    ("tension", ["tortura", "sexo"], ["sangre"]),
    ("intenso", ["sexo"], ["sangre", "tortura"]),
])
def test_cada_nivel_veta_lo_suyo(intensidad: str, vetados: list[str],
                                 admitidos: list[str]) -> None:
    con, _, nid = _novela(intensidad)
    for termino in vetados:
        assert _terminos(con, nid, f"Hubo {termino} en la cubierta.") == [termino], termino
    for termino in admitidos:
        assert _terminos(con, nid, f"Hubo {termino} en la cubierta.") == [], termino


def test_los_vetados_del_brief_valen_en_cualquier_nivel() -> None:
    con, _, nid = _novela("intenso")
    [h] = politica.buscar("Las arañas bajaban.", politica.reglas(con, nid))
    assert (h.regla.termino, h.regla.origen, h.forma) == ("arañas", "brief", "arañas")


def test_sin_brief_solo_lo_que_se_veta_en_todos_los_niveles() -> None:
    con, _ = nueva_bd()
    g = fabrica.novela_minima(con)
    assert _terminos(con, g.novela_id, "Sangre y sexo.") == ["sexo"]


def test_un_termino_de_la_novela_se_aplica_solo_a_ella() -> None:
    con, _ = nueva_bd()
    g = fabrica.novela_minima(con)
    con.execute("INSERT INTO termino_vetado (novela_id, termino) VALUES (?, 'tripa')",
                (g.novela_id,))
    [regla] = [r for r in politica.reglas(con, g.novela_id) if r.termino == "tripa"]
    assert regla.origen == "novela"
    otra = fabrica.novela_minima(con)
    assert "tripa" not in {r.termino for r in politica.reglas(con, otra.novela_id)}


# --- RF3-GRD-02: la busqueda --------------------------------------------------------------------


@pytest.mark.parametrize("texto", [
    "Había SANGRE en el suelo.",           # mayusculas
    "Los cadáveres flotaban.",             # tilde y plural
    "La san​gre goteaba.",            # espacio de ancho cero dentro de la palabra
])
def test_las_variantes_casan(texto: str) -> None:
    con, _, nid = _novela("atmosferico")
    assert _terminos(con, nid, texto)


def test_la_posicion_es_la_del_texto_original() -> None:
    con, _, nid = _novela("atmosferico")
    texto = "Al fondo, la san​gre goteaba."
    [h] = politica.buscar(texto, politica.reglas(con, nid))
    assert texto[h.inicio:h.fin] == "san​gre" == h.forma
    assert "goteaba" in h.fragmento


@pytest.mark.parametrize("texto", [
    "La tripulación esperaba.",            # subcadena de «tripa»
    "Era el sexto turno.",                 # subcadena de «sexo»
    "Lo hizo a sangre fría.",              # excepcion de «sangre»
])
def test_lo_que_no_es_el_termino_no_casa(texto: str) -> None:
    con, _, nid = _novela("atmosferico")
    con.execute("INSERT INTO termino_vetado (novela_id, termino) VALUES (?, 'tripa')", (nid,))
    assert _terminos(con, nid, texto) == []


def test_la_huella_cambia_con_la_politica() -> None:
    con, _, nid = _novela("tension")
    antes = politica.huella(politica.reglas(con, nid))
    assert politica.huella(politica.reglas(con, nid)) == antes
    con.execute("INSERT INTO termino_vetado (novela_id, termino) VALUES (?, 'bruma')", (nid,))
    assert politica.huella(politica.reglas(con, nid)) != antes


# --- RF3-GRD-03 y RF3-GRD-04: el recorrido entero -----------------------------------------------


def _redactor(veces_con_termino: int) -> Any:
    llevadas = {"n": 0}

    def redactar(entrada: str, agente: str) -> dict[str, Any]:
        salida = demo.redaccion(entrada, agente)
        if demo._capitulo(entrada) == 1 and llevadas["n"] < veces_con_termino:
            llevadas["n"] += 1
            salida["escenas"][0]["texto"] += " Tenía marcas de tortura en las muñecas."
        return salida

    return redactar


def test_un_termino_vetado_devuelve_el_capitulo_y_queda_registrado() -> None:
    con, ruta, nid = _novela("tension")
    puerto = puerto_falso(con)
    puerto.registrar("redaccion", _redactor(1))
    ctx = pipeline.Contexto(con=con, puerto=puerto, cfg=cfg_de(ruta), novela_id=nid)
    assert pipeline.avanzar(ctx) in ("completada", "completada_con_avisos")

    redacciones = [i["entrada"] for i in puerto.invocaciones
                   if i["agente"] == "redaccion" and demo._capitulo(i["entrada"]) == 1]
    assert len(redacciones) == 2
    assert "termino_vetado" in redacciones[1] and "tortura" in redacciones[1]
    [fila] = con.execute("SELECT * FROM decision_politica WHERE novela_id = ?", (nid,)).fetchall()
    assert (fila["capitulo"], fila["intento"], fila["termino"], fila["origen"], fila["accion"]) \
        == (1, 1, "tortura", "global", "reintentar")
    assert "muñecas" in fila["fragmento"]
    assert len(fila["huella_politica"]) == 64 and len(fila["huella_texto"]) == 64


def test_agotados_los_intentos_para_y_el_registro_sobrevive_a_la_reversion() -> None:
    con, ruta, nid = _novela("tension")
    puerto = puerto_falso(con)
    puerto.registrar("redaccion", _redactor(99))
    ctx = pipeline.Contexto(con=con, puerto=puerto, cfg=cfg_de(ruta), novela_id=nid)
    assert pipeline.avanzar(ctx) == "parada"
    assert fallo.paradas_abiertas(con, nid)[0]["tipo"] == "oficio"
    acciones = [f[0] for f in con.execute(
        "SELECT accion FROM decision_politica WHERE novela_id = ? ORDER BY intento", (nid,))]
    assert acciones == ["reintentar", "reintentar", "parar"]
    with transaccion(con):
        fallo.revertir_grafo(con, nid, 1, motivo="prueba")
    assert contar(con, "SELECT COUNT(*) FROM decision_politica WHERE novela_id = ?", nid) == 3
