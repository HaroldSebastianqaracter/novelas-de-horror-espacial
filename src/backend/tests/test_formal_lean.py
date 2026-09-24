"""El validador formal de la cronologia en Lean 4 (specs/spec-lean.md).

Dos grupos. Los del generador corren sin Lean: que el fichero sale de la story bible como dice
RF-LEAN-02 y que el ejemplo versionado esta al dia. Los de la verificacion necesitan `lake` y se
saltan si no esta instalado: sobre la novela de demo del banco de la puerta 3 meten errores que
la puerta 3 no ve, y comprueban que Lean si los ve (RF-LEAN-07).
"""

from __future__ import annotations

import shutil
import sqlite3
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from compartido import db
from compartido.grafo import insertar
from compartido.puerta_base import Conflicto, ResultadoPuerta
from compartido.puerto import demo as agentes_falsos
from evals import banco_puerta3 as banco
from orquestador import lean
from tareas.continuidad import puerta

sin_lean = pytest.mark.skipif(lean.lake_disponible() is None, reason="Lean no esta instalado")


@pytest.fixture(scope="module")
def base(tmp_path_factory: pytest.TempPathFactory) -> banco.Base:
    return banco.construir_base(tmp_path_factory.mktemp("lean"))


@pytest.fixture
def con(base: banco.Base, tmp_path: Path) -> Iterator[sqlite3.Connection]:
    """Una copia de la novela de demo para cada test."""
    destino = tmp_path / "caso.db"
    shutil.copyfile(base.ruta, destino)
    conexion = db.conectar(destino)
    try:
        yield conexion
    finally:
        conexion.close()


def _evento(con: sqlite3.Connection, b: banco.Base, escena: tuple[int, int], orden: int,
            dia: int, descripcion: str = "Suceso del caso") -> int:
    return insertar(con, "evento", novela_id=b.novela_id, linea_de_tiempo_id=b.linea_id,
                    escena_id=b.escenas[escena], fecha_interna=f"dia {dia}", dia=dia,
                    orden_interno=orden, descripcion=descripcion, dramatizado=1)


def _analepsis(con: sqlite3.Connection, b: banco.Base, escena: tuple[int, int]) -> None:
    con.execute("UPDATE escena SET analepsis = 1 WHERE id = ?", (b.escenas[escena],))


def _reparto(con: sqlite3.Connection, b: banco.Base, escena: tuple[int, int], nombre: str) -> None:
    con.execute("INSERT OR IGNORE INTO escena_personaje (escena_id, personaje_id) VALUES (?,?)",
                (b.escenas[escena], b.personajes[nombre]))


def _muere(con: sqlite3.Connection, b: banco.Base, nombre: str, escena: tuple[int, int]) -> None:
    insertar(con, "estado_personaje", novela_id=b.novela_id, personaje_id=b.personajes[nombre],
             escena_id=b.escenas[escena], condicion="muerto")


# --- RF-LEAN-02: el generador, sin Lean --------------------------------------------------------


def test_el_ejemplo_versionado_es_lo_que_genera_la_demo(con: sqlite3.Connection,
                                                        base: banco.Base) -> None:
    """Si cambia el generador o la demo, `Storymaker/Ejemplo.lean` se regenera a conciencia."""
    ejemplo = lean.directorio_lean() / "Storymaker" / "Ejemplo.lean"
    assert ejemplo.read_text(encoding="utf-8") == lean.generar(
        con, base.novela_id, espacio="Ejemplo")


def test_el_fichero_es_determinista(con: sqlite3.Connection, base: banco.Base) -> None:
    assert lean.generar(con, base.novela_id) == lean.generar(con, base.novela_id)


def test_la_presencia_es_la_vista_sin_los_estados_muerto(con: sqlite3.Connection,
                                                         base: banco.Base) -> None:
    """Sin estados `muerto`, la consulta del generador da lo mismo que la vista `presencia`."""
    con.execute("DELETE FROM estado_personaje WHERE condicion = 'muerto'")
    con.execute("INSERT INTO presencia_escena (novela_id, escena_id, personaje_id) VALUES (?,?,?)",
                (base.novela_id, base.escenas[(1, 1)], base.personajes["Reyes"]))
    propia = set(con.execute(lean._SQL_PRESENCIA).fetchall())  # pyright: ignore[reportPrivateUsage]
    vista = set(con.execute("SELECT escena_id, personaje_id FROM presencia").fetchall())
    assert propia == vista


