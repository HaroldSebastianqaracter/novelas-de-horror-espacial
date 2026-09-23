"""El indice filtra antes de ordenar y no mezcla modelos (spec2, fase 7).

RF2-CTX-07 (la distancia solo sobre candidatos admitidos), RF2-CTX-09 (todo fallo es aviso),
RF2-CTX-10 (el indice sabe con que modelo se construyo) y RF2-FALLO-04b (toda reversion lo
purga). El golden set con el modelo real va marcado `modelo` y no corre por defecto.
"""

from __future__ import annotations

import sqlite3

import pytest

from compartido.vectores import Indice
from tests.entorno import nueva_bd
from tests.fabrica import Grafo, novela_minima


def _grafo_con_capitulo(n_escenas_lejos: int) -> tuple[sqlite3.Connection, Grafo, int]:
    """La novela minima y un capitulo 10 con una escena en el Puente y muchas en la Esclusa.

    Las de la Esclusa dicen exactamente lo que dira la consulta; la del Puente, solo parte.
    """
    con, _ = nueva_bd()
    con.execute("BEGIN")
    g = novela_minima(con)
    acto = con.execute("SELECT id FROM acto WHERE novela_id = ?", (g.novela_id,)).fetchone()[0]
    cap = con.execute(
        "INSERT INTO capitulo (novela_id, acto_id, numero, estado) VALUES (?,?,10,'completado')",
        (g.novela_id, acto),
    ).lastrowid
    textos = [("Puente", "el puente cruje y huele a ozono quemado")] + [
        ("Esclusa", "la compuerta respira detras del casco helado") for _ in range(n_escenas_lejos)
    ]
    for orden, (lugar, texto) in enumerate(textos, start=1):
        escena = con.execute(
            "INSERT INTO escena (novela_id, capitulo_id, pov_id, lugar_id, orden, objetivo, "
            "conflicto, valor_inicial, valor_final) VALUES (?,?,?,?,?,'o','c','a','b')",
            (g.novela_id, cap, g.personajes["Kowalski"], g.lugares[lugar], orden),
        ).lastrowid
        con.execute(
            "INSERT INTO escena_texto (novela_id, escena_id, version, texto, estado) "
            "VALUES (?,?,1,?,'vigente')", (g.novela_id, escena, texto),
        )
    con.execute("COMMIT")
    return con, g, int(cap)


def test_el_filtro_admite_antes_de_que_la_similitud_ordene() -> None:
    """Cincuenta escenas de otro lugar mas parecidas a la consulta no tapan la del lugar."""
    con, g, _ = _grafo_con_capitulo(50)
    indice = Indice(con, modelo="hash")
    assert indice.disponible
    con.execute("BEGIN")
    indice.indexar_capitulo(g.novela_id, 10)
    con.execute("COMMIT")

    fragmentos = indice.recuperar(
        g.novela_id, "la compuerta respira detras del casco helado del puente",
        hasta_capitulo=11, lugares=[g.lugares["Puente"]], limite=3,
    )
    assert [f.lugar for f in fragmentos] == ["Puente"]


# --- RF2-CTX-10: el indice sabe con que modelo se construyo --------------------------------------


def test_cambiar_de_modelo_rehace_el_indice_con_la_dimension_nueva() -> None:
    from compartido.vectores.embebido import EmbedderHash

    con, g, _ = _grafo_con_capitulo(3)
    viejo = Indice(con, modelo="hash", embedder=EmbedderHash(384))
    viejo.indexar_capitulo(g.novela_id, 10)
    assert tuple(con.execute("SELECT modelo, dimension FROM indice_estado").fetchone()) == (
        "hash-384", 384,
    )

    # Otro proceso arranca con otro modelo: arrancar no toca el registro.
    nuevo = Indice(con, modelo="hash", embedder=EmbedderHash(128))
    assert tuple(con.execute("SELECT modelo, dimension FROM indice_estado").fetchone()) == (
        "hash-384", 384,
    )
    # Al usarlo, rehace las tablas con su dimension y reindexa todo lo escrito.
    fragmentos = nuevo.recuperar(
        g.novela_id, "el puente cruje", hasta_capitulo=11, lugares=[g.lugares["Puente"]],
    )
    assert [f.lugar for f in fragmentos] == ["Puente"]
    assert tuple(con.execute("SELECT modelo, dimension FROM indice_estado").fetchone()) == (
        "hash-128", 128,
    )
    assert con.execute("SELECT COUNT(*) FROM vec_escena").fetchone()[0] == 4


