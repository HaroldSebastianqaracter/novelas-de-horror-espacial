"""El paquete no pierde canon en silencio (spec2, fase 4: RF2-CTX-01, 03, 11 y 12).

La propiedad central se ataca con hypothesis: para cualquier conjunto de bloques y elementos y
cualquier presupuesto, o el paquete cabe con TODO lo obligatorio, o se lanza
`PresupuestoExcedido` porque lo obligatorio no cabe; nunca se corta a mitad de elemento; y todo
bloque que pierde elementos queda anotado en `recortes`.
"""

from __future__ import annotations

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

import config
from compartido.contexto import (
    Bloque,
    Elemento,
    Paquete,
    Presupuesto,
    PresupuestoExcedido,
    ajustar,
    estimar,
)
from compartido.grafo import lectura
from compartido.puerto import demo as agentes_falsos
from orquestador import fallo, pipeline
from tests.entorno import (
    cfg_de,
    contar,
    crear_novela,
    hechos_del_capitulo,
    nueva_bd,
    puerto_falso,
)
from tests.fabrica import novela_minima

BLOQUES = config.BLOQUES_POR_AGENTE["redaccion"]

_elemento = st.builds(
    Elemento,
    texto=st.text(alphabet="abcdefghij ", min_size=1, max_size=400).filter(str.strip),
    obligatorio=st.booleans(),
)
_bloque = st.tuples(
    st.sampled_from(BLOQUES),
    st.lists(_elemento, min_size=1, max_size=25),
    st.one_of(st.none(), st.lists(_elemento.map(
        lambda e: Elemento(e.texto)), min_size=1, max_size=2)),
)


def _minimo(bloque: Bloque, fijos: frozenset[str]) -> int:
    """Lo que ocupa el bloque con solo lo que ajustar no puede quitar."""
    if bloque.nombre in fijos:
        return bloque.tokens
    return Bloque(bloque.nombre, [e for e in bloque.elementos if e.obligatorio],
                  bloque.titulo, bloque.separador).tokens


@settings(max_examples=300, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    bloques=st.lists(_bloque, min_size=1, max_size=6, unique_by=lambda b: b[0]),
    topes=st.dictionaries(st.sampled_from(BLOQUES), st.integers(0, 400)),
    techo=st.integers(0, 3000),
)
def test_lo_obligatorio_nunca_se_pierde_y_ningun_recorte_es_silencioso(
    bloques: list[tuple[str, list[Elemento], list[Elemento] | None]],
    topes: dict[str, int],
    techo: int,
) -> None:
    p = Paquete(agente="redaccion")
    for nombre, elementos, alternativa in bloques:
        p.bloques.append(Bloque(nombre, list(elementos), alternativa=alternativa))
    originales = {b.nombre: list(b.elementos) for b in p.bloques}
    alternativas = {b.nombre: list(b.alternativa or []) for b in p.bloques}
    presupuesto = Presupuesto(bloques=topes, techo=techo)
    minimo = sum(_minimo(b, presupuesto.fijos) for b in p.bloques)

    try:
        ajustado = ajustar(p, presupuesto)
    except PresupuestoExcedido:
        # Solo se para si ni quitando todo lo opcional cabe.
        assert minimo > techo
        return

    assert ajustado.total <= techo
    quedan = {b.nombre: b.elementos for b in ajustado.bloques}
    for nombre, elementos in originales.items():
        restantes = quedan.get(nombre, [])
        # Todo lo obligatorio sigue ahi, entero y en su bloque.
        for e in elementos:
            if e.obligatorio:
                assert e in restantes
        # Nada se ha cortado a mitad: todo lo que queda es un elemento original.
        for e in restantes:
            assert e in elementos or e in alternativas[nombre]
        if nombre in presupuesto.fijos:
            assert restantes == elementos
        # Todo bloque que pierde algo queda anotado, con el numero exacto de elementos.
        perdidos = sum(1 for e in elementos if e not in restantes)
        if perdidos:
            assert ajustado.recortes[nombre]["elementos"] >= perdidos
        elif nombre not in ajustado.recortes:
            assert restantes == [e for e in elementos if e.texto.strip()]


def test_el_capitulo_anterior_cae_a_su_resumen_antes_de_perder_parrafos() -> None:
    p = Paquete(agente="redaccion")
    p.anadir_elementos(
        "capitulo_anterior",
        [Elemento("parrafo " * 200, posicion=i) for i in range(10)],
        alternativa=[Elemento("el resumen del capitulo")],
    )
    ajustado = ajustar(p, Presupuesto(bloques={"capitulo_anterior": 100}, techo=10_000))
    assert "el resumen del capitulo" in ajustado.render()
    assert "parrafo" not in ajustado.render()
    recorte = ajustado.recortes["capitulo_anterior"]
    assert (recorte["elementos"], recorte["sustituido"]) == (10, 1)


def test_el_estado_rodante_se_lee_en_orden_y_se_recorta_por_lo_mas_antiguo() -> None:
    p = Paquete(agente="redaccion")
    p.anadir_elementos(
        "estado_rodante",
        [Elemento(f"Capitulo {n}: " + "x" * 300, posicion=n) for n in (5, 4, 3, 2, 1)],
    )
    tope = estimar(p.bloques[0].render()) - 50  # sobra menos que un capitulo
    ajustado = ajustar(p, Presupuesto(bloques={"estado_rodante": tope}, techo=10_000))
    texto = ajustado.render()
    assert "Capitulo 1:" not in texto
    assert texto.index("Capitulo 2:") < texto.index("Capitulo 5:")


