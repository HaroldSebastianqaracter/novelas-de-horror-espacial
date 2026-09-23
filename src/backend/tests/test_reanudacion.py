"""Reanudar nunca se salta una puerta (spec2, fase 2: RF2-WK-06, RF2-FALLO-03, RF2-PIPE-00).

Resolver una parada de planificacion rehace la fase con el informe de la puerta; la tabla de
acciones por tipo de parada rechaza lo demas sin tocar nada; y `avanzar` deriva del grafo que
toca, asi que ni una caida ni una parada le hacen saltarse la puerta 1 o la 2.
"""

from __future__ import annotations

import json

import pytest

import worker
from compartido import db
from compartido.grafo import lectura
from compartido.puerta_base import Conflicto, ResultadoPuerta
from compartido.puerto import demo as agentes_falsos
from orquestador import cola, fallo, pipeline, vigencia
from tests.entorno import cfg_de, contar, contexto, crear_novela, nueva_bd, puerto_falso


def _falla(puerta: int):  # sustituto de un evaluar de puerta
    def evaluar(*_: object) -> ResultadoPuerta:
        return ResultadoPuerta(
            puerta=puerta, conflictos=[Conflicto("forzado", f"la puerta {puerta} falla")]
        )

    return evaluar


class Caida(BaseException):
    """Simula que el proceso muere: ningun except del pipeline la captura."""


def _intencion(con, tipo: str, novela_id: int, **payload: object) -> cola.Intencion:
    iid = cola.encolar(con, tipo, novela_id, **payload)
    con.execute("UPDATE intencion SET estado = 'en_curso' WHERE id = ?", (iid,))
    return cola.Intencion(id=iid, tipo=tipo, novela_id=novela_id, payload=dict(payload))


def _estado_intencion(con, intencion: cola.Intencion) -> tuple[str, str | None]:
    f = con.execute("SELECT estado, motivo FROM intencion WHERE id = ?", (intencion.id,)).fetchone()
    return str(f["estado"]), f["motivo"]


def _veredictos(con, novela_id: int, puerta: int) -> list[str]:
    return [
        str(f["veredicto"]) for f in con.execute(
            "SELECT veredicto FROM resultado_puerta WHERE novela_id = ? AND puerta = ? "
            "ORDER BY id", (novela_id, puerta),
        )
    ]


def _entradas(w: worker.Worker, agente: str) -> list[str]:
    return [i["entrada"] for i in w.puerto.invocaciones if i["agente"] == agente]  # type: ignore[attr-defined]


@pytest.fixture()
def w() -> worker.Worker:
    _, ruta = nueva_bd()
    return worker.Worker(cfg_de(ruta))


# --- Rehacer una fase de planificacion -----------------------------------------------------------


def test_rehacer_la_escaleta_la_regenera_con_el_informe_y_la_reevalua(
    w: worker.Worker, monkeypatch: pytest.MonkeyPatch
) -> None:
    novela_id = crear_novela(w.con)
    real = pipeline.p_escaleta.evaluar
    monkeypatch.setattr(pipeline.p_escaleta, "evaluar", _falla(2))
    w._correr(novela_id)

    parada = fallo.paradas_abiertas(w.con, novela_id)[0]
    assert parada["tipo"] == "escaleta"
    assert lectura.total_capitulos(w.con, novela_id) == 0
    # El autor puede leer lo que se rechazo sin abrir la base de datos.
    assert json.loads(parada["informe"])["escaleta_rechazada"]

    monkeypatch.setattr(pipeline.p_escaleta, "evaluar", real)
    intencion = _intencion(w.con, "resolver_parada", novela_id, parada_id=parada["id"],
                           accion="rehacer")
    w._resolver_parada(intencion)

    assert _estado_intencion(w.con, intencion)[0] == "hecha"
    veredictos = _veredictos(w.con, novela_id, 2)
    assert veredictos[:2] == ["falla", "falla"] and veredictos[2] != "falla"
    assert "LA ESCALETA ANTERIOR FALLO POR ESTO" in _entradas(w, "escaleta")[-1]
    assert (lectura.ejecucion(w.con, novela_id) or {})["estado"] in (
        "completada", "completada_con_avisos",
    )
    assert db.verificar_integridad(w.con) == []


