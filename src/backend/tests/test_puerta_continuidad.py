"""Tests de la puerta 3 por mutacion (propiedades 6 y 7 del plan de verificacion).

El grafo de `fabrica.novela_minima` es correcto. Cada test introduce UNA contradiccion y
exige que la puerta la detecte; los dos ultimos exigen lo contrario, que no invente
conflictos donde hay una explicacion legitima (supersede_a y analepsis).
"""

from __future__ import annotations

import sqlite3
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

from compartido import db
from tareas.continuidad import puerta
from tests.fabrica import Grafo, hecho, novela_minima


@pytest.fixture()
def grafo() -> Iterator[tuple[sqlite3.Connection, Grafo]]:
    ruta = Path(tempfile.mkdtemp()) / "novela.db"
    con = db.preparar(ruta)
    con.execute("BEGIN")
    g = novela_minima(con)
    con.execute("COMMIT")
    yield con, g
    con.close()


def comprobaciones(con: sqlite3.Connection, g: Grafo, capitulo: int = 2) -> set[str]:
    resultado = puerta.evaluar(con, g.novela_id, capitulo)
    return {c.comprobacion for c in resultado.bloqueantes}


# --- El grafo limpio no produce conflictos ------------------------------------------------


def test_grafo_correcto_pasa(grafo: tuple[sqlite3.Connection, Grafo]) -> None:
    con, g = grafo
    assert db.verificar_integridad(con) == []
    for capitulo in (1, 2):
        resultado = puerta.evaluar(con, g.novela_id, capitulo)
        assert resultado.pasa, [str(c) for c in resultado.bloqueantes]


# --- Una mutacion por tipo de conflicto ----------------------------------------------------


def test_detecta_contradiccion_factual(grafo: tuple[sqlite3.Connection, Grafo]) -> None:
    con, g = grafo
    hecho(con, g, (2, 1), "Ibarra", "color de ojos", "azules", cita="los ojos azules")
    assert "continuidad_factual" in comprobaciones(con, g)


def test_detecta_conocimiento_no_adquirido(grafo: tuple[sqlite3.Connection, Grafo]) -> None:
    con, g = grafo
    # Reyes usa el hecho sin haberlo recibido nunca.
    con.execute(
        "INSERT INTO uso_conocimiento (novela_id, personaje_id, hecho_id, escena_id) "
        "VALUES (?,?,?,?)",
        (g.novela_id, g.personajes["Reyes"], g.hechos["ojos"], g.escenas[(2, 1)]),
    )
    assert "conocimiento_no_adquirido" in comprobaciones(con, g)


def test_detecta_personaje_muerto_que_reaparece(grafo: tuple[sqlite3.Connection, Grafo]) -> None:
    con, g = grafo
    con.execute(
        "INSERT INTO estado_personaje (novela_id, personaje_id, escena_id, condicion, "
        "salud_fisica) VALUES (?,?,?, 'muerto', 'fallecida por descompresion')",
        (g.novela_id, g.personajes["Ibarra"], g.escenas[(1, 2)]),
    )
    assert "presencia_imposible" in comprobaciones(con, g)


def test_detecta_dos_lugares_a_la_vez(grafo: tuple[sqlite3.Connection, Grafo]) -> None:
    """Simultaneo es el mismo orden interno, no la misma fecha."""
    con, g = grafo
    for orden in (1, 2):
        con.execute(
            "UPDATE evento SET fecha_interna = 'dia 3', orden_interno = 30 WHERE escena_id = ?",
            (g.escenas[(2, orden)],),
        )
    assert "presencia_imposible" in comprobaciones(con, g)


def test_misma_fecha_en_distinto_momento_no_es_ubicuidad(
    grafo: tuple[sqlite3.Connection, Grafo],
) -> None:
    """Dos escenas del mismo dia en sitios distintos son lo normal: el tiempo pasa."""
    con, g = grafo
    con.execute("UPDATE evento SET fecha_interna = 'dia 3', orden_interno = 30 WHERE escena_id = ?",
                (g.escenas[(2, 1)],))
    con.execute("UPDATE evento SET fecha_interna = 'dia 3', orden_interno = 31 WHERE escena_id = ?",
                (g.escenas[(2, 2)],))
    assert "presencia_imposible" not in comprobaciones(con, g)


