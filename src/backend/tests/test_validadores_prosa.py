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

from compartido.grafo import insertar, lectura, normalizar
from compartido.puerto import demo
from compartido.texto import nombra
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


def test_un_nombre_sin_su_tilde_a_mitad_de_frase_devuelve_el_capitulo() -> None:
    con, g = _con_personaje("Sebastián Núñez")
    conflictos = _mecanica(con, g, "Luego hablo con Nunez y con Núñez, que era el mismo, y con "
                                   "Sebastian.")
    c = conflictos["nombre_mal_escrito"]
    assert not c.aviso
    assert {(e["escrito"], e["canon"]) for e in c.datos["errores"]} == {
        ("Nunez", "«Núñez»"), ("Sebastian", "«Sebastián»")}
    assert "«Nunez» (1 vez) se escribe «Núñez»" in c.descripcion


@pytest.mark.parametrize("texto", [
    # Bien escrito, tambien en mayusculas.
    "Sebastián abrio la escotilla y NÚÑEZ grito.",
    # En minuscula no es el nombre.
    "Dijo que un tal sebastian no existia.",
])
def test_lo_bien_escrito_no_para(texto: str) -> None:
    con, g = _con_personaje("Sebastián Núñez")
    conflictos = _mecanica(con, g, texto)
    assert "nombre_mal_escrito" not in conflictos and "nombre_por_revisar" not in conflictos


@pytest.mark.parametrize(("nombre", "texto"), [
    ("Jordi Mas", "Más tarde llego."),
    ("Elena Cortés", "Elena grito. Cortes profundos le cruzaban los brazos."),
    # Validador de 469d64d: aperturas que el primer patron no reconocia.
    ("Jordi Mas", "Espero un rato… Más tarde llego."),
    ("Jordi Mas", "“¿Vienes?” Más tarde lo supo."),
    ("Jordi Mas", "- Más aire -dijo."),
    ("Jordi Mas", "–Más aire –dijo."),
    ("Jordi Mas", "Respiro. *Más cerca*, penso."),
    ("Lucía Peña", "“Pena es lo que me das”, dijo."),
])
def test_al_empezar_frase_solo_avisa(nombre: str, texto: str) -> None:
    """Ahi puede ser una palabra corriente, y «corregirla» le pediria al redactor una falta."""
    con, g = _con_personaje(nombre)
    conflictos = _mecanica(con, g, texto)
    assert "nombre_mal_escrito" not in conflictos
    assert conflictos["nombre_por_revisar"].aviso


def test_el_nombre_del_destinatario_al_empezar_frase_si_devuelve_el_capitulo() -> None:
    """Validador de bfb95a3: es el error mas visible del regalo. Si la palabra no sale nunca en
    minuscula en el capitulo, no es una palabra corriente."""
    con, ruta = nueva_bd()
    nid = crear(con, ruta)  # la destinataria del brief de ejemplo lleva tilde y eñe
    pipeline.planificar(pipeline.Contexto(con=con, puerto=puerto_falso(con), cfg=cfg_de(ruta),
                                          novela_id=nid))
    brief = lectura.brief(con, nid)
    assert brief is not None
    nombre = brief.destinatario.nombre.split()[-1]
    sin_tilde = p_oficio._plano(nombre).capitalize()
    assert sin_tilde != nombre
    r = {c.comprobacion: c for c in p_oficio.evaluar(
        con, nid, 1, f"—{sin_tilde}, ven —dijo ella. Luego se fue.").conflictos}
    assert "nombre_mal_escrito" in r


def test_tras_dos_puntos_una_mayuscula_es_un_nombre() -> None:
    con, g = _con_personaje("Sebastián Núñez")
    assert "nombre_mal_escrito" in _mecanica(con, g, "Llego tarde: Sebastian no estaba.")


@pytest.mark.parametrize("texto", [
    "Le dijo: «Tomas el primer turno».",
    "Le dijo: —Tomas el primer turno.",
])
def test_tras_dos_puntos_que_abren_cita_o_dialogo_es_inicio_de_frase(texto: str) -> None:
    """Validador de a5d0355: ahi va mayuscula, y «Tomas» puede ser el verbo."""
    con, g = _con_personaje("Tomás Ruiz")
    conflictos = _mecanica(con, g, texto)
    assert "nombre_mal_escrito" not in conflictos and "nombre_por_revisar" in conflictos


def test_el_nombre_del_destinatario_que_sale_en_minuscula_solo_avisa() -> None:
    """Si la palabra sale en minuscula en el capitulo, es una palabra corriente."""
    con, ruta = nueva_bd()
    nid = crear(con, ruta)
    pipeline.planificar(pipeline.Contexto(con=con, puerto=puerto_falso(con), cfg=cfg_de(ruta),
                                          novela_id=nid))
    brief = lectura.brief(con, nid)
    assert brief is not None
    sin_tilde = p_oficio._plano(brief.destinatario.nombre.split()[-1])
    texto = f"{sin_tilde.capitalize()} de nuevo. Dijo {sin_tilde} sin pensar."
    conflictos = {c.comprobacion for c in p_oficio.evaluar(con, nid, 1, texto).conflictos}
    assert "nombre_mal_escrito" not in conflictos and "nombre_por_revisar" in conflictos


def test_una_forma_que_devuelve_el_capitulo_cuenta_todas_sus_veces() -> None:
    con, g = _con_personaje("Sebastián Núñez")
    c = _mecanica(con, g, "Sebastian abrio. Luego miro a Sebastian.")["nombre_mal_escrito"]
    assert c.datos["errores"][0]["veces"] == 2
    assert "nombre_por_revisar" not in _mecanica(con, g, "Sebastian abrio. Luego miro a Sebastian.")


def test_dos_grafias_del_canon_se_ofrecen_las_dos() -> None:
    con, g = _con_personaje("Ángel Ruiz")
    insertar(con, "personaje", novela_id=g.novela_id, nombre="Angel Mora",
             nombre_clave=normalizar("Angel Mora"), rol_narrativo="aliado", tipo_arco="plano")
    conflictos = _mecanica(con, g, "Llego Ángel, y despues Angel, y luego ÁNGEL, y al final Àngel.")
    [error] = conflictos["nombre_mal_escrito"].datos["errores"]
    assert error == {"escrito": "Àngel", "canon": "«Angel» o «Ángel»", "veces": 1}


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


@pytest.mark.parametrize(("nombre", "texto", "nombrado"), [
    ("Nala", "Nala ladro dos veces.", True),
    ("Nala Pérez", "Pérez no contesto.", True),
    # Validador de 469d64d: una particula o una palabra corriente no nombran a nadie.
    ("Pedro del Río", "El tunel del sector seguia a oscuras.", False),
    ("María de los Ángeles", "Los paneles fallaban.", False),
    ("Luz", "La luz parpadeo.", False),
    ("Luz", "Luz entro sin avisar.", True),
    ("Abuela Carmen", "La abuela de alguien.", False),
])
def test_nombrar_a_un_allegado(nombre: str, texto: str, nombrado: bool) -> None:
    assert nombra(texto, nombre) is nombrado


def test_sin_brief_no_se_buscan_allegados() -> None:
    con, g = _con_personaje("Otro")
    assert p_oficio._allegados_ausentes(con, g.novela_id, 2, "Nadie.") == []
