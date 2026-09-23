"""El capitulo a medias no sobrevive a nada (spec2, fase 1: RF2-PIPE-08, RF2-PER-07).

Entre el tramo 2 y el 3 un capitulo tiene texto y hechos sin estar completado. Cada test de
aqui saca el bucle de capitulo por un camino distinto de «capitulo cerrado» y comprueba que
ese estado intermedio no se queda en el grafo. `parar` durante el oficio y la caida real del
worker estan en tests/test_auditoria.py (hallazgos 5 y 6).
"""

from __future__ import annotations

import pytest

import worker
from compartido import db
from compartido.grafo import lectura
from compartido.puerto import AgenteInterrumpido
from compartido.puerto import demo as agentes_falsos
from orquestador import cola, pipeline
from tests.entorno import (
    cfg_de,
    contexto,
    crear_novela,
    hechos_del_capitulo,
    nueva_bd,
    puerto_falso,
    textos_vigentes_del_capitulo,
)
from tests.fabrica import novela_minima


def test_una_salida_invalida_del_oficio_revierte_el_capitulo() -> None:
    """El juez devuelve basura dos veces: la ejecucion acaba en error, sin capitulo a medias."""
    _, ruta = nueva_bd()
    w = worker.Worker(cfg_de(ruta))
    novela_id = crear_novela(w.con)
    w.puerto.registrar("oficio", lambda entrada, agente: {"veredictos": []})  # type: ignore[attr-defined]

    w._correr(novela_id)

    assert (lectura.ejecucion(w.con, novela_id) or {})["estado"] == "error"
    assert hechos_del_capitulo(w.con, novela_id, 1) == 0
    assert textos_vigentes_del_capitulo(w.con, novela_id, 1) == 0
    assert db.verificar_integridad(w.con) == []


def test_un_agente_interrumpido_durante_el_juez_revierte_el_capitulo() -> None:
    con, ruta = nueva_bd()
    novela_id = crear_novela(con)
    puerto = puerto_falso(con)

    def oficio(entrada: str, agente: str) -> dict:
        if "capitulo 2" in entrada.lower():
            raise AgenteInterrumpido("parar durante el juicio")
        return agentes_falsos.oficio(entrada, agente)

    puerto.registrar("oficio", oficio)
    assert pipeline.avanzar(contexto(con, puerto, ruta, novela_id)) == "detenida"

    assert lectura.ultimo_capitulo_completado(con, novela_id) == 1
    assert hechos_del_capitulo(con, novela_id, 1) > 0
    assert hechos_del_capitulo(con, novela_id, 2) == 0
    assert textos_vigentes_del_capitulo(con, novela_id, 2) == 0
    assert db.verificar_integridad(con) == []


def test_reanudar_tras_parar_en_el_oficio_no_abre_una_parada_falsa() -> None:
    """La segunda mitad del hallazgo 5: el intento abandonado ya no choca con el nuevo."""
    con, ruta = nueva_bd()
    novela_id = crear_novela(con)
    puerto = puerto_falso(con)
    estado = {"parado": False}

    def extraccion(entrada: str, agente: str) -> dict:
        salida = agentes_falsos.extraccion(entrada, agente)
        if "capitulo 2" in entrada.lower():
            # Un atributo que solo fija el capitulo 2: el intento abandonado dice una cosa y
            # el nuevo otra. Si el abandonado siguiera en el grafo, chocarian.
            valor = "templada" if estado["parado"] else "helada"
            salida["hechos"].append({
                "escena_orden": 1, "sujeto_tipo": "lugar", "sujeto_ref": agentes_falsos.LUGARES[0],
                "atributo": "temperatura", "valor": valor, "categoria": "fisico",
                "cita": f"el aire estaba {valor}", "supersede_a": "",
            })
            if not estado["parado"]:
                estado["parado"] = True
                cola.encolar(con, "parar", novela_id)
        return salida

    puerto.registrar("extraccion", extraccion)
    assert pipeline.avanzar(contexto(con, puerto, ruta, novela_id)) == "detenida"
    con.execute("UPDATE intencion SET estado = 'hecha' WHERE tipo = 'parar'")

    final = pipeline.avanzar(contexto(con, puerto, ruta, novela_id))
    assert final in ("completada", "completada_con_avisos"), final
    assert db.verificar_integridad(con) == []


@pytest.mark.parametrize("estado", ["detenida", "error", "parada", "completada"])
def test_la_integridad_ve_el_capitulo_a_medias_sin_ejecucion_activa(estado: str) -> None:
    con, _ = nueva_bd()
    con.execute("BEGIN")
    g = novela_minima(con)
    con.execute("COMMIT")
    # Con la ejecucion activa, los hechos de capitulos sin completar son el tramo 2.
    assert db.verificar_integridad(con) == []

    con.execute("UPDATE ejecucion SET estado = ? WHERE novela_id = ?", (estado, g.novela_id))
    reglas = {v.regla for v in db.verificar_integridad(con)}
    assert "estado_en_capitulo_no_completado" in reglas

    # Quien sabe que la ejecucion sigue viva puede decirlo y la regla no aplica.
    reglas = {v.regla for v in db.verificar_integridad(con, activas={g.novela_id})}
    assert "estado_en_capitulo_no_completado" not in reglas