def test_detecta_objeto_sin_traslado(grafo: tuple[sqlite3.Connection, Grafo]) -> None:
    con, g = grafo
    # La baliza aparece en la esclusa sin que nadie la haya movido alli.
    con.execute("UPDATE escena SET lugar_id = ? WHERE id = ?",
                (g.lugares["Esclusa"], g.escenas[(2, 2)]))
    con.execute("DELETE FROM estado_objeto WHERE escena_id = ?", (g.escenas[(2, 2)],))
    assert "objeto_sin_traslado" in comprobaciones(con, g)


def test_detecta_retroceso_temporal(grafo: tuple[sqlite3.Connection, Grafo]) -> None:
    con, g = grafo
    con.execute("UPDATE evento SET orden_interno = 0 WHERE escena_id = ?",
                (g.escenas[(2, 1)],))
    assert "coherencia_temporal" in comprobaciones(con, g)


def test_detecta_entidad_fuera_de_canon(grafo: tuple[sqlite3.Connection, Grafo]) -> None:
    con, g = grafo
    con.execute(
        "INSERT INTO entidad_no_reconocida (novela_id, escena_id, nombre, contexto) "
        "VALUES (?,?,'Doctor Vance','aparece sin estar en el paquete')",
        (g.novela_id, g.escenas[(2, 1)]),
    )
    # Aviso, no parada (RF2-PIPE-22).
    resultado = puerta.evaluar(con, g.novela_id, 2)
    assert "entidad_fuera_de_canon" in {c.comprobacion for c in resultado.conflictos if c.aviso}
    assert "entidad_fuera_de_canon" not in comprobaciones(con, g)


def test_estar_en_la_escena_donde_se_fija_el_hecho_es_saberlo(
    grafo: tuple[sqlite3.Connection, Grafo],
) -> None:
    """RF2-PIPE-21: Ibarra estaba en la escena 1.1, donde se fijo el hecho; Reyes no."""
    con, g = grafo
    con.execute(
        "INSERT INTO uso_conocimiento (novela_id, personaje_id, hecho_id, escena_id) "
        "VALUES (?,?,?,?)",
        (g.novela_id, g.personajes["Ibarra"], g.hechos["ojos"], g.escenas[(2, 1)]),
    )
    assert "conocimiento_no_adquirido" not in comprobaciones(con, g)


# --- Nada de falsos positivos --------------------------------------------------------------


def test_supersede_no_es_contradiccion(grafo: tuple[sqlite3.Connection, Grafo]) -> None:
    """Una herida que cicatriza no contradice la herida."""
    con, g = grafo
    hecho(con, g, (2, 1), "Ibarra", "color de ojos", "azules", supersede_a=g.hechos["ojos"])
    assert "continuidad_factual" not in comprobaciones(con, g)


def test_analepsis_no_es_retroceso_temporal(grafo: tuple[sqlite3.Connection, Grafo]) -> None:
    """Un flashback marcado no es un error de cronologia."""
    con, g = grafo
    con.execute("UPDATE evento SET orden_interno = 0 WHERE escena_id = ?",
                (g.escenas[(2, 1)],))
    con.execute("UPDATE escena SET analepsis = 1 WHERE id = ?", (g.escenas[(2, 1)],))
    assert "coherencia_temporal" not in comprobaciones(con, g)


def test_sorpresa_repetida_es_aviso_y_no_para(grafo: tuple[sqlite3.Connection, Grafo]) -> None:
    con, g = grafo
    con.execute(
        "INSERT INTO estado_conocimiento (novela_id, personaje_id, hecho_id, escena_id, postura,"
        " via) VALUES (?,?,?,?, 'sabe','se_lo_contaron')",
        (g.novela_id, g.personajes["Kowalski"], g.hechos["ojos"], g.escenas[(2, 1)]),
    )
    resultado = puerta.evaluar(con, g.novela_id, 2)
    assert resultado.pasa, "una sorpresa repetida es aviso, no debe parar el pipeline"
    assert any(c.comprobacion == "sorpresa_imposible" for c in resultado.avisos)


# --- El indice no cambia ningun veredicto (propiedad 25) -----------------------------------


def test_puerta_no_depende_del_indice(grafo: tuple[sqlite3.Connection, Grafo]) -> None:
    """Ningun veredicto de puerta cambia si el indice vectorial esta o no."""
    from compartido.vectores import Indice

    con, g = grafo
    sin_indice = {c.comprobacion for c in puerta.evaluar(con, g.novela_id, 2).conflictos}
    con.execute("BEGIN")
    Indice(con, modelo="hash")
    con.execute("COMMIT")
    con_indice = {c.comprobacion for c in puerta.evaluar(con, g.novela_id, 2).conflictos}
    assert sin_indice == con_indice


