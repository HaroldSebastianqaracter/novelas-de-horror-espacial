"""La demo ejercita de verdad la puerta 3 (spec2, fase 10: RF2-DEMO-01).

La «prueba pequena» de la v1 corrio con un solo atributo y cero usos: la puerta 3 pasaba
porque no tenia nada que comparar. Aqui se comprueba lo contrario de lo que comprobaba aquel
verde: que cada comprobacion de la puerta tuvo datos sobre los que decidir. Y despues se rompe
la demo a proposito, una comprobacion cada vez, para ver que esa comprobacion para el pipeline.
Es mutation testing sobre el recorrido entero, no sobre un grafo fabricado a mano.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from typing import Any

import pytest

from compartido.puerto import demo
from orquestador import fallo, pipeline
from tests.entorno import contexto, crear_novela, nueva_bd, puerto_falso


def _correr(
    extraccion: Callable[[str, str], dict[str, Any]] | None = None,
) -> tuple[sqlite3.Connection, int, str]:
    con, ruta = nueva_bd()
    novela_id = crear_novela(con)
    puerto = puerto_falso(con)
    if extraccion is not None:
        puerto.registrar("extraccion", extraccion)
    final = pipeline.avanzar(contexto(con, puerto, ruta, novela_id))
    return con, novela_id, final


def _uno(con: sqlite3.Connection, sql: str) -> int:
    return int(con.execute(sql).fetchone()[0])


@pytest.fixture(scope="module")
def demo_entera() -> tuple[sqlite3.Connection, int, str]:
    return _correr()


def test_la_demo_termina_limpia(demo_entera: tuple[sqlite3.Connection, int, str]) -> None:
    """Siembra pagada e hilos cerrados en orden: la puerta 5 no tiene nada que avisar."""
    _, _, final = demo_entera
    assert final == "completada"


# Cada comprobacion de la puerta 3, con la consulta que demuestra que tuvo datos.
_DATOS_POR_COMPROBACION = {
    "continuidad_factual: pares del mismo sujeto y atributo en escenas distintas": """
        SELECT COUNT(*) FROM hecho a JOIN hecho b
          ON a.sujeto_clave = b.sujeto_clave AND a.atributo_clave = b.atributo_clave
         AND a.id < b.id AND a.escena_id <> b.escena_id""",
    "continuidad_factual: una cadena de tres supersesiones": """
        SELECT COUNT(*) FROM hecho c JOIN hecho b ON b.id = c.supersede_a
        JOIN hecho a ON a.id = b.supersede_a""",
    "conocimiento_no_adquirido: usos de conocimiento": "SELECT COUNT(*) FROM uso_conocimiento",
    "sorpresa_imposible: adquisiciones por presencia o relato":
        "SELECT COUNT(*) FROM estado_conocimiento WHERE via IN ('presencio', 'se_lo_contaron')",
    "presencia_imposible: una muerte registrada":
        "SELECT COUNT(*) FROM estado_personaje WHERE condicion = 'muerto'",
    "presencia_imposible: personajes en varias escenas con eventos ordenados": """
        SELECT COUNT(*) FROM escena_personaje a JOIN escena_personaje b
          ON a.personaje_id = b.personaje_id AND a.escena_id < b.escena_id
        JOIN evento ea ON ea.escena_id = a.escena_id AND ea.orden_interno IS NOT NULL
        JOIN evento eb ON eb.escena_id = b.escena_id AND eb.orden_interno IS NOT NULL""",
    "objeto_sin_traslado: un objeto que cambia de sitio con su traslado":
        "SELECT COUNT(DISTINCT ubicacion_lugar_id) - 1 FROM estado_objeto",
    "coherencia_temporal: eventos dramatizados ordenados en varios capitulos": """
        SELECT COUNT(DISTINCT eo.capitulo_numero) - 1 FROM evento e
        JOIN escena_ordinal eo ON eo.escena_id = e.escena_id
        WHERE e.dramatizado = 1 AND e.orden_interno IS NOT NULL""",
}


@pytest.mark.parametrize("comprobacion", sorted(_DATOS_POR_COMPROBACION))
def test_cada_comprobacion_de_la_puerta_3_tuvo_datos(
    demo_entera: tuple[sqlite3.Connection, int, str], comprobacion: str
) -> None:
    con, _, _ = demo_entera
    assert _uno(con, _DATOS_POR_COMPROBACION[comprobacion]) > 0, comprobacion


def test_la_sorpresa_repetida_salio_como_aviso(
    demo_entera: tuple[sqlite3.Connection, int, str],
) -> None:
    con, novela_id, _ = demo_entera
    detalles = [json.loads(f[0]) for f in con.execute(
        "SELECT detalle FROM resultado_puerta WHERE novela_id = ? AND puerta = 3", (novela_id,)
    )]
    avisos = {c["comprobacion"] for d in detalles for c in d["conflictos"] if c["aviso"]}
    assert "sorpresa_imposible" in avisos


def test_la_siembra_y_los_hilos_recorren_su_ciclo(
    demo_entera: tuple[sqlite3.Connection, int, str],
) -> None:
    con, _, _ = demo_entera
    assert [f[0] for f in con.execute("SELECT estado FROM siembra_vigente")] == ["pagada"]
    assert {f[0] for f in con.execute("SELECT estado FROM hilo_vigente")} == {"resuelto"}



def test_un_hilo_que_no_esta_en_la_lista_se_descarta_y_cuenta() -> None:
    """RF2-PIPE-18: el extractor nombra un hilo 99 que el paquete nunca le dio."""

    def hilo_inventado(s: dict[str, Any]) -> None:
        s["hilos"].append({"escena_orden": 1, "hilo": 99, "nuevo_estado": "resuelto"})

    con, _, final = _correr(_en_el_capitulo_2(hilo_inventado))
    assert final == "completada"
    recuentos = [json.loads(f[0])["recuento"] for f in con.execute(
        "SELECT payload FROM traza_evento WHERE tipo = 'extraccion_descartes'"
    )]
    assert {"hilo_desconocido": 1} in [r.get("hilos") for r in recuentos]

# --- Romper la demo a proposito ------------------------------------------------------------------


def _en_el_capitulo_2(cambio: Callable[[dict[str, Any]], None]):  # noqa: ANN202
    def extraccion(entrada: str, agente: str) -> dict[str, Any]:
        salida = demo.extraccion(entrada, agente)
        if demo._capitulo(entrada) == 2:
            cambio(salida)
        return salida

    return extraccion


def _contradice(s: dict[str, Any]) -> None:
    s["hechos"][0]["valor"] = "aire limpio y sin olor"


def _usa_sin_saber(s: dict[str, Any]) -> None:
    # Reyes no estuvo en ninguna escena donde se fijo la voz de Idris (RF2-PIPE-21).
    s["usos_de_conocimiento"].append({
        "escena_orden": 1, "personaje_ref": demo.PERSONAJES[2], "sujeto_ref": demo.PERSONAJES[0],
        "atributo": "voz",
    })


def _muere_y_sigue(s: dict[str, Any]) -> None:
    s["estados_personaje"].append({
        "escena_orden": 1, "personaje_ref": demo.PERSONAJES[1], "condicion": "muerto",
    })


def _a_la_vez_en_dos_sitios(s: dict[str, Any]) -> None:
    for e in s["eventos"]:
        e["orden_interno"] = 20


def _objeto_sin_traslado(s: dict[str, Any]) -> None:
    s["estados_objeto"] = []


def _vuelve_atras(s: dict[str, Any]) -> None:
    for e in s["eventos"]:
        e["orden_interno"] = 1


def _inventa(s: dict[str, Any]) -> None:
    s["entidades_no_reconocidas"] = [{"escena_orden": 1, "nombre": "Doctor Vance"}]


@pytest.mark.parametrize(("cambio", "comprobacion"), [
    (_contradice, "continuidad_factual"),
    (_usa_sin_saber, "conocimiento_no_adquirido"),
    (_muere_y_sigue, "presencia_imposible"),
    (_a_la_vez_en_dos_sitios, "presencia_imposible"),
    (_objeto_sin_traslado, "objeto_sin_traslado"),
    (_vuelve_atras, "coherencia_temporal"),
])
def test_romper_la_demo_en_una_comprobacion_para_el_pipeline(
    cambio: Callable[[dict[str, Any]], None], comprobacion: str
) -> None:
    con, novela_id, final = _correr(_en_el_capitulo_2(cambio))
    assert final == "parada"
    parada = fallo.paradas_abiertas(con, novela_id)[0]
    informe = json.loads(parada["informe"])
    bloqueantes = {c["comprobacion"] for c in informe["conflictos"] if not c["aviso"]}
    assert comprobacion in bloqueantes, bloqueantes
    assert parada["capitulo"] in (2, 3)


def test_repetir_un_rasgo_no_crea_otro_hecho(
    demo_entera: tuple[sqlite3.Connection, int, str],
) -> None:
    """RF2-PIPE-19: el olor del puente se dice en cada capitulo y queda un solo hecho."""
    con, _, _ = demo_entera
    assert _uno(con, "SELECT COUNT(*) FROM hecho WHERE atributo_clave = 'olor'") == 1


def test_una_entidad_inventada_es_un_aviso_y_la_demo_sigue() -> None:
    """RF2-PIPE-22: el redactor inventa un nombre; queda registrado, no para."""
    con, novela_id, final = _correr(_en_el_capitulo_2(_inventa))
    assert final == "completada"
    detalles = [json.loads(f[0]) for f in con.execute(
        "SELECT detalle FROM resultado_puerta WHERE novela_id = ? AND puerta = 3", (novela_id,)
    )]
    avisos = {c["comprobacion"] for d in detalles for c in d["conflictos"] if c["aviso"]}
    assert "entidad_fuera_de_canon" in avisos
    assert _uno(con, "SELECT COUNT(*) FROM entidad_no_reconocida") == 1


# --- RF2-PIPE-23 y RF2-PIPE-24: lo que la primera pasada real ensenyo -----------------------------


def test_el_paquete_del_extractor_trae_el_valor_vigente(
    demo_entera: tuple[sqlite3.Connection, int, str],
) -> None:
    """Con el valor delante, el extractor puede repetirlo igual en vez de reformularlo."""
    import config
    from compartido.contexto import Presupuesto
    from tareas.extraccion import servicio

    con, novela_id, _ = demo_entera
    render = servicio.paquete(
        con, novela_id, 2, {1: "texto", 2: "texto"}, presupuesto=Presupuesto(
            bloques=config.PRESUPUESTO_BLOQUES, techo=config.PRESUPUESTO_PAQUETE),
    ).render()
    assert "olor = metal frio y algo dulce" in render
    # De la herida solo sale el ultimo eslabon de la cadena, no los sustituidos.
    assert "herida en la mano = cicatriz rosada" in render
    assert "corte abierto" not in render


def test_la_cita_manda_sobre_el_numero_de_escena() -> None:
    """El extractor dice escena 1, pero la frase solo esta en la 2: el hecho es de la 2."""
    frase = "La baliza pesa tres kilos y medio."

    def redaccion(entrada: str, agente: str) -> dict[str, Any]:
        salida = demo.redaccion(entrada, agente)
        if demo._capitulo(entrada) == 2:
            salida["escenas"][1]["texto"] += " " + frase
        return salida

    def extraccion(entrada: str, agente: str) -> dict[str, Any]:
        salida = demo.extraccion(entrada, agente)
        if demo._capitulo(entrada) == 2:
            salida["hechos"].append({
                "escena_orden": 1, "sujeto_tipo": "objeto", "sujeto_ref": demo.OBJETO,
                "atributo": "peso", "valor": "tres kilos y medio", "categoria": "fisico",
                "cita": "pesa tres kilos y medio",
            })
        return salida

    con, ruta = nueva_bd()
    novela_id = crear_novela(con)
    puerto = puerto_falso(con)
    puerto.registrar("redaccion", redaccion)
    puerto.registrar("extraccion", extraccion)
    assert pipeline.avanzar(contexto(con, puerto, ruta, novela_id)) == "completada"
    orden = con.execute(
        "SELECT e.orden FROM hecho h JOIN escena e ON e.id = h.escena_id WHERE h.atributo = 'peso'"
    ).fetchone()[0]
    assert orden == 2
    correcciones = [json.loads(f[0]).get("correcciones") for f in con.execute(
        "SELECT payload FROM traza_evento WHERE tipo = 'extraccion_descartes'"
    )]
    assert {"escena_por_cita": 1} in correcciones