def test_seguir_muerto_no_es_estar(con: sqlite3.Connection, base: banco.Base) -> None:
    """Reyes muere en la 3.2 (demo). Registrar en la 3.2 que sigue muerto no lo pone alli."""
    crono = lean.extraer(con, base.novela_id)
    assert base.personajes["Reyes"] not in {p for _, p, _ in crono.presencias}
    assert crono.muertes == {base.personajes["Reyes"]: 3}


def test_una_muerte_revocada_no_cuenta(con: sqlite3.Connection, base: banco.Base) -> None:
    _muere(con, base, "Vaan", (2, 1))
    insertar(con, "estado_personaje", novela_id=base.novela_id,
             personaje_id=base.personajes["Vaan"], escena_id=base.escenas[(3, 1)],
             condicion="vivo")
    assert base.personajes["Vaan"] not in lean.extraer(con, base.novela_id).muertes


def test_la_muerte_cae_el_dia_de_la_primera_escena_de_la_racha(con: sqlite3.Connection,
                                                              base: banco.Base) -> None:
    _muere(con, base, "Reyes", (2, 2))
    assert lean.extraer(con, base.novela_id).muertes[base.personajes["Reyes"]] == 2


def test_la_muerte_cae_el_mayor_dia_de_su_escena(con: sqlite3.Connection,
                                                base: banco.Base) -> None:
    """Reyes muere en la 3.2 (dia 3); si la escena dramatiza tambien el dia 4, muere el 4."""
    _evento(con, base, (3, 2), 33, 4)
    assert lean.extraer(con, base.novela_id).muertes[base.personajes["Reyes"]] == 4


def test_solo_se_leen_edades_con_cifras(con: sqlite3.Connection, base: banco.Base) -> None:
    for valor in ("45 años", "treinta y ocho", "unos 40", "6 meses", "34 y medio", "52"):
        banco._hecho(con, base, (3, 1), "Idris", "edad", valor)  # pyright: ignore[reportPrivateUsage]
    edades = lean.extraer(con, base.novela_id).edades
    idris = base.personajes["Idris"]
    assert [(p, d, e) for _, p, d, e in edades] == [(idris, 3, 45), (idris, 3, 52)]


def test_un_evento_referido_no_pone_a_nadie_en_el(con: sqlite3.Connection,
                                                   base: banco.Base) -> None:
    """Un suceso que la 3.1 cuenta sin dramatizar (la fundacion, hace 60 años) no es una
    presencia de quien esta en la escena, ni fija el dia de la escena."""
    ev = insertar(con, "evento", novela_id=base.novela_id, linea_de_tiempo_id=base.linea_id,
                  escena_id=base.escenas[(3, 1)], fecha_interna="hace sesenta años",
                  dia=-21900, descripcion="La colonia se funda", tipo="referido",
                  dramatizado=0)
    crono = lean.extraer(con, base.novela_id)
    assert all(e != ev for e, _, _ in crono.presencias)
    assert not any(e.analepsis or e.linea or e.previo for e in crono.eventos if e.id == ev)


def test_un_referido_sin_escena_no_es_un_antecedente(con: sqlite3.Connection,
                                                      base: banco.Base) -> None:
    ev = insertar(con, "evento", novela_id=base.novela_id, linea_de_tiempo_id=base.linea_id,
                  fecha_interna="pasado manana", dia=5, descripcion="Llega el relevo",
                  tipo="referido", dramatizado=0)
    crono = lean.extraer(con, base.novela_id)
    assert [e.previo for e in crono.eventos if e.id == ev] == [False]
    # El antecedente del mundo de la demo si lo es.
    assert any(e.previo for e in crono.eventos)


def test_el_presente_de_una_analepsis(con: sqlite3.Connection, base: banco.Base) -> None:
    """El presente de la 3.2 es el mayor dia de la linea principal antes de ella: el 3 de la 3.1."""
    _analepsis(con, base, (3, 2))
    crono = lean.extraer(con, base.novela_id)
    de_la_32 = [e for e in crono.eventos if e.analepsis]
    assert de_la_32 and all(e.presente == 3 and not e.linea for e in de_la_32)