# --- spec2, fase 5: sin falsos positivos ni puntos muertos --------------------------------


def test_una_cadena_de_tres_supersesiones_no_es_contradiccion(
    grafo: tuple[sqlite3.Connection, Grafo],
) -> None:
    """grises -> azules -> verdes -> negros: cada eslabon sustituye al anterior."""
    con, g = grafo
    previo = g.hechos["ojos"]
    for escena, valor in (((1, 2), "azules"), ((2, 1), "verdes"), ((2, 2), "negros")):
        previo = hecho(con, g, escena, "Ibarra", "color de ojos", valor, supersede_a=previo)
    assert "continuidad_factual" not in comprobaciones(con, g, 1)
    assert "continuidad_factual" not in comprobaciones(con, g, 2)


@pytest.mark.parametrize(
    ("antes", "despues"),
    [
        ("Ámbar", "ámbar"), ("ÑANDÚ", "ñandú"), ("gris  claro ", "Gris claro"),
        ("Pingüino", "pinguino"),
    ],
)
def test_mayusculas_tildes_y_espacios_no_cambian_el_valor(
    grafo: tuple[sqlite3.Connection, Grafo], antes: str, despues: str
) -> None:
    con, g = grafo
    hecho(con, g, (1, 1), "Reyes", "color de pelo", antes)
    hecho(con, g, (2, 1), "Reyes", "color de pelo", despues)
    assert "continuidad_factual" not in comprobaciones(con, g)


def test_la_ene_es_una_letra_y_si_distingue(grafo: tuple[sqlite3.Connection, Grafo]) -> None:
    con, g = grafo
    hecho(con, g, (1, 1), "Reyes", "apodo", "Peña")
    hecho(con, g, (2, 1), "Reyes", "apodo", "Pena")
    assert "continuidad_factual" in comprobaciones(con, g)


def test_cada_par_contradictorio_se_informa_una_vez(
    grafo: tuple[sqlite3.Connection, Grafo],
) -> None:
    """Dos valores nuevos en la misma escena chocan con el antiguo y entre si: tres pares."""
    con, g = grafo
    hecho(con, g, (2, 1), "Ibarra", "color de ojos", "azules")
    hecho(con, g, (2, 1), "Ibarra", "color de ojos", "verdes")
    pares = [
        frozenset((c.datos["hecho_nuevo_id"], c.datos["hecho_previo_id"]))
        for c in puerta.evaluar(con, g.novela_id, 2).bloqueantes
        if c.comprobacion == "continuidad_factual"
    ]
    assert len(pares) == 3
    assert len(set(pares)) == 3


def _condicion(con: sqlite3.Connection, g: Grafo, escena: tuple[int, int], cual: str) -> None:
    con.execute(
        "INSERT INTO estado_personaje (novela_id, personaje_id, escena_id, condicion) "
        "VALUES (?,?,?,?)", (g.novela_id, g.personajes["Ibarra"], g.escenas[escena], cual),
    )


def test_la_ultima_condicion_manda(grafo: tuple[sqlite3.Connection, Grafo]) -> None:
    """Un desaparecido que aparece vivo puede volver; uno que sigue muerto, no."""
    con, g = grafo
    _condicion(con, g, (1, 1), "desaparecido")
    _condicion(con, g, (1, 2), "vivo")
    assert "presencia_imposible" not in comprobaciones(con, g)

    _condicion(con, g, (1, 2), "muerto")
    assert "presencia_imposible" in comprobaciones(con, g)


def test_la_muerte_no_impide_una_analepsis(grafo: tuple[sqlite3.Connection, Grafo]) -> None:
    con, g = grafo
    _condicion(con, g, (1, 2), "muerto")
    con.execute("UPDATE escena SET analepsis = 1 WHERE capitulo_id = ?", (g.capitulos[2],))
    assert "presencia_imposible" not in comprobaciones(con, g)


def test_un_hecho_revocado_no_contradice(grafo: tuple[sqlite3.Connection, Grafo]) -> None:
    con, g = grafo
    hecho(con, g, (2, 1), "Ibarra", "color de ojos", "azules")
    assert "continuidad_factual" in comprobaciones(con, g)
    con.execute(
        "INSERT INTO hecho_revocacion (novela_id, hecho_id, capitulo, motivo) "
        "VALUES (?,?,2,'retcon')", (g.novela_id, g.hechos["ojos"]),
    )
    assert "continuidad_factual" not in comprobaciones(con, g)