def test_rehacer_la_estructura_la_regenera_con_el_informe_y_reevalua_la_puerta_1(
    w: worker.Worker, monkeypatch: pytest.MonkeyPatch
) -> None:
    novela_id = crear_novela(w.con)
    real = pipeline.p_estructura.evaluar
    monkeypatch.setattr(pipeline.p_estructura, "evaluar", _falla(1))
    w._correr(novela_id)
    parada = fallo.paradas_abiertas(w.con, novela_id)[0]
    assert parada["tipo"] == "estructura"
    personajes = contar(w.con, "SELECT COUNT(*) FROM personaje WHERE novela_id = ?", novela_id)

    monkeypatch.setattr(pipeline.p_estructura, "evaluar", real)
    w._resolver_parada(_intencion(w.con, "resolver_parada", novela_id,
                                  parada_id=parada["id"], accion="rehacer"))

    assert _veredictos(w.con, novela_id, 1) == ["falla", "pasa"]
    estructuras = _entradas(w, "estructura")
    assert len(estructuras) == 2
    assert "NO PASO LA PUERTA 1" in estructuras[-1]
    # Solo se rehace la estructura: el elenco y el mundo se conservan.
    assert len(_entradas(w, "elenco")) == 1
    assert contar(w.con, "SELECT COUNT(*) FROM personaje WHERE novela_id = ?",
                  novela_id) == personajes
    assert contar(w.con, "SELECT COUNT(*) FROM hilo WHERE novela_id = ?", novela_id) == 2
    assert (lectura.ejecucion(w.con, novela_id) or {})["estado"].startswith("completada")


# --- La tabla cerrada de acciones ----------------------------------------------------------------


@pytest.mark.parametrize("accion", ["relanzar", "aceptar_retcon"])
def test_una_parada_de_estructura_solo_se_resuelve_rehaciendo(
    w: worker.Worker, monkeypatch: pytest.MonkeyPatch, accion: str
) -> None:
    novela_id = crear_novela(w.con)
    monkeypatch.setattr(pipeline.p_estructura, "evaluar", _falla(1))
    w._correr(novela_id)
    parada_id = int(fallo.paradas_abiertas(w.con, novela_id)[0]["id"])
    actos = contar(w.con, "SELECT COUNT(*) FROM acto WHERE novela_id = ?", novela_id)

    intencion = _intencion(w.con, "resolver_parada", novela_id, parada_id=parada_id,
                           accion=accion, desde_capitulo=1)
    w._resolver_parada(intencion)

    estado, motivo = _estado_intencion(w.con, intencion)
    assert estado == "rechazada"
    assert "rehacer" in (motivo or "")
    # Rechazar es no tocar nada.
    assert (lectura.ejecucion(w.con, novela_id) or {})["estado"] == "parada"
    assert contar(w.con, "SELECT COUNT(*) FROM acto WHERE novela_id = ?", novela_id) == actos
    assert fallo.paradas_abiertas(w.con, novela_id)[0]["id"] == parada_id


def test_relanzar_directo_sobre_una_parada_de_estructura_se_rechaza(
    w: worker.Worker, monkeypatch: pytest.MonkeyPatch
) -> None:
    novela_id = crear_novela(w.con)
    monkeypatch.setattr(pipeline.p_estructura, "evaluar", _falla(1))
    w._correr(novela_id)

    intencion = _intencion(w.con, "relanzar", novela_id, desde_capitulo=1)
    w._relanzar(intencion)
    assert _estado_intencion(w.con, intencion)[0] == "rechazada"
    assert (lectura.ejecucion(w.con, novela_id) or {})["estado"] == "parada"


def test_aceptar_retcon_sin_hecho_que_revocar_se_rechaza(w: worker.Worker) -> None:
    """Un conflicto que no es factual (un muerto que reaparece) no tiene hecho previo."""
    novela_id = crear_novela(w.con)

    def muere_y_sigue(entrada: str, agente: str) -> dict:
        salida = agentes_falsos.extraccion(entrada, agente)
        if "capitulo 2" in entrada.lower():
            salida["estados_personaje"].append({
                "escena_orden": 1, "personaje_ref": agentes_falsos.PERSONAJES[1],
                "condicion": "muerto",
            })
        return salida

    w.puerto.registrar("extraccion", muere_y_sigue)  # type: ignore[attr-defined]
    w._correr(novela_id)
    parada = fallo.paradas_abiertas(w.con, novela_id)[0]
    assert parada["tipo"] == "continuidad"

    intencion = _intencion(w.con, "resolver_parada", novela_id, parada_id=parada["id"],
                           accion="aceptar_retcon")
    w._resolver_parada(intencion)
    assert _estado_intencion(w.con, intencion)[0] == "rechazada"
    assert lectura.ultimo_capitulo_completado(w.con, novela_id) == 1