# --- El presupuesto sale de la configuracion (RF2-CTX-12) ---------------------------------------


def test_novelas_presupuesto_tokens_fija_el_techo_del_paquete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NOVELAS_DB_PATH", "x.db")
    monkeypatch.setenv("NOVELAS_PRESUPUESTO_TOKENS", "60000")
    assert config.cargar().presupuesto_paquete == 60_000 - config.RESERVA_SALIDA
    monkeypatch.setenv("NOVELAS_PRESUPUESTO_TOKENS", str(config.RESERVA_SALIDA))
    with pytest.raises(config.ConfiguracionInvalida):
        config.cargar()


def test_un_techo_bajo_llega_al_paquete_y_el_recorte_queda_en_la_traza() -> None:
    con, ruta = nueva_bd()
    novela_id = crear_novela(con)
    cfg = cfg_de(ruta, presupuesto_bloques={**config.PRESUPUESTO_BLOQUES, "canon": 150})
    ctx = pipeline.Contexto(con=con, puerto=puerto_falso(con), cfg=cfg, novela_id=novela_id)
    pipeline.avanzar(ctx)

    eventos = [
        f["payload"] for f in con.execute(
            "SELECT payload FROM traza_evento WHERE tipo = 'paquete_recortado'"
        )
    ]
    assert eventos, "un bloque de canon de 150 tokens obliga a recortar y tiene que verse"
    assert any('"canon"' in e for e in eventos)


def test_si_lo_obligatorio_del_juez_no_cabe_hay_parada_de_presupuesto_y_se_revierte(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El paquete del oficio se monta tras el tramo 2: la parada revierte el capitulo."""
    con, ruta = nueva_bd()
    novela_id = crear_novela(con)

    def no_cabe(*_: object, **__: object) -> Paquete:
        raise PresupuestoExcedido("no cabe", detalle={"prosa": 99_999}, total=99_999,
                                  techo=74_000)

    monkeypatch.setattr(pipeline.s_oficio, "paquete", no_cabe)
    ctx = pipeline.Contexto(con=con, puerto=puerto_falso(con), cfg=cfg_de(ruta),
                            novela_id=novela_id)
    assert pipeline.avanzar(ctx) == "parada"
    parada = fallo.paradas_abiertas(con, novela_id)[0]
    assert (parada["tipo"], parada["capitulo"]) == ("presupuesto", 1)
    assert hechos_del_capitulo(con, novela_id, 1) == 0


# --- Lo que se lee del grafo (RF2-CTX-11) --------------------------------------------------------


def _grafo():  # noqa: ANN202
    con, _ = nueva_bd()
    con.execute("BEGIN")
    g = novela_minima(con)
    con.execute("COMMIT")
    return con, g


def test_los_hechos_del_reparto_se_marcan_y_no_traen_sustituidos_ni_futuros() -> None:
    con, g = _grafo()
    ibarra = g.personajes["Ibarra"]
    # El capitulo 1 sustituye los ojos grises por azules; el 2 dice verdes (futuro).
    con.execute(
        "INSERT INTO hecho (novela_id, escena_id, sujeto_tipo, sujeto_id, sujeto_nombre, "
        "atributo, valor, supersede_a) VALUES (?,?,'personaje',?,'Ibarra','color de ojos',"
        "'azules',?)", (g.novela_id, g.escenas[(1, 2)], ibarra, g.hechos["ojos"]),
    )
    con.execute(
        "INSERT INTO hecho (novela_id, escena_id, sujeto_tipo, sujeto_nombre, atributo, valor)"
        " VALUES (?,?,'mundo','Estacion','gravedad','media')", (g.novela_id, g.escenas[(1, 1)]),
    )
    hechos = lectura.hechos_del_reparto(con, g.novela_id, 2)
    valores = {(h["atributo"], h["valor"]): h["obligatorio"] for h in hechos}
    assert valores == {("color de ojos", "azules"): 1, ("gravedad", "media"): 0}
    # Los obligatorios van delante de los opcionales, que se recortan desde el final.
    assert [h["obligatorio"] for h in hechos] == sorted(
        [h["obligatorio"] for h in hechos], reverse=True
    )


def test_del_conocimiento_solo_entra_la_ultima_postura() -> None:
    con, g = _grafo()
    kowalski = g.personajes["Kowalski"]
    con.execute(
        "INSERT INTO estado_conocimiento (novela_id, personaje_id, hecho_id, escena_id, postura,"
        " via) VALUES (?,?,?,?,'sospecha','dedujo')",
        (g.novela_id, kowalski, g.hechos["ojos"], g.escenas[(1, 2)]),
    )
    posturas = [
        c["postura"] for c in lectura.conocimiento_del_reparto(con, g.novela_id, 2)
        if c["personaje"] == "Kowalski"
    ]
    assert posturas == ["sospecha"]


def test_la_prosa_viaja_en_su_propio_bloque() -> None:
    con, ruta = nueva_bd()
    novela_id = crear_novela(con)
    puerto = puerto_falso(con)
    ctx = pipeline.Contexto(con=con, puerto=puerto, cfg=cfg_de(ruta), novela_id=novela_id)
    pipeline.avanzar(ctx)
    for agente in ("extraccion", "oficio"):
        bloques = [i["tokens_por_bloque"] for i in puerto.invocaciones if i["agente"] == agente]
        assert bloques and all("prosa" in b for b in bloques), agente
    assert contar(con, "SELECT COUNT(*) FROM capitulo WHERE estado = 'completado'") == (
        agentes_falsos.CAPITULOS
    )
