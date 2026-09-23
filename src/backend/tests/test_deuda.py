"""Deuda menor (spec2, fase 9): RF2-PER-12, RF2-PIPE-15 y la limpieza de escritura.

Cada test fija un comportamiento que la auditoria encontro torcido: el orden de los hilos,
el ordinal de escena que colisionaba, la latencia medida entre extremos, los dos avisos que
le faltaban a la puerta 5 y las columnas que se interpolaban sin comprobar.
"""

from __future__ import annotations

import sqlite3

import pytest

from compartido.grafo import lectura
from orquestador import puerta_global
from tests.entorno import nueva_bd
from tests.fabrica import Grafo, novela_minima


@pytest.fixture()
def grafo() -> tuple[sqlite3.Connection, Grafo]:
    con, _ = nueva_bd()
    con.execute("BEGIN")
    g = novela_minima(con)
    con.execute("COMMIT")
    return con, g


def _hilo(con: sqlite3.Connection, g: Grafo, tipo: str, conflicto: str) -> int:
    return int(con.execute(
        "INSERT INTO hilo (novela_id, tipo, conflicto_central) VALUES (?,?,?)",
        (g.novela_id, tipo, conflicto),
    ).lastrowid or 0)


def _estado_hilo(con: sqlite3.Connection, g: Grafo, hilo: int, escena: int, estado: str) -> None:
    con.execute(
        "INSERT INTO hilo_estado (novela_id, hilo_id, escena_id, estado) VALUES (?,?,?,?)",
        (g.novela_id, hilo, escena, estado),
    )


def _capitulos(con: sqlite3.Connection, g: Grafo, hasta: int) -> dict[int, int]:
    """Capitulos 3..hasta, con una escena cada uno. Devuelve {numero: escena_id}."""
    acto = con.execute("SELECT id FROM acto WHERE novela_id = ?", (g.novela_id,)).fetchone()[0]
    escenas = {1: g.escenas[(1, 1)], 2: g.escenas[(2, 1)]}
    for numero in range(3, hasta + 1):
        cap = con.execute(
            "INSERT INTO capitulo (novela_id, acto_id, numero) VALUES (?,?,?)",
            (g.novela_id, acto, numero),
        ).lastrowid
        escenas[numero] = int(con.execute(
            "INSERT INTO escena (novela_id, capitulo_id, pov_id, lugar_id, orden, objetivo, "
            "conflicto, valor_inicial, valor_final) VALUES (?,?,?,?,1,'o','c','a','b')",
            (g.novela_id, cap, g.personajes["Kowalski"], g.lugares["Puente"]),
        ).lastrowid or 0)
    return escenas


def test_los_hilos_se_leen_con_el_principal_primero(
    grafo: tuple[sqlite3.Connection, Grafo],
) -> None:
    con, g = grafo
    _hilo(con, g, "subtrama", "La confianza")
    _hilo(con, g, "principal", "Salir de la estacion")
    assert lectura.hilos(con, g.novela_id)[0]["tipo"] == "principal"


def test_el_ordinal_de_escena_no_colisiona_con_capitulos_largos(
    grafo: tuple[sqlite3.Connection, Grafo],
) -> None:
    """Con numero*1000+orden, la escena 1500 del capitulo 1 iba DESPUES de la 1 del 2."""
    con, g = grafo
    larga = con.execute(
        "INSERT INTO escena (novela_id, capitulo_id, pov_id, lugar_id, orden, objetivo, "
        "conflicto, valor_inicial, valor_final) VALUES (?,?,?,?,1500,'o','c','a','b')",
        (g.novela_id, g.capitulos[1], g.personajes["Kowalski"], g.lugares["Puente"]),
    ).lastrowid
    ordinal = dict(con.execute("SELECT escena_id, ordinal FROM escena_ordinal").fetchall())
    assert ordinal[larga] < ordinal[g.escenas[(2, 1)]]