def test_sin_modelo_no_hay_hash_de_repuesto(monkeypatch: pytest.MonkeyPatch) -> None:
    from compartido.vectores import EmbeddingNoDisponible, embebido

    def no_carga(*_: object, **__: object) -> None:
        raise EmbeddingNoDisponible("no hay modelo")

    monkeypatch.setattr(embebido.EmbedderFastEmbed, "__init__", no_carga)
    monkeypatch.setattr(embebido.EmbedderModel2Vec, "__init__", no_carga)
    with pytest.raises(EmbeddingNoDisponible):
        embebido.construir("intfloat/multilingual-e5-small")
    assert embebido.construir("hash").nombre == "hash-384"


# --- RF2-CTX-09: todo fallo del indice es un aviso ------------------------------------------------


def test_si_el_modelo_no_carga_el_pipeline_sigue_y_la_traza_lo_avisa(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from compartido.vectores import EmbeddingNoDisponible
    from compartido.vectores import indice as modulo
    from orquestador import pipeline
    from tests.entorno import cfg_de, crear_novela, puerto_falso

    def no_carga(*_: object, **__: object) -> None:
        raise EmbeddingNoDisponible("el modelo no esta descargado")

    monkeypatch.setattr(modulo, "construir", no_carga)
    con, ruta = nueva_bd()
    novela_id = crear_novela(con)
    ctx = pipeline.Contexto(con=con, puerto=puerto_falso(con), cfg=cfg_de(ruta),
                            novela_id=novela_id, indice=Indice(con, modelo="fastembed"))
    assert pipeline.avanzar(ctx).startswith("completada")

    avisos = [f["payload"] for f in con.execute(
        "SELECT payload FROM traza_evento WHERE tipo = 'indice_fallo'"
    )]
    assert avisos and any("no esta descargado" in a for a in avisos)


# --- RF2-FALLO-04b: toda reversion purga el indice ------------------------------------------------


def test_revertir_saca_del_indice_lo_que_deja_de_ser_vigente() -> None:
    from compartido.db import transaccion
    from orquestador import fallo, pipeline
    from tests.entorno import cfg_de, crear_novela, puerto_falso

    con, ruta = nueva_bd()
    novela_id = crear_novela(con)
    puerto = puerto_falso(con)
    ctx = pipeline.Contexto(con=con, puerto=puerto, cfg=cfg_de(ruta), novela_id=novela_id,
                            indice=Indice(con, modelo="hash"))
    assert pipeline.avanzar(ctx).startswith("completada")
    # El capitulo 2 ya recibio prosa recuperada de los anteriores.
    redacciones = [i["entrada"] for i in puerto.invocaciones if i["agente"] == "redaccion"]
    assert "COMO SE DESCRIBIO ESTO ANTES" in redacciones[1]
    antes = con.execute("SELECT COUNT(*) FROM vec_escena").fetchone()[0]

    with transaccion(con):
        fallo.revertir_grafo(con, novela_id, 2)

    fuera = con.execute(
        "SELECT COUNT(*) FROM vec_escena WHERE escena_texto_id IN "
        "(SELECT id FROM escena_texto WHERE estado = 'descartada')"
    ).fetchone()[0]
    assert fuera == 0
    assert con.execute("SELECT COUNT(*) FROM vec_escena").fetchone()[0] < antes
    assert con.execute(
        "SELECT COUNT(*) FROM vec_hecho WHERE hecho_id NOT IN (SELECT id FROM hecho_vigente)"
    ).fetchone()[0] == 0


# --- Golden set con el modelo real (no corre por defecto) -----------------------------------------

_CORPUS = {
    "Puente": [
        "Las consolas del puente parpadeaban en ambar mientras el ventanal mostraba el planeta.",
        "Vaan golpeo el panel de navegacion hasta que la alarma dejo de sonar.",
        "En el puente, el olor a ozono de los reles quemados no se iba.",
    ],
    "Esclusa": [
        "La doble compuerta tardo un minuto entero en igualar la presion.",
        "Idris sello el traje antes de entrar y comprobo la reserva de oxigeno.",
        "La hoja exterior estaba cubierta de escarcha y de marcas de unas.",
    ],
    "Modulo de carga": [
        "Los contenedores estaban abiertos y vacios, con las etiquetas arrancadas.",
        "Algo habia arrastrado cajas por el suelo dejando un rastro oscuro y pegajoso.",
        "Hacia un frio que cortaba la respiracion y empanaba el visor.",
    ],
}
#: consulta -> texto esperado. Lo escribe el equipo: es pequeno y es su punto ciego.
_GOLDEN = {
    "igualar la presion de la compuerta antes de pasar": _CORPUS["Esclusa"][0],
    "comprobar el oxigeno del traje sellado": _CORPUS["Esclusa"][1],
    "marcas y hielo en la hoja exterior": _CORPUS["Esclusa"][2],
    "olor a reles quemados": _CORPUS["Puente"][2],
    "la alarma no dejaba de sonar": _CORPUS["Puente"][1],
    "cajas arrastradas y un rastro en el suelo": _CORPUS["Modulo de carga"][1],
    "contenedores vacios sin etiquetas": _CORPUS["Modulo de carga"][0],
    "un frio que empana el visor": _CORPUS["Modulo de carga"][2],
}


@pytest.mark.modelo
def test_golden_set_de_recuperacion_con_el_modelo_real() -> None:
    """Recall@3 sin juez: la escena esperada tiene que estar entre las tres primeras."""
    con, _ = nueva_bd()
    con.execute("BEGIN")
    g = novela_minima(con)
    acto = con.execute("SELECT id FROM acto WHERE novela_id = ?", (g.novela_id,)).fetchone()[0]
    cap = con.execute(
        "INSERT INTO capitulo (novela_id, acto_id, numero, estado) VALUES (?,?,10,'completado')",
        (g.novela_id, acto),
    ).lastrowid
    orden = 0
    for lugar, textos in _CORPUS.items():
        for texto in textos:
            orden += 1
            escena = con.execute(
                "INSERT INTO escena (novela_id, capitulo_id, pov_id, lugar_id, orden, objetivo, "
                "conflicto, valor_inicial, valor_final) VALUES (?,?,?,?,?,'o','c','a','b')",
                (g.novela_id, cap, g.personajes["Kowalski"], g.lugares[lugar], orden),
            ).lastrowid
            con.execute(
                "INSERT INTO escena_texto (novela_id, escena_id, version, texto, estado) "
                "VALUES (?,?,1,?,'vigente')", (g.novela_id, escena, texto),
            )
    con.execute("COMMIT")

    indice = Indice(con, modelo="minishlab/potion-multilingual-128M")
    todos = list(g.lugares.values())
    aciertos = 0
    for consulta, esperado in _GOLDEN.items():
        fragmentos = indice.recuperar(
            g.novela_id, consulta, hasta_capitulo=11, lugares=todos, limite=3,
        )
        aciertos += esperado in [f.texto for f in fragmentos]
    recall = aciertos / len(_GOLDEN)
    assert recall >= 0.75, f"recall@3 = {recall:.2f}"