def test_el_extractor_recibe_el_ultimo_orden_interno() -> None:
    """Para seguir la escala tiene que saber donde va (RF2-PIPE-10)."""
    import config
    from compartido.contexto import Presupuesto
    from tareas.extraccion import servicio

    ruta = Path(tempfile.mkdtemp()) / "novela.db"
    con = db.preparar(ruta)
    con.execute("BEGIN")
    g = novela_minima(con)
    con.execute("COMMIT")
    paquete = servicio.paquete(
        con, g.novela_id, 2, {1: "texto"},
        presupuesto=Presupuesto(bloques=config.PRESUPUESTO_BLOQUES,
                                techo=config.PRESUPUESTO_PAQUETE),
    )
    assert "El ultimo orden_interno registrado en la novela es 4" in paquete.render()


# --- RF2-PIPE-26: un lugar y los que contiene son el mismo sitio -----------------------------


def test_un_objeto_que_pasa_a_un_lugar_contenido_no_se_ha_movido(
    grafo: tuple[sqlite3.Connection, Grafo],
) -> None:
    """La baliza esta en el modulo de carga y aparece en la esclusa, que esta DENTRO."""
    con, g = grafo
    con.execute("UPDATE escena SET lugar_id = ? WHERE id = ?",
                (g.lugares["Esclusa"], g.escenas[(2, 2)]))
    con.execute("DELETE FROM estado_objeto WHERE escena_id = ?", (g.escenas[(2, 2)],))
    con.execute("UPDATE lugar SET dentro_de_id = ? WHERE id = ?",
                (g.lugares["Modulo de carga"], g.lugares["Esclusa"]))
    assert "objeto_sin_traslado" not in comprobaciones(con, g)
    # Sin la contencion, el mismo grafo si para: es la comprobacion la que cambia.
    con.execute("UPDATE lugar SET dentro_de_id = NULL")
    assert "objeto_sin_traslado" in comprobaciones(con, g)


def test_estar_a_la_vez_en_un_lugar_y_en_otro_que_contiene_no_es_ubicuidad(
    grafo: tuple[sqlite3.Connection, Grafo],
) -> None:
    con, g = grafo
    for escena in ((2, 1), (2, 2)):  # Puente y Modulo de carga, en el mismo momento
        con.execute("UPDATE evento SET orden_interno = 30 WHERE escena_id = ?",
                    (g.escenas[escena],))
    assert "presencia_imposible" in comprobaciones(con, g)
    con.execute("UPDATE lugar SET dentro_de_id = ? WHERE id = ?",
                (g.lugares["Puente"], g.lugares["Modulo de carga"]))
    assert "presencia_imposible" not in comprobaciones(con, g)


# --- RF2-PIPE-27: entre capitulos, lo que sabe la faccion lo sabe cada miembro ----------------


def _misma_faccion(con: sqlite3.Connection, g: Grafo, *nombres: str) -> None:
    from compartido.grafo import insertar

    faccion = insertar(con, "faccion", novela_id=g.novela_id, nombre="La cuadrilla")
    for nombre in nombres:
        con.execute("UPDATE personaje SET faccion_id = ? WHERE id = ?",
                    (faccion, g.personajes[nombre]))


def _usa_reyes_los_ojos(con: sqlite3.Connection, g: Grafo, escena: tuple[int, int]) -> None:
    con.execute(
        "INSERT INTO uso_conocimiento (novela_id, personaje_id, hecho_id, escena_id) "
        "VALUES (?,?,?,?)",
        (g.novela_id, g.personajes["Reyes"], g.hechos["ojos"], g.escenas[escena]),
    )


def test_lo_que_sabia_la_faccion_en_un_capitulo_anterior_lo_sabe_el_miembro(
    grafo: tuple[sqlite3.Connection, Grafo],
) -> None:
    """Los ojos se fijan en la escena 1.1, con Ibarra delante; Reyes los usa en el capitulo 2."""
    con, g = grafo
    _usa_reyes_los_ojos(con, g, (2, 1))
    assert "conocimiento_no_adquirido" in comprobaciones(con, g)
    _misma_faccion(con, g, "Reyes", "Ibarra")
    assert "conocimiento_no_adquirido" not in comprobaciones(con, g)