def test_un_hilo_latente_se_mide_por_tramo_continuo(
    grafo: tuple[sqlite3.Connection, Grafo],
) -> None:
    """Latente en el capitulo 1 y otra vez en el 8, activo entre medias: no son 7 capitulos."""
    con, g = grafo
    escenas = _capitulos(con, g, 9)
    hilo = _hilo(con, g, "subtrama", "La deuda de Reyes")
    _estado_hilo(con, g, hilo, escenas[1], "latente")
    _estado_hilo(con, g, hilo, escenas[2], "complicando")
    _estado_hilo(con, g, hilo, escenas[8], "latente")
    _estado_hilo(con, g, hilo, escenas[9], "resuelto")
    avisos = {c.comprobacion for c in puerta_global.evaluar(con, g.novela_id).conflictos}
    assert "hilo_latente_demasiado_tiempo" not in avisos

    # Latente seis capitulos seguidos, en cambio, si avisa.
    otro = _hilo(con, g, "subtrama", "El manifiesto")
    _estado_hilo(con, g, otro, escenas[2], "latente")
    _estado_hilo(con, g, otro, escenas[9], "resuelto")
    avisos = {c.comprobacion for c in puerta_global.evaluar(con, g.novela_id).conflictos}
    assert "hilo_latente_demasiado_tiempo" in avisos


def test_un_pago_sin_siembra_previa_es_aviso(grafo: tuple[sqlite3.Connection, Grafo]) -> None:
    con, g = grafo
    siembra = con.execute(
        "INSERT INTO siembra (novela_id, elemento, origen) VALUES (?, 'El sellante', 'estructura')",
        (g.novela_id,),
    ).lastrowid
    con.execute(
        "INSERT INTO siembra_estado (novela_id, siembra_id, escena_id, estado) "
        "VALUES (?,?,?, 'pagada')", (g.novela_id, siembra, g.escenas[(2, 2)]),
    )
    resultado = puerta_global.evaluar(con, g.novela_id)
    assert "pago_sin_siembra" in {c.comprobacion for c in resultado.avisos}
    assert resultado.pasa, "la puerta 5 no bloquea en la v2"


def test_cerrar_los_hilos_en_el_orden_en_que_se_abrieron_es_aviso(
    grafo: tuple[sqlite3.Connection, Grafo],
) -> None:
    con, g = grafo
    escenas = _capitulos(con, g, 4)
    a = _hilo(con, g, "principal", "Salir")
    b = _hilo(con, g, "subtrama", "Confiar")
    _estado_hilo(con, g, a, escenas[1], "abierto")
    _estado_hilo(con, g, b, escenas[2], "abierto")
    _estado_hilo(con, g, a, escenas[3], "resuelto")  # el primero en abrirse cierra primero
    _estado_hilo(con, g, b, escenas[4], "resuelto")
    assert "cierre_fuera_de_orden" in {
        c.comprobacion for c in puerta_global.evaluar(con, g.novela_id).avisos
    }


# --- Escritura: columnas comprobadas y NULL explicito --------------------------------------------


def test_insertar_una_columna_desconocida_es_un_error_antes_de_llegar_a_sqlite(
    grafo: tuple[sqlite3.Connection, Grafo],
) -> None:
    from compartido.grafo import insertar

    con, g = grafo
    with pytest.raises(ValueError, match="columna"):
        insertar(con, "objeto", novela_id=g.novela_id, nombre="Llave", poder_oculto="x")
    with pytest.raises(ValueError, match="tabla"):
        insertar(con, "tabla_que_no_existe", nombre="x")


def test_actualizar_puede_poner_una_columna_a_null(grafo: tuple[sqlite3.Connection, Grafo]) -> None:
    from compartido.grafo import NULO, actualizar

    con, g = grafo
    cap = g.capitulos[1]
    actualizar(con, "capitulo", cap, resumen="algo")
    actualizar(con, "capitulo", cap, resumen=NULO)
    assert con.execute("SELECT resumen FROM capitulo WHERE id = ?", (cap,)).fetchone()[0] is None
    # None sigue significando «no tocar».
    actualizar(con, "capitulo", cap, resumen="otra vez", objetivo=None)
    assert con.execute("SELECT objetivo FROM capitulo WHERE id = ?", (cap,)).fetchone()[0]


