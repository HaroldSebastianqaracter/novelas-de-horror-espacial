"""Lo que enseño la primera pasada real (specs/spec3.md, 3.11: RF3-PAS-01 a RF3-PAS-06).

Los casos salen de la pasada del 23 de septiembre sobre `novela_real.db`: un valor compuesto
que el extractor guardo tal cual, la variante de un lugar del canon, el nombre del propio mundo
tomado por entidad desconocida y un nombre menor que avisaba en cada capitulo.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

import pytest
from pydantic import ValidationError

from compartido.grafo import Resolvedor, clave_laxa
from compartido.puerto import demo
from orquestador import pipeline
from tareas.extraccion.esquemas import PALABRAS_RESUMEN, PALABRAS_VALOR, SalidaExtraccion
from tests import fabrica
from tests.entorno import contexto, crear_novela, nueva_bd, puerto_falso

#: Un valor real de la pasada: doce palabras con tres datos dentro.
COMPUESTO = "doce por minuto, saturacion en ochenta y uno, once minutos hasta confusion"


def _salida(*valores: str) -> dict[str, Any]:
    return {
        "hechos": [
            {"escena_orden": 1, "sujeto_tipo": "personaje", "sujeto_ref": "Trebo",
             "atributo": f"dato {i}", "valor": v}
            for i, v in enumerate(valores)
        ],
        "resumen": "La cuadrilla entra en el anillo y encuentra la sala vacia.",
        "resumen_breve": "Entran en el anillo.",
    }


# --- RF3-PAS-01: un hecho, un dato ---------------------------------------------------------------


def test_un_valor_compuesto_se_rechaza_y_el_error_los_lista_todos() -> None:
    with pytest.raises(ValidationError) as error:
        SalidaExtraccion.model_validate(_salida("grises", COMPUESTO, COMPUESTO + " y mas"))
    mensaje = str(error.value)
    assert "«Trebo: dato 1» (12 palabras)" in mensaje
    assert "«Trebo: dato 2» (14 palabras)" in mensaje
    assert "«Trebo: dato 0»" not in mensaje


def test_diez_palabras_pasan_y_once_no() -> None:
    assert PALABRAS_VALOR == 10
    diez = " ".join(["palabra"] * 10)
    assert SalidaExtraccion.model_validate(_salida("doce por minuto", diez)).hechos[1].valor == diez
    with pytest.raises(ValidationError, match="11 palabras"):
        SalidaExtraccion.model_validate(_salida(diez + " mas"))


def test_el_esquema_que_recibe_el_agente_declara_el_limite() -> None:
    esquema = json.dumps(SalidaExtraccion.model_json_schema(), ensure_ascii=False)
    assert f"{PALABRAS_VALOR} palabras como mucho" in esquema
    assert "{0,9}" in esquema


# --- RF3-PAS-02: el resumen --------------------------------------------------------------------


def test_el_esquema_pide_un_resumen_mas_corto_que_el_limite() -> None:
    esquema = json.dumps(SalidaExtraccion.model_json_schema(), ensure_ascii=False)
    assert "unas 160 palabras" in esquema
    # El recorte actua por encima de 250, no de 200 (el test de test_deuda.py deriva de aqui).
    largo = "La cuadrilla avanza. " * 90  # 270 palabras
    assert PALABRAS_RESUMEN == 250
    resumen = SalidaExtraccion.model_validate({**_salida(), "resumen": largo}).resumen
    assert len(resumen.split()) == 249


# --- RF3-PAS-04: variantes de un nombre del canon -----------------------------------------------


def test_la_clave_laxa_ignora_puntuacion_articulos_y_preposiciones() -> None:
    assert clave_laxa("Bodega fría del sector 7") == clave_laxa("Bodega fría, sector 7")
    assert clave_laxa("la Operadora") == clave_laxa("la operadora") == "operadora"
    assert clave_laxa("Malla-3") == "malla 3"
    # La eñe sigue siendo una letra.
    assert clave_laxa("Peña") != clave_laxa("Pena")


def test_una_letra_designa_y_no_se_quita() -> None:
    """Hallazgo del validador: con «a» e «y» como palabras vacias, tres sitios eran uno."""
    claves = {clave_laxa(n) for n in ("Anillo A", "Anillo Y", "Anillo")}
    assert len(claves) == 3
    con, _ = nueva_bd()
    g = fabrica.novela_minima(con)
    assert Resolvedor(con, g.novela_id).id_de("lugar", "Puente A") is None


def test_el_resolvedor_acepta_una_variante_solo_si_no_es_ambigua() -> None:
    con, _ = nueva_bd()
    g = fabrica.novela_minima(con)
    r = Resolvedor(con, g.novela_id)
    assert r.id_de("lugar", "el modulo de la carga") == g.lugares["Modulo de carga"]
    assert r.por_variante == [("lugar", "el modulo de la carga")]
    # Dos lugares con la misma clave laxa: no decide por su cuenta.
    con.execute(
        "INSERT INTO lugar (novela_id, mundo_id, nombre, nombre_clave) "
        "SELECT novela_id, mundo_id, 'Modulo, carga', 'modulo, carga' FROM lugar WHERE id = ?",
        (g.lugares["Puente"],),
    )
    assert Resolvedor(con, g.novela_id).id_de("lugar", "el modulo de la carga") is None


# --- RF3-PAS-03 a RF3-PAS-06: los nombres menores sobre la demo ---------------------------------


@pytest.fixture(scope="module")
def demo_con_nombres() -> tuple[sqlite3.Connection, int, list[dict[str, Any]]]:
    """El capitulo 1 inventa nombres como en la pasada real; el 2 repite uno y trae dos nuevos,
    uno de ellos parecido a un lugar del canon («Puente A» no es «Puente»)."""
    por_capitulo = {
        1: ["Estacion Cerro Quince", "Berila IV", "berila iv", "Modulo, carga"],
        2: ["Berila IV", "Malla-3", "Puente A"],
    }

    def extraccion(entrada: str, agente: str) -> dict[str, Any]:
        salida = demo.extraccion(entrada, agente)
        salida["entidades_no_reconocidas"] = [
            {"escena_orden": 1, "nombre": n} for n in por_capitulo.get(demo._capitulo(entrada), [])
        ]
        return salida

    con, ruta = nueva_bd()
    novela_id = crear_novela(con)
    puerto = puerto_falso(con)
    puerto.registrar("extraccion", extraccion)
    assert pipeline.avanzar(contexto(con, puerto, ruta, novela_id)) == "completada"
    return con, novela_id, puerto.invocaciones


def test_solo_se_registran_los_nombres_que_no_son_del_canon_ni_repetidos(
    demo_con_nombres: tuple[sqlite3.Connection, int, list[dict[str, Any]]],
) -> None:
    con, _, _ = demo_con_nombres
    registrados = [
        (int(f[0]), str(f[1])) for f in con.execute(
            "SELECT eo.capitulo_numero, en.nombre FROM entidad_no_reconocida en "
            "JOIN escena_ordinal eo ON eo.escena_id = en.escena_id ORDER BY en.id"
        )
    ]
    # El mundo, la variante del lugar y la repeticion con minuscula no entran.
    assert registrados == [
        (1, "Berila IV"), (2, "Berila IV"), (2, "Malla-3"), (2, "Puente A"),
    ]
    correcciones = [json.loads(f[0]).get("correcciones") for f in con.execute(
        "SELECT payload FROM traza_evento WHERE tipo = 'extraccion_descartes' "
        "AND json_extract(payload, '$.capitulo') = 1"
    )]
    assert correcciones[0]["entidad_del_canon"] == 2
    assert correcciones[0]["entidad_repetida"] == 1
    # Comprobar el canon no pasa por el resolvedor: no cuenta dos veces en la traza.
    assert "nombre_por_variante" not in correcciones[0]


def test_un_nombre_menor_solo_avisa_la_primera_vez(
    demo_con_nombres: tuple[sqlite3.Connection, int, list[dict[str, Any]]],
) -> None:
    con, novela_id, _ = demo_con_nombres
    avisos: dict[int, list[str]] = {}
    for f in con.execute(
        "SELECT capitulo, detalle FROM resultado_puerta WHERE novela_id = ? AND puerta = 3",
        (novela_id,),
    ):
        avisos[int(f[0])] = [
            c["datos"]["nombre"] for c in json.loads(f[1])["conflictos"]
            if c["comprobacion"] == "entidad_fuera_de_canon"
        ]
    assert avisos[1] == ["Berila IV"]
    assert avisos[2] == ["Malla-3", "Puente A"]


def test_el_redactor_y_el_extractor_reciben_los_nombres_menores_y_el_mundo(
    demo_con_nombres: tuple[sqlite3.Connection, int, list[dict[str, Any]]],
) -> None:
    _, _, invocaciones = demo_con_nombres

    def entradas(agente: str, capitulo: int) -> list[str]:
        return [i["entrada"] for i in invocaciones
                if i["agente"] == agente and demo._capitulo(i["entrada"]) == capitulo]

    for agente in ("redaccion", "extraccion"):
        assert all("Berila IV" not in e for e in entradas(agente, 1)), agente
        assert all("Berila IV" in e for e in entradas(agente, 2)), agente
        assert all("Malla-3" in e for e in entradas(agente, 3)), agente
    assert all("Estacion Cerro Quince" in e for e in entradas("extraccion", 1))