def test_aceptar_retcon_revierte_desde_el_capitulo_de_la_parada_y_no_desde_el_1(
    w: worker.Worker,
) -> None:
    novela_id = crear_novela(w.con)

    def contradice(entrada: str, agente: str) -> dict:
        # Desde el capitulo 2 el olor es otro: contradice al 1 hasta que el autor lo revoca.
        salida = agentes_falsos.extraccion(entrada, agente)
        if agentes_falsos._capitulo(entrada) >= 2:
            salida["hechos"][0]["valor"] = "aire limpio y sin olor"
        return salida

    w.puerto.registrar("extraccion", contradice)  # type: ignore[attr-defined]
    w._correr(novela_id)
    parada = fallo.paradas_abiertas(w.con, novela_id)[0]
    assert (parada["tipo"], parada["capitulo"]) == ("continuidad", 2)
    compilado_1 = w.con.execute(
        "SELECT cc.id FROM capitulo_compilado cc JOIN capitulo c ON c.id = cc.capitulo_id "
        "WHERE c.novela_id = ? AND c.numero = 1 AND cc.estado = 'vigente'", (novela_id,)
    ).fetchone()["id"]

    intencion = _intencion(w.con, "resolver_parada", novela_id, parada_id=parada["id"],
                           accion="aceptar_retcon")
    w._resolver_parada(intencion)

    assert _estado_intencion(w.con, intencion)[0] == "hecha"
    # El capitulo 1 no se ha regenerado: su compilado vigente es el mismo.
    assert w.con.execute(
        "SELECT cc.id FROM capitulo_compilado cc JOIN capitulo c ON c.id = cc.capitulo_id "
        "WHERE c.novela_id = ? AND c.numero = 1 AND cc.estado = 'vigente'", (novela_id,)
    ).fetchone()["id"] == compilado_1
    assert (lectura.ejecucion(w.con, novela_id) or {})["estado"].startswith("completada")


# --- avanzar deriva del grafo --------------------------------------------------------------------