def test_un_evento_sin_dia_se_cuenta_y_no_entra(con: sqlite3.Connection, base: banco.Base) -> None:
    insertar(con, "evento", novela_id=base.novela_id, linea_de_tiempo_id=base.linea_id,
             escena_id=base.escenas[(3, 1)], fecha_interna="un dia", descripcion="Sin dia",
             dramatizado=1)
    crono = lean.extraer(con, base.novela_id)
    assert crono.eventos_sin_dia == 1
    assert "Sin dia, no comprobados: 1." in lean.escribir(crono)


def test_un_comentario_no_puede_cerrar_el_bloque(con: sqlite3.Connection, base: banco.Base) -> None:
    _evento(con, base, (3, 1), 33, 3, descripcion="Cierra -/ el bloque\ny salta de linea")
    texto = lean.generar(con, base.novela_id)
    assert "Cierra - / el bloque y salta de linea" in texto


def test_leer_testigos() -> None:
    salida = ("TESTIGO lean_nadie_tras_morir evento=7 otro=0 personaje=3 hecho=0 dia=3 "
              "limite=-2\nruido\n")
    assert lean.leer_testigos(salida) == [("lean_nadie_tras_morir", {
        "evento": 7, "otro": 0, "personaje": 3, "hecho": 0, "dia": 3, "limite": -2})]