def test_dentro_del_mismo_capitulo_la_faccion_no_transmite(
    grafo: tuple[sqlite3.Connection, Grafo],
) -> None:
    """Un hecho fijado en la escena 2.1 con Ibarra delante no llega a Reyes en la 2.2."""
    con, g = grafo
    nuevo = hecho(con, g, (2, 1), "Kowalski", "cicatriz", "en la ceja", cita="la cicatriz")
    con.execute(
        "INSERT INTO uso_conocimiento (novela_id, personaje_id, hecho_id, escena_id) "
        "VALUES (?,?,?,?)", (g.novela_id, g.personajes["Reyes"], nuevo, g.escenas[(2, 2)]),
    )
    _misma_faccion(con, g, "Reyes", "Ibarra")
    assert "conocimiento_no_adquirido" in comprobaciones(con, g)


# --- RF2-PIPE-28: el objeto viaja con su poseedor ----------------------------------------------


def test_un_objeto_que_lleva_alguien_viaja_con_el(grafo: tuple[sqlite3.Connection, Grafo]) -> None:
    """La baliza aparece en la esclusa sin traslado; si la llevaba Kowalski, que esta, no para."""
    con, g = grafo
    con.execute("UPDATE escena SET lugar_id = ? WHERE id = ?",
                (g.lugares["Esclusa"], g.escenas[(2, 2)]))
    con.execute("DELETE FROM estado_objeto WHERE escena_id = ?", (g.escenas[(2, 2)],))
    assert "objeto_sin_traslado" in comprobaciones(con, g)
    con.execute("UPDATE estado_objeto SET poseedor_id = ? WHERE objeto_id = ?",
                (g.personajes["Kowalski"], g.objetos["Baliza"]))
    assert "objeto_sin_traslado" not in comprobaciones(con, g)
    # Si el poseedor no esta en la escena, vuelve a parar.
    con.execute("DELETE FROM escena_personaje WHERE escena_id = ? AND personaje_id = ?",
                (g.escenas[(2, 2)], g.personajes["Kowalski"]))
    con.execute("UPDATE escena SET pov_id = ? WHERE id = ?",
                (g.personajes["Ibarra"], g.escenas[(2, 2)]))
    assert "objeto_sin_traslado" in comprobaciones(con, g)


# --- RF2-PIPE-29: romper un habito es aviso, no conflicto ------------------------------------


def test_cambiar_el_valor_de_una_conducta_es_aviso(grafo: tuple[sqlite3.Connection, Grafo]) -> None:
    con, g = grafo
    hecho(con, g, (1, 1), "Ibarra", "ritual de entrada", "cuenta hasta cuatro", cita="cuatro")
    hecho(con, g, (2, 1), "Ibarra", "ritual de entrada", "no conto", cita="no conto")
    assert "continuidad_factual" in comprobaciones(con, g)
    con.execute(
        "INSERT INTO atributo_conducta (novela_id, escena_id, sujeto_clave, atributo_clave) "
        "VALUES (?, ?, 'ibarra', 'ritual de entrada')", (g.novela_id, g.escenas[(1, 1)]),
    )
    assert "continuidad_factual" not in comprobaciones(con, g)
    avisos = {c.comprobacion for c in puerta.evaluar(con, g.novela_id, 2).conflictos if c.aviso}
    assert "continuidad_factual" in avisos


# --- RF2-PIPE-30: quien actua en una escena esta en ella ----------------------------------------


def test_quien_actua_en_la_escena_esta_en_ella_aunque_no_estuviera_en_el_reparto(
    grafo: tuple[sqlite3.Connection, Grafo],
) -> None:
    """Un dato se fija en la 2.1, donde la escaleta no puso a Reyes, y Reyes lo usa ALLI."""
    con, g = grafo
    nuevo = hecho(con, g, (2, 1), "Kowalski", "pozo", "metro diez", cita="metro diez")
    con.execute(
        "INSERT INTO uso_conocimiento (novela_id, personaje_id, hecho_id, escena_id) "
        "VALUES (?,?,?,?)", (g.novela_id, g.personajes["Reyes"], nuevo, g.escenas[(2, 2)]),
    )
    assert "conocimiento_no_adquirido" in comprobaciones(con, g)
    # Si Reyes actua en la 2.1 (aqui, un estado registrado alli), estaba cuando se dijo.
    con.execute(
        "INSERT INTO estado_personaje (novela_id, personaje_id, escena_id, condicion) "
        "VALUES (?,?,?, 'vivo')", (g.novela_id, g.personajes["Reyes"], g.escenas[(2, 1)]),
    )
    assert "conocimiento_no_adquirido" not in comprobaciones(con, g)