def test_una_caida_entre_la_estructura_y_la_puerta_1_no_salta_la_puerta(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Al arrancar tras la caida se evalua la puerta 1, y si falla no se escaleta."""
    con, ruta = nueva_bd()
    novela_id = crear_novela(con)

    def cae(*_: object) -> ResultadoPuerta:
        raise Caida()

    monkeypatch.setattr(pipeline.p_estructura, "evaluar", cae)
    with pytest.raises(Caida):
        pipeline.avanzar(contexto(con, puerto_falso(con), ruta, novela_id))
    assert contar(con, "SELECT COUNT(*) FROM acto WHERE novela_id = ?", novela_id) > 0
    assert _veredictos(con, novela_id, 1) == []

    w = worker.Worker(cfg_de(ruta))
    w.recuperar()
    assert (lectura.ejecucion(w.con, novela_id) or {})["estado"] == "detenida"

    monkeypatch.setattr(pipeline.p_estructura, "evaluar", _falla(1))
    w._arrancar(_intencion(w.con, "arrancar", novela_id))

    assert _veredictos(w.con, novela_id, 1) == ["falla"]
    assert lectura.total_capitulos(w.con, novela_id) == 0
    assert _entradas(w, "escaleta") == []
    assert fallo.paradas_abiertas(w.con, novela_id)[0]["tipo"] == "estructura"


def test_la_puerta_deja_de_estar_vigente_si_cambia_lo_que_juzgo() -> None:
    con, ruta = nueva_bd()
    novela_id = crear_novela(con)
    ctx = contexto(con, puerto_falso(con), ruta, novela_id)
    pipeline.planificar(ctx)
    pipeline.escaletar(ctx)
    assert vigencia.puerta_vigente(con, novela_id, 1)
    assert vigencia.puerta_vigente(con, novela_id, 2)

    con.execute("UPDATE escena SET objetivo = 'otro objetivo' WHERE novela_id = ?", (novela_id,))
    assert vigencia.puerta_vigente(con, novela_id, 1)
    assert not vigencia.puerta_vigente(con, novela_id, 2)

    # Cambiar el estado de un capitulo al escribirlo no es replanificar.
    con.execute("UPDATE capitulo SET estado = 'completado' WHERE novela_id = ?", (novela_id,))
    con.execute("UPDATE escena SET objetivo = 'Revisar la cubierta' WHERE novela_id = ?",
                (novela_id,))
    assert not vigencia.puerta_vigente(con, novela_id, 2)


def test_generar_un_capitulo_sin_puertas_vigentes_acaba_en_error(
    w: worker.Worker, monkeypatch: pytest.MonkeyPatch
) -> None:
    """El guardarrail de RF2-PIPE-00b: aunque la derivacion fallara, no sale un capitulo."""
    novela_id = crear_novela(w.con)
    monkeypatch.setattr(pipeline.vigencia, "puerta_vigente", lambda *_: True)
    ctx = pipeline.Contexto(con=w.con, puerto=w.puerto, cfg=w.cfg, novela_id=novela_id)
    pipeline.planificar(ctx)
    monkeypatch.undo()

    with pytest.raises(pipeline.PuertasNoVigentes):
        pipeline.generar_capitulo(ctx, 1)
    assert lectura.total_capitulos(w.con, novela_id) == 0


def test_arrancar_una_novela_completada_se_rechaza(w: worker.Worker) -> None:
    novela_id = crear_novela(w.con)
    w._correr(novela_id)
    assert (lectura.ejecucion(w.con, novela_id) or {})["estado"].startswith("completada")

    intencion = _intencion(w.con, "arrancar", novela_id)
    w._arrancar(intencion)
    estado, motivo = _estado_intencion(w.con, intencion)
    assert estado == "rechazada"
    assert "relanza" in (motivo or "")
    assert (lectura.ejecucion(w.con, novela_id) or {})["estado"].startswith("completada")


def test_el_retcon_es_un_registro_y_relanzar_desde_antes_lo_deshace(w: worker.Worker) -> None:
    """Revocar inserta en hecho_revocacion sin tocar el hecho (RF2-PER-06), y relanzar desde
    antes del capitulo del retcon devuelve el hecho revocado al canon."""
    novela_id = crear_novela(w.con)

    def contradice(entrada: str, agente: str) -> dict:
        salida = agentes_falsos.extraccion(entrada, agente)
        if agentes_falsos._capitulo(entrada) >= 3:
            # Un rasgo sin conocimiento ni usos asociados: el conflicto es solo factual.
            for h in salida["hechos"]:
                if h["atributo"] == "voz":
                    h["valor"] = "aguda y rota"
        return salida

    w.puerto.registrar("extraccion", contradice)  # type: ignore[attr-defined]
    w._correr(novela_id)
    parada = fallo.paradas_abiertas(w.con, novela_id)[0]
    assert (parada["tipo"], parada["capitulo"]) == ("continuidad", 3)
    revocables = fallo.hechos_a_revocar(w.con, int(parada["id"]))
    valores = {
        f["id"]: f["valor"] for f in w.con.execute("SELECT id, valor FROM hecho").fetchall()
    }

    w._resolver_parada(_intencion(w.con, "resolver_parada", novela_id, parada_id=parada["id"],
                                  accion="aceptar_retcon"))
    assert {
        f["hecho_id"] for f in w.con.execute("SELECT hecho_id FROM hecho_revocacion")
    } == revocables
    # El hecho revocado sigue ahi, intacto: lo que cambia es que hay una revocacion.
    assert all(
        w.con.execute("SELECT valor FROM hecho WHERE id = ?", (h,)).fetchone()[0] == valores[h]
        for h in revocables
    )
    assert (lectura.ejecucion(w.con, novela_id) or {})["estado"].startswith("completada")

    del_capitulo_1 = w.con.execute(
        "SELECT h.id FROM hecho h JOIN escena_ordinal eo ON eo.escena_id = h.escena_id "
        "WHERE eo.capitulo_numero = 1 AND h.atributo = 'voz'"
    ).fetchone()["id"]
    assert del_capitulo_1 in revocables
    w._relanzar(_intencion(w.con, "relanzar", novela_id, desde_capitulo=2))

    # La revocacion era del capitulo 3: relanzar desde el 2 la deshace con todo lo demas.
    assert w.con.execute("SELECT COUNT(*) FROM hecho_revocacion").fetchone()[0] == 0
    # El hecho del capitulo 1 vuelve a ser canon, y el capitulo 3 vuelve a chocar con el.
    assert fallo.paradas_abiertas(w.con, novela_id)[0]["capitulo"] == 3
    assert del_capitulo_1 in fallo.hechos_a_revocar(
        w.con, int(fallo.paradas_abiertas(w.con, novela_id)[0]["id"])
    )


# --- RF2-FALLO-07: dar por sabido lo que se supo fuera de escena --------------------------------


def _usa_sin_haber_estado(entrada: str, agente: str) -> dict:
    """Reyes usa en el capitulo 2 la voz de Idris, fijada en el 1 en escenas donde no estaba."""
    salida = agentes_falsos.extraccion(entrada, agente)
    if "capitulo 2" in entrada.lower():
        salida["usos_de_conocimiento"].append({
            "escena_orden": 1, "personaje_ref": agentes_falsos.PERSONAJES[2],
            "sujeto_ref": agentes_falsos.PERSONAJES[0], "atributo": "voz",
        })
    return salida


def _reyes_sin_faccion(entrada: str, agente: str) -> dict:
    """Sin faccion, lo que sabe la cuadrilla no le llega entre capitulos (RF2-PIPE-27)."""
    salida = agentes_falsos.elenco(entrada, agente)
    for p in salida["personajes"]:
        if p["nombre"] == agentes_falsos.PERSONAJES[2]:
            p["faccion"] = ""
    return salida


def test_dar_por_sabido_registra_lo_contado_y_el_capitulo_pasa(w: worker.Worker) -> None:
    novela_id = crear_novela(w.con)
    w.puerto.registrar("elenco", _reyes_sin_faccion)  # type: ignore[attr-defined]
    w.puerto.registrar("extraccion", _usa_sin_haber_estado)  # type: ignore[attr-defined]
    w._correr(novela_id)
    parada = fallo.paradas_abiertas(w.con, novela_id)[0]
    assert parada["tipo"] == "continuidad" and parada["capitulo"] == 2

    intencion = _intencion(w.con, "resolver_parada", novela_id, parada_id=parada["id"],
                           accion="dar_por_sabido")
    w._resolver_parada(intencion)
    assert _estado_intencion(w.con, intencion)[0] == "hecha"
    # Contado en la ultima escena del capitulo 1, y por eso sobrevive a relanzar el 2.
    fila = w.con.execute(
        "SELECT ec.via, ec.postura, eo.capitulo_numero FROM estado_conocimiento ec"
        " JOIN personaje p ON p.id = ec.personaje_id"
        " JOIN escena_ordinal eo ON eo.escena_id = ec.escena_id WHERE p.nombre = 'Reyes'"
    ).fetchone()
    assert tuple(fila) == ("se_lo_contaron", "sabe", 1)

    # Aunque el extractor vuelva a registrar el mismo uso, el capitulo ya pasa.
    w._correr(novela_id)
    assert lectura.ultimo_capitulo_completado(w.con, novela_id) == agentes_falsos.CAPITULOS


def test_dar_por_sabido_sin_conflicto_de_conocimiento_se_rechaza(w: worker.Worker) -> None:
    novela_id = crear_novela(w.con)

    def muere_y_sigue(entrada: str, agente: str) -> dict:
        salida = agentes_falsos.extraccion(entrada, agente)
        if "capitulo 2" in entrada.lower():
            salida["estados_personaje"].append({
                "escena_orden": 1, "personaje_ref": agentes_falsos.PERSONAJES[1],
                "condicion": "muerto",
            })
        return salida

    w.puerto.registrar("extraccion", muere_y_sigue)  # type: ignore[attr-defined]
    w._correr(novela_id)
    parada = fallo.paradas_abiertas(w.con, novela_id)[0]
    intencion = _intencion(w.con, "resolver_parada", novela_id, parada_id=parada["id"],
                           accion="dar_por_sabido")
    w._resolver_parada(intencion)
    estado, motivo = _estado_intencion(w.con, intencion)
    assert estado == "rechazada" and "conocimiento" in (motivo or "")
