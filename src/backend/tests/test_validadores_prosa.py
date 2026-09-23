"""Los validadores deterministas de la prosa (specs/spec3.md, 3.6: RF3-VAL-01 a RF3-VAL-03).

Tres errores que el lector de un regalo ve: su nombre sin la tilde, un allegado que la escaleta
prometio y no sale, y un capitulo de longitud impropia. Los dos primeros devuelven el capitulo
al redactor desde la parte mecanica de la puerta 4; el tercero es un aviso.
"""

from __future__ import annotations

import re
import sqlite3
from typing import Any

import pytest

from compartido.grafo import insertar, normalizar
from compartido.puerto import demo
from orquestador import pipeline
from tareas.oficio import puerta as p_oficio
from tests import fabrica
from tests.entorno import cfg_de, nueva_bd, puerto_falso
from tests.test_personalizacion import crear


def _con_personaje(nombre: str) -> tuple[sqlite3.Connection, fabrica.Grafo]:
    con, _ = nueva_bd()
    g = fabrica.novela_minima(con)
    insertar(con, "personaje", novela_id=g.novela_id, nombre=nombre,
             nombre_clave=normalizar(nombre), rol_narrativo="aliado", tipo_arco="plano")
    return con, g


def _mecanica(con: sqlite3.Connection, g: fabrica.Grafo, texto: str) -> dict[str, Any]:
    r = p_oficio.evaluar(con, g.novela_id, 2, texto)
    return {c.comprobacion: c for c in r.conflictos}


# --- RF3-VAL-01 ---------------------------------------------------------------------------------


def test_un_nombre_sin_su_tilde_devuelve_el_capitulo() -> None:
    con, g = _con_personaje("Sebastián Núñez")
    conflictos = _mecanica(con, g, "Sebastian abrio la escotilla. Luego hablo con Nunez y con "
                                   "Núñez, que era el mismo.")
    c = conflictos["nombre_mal_escrito"]
    assert not c.aviso
    assert {(e["escrito"], e["canon"]) for e in c.datos["errores"]} == {
        ("Sebastian", "Sebastián"), ("Nunez", "Núñez")}
    assert "«Sebastian» (1 vez/veces) se escribe «Sebastián»" in c.descripcion


@pytest.mark.parametrize("texto", [
    # Bien escrito, tambien en mayusculas.
    "Sebastián abrio la escotilla y NÚÑEZ grito.",
    # En minuscula no es el nombre.
    "Dijo que un tal sebastian no existia.",
])
def test_lo_bien_escrito_no_para(texto: str) -> None:
    con, g = _con_personaje("Sebastián Núñez")
    assert "nombre_mal_escrito" not in _mecanica(con, g, texto)


def test_al_empezar_frase_una_palabra_corta_no_es_un_nombre_mal_escrito() -> None:
    """«Más» al empezar frase y el apellido «Mas» solo se distinguen por la tilde."""
    con, g = _con_personaje("Jordi Mas")
    assert "nombre_mal_escrito" not in _mecanica(con, g, "Más tarde llego Mas. —Más aire.")
    # A mitad de frase si se mira.
    assert "nombre_mal_escrito" in _mecanica(con, g, "Llego Más con el casco.")


# --- RF3-VAL-02 ---------------------------------------------------------------------------------


def test_la_longitud_real_fuera_del_rango_es_un_aviso() -> None:
    con, g = _con_personaje("Otro")
    insertar(con, "restriccion", novela_id=g.novela_id, tipo="longitud_capitulo_palabras",
             valor="10-20")
    corto = _mecanica(con, g, "Cinco palabras nada mas aqui.")
    assert corto["longitud_real"].aviso
    assert corto["longitud_real"].datos == {"palabras": 5, "minimo": 10, "maximo": 20}
    assert "longitud_real" not in _mecanica(con, g, " ".join(["palabra"] * 15))
    assert "longitud_real" in _mecanica(con, g, " ".join(["palabra"] * 21))


# --- RF3-VAL-03 ---------------------------------------------------------------------------------


def test_un_allegado_planificado_que_la_prosa_no_nombra_vuelve_al_redactor() -> None:
    con, ruta = nueva_bd()
    novela_id = crear(con, ruta)
    puerto = puerto_falso(con)
    olvidado: list[int] = []

    def redactor_olvidadizo(entrada: str, agente: str) -> dict[str, Any]:
        """En el primer capitulo con un allegado, la primera vez se lo deja fuera."""
        salida = demo.redaccion(entrada, agente)
        if not olvidado and re.search(r"ALL\d+: ", entrada):
            olvidado.append(demo._capitulo(entrada))
            for e in salida["escenas"]:
                e["texto"] = re.sub(r" [^.]+ esperaba al otro lado\.", "", e["texto"])
        return salida

    puerto.registrar("redaccion", redactor_olvidadizo)
    ctx = pipeline.Contexto(con=con, puerto=puerto, cfg=cfg_de(ruta), novela_id=novela_id)
    final = pipeline.avanzar(ctx)
    assert final in ("completada", "completada_con_avisos"), final
    capitulo = olvidado[0]
    fallos = [str(f["detalle"]) for f in con.execute(
        "SELECT detalle FROM resultado_puerta WHERE novela_id = ? AND puerta = 4 "
        "AND capitulo = ? ORDER BY id", (novela_id, capitulo))]
    assert "allegado_ausente" in fallos[0]
    assert "allegado_ausente" not in fallos[-1]
    redacciones = [i["entrada"] for i in puerto.invocaciones
                   if i["agente"] == "redaccion" and demo._capitulo(i["entrada"]) == capitulo]
    assert len(redacciones) == 2
    assert "allegado_ausente" in redacciones[1]


def test_sin_brief_no_se_buscan_allegados() -> None:
    con, g = _con_personaje("Otro")
    assert p_oficio._allegados_ausentes(con, g.novela_id, 2, "Nadie.") == []