def test_sin_lean_la_puerta_bloquea_y_dice_como_instalarlo(
    con: sqlite3.Connection, base: banco.Base, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(lean, "lake_disponible", lambda: None)
    r = lean.verificar(con, base.novela_id)
    assert not r.pasa and [c.comprobacion for c in r.bloqueantes] == ["lean_no_disponible"]
    assert "elan" in r.bloqueantes[0].descripcion



def test_la_linea_de_comandos_imprime_el_fichero(base: banco.Base,
                                                  capsys: pytest.CaptureFixture[str]) -> None:
    import verificar_lean

    codigo = verificar_lean.main(
        ["--novela", str(base.novela_id), "--db", str(base.ruta), "--generar"])
    assert codigo == 0
    assert "theorem nadie_tras_morir : NadieTrasMorir datos" in capsys.readouterr().out

# --- RF-LEAN-05 y RF-LEAN-07: la verificacion, con Lean ------------------------------------------


def _puerta_3(con: sqlite3.Connection, b: banco.Base) -> set[str]:
    """Los bloqueantes de la puerta 3 sobre el capitulo 3, con su prosa."""
    prosa = banco._textos(con, b.novela_id, banco.CAPITULO)  # pyright: ignore[reportPrivateUsage]
    r = puerta.evaluar(con, b.novela_id, banco.CAPITULO, textos=prosa)
    return {c.comprobacion for c in r.bloqueantes}


def _recuerdo_tras_la_muerte(con: sqlite3.Connection, b: banco.Base) -> None:
    """Reyes muere el dia 1 (1.2); la 3.2 es un recuerdo del dia 2 y Reyes esta en ella."""
    _muere(con, b, "Reyes", (1, 2))
    _analepsis(con, b, (3, 2))
    con.execute("UPDATE evento SET dia = 2 WHERE escena_id = ?", (b.escenas[(3, 2)],))
    _reparto(con, b, (3, 2), "Reyes")


def _presente_por_el_extractor_tras_morir(con: sqlite3.Connection, b: banco.Base) -> None:
    """Reyes muere en la 2.2; en la 3.1 el extractor lo registra presente, fuera del reparto."""
    _muere(con, b, "Reyes", (2, 2))
    con.execute("INSERT INTO presencia_escena (novela_id, escena_id, personaje_id) VALUES (?,?,?)",
                (b.novela_id, b.escenas[(3, 1)], b.personajes["Reyes"]))


def _recuerdo_antes_de_nacer(con: sqlite3.Connection, b: banco.Base) -> None:
    """La 3.2 recuerda un suceso de hace 41 años con Idris, que tiene 38."""
    _analepsis(con, b, (3, 2))
    _evento(con, b, (3, 2), 5, -15000, descripcion="Idris ve el primer lanzamiento")


def _edad_que_no_cuadra(con: sqlite3.Connection, b: banco.Base) -> None:
    """La prosa da a Idris 45 años; el elenco le dio 38."""
    banco._hecho(con, b, (3, 1), "Idris", "edad", "45 años")  # pyright: ignore[reportPrivateUsage]


def _recuerdo_del_futuro(con: sqlite3.Connection, b: banco.Base) -> None:
    """Un evento de la analepsis 3.2 cae el dia 9, cuando la historia va por el 3."""
    _analepsis(con, b, (3, 2))
    _evento(con, b, (3, 2), 6, 9)


CASOS: list[tuple[str, Callable[[sqlite3.Connection, banco.Base], None], str]] = [
    ("recuerdo_tras_la_muerte", _recuerdo_tras_la_muerte, "lean_nadie_tras_morir"),
    ("presente_por_el_extractor_tras_morir", _presente_por_el_extractor_tras_morir,
     "lean_nadie_tras_morir"),
    ("recuerdo_antes_de_nacer", _recuerdo_antes_de_nacer, "lean_nadie_antes_de_nacer"),
    ("edad_que_no_cuadra", _edad_que_no_cuadra, "lean_edad_coherente"),
    ("recuerdo_del_futuro", _recuerdo_del_futuro, "lean_el_tiempo_no_retrocede"),
]


@sin_lean
def test_la_novela_de_demo_pasa(con: sqlite3.Connection, base: banco.Base) -> None:
    r = lean.verificar(con, base.novela_id)
    assert r.conflictos == []


@sin_lean
@pytest.mark.parametrize(("mutar", "esperado"), [(m, e) for _, m, e in CASOS],
                         ids=[n for n, _, _ in CASOS])
def test_lean_ve_lo_que_la_puerta_3_no_ve(
    con: sqlite3.Connection, base: banco.Base,
    mutar: Callable[[sqlite3.Connection, banco.Base], None], esperado: str,
) -> None:
    with db.transaccion(con):
        mutar(con, base)
    assert _puerta_3(con, base) == set(), "la puerta 3 ya lo veia: no es evidencia"
    r = lean.verificar(con, base.novela_id)
    assert not r.pasa
    assert {c.comprobacion for c in r.bloqueantes} == {esperado}
    # El editor recibe el capitulo donde corregir, tambien en una edad (que no tiene evento).
    assert all(c.descripcion and c.capitulo == banco.CAPITULO for c in r.bloqueantes)


@sin_lean
def test_un_recuerdo_en_el_pasado_pasa(con: sqlite3.Connection, base: banco.Base) -> None:
    """Control limpio: la analepsis del banco (L04), un recuerdo del dia -3 con Idris."""
    with db.transaccion(con):
        _analepsis(con, base, (3, 2))
        _evento(con, base, (3, 2), 5, -3)
    assert lean.verificar(con, base.novela_id).conflictos == []


@sin_lean
def test_un_fichero_que_no_compila_es_lean_error(con: sqlite3.Connection, base: banco.Base,
                                                 monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lean, "escribir", lambda *_a, **_k: "esto no es Lean\n")
    r = lean.verificar(con, base.novela_id)
    assert [c.comprobacion for c in r.bloqueantes] == ["lean_error"]


# --- RF-LEAN-06: la puerta antes de publicar -----------------------------------------------------


def _lean_que_falla(capitulo: int = 2) -> Callable[..., ResultadoPuerta]:
    return lambda *_a, **_k: ResultadoPuerta(puerta=lean.PUERTA, conflictos=[Conflicto(
        comprobacion="lean_nadie_tras_morir", capitulo=capitulo,
        descripcion="Reyes esta en un suceso el dia 3, pero murio el dia 2.")])


def _generar(
    monkeypatch: pytest.MonkeyPatch, verificar: Callable[..., ResultadoPuerta] | None,
) -> tuple[sqlite3.Connection, int, str]:
    from orquestador import pipeline
    from tests.entorno import cfg_de, crear_novela, nueva_bd, puerto_falso

    if verificar is not None:
        monkeypatch.setattr(lean, "comprobar", verificar)
    conexion, ruta = nueva_bd()
    novela_id = crear_novela(conexion)
    ctx = pipeline.Contexto(con=conexion, puerto=puerto_falso(conexion),
                            cfg=cfg_de(ruta, verificacion_formal=True), novela_id=novela_id)
    return conexion, novela_id, pipeline.avanzar(ctx)


def _puertas_6(conexion: sqlite3.Connection, novela_id: int) -> list[str]:
    return [str(f[0]) for f in conexion.execute(
        "SELECT veredicto FROM resultado_puerta WHERE novela_id = ? AND puerta = 6", (novela_id,))]


def test_si_lean_falla_la_generacion_para_y_no_publica(monkeypatch: pytest.MonkeyPatch) -> None:
    conexion, novela_id, final = _generar(monkeypatch, _lean_que_falla(2))
    assert final == "parada"
    parada = conexion.execute("SELECT tipo, capitulo, informe FROM parada").fetchone()
    assert (parada["tipo"], parada["capitulo"]) == ("formal", 2)
    assert "lean_nadie_tras_morir" in parada["informe"]
    assert conexion.execute("SELECT COUNT(*) FROM novela_version").fetchone()[0] == 0
    assert _puertas_6(conexion, novela_id) == ["falla"]


def test_si_lean_pasa_la_novela_se_publica(monkeypatch: pytest.MonkeyPatch) -> None:
    conexion, novela_id, final = _generar(
        monkeypatch, lambda *_a, **_k: ResultadoPuerta(puerta=lean.PUERTA))
    assert final in ("completada", "completada_con_avisos")
    assert conexion.execute("SELECT COUNT(*) FROM novela_version").fetchone()[0] == 1
    assert _puertas_6(conexion, novela_id) == ["pasa"]


def test_sin_lean_la_generacion_para(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lean, "lake_disponible", lambda: None)
    conexion, _, final = _generar(monkeypatch, None)
    assert final == "parada"
    parada = conexion.execute("SELECT tipo, capitulo, informe FROM parada").fetchone()
    assert parada["tipo"] == "formal" and "lean_no_disponible" in parada["informe"]
    # Sin capitulo en el conflicto, apunta al ultimo: relanzar no rehace la novela entera.
    assert parada["capitulo"] == 3


def test_una_parada_formal_se_resuelve_relanzando() -> None:
    from orquestador import estados

    assert estados.acciones_validas("formal") == ["relanzar"]
    assert estados.siguiente("parada", "relanzar", tipo_parada="formal") == "generando"


def test_un_cambio_del_lector_que_rompe_la_cronologia_fracasa_sin_parada(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import worker
    from compartido.grafo import lectura
    from tests.entorno import cfg_de
    from tests.test_cambio_lector import SOLO_EN_EL_DOS, _completa, _id, _pedir

    conexion, ruta, novela_id = _completa()
    monkeypatch.setattr(lean, "comprobar", _lean_que_falla(2))
    reyes = _id(conexion, "personaje", SOLO_EN_EL_DOS)
    w = worker.Worker(cfg_de(ruta, verificacion_formal=True), con=conexion)
    intencion = _pedir(conexion, ruta, novela_id, "Que se llame Oriol",
                       {"tipo": "entidad", "entidad": "personajes", "id": reyes}, w=w)
    cambio = lectura.cambio(conexion, novela_id, intencion["resultado"]["cambio_id"]) or {}
    assert cambio["estado"] == "fallido" and "Lean" in str(cambio["informe"])
    entidad = lectura.entidad(conexion, novela_id, "personaje", reyes) or {}
    assert entidad["nombre"] == SOLO_EN_EL_DOS
    assert [v["numero"] for v in lectura.versiones(conexion, novela_id)] == [1]
    assert conexion.execute(
        "SELECT COUNT(*) FROM parada WHERE tipo = 'formal'").fetchone()[0] == 0
    # La puerta 6 queda registrada aunque el cambio se deshaga (sale a Langfuse).
    assert _puertas_6(conexion, novela_id) == ["falla"]
    estado = conexion.execute("SELECT estado FROM ejecucion WHERE novela_id = ?",
                              (novela_id,)).fetchone()[0]
    assert estado in ("completada", "completada_con_avisos")


def test_la_configuracion_de_verdad_activa_la_verificacion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import config

    monkeypatch.setenv("NOVELAS_DB_PATH", "x.db")
    monkeypatch.delenv("NOVELAS_VERIFICACION_FORMAL", raising=False)
    assert config.cargar().verificacion_formal is True
    monkeypatch.setenv("NOVELAS_VERIFICACION_FORMAL", "0")
    assert config.cargar().verificacion_formal is False


def test_al_relanzar_una_parada_formal_el_redactor_recibe_lo_que_encontro_lean(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import worker
    from compartido.db import transaccion
    from orquestador import cola
    from tests.entorno import cfg_de

    llamadas: list[int] = []

    def falla_la_primera(*_a: object, **_k: object) -> ResultadoPuerta:
        llamadas.append(1)
        return (_lean_que_falla(2)() if len(llamadas) == 1
                else ResultadoPuerta(puerta=lean.PUERTA))

    conexion, novela_id, final = _generar(monkeypatch, falla_la_primera)
    assert final == "parada"
    ruta = Path(conexion.execute("PRAGMA database_list").fetchone()[2])
    w = worker.Worker(cfg_de(ruta, verificacion_formal=True), con=conexion)
    entradas: list[str] = []
    w.puerto.registrar(  # type: ignore[attr-defined]
        "redaccion", lambda e, a: entradas.append(e) or agentes_falsos.redaccion(e, a))
    parada_id = conexion.execute("SELECT id FROM parada").fetchone()[0]
    with transaccion(conexion):
        iid = cola.encolar(conexion, "resolver_parada", novela_id, parada_id=parada_id,
                           accion="relanzar")
    w._resolver_parada(cola.Intencion(id=iid, tipo="resolver_parada", novela_id=novela_id,
                                      payload={"parada_id": parada_id, "accion": "relanzar"}))
    estado = conexion.execute("SELECT estado FROM ejecucion WHERE novela_id = ?",
                              (novela_id,)).fetchone()[0]
    assert estado in ("completada", "completada_con_avisos")
    # El capitulo 2 recibe el conflicto en su primer intento; el 3, que no lo tenia, no.
    assert "lean_nadie_tras_morir" in entradas[0]
    assert all("lean_nadie_tras_morir" not in e for e in entradas[1:])
    assert _puertas_6(conexion, novela_id) == ["falla", "pasa"]
    # Completada la novela, lo que encontro Lean ya no vale para otra regeneracion.
    from orquestador import pipeline

    ctx = pipeline.Contexto(con=conexion, puerto=w.puerto, cfg=w.cfg, novela_id=novela_id)
    assert pipeline._criterios_formales(ctx, 2) == []  # pyright: ignore[reportPrivateUsage]


def test_un_cambio_que_fracaso_en_lean_no_da_criterios_al_redactor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """La puerta 6 de un cambio fallido se calculo sobre un canon deshecho: no es feedback."""
    import worker
    from orquestador import pipeline
    from tests.entorno import cfg_de
    from tests.test_cambio_lector import SOLO_EN_EL_DOS, _completa, _id, _pedir

    conexion, ruta, novela_id = _completa()
    monkeypatch.setattr(lean, "comprobar", _lean_que_falla(2))
    w = worker.Worker(cfg_de(ruta, verificacion_formal=True), con=conexion)
    _pedir(conexion, ruta, novela_id, "Que se llame Oriol",
           {"tipo": "entidad", "entidad": "personajes",
            "id": _id(conexion, "personaje", SOLO_EN_EL_DOS)}, w=w)
    ctx = pipeline.Contexto(con=conexion, puerto=w.puerto, cfg=w.cfg, novela_id=novela_id)
    assert _puertas_6(conexion, novela_id) == ["falla"]
    assert pipeline._criterios_formales(ctx, 2) == []  # pyright: ignore[reportPrivateUsage]


def test_sin_lean_el_redactor_no_recibe_la_herramienta_como_criterio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from orquestador import pipeline
    from tests.entorno import cfg_de

    monkeypatch.setattr(lean, "lake_disponible", lambda: None)
    conexion, novela_id, final = _generar(monkeypatch, None)
    assert final == "parada"
    ruta = Path(conexion.execute("PRAGMA database_list").fetchone()[2])
    ctx = pipeline.Contexto(con=conexion, puerto=None,  # type: ignore[arg-type]
                            cfg=cfg_de(ruta), novela_id=novela_id)
    assert pipeline._criterios_formales(ctx, 3) == []  # pyright: ignore[reportPrivateUsage]


def test_la_puerta_6_va_a_la_unidad_de_cierre_en_langfuse() -> None:
    from orquestador import observabilidad

    assert observabilidad._unidad_de_puerta(6, None) == "cierre"  # pyright: ignore[reportPrivateUsage]