def test_un_evento_puede_llevar_en_su_payload_una_clave_tipo(
    grafo: tuple[sqlite3.Connection, Grafo],
) -> None:
    import json

    from compartido.grafo import emitir_evento

    con, g = grafo
    emitir_evento(con, g.novela_id, "parada", tipo="continuidad", novela_id=99)
    fila = con.execute(
        "SELECT tipo, novela_id, payload FROM traza_evento ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert (fila["tipo"], fila["novela_id"]) == ("parada", g.novela_id)
    assert json.loads(fila["payload"]) == {"tipo": "continuidad", "novela_id": 99}


# --- RF2-PIPE-20: un resumen largo se recorta, no tira la extraccion -----------------------------


def test_un_resumen_largo_se_recorta_por_la_ultima_frase_completa() -> None:
    from tareas.extraccion.esquemas import recortar

    texto = "Primera frase corta. Segunda frase algo mas larga que la otra. Tercera sin punto"
    assert recortar(texto, 12) == "Primera frase corta. Segunda frase algo mas larga que la otra."
    assert recortar(texto, 5) == "Primera frase corta."
    assert recortar("una dos tres cuatro cinco", 3) == "una dos tres"
    assert recortar(texto, 100) == texto


def test_una_extraccion_con_el_resumen_largo_entra_recortada_y_la_traza_lo_dice() -> None:
    import json

    from compartido.puerto import demo
    from orquestador import pipeline
    from tareas.extraccion.esquemas import PALABRAS_RESUMEN
    from tests.entorno import contexto, crear_novela, nueva_bd, puerto_falso

    # Frases de tres palabras, diez de mas que el limite (RF3-PAS-02 lo subio de 200 a 250).
    frases = PALABRAS_RESUMEN // 3 + 4
    largo, cabe = frases * 3, (PALABRAS_RESUMEN // 3) * 3

    def extraccion(entrada: str, agente: str) -> dict[str, object]:
        salida = demo.extraccion(entrada, agente)
        salida["resumen"] = "La cuadrilla avanza. " * frases
        return salida

    con, ruta = nueva_bd()
    novela_id = crear_novela(con)
    puerto = puerto_falso(con)
    puerto.registrar("extraccion", extraccion)
    assert pipeline.avanzar(contexto(con, puerto, ruta, novela_id)) == "completada"
    resumen = con.execute("SELECT resumen FROM capitulo WHERE numero = 1").fetchone()[0]
    assert len(resumen.split()) == cabe and resumen.endswith(".")
    eventos = [json.loads(f[0]) for f in con.execute(
        "SELECT payload FROM traza_evento WHERE tipo = 'resumen_recortado'"
    )]
    assert eventos and eventos[0]["palabras"] == {"resumen": largo}


# --- RF2-PER-13: el mundo declara que lugar esta dentro de cual ----------------------------------


def test_el_mundo_rechaza_contenedores_desconocidos_y_ciclos() -> None:
    import pytest
    from pydantic import ValidationError

    from compartido.puerto import demo
    from tareas.mundo.esquemas import SalidaMundo

    base = demo.mundo("", "mundo")
    bien = dict(base, lugares=[dict(base["lugares"][0]),
                               dict(base["lugares"][1], dentro_de=base["lugares"][0]["nombre"]),
                               dict(base["lugares"][2])])
    assert SalidaMundo.model_validate(bien).lugares[1].dentro_de

    desconocido = dict(base, lugares=[dict(base["lugares"][0], dentro_de="Otra estacion"),
                                      *base["lugares"][1:]])
    with pytest.raises(ValidationError, match="no existe"):
        SalidaMundo.model_validate(desconocido)

    a, b = base["lugares"][0]["nombre"], base["lugares"][1]["nombre"]
    ciclo = dict(base, lugares=[dict(base["lugares"][0], dentro_de=b),
                                dict(base["lugares"][1], dentro_de=a), base["lugares"][2]])
    with pytest.raises(ValidationError, match="ciclo"):
        SalidaMundo.model_validate(ciclo)
