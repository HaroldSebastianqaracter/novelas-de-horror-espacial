"""Los huecos de la story bible (specs/spec3.md, 3.3: RF3-BIB-01 a RF3-BIB-15).

La demo con el puerto falso deja datos reales de las cuatro piezas: usos de hechos por
reafirmacion y por mencion, edades, dias en la cronologia y la version 1. Sobre la fabrica de
grafos se muta una cosa cada vez para ver que cada comprobacion nueva la detecta.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

import config
import main
from compartido import db
from compartido.db import transaccion, verificar_integridad
from compartido.grafo import insertar, insertar_hecho, lectura
from compartido.puerto import demo
from orquestador import fallo, pipeline, versiones, vigencia
from tareas.continuidad import puerta as p_continuidad
from tareas.elenco.esquemas import PersonajeSalida
from tareas.estructura import puerta as p_estructura
from tareas.extraccion import servicio as s_extraccion
from tareas.extraccion.esquemas import EventoExtraido
from tareas.mundo import servicio as s_mundo
from tareas.mundo.esquemas import EventoPrevio, SalidaMundo
from tests import fabrica
from tests.entorno import contar, contexto, crear_novela, nueva_bd, puerto_falso
from tests.test_demo import _correr, _en_el_capitulo_2
from tests.test_personalizacion import comprobaciones, crear, id_destinatario, planificada


def _demo() -> tuple[sqlite3.Connection, int, Path]:
    con, ruta = nueva_bd()
    novela_id = crear_novela(con)
    assert pipeline.avanzar(contexto(con, puerto_falso(con), ruta, novela_id)) == "completada"
    return con, novela_id, ruta


@pytest.fixture(scope="module")
def demo_entera() -> tuple[sqlite3.Connection, int, Path]:
    return _demo()


def _hecho(con: sqlite3.Connection, novela_id: int, atributo: str) -> int:
    return int(con.execute(
        "SELECT id FROM hecho WHERE novela_id = ? AND atributo = ?", (novela_id, atributo)
    ).fetchone()[0])


def _nombres(violaciones: list[db.Violacion]) -> set[str]:
    return {v.regla for v in violaciones}


# --- RF3-BIB-01 y RF3-BIB-02: donde se usa cada hecho ----------------------------------------


def test_repetir_un_hecho_vigente_deja_su_uso_con_la_cita(
    demo_entera: tuple[sqlite3.Connection, int, Path],
) -> None:
    """El olor del puente se dice en cada capitulo: un solo hecho y dos reafirmaciones."""
    con, novela_id, _ = demo_entera
    olor = _hecho(con, novela_id, "olor")
    usos = lectura.usos_de_hecho(con, novela_id, olor)
    assert [(u["capitulo"], u["via"]) for u in usos if u["via"] in ("establece", "reafirma")] == [
        (1, "establece"), (2, "reafirma"), (3, "reafirma"),
    ]
    assert {u["cita"] for u in usos if u["via"] == "reafirma"} == {
        "olor: metal frio y algo dulce"
    }


def test_el_valor_exacto_en_la_prosa_es_una_mencion(
    demo_entera: tuple[sqlite3.Connection, int, Path],
) -> None:
    """La distancia a la esclusa se fija una vez y la prosa la repite en cada escena."""
    con, novela_id, _ = demo_entera
    distancia = _hecho(con, novela_id, "distancia al puente")
    menciones = [
        (u["capitulo"], u["escena_orden"]) for u in lectura.usos_de_hecho(con, novela_id, distancia)
        if u["via"] == "menciona"
    ]
    # La escena que lo establece no se cuenta como uso suyo.
    assert menciones == [(1, 2), (2, 1), (2, 2), (3, 1), (3, 2)]
    assert lectura.capitulos_de_hecho(con, novela_id, distancia) == [1, 2, 3]


def test_un_rasgo_descriptivo_no_se_busca_en_la_prosa(
    demo_entera: tuple[sqlite3.Connection, int, Path],
) -> None:
    """«Alta» o «castano corto» aparecen en cualquier descripcion: no son menciones."""
    con, _, _ = demo_entera
    assert contar(con, """
        SELECT COUNT(*) FROM hecho_uso u JOIN hecho h ON h.id = u.hecho_id
        WHERE u.via = 'menciona' AND h.categoria NOT IN ('nombre', 'fecha', 'distancia')
          AND h.valor NOT GLOB '*[0-9]*'
    """) == 0


def _hecho_literal(con: sqlite3.Connection, g: fabrica.Grafo, escena: tuple[int, int],
                   valor: str, categoria: str = "nombre") -> int:
    return insertar_hecho(
        con, novela_id=g.novela_id, escena_id=g.escenas[escena], sujeto_tipo="mundo",
        sujeto_id=None, sujeto_nombre="Estacion Tesalia", atributo=f"dato {valor}", valor=valor,
        categoria=categoria, cita=None, supersede_a=None,
    )


def test_una_mencion_solo_cuenta_hechos_de_escenas_anteriores() -> None:
    con, _ = nueva_bd()
    g = fabrica.novela_minima(con)
    hid = _hecho_literal(con, g, (1, 2), "Tesalia Norte")
    por_orden = {1: g.escenas[(1, 1)], 2: g.escenas[(1, 2)]}
    texto = "La baliza de Tesalia Norte seguia muda."
    # La escena 1 va antes que el hecho, y la 2 es la que lo establece.
    assert s_extraccion.registrar_menciones(
        con, g.novela_id, por_orden, {1: texto, 2: texto}
    ) == 0
    assert s_extraccion.registrar_menciones(
        con, g.novela_id, {1: g.escenas[(2, 1)]}, {1: texto}
    ) == 1
    assert lectura.capitulos_de_hecho(con, g.novela_id, hid) == [1, 2]


def test_un_valor_corto_sin_cifras_no_se_busca_y_una_cifra_si() -> None:
    con, _ = nueva_bd()
    g = fabrica.novela_minima(con)
    _hecho_literal(con, g, (1, 1), "Oz")
    _hecho_literal(con, g, (1, 1), "12", categoria="fisico")
    registrados = s_extraccion.registrar_menciones(
        con, g.novela_id, {1: g.escenas[(2, 1)]}, {1: "Oz conto 12 pasos hasta la puerta."}
    )
    assert registrados == 1
    assert con.execute("SELECT cita FROM hecho_uso").fetchone()[0] == "12"


@pytest.mark.parametrize(("sustituido_en", "menciones"), [((1, 2), 0), ((2, 2), 1)])
def test_un_valor_solo_se_busca_mientras_no_este_sustituido(
    sustituido_en: tuple[int, int], menciones: int
) -> None:
    """Repetir «12 metros» en la escena 2.1: despues de la sustitucion no es un uso; antes de
    ella, cuando todavia era el valor vigente, si."""
    con, _ = nueva_bd()
    g = fabrica.novela_minima(con)
    viejo = _hecho_literal(con, g, (1, 1), "12 metros", categoria="distancia")
    insertar_hecho(
        con, novela_id=g.novela_id, escena_id=g.escenas[sustituido_en], sujeto_tipo="mundo",
        sujeto_id=None, sujeto_nombre="Estacion Tesalia", atributo="dato 12 metros",
        valor="15 metros", categoria="distancia", cita=None, supersede_a=viejo,
    )
    assert s_extraccion.registrar_menciones(
        con, g.novela_id, {1: g.escenas[(2, 1)]}, {1: "Antes estaba a 12 metros."}
    ) == menciones


def test_revertir_un_capitulo_borra_sus_usos() -> None:
    con, novela_id, _ = _demo()
    with transaccion(con):
        borrado = fallo.revertir_grafo(con, novela_id, 2)
    assert borrado["hecho_uso"] > 0
    capitulos = {int(f[0]) for f in con.execute(
        "SELECT eo.capitulo_numero FROM hecho_uso u JOIN escena_ordinal eo "
        "ON eo.escena_id = u.escena_id"
    )}
    assert capitulos == {1}


def test_la_integridad_detecta_un_uso_anterior_a_su_hecho() -> None:
    con, _ = nueva_bd()
    g = fabrica.novela_minima(con)
    ojos = g.hechos["ojos"]
    con.execute(
        "INSERT INTO hecho_uso (novela_id, hecho_id, escena_id, via) VALUES (?,?,?,'reafirma')",
        (g.novela_id, ojos, g.escenas[(2, 1)]),
    )
    assert "uso_antes_del_hecho" not in _nombres(verificar_integridad(con))
    con.execute(
        "INSERT INTO hecho_uso (novela_id, hecho_id, escena_id, via) VALUES (?,?,?,'reafirma')",
        (g.novela_id, ojos, g.escenas[(1, 1)]),
    )
    assert "uso_antes_del_hecho" in _nombres(verificar_integridad(con))


# --- RF3-BIB-03: lo que ve la puerta 3 --------------------------------------------------------


def _avisos(con: sqlite3.Connection, novela_id: int, capitulo: int,
            textos: dict[int, str]) -> set[str]:
    return {
        c.comprobacion for c in p_continuidad.busquedas_dirigidas(con, novela_id, capitulo, textos)
    }


def test_una_reafirmacion_cuenta_como_registro_de_la_entidad_nombrada() -> None:
    """Antes, nombrar a Ibarra y solo reafirmar sus ojos dejaba un falso `nombre_sin_registro`."""
    con, _ = nueva_bd()
    g = fabrica.novela_minima(con)
    textos = {1: "Ibarra miro la escotilla sin parpadear."}
    assert "nombre_sin_registro" in _avisos(con, g.novela_id, 2, textos)
    con.execute(
        "INSERT INTO hecho_uso (novela_id, hecho_id, escena_id, via, cita) "
        "VALUES (?,?,?,'reafirma','los ojos grises')",
        (g.novela_id, g.hechos["ojos"], g.escenas[(2, 1)]),
    )
    assert "nombre_sin_registro" not in _avisos(con, g.novela_id, 2, textos)


def test_una_cifra_que_ya_esta_en_el_canon_no_avisa() -> None:
    con, _ = nueva_bd()
    g = fabrica.novela_minima(con)
    _hecho_literal(con, g, (1, 1), "12 metros", categoria="distancia")
    textos = {1: "La esclusa quedaba a 12 metros."}
    assert "cifra_sin_hecho" in _avisos(con, g.novela_id, 2, textos)
    s_extraccion.registrar_menciones(con, g.novela_id, {1: g.escenas[(2, 1)]}, textos)
    assert "cifra_sin_hecho" not in _avisos(con, g.novela_id, 2, textos)


# --- RF3-BIB-04 a RF3-BIB-07: edad ------------------------------------------------------------


def test_el_elenco_tiene_que_declarar_la_edad() -> None:
    base = {
        "nombre": "Idris", "rol_narrativo": "protagonista", "deseo": "Volver a casa",
        "necesidad_interna": "Soltar el pasado", "fantasma": "El accidente del muelle",
        "herida": "La culpa que le quedo", "mentira": "Si suelta, mata", "defecto": "No suelta",
        "tipo_arco": "positivo", "idiolecto": "Frases cortas", "posicion_tematica": "Salvar",
    }
    with pytest.raises(ValidationError):
        PersonajeSalida.model_validate(base)
    with pytest.raises(ValidationError):
        PersonajeSalida.model_validate({**base, "edad": -1})
    assert PersonajeSalida.model_validate({**base, "edad": 34}).edad == 34


def test_el_nacimiento_cae_a_mitad_de_ano() -> None:
    con, _ = nueva_bd()
    g = fabrica.novela_minima(con)
    con.execute("UPDATE personaje SET edad = 34 WHERE id = ?", (g.personajes["Kowalski"],))
    nacimiento = int(con.execute(
        "SELECT nacimiento_dia FROM personaje_nacimiento WHERE personaje_id = ?",
        (g.personajes["Kowalski"],),
    ).fetchone()[0])
    assert nacimiento == -(34 * 365) - 182

    def edad(dia: int) -> int:
        return (dia - nacimiento) // 365

    # Medio ano antes y despues del dia 0 tiene la edad declarada; ni un dia mas.
    assert [edad(d) for d in (-183, -182, 0, 182, 183)] == [33, 34, 34, 34, 35]
    # Sin edad (novelas anteriores al bloque 3) no hay nacimiento que inventar.
    assert contar(con, "SELECT COUNT(*) FROM personaje_nacimiento") == 1


def test_puerta_1_el_protagonista_tiene_la_edad_del_destinatario() -> None:
    con, novela_id = planificada()
    assert lectura.brief(con, novela_id) is not None
    con.execute("UPDATE personaje SET edad = edad + 1 WHERE id = ?",
                (id_destinatario(con, novela_id),))
    resultado = p_estructura.evaluar(con, novela_id)
    assert "edad_del_destinatario" in comprobaciones(resultado)


def test_un_rechazo_por_edad_se_rehace_desde_el_elenco() -> None:
    con, novela_id = planificada()
    con.execute("UPDATE personaje SET edad = 3 WHERE id = ?", (id_destinatario(con, novela_id),))
    resultado = p_estructura.evaluar(con, novela_id)
    insertar(con, "resultado_puerta", novela_id=novela_id, puerta=1, veredicto="falla",
             detalle=json.dumps(resultado.informe()))
    assert fallo.fase_a_rehacer(con, novela_id) == "elenco"


def test_la_edad_entra_en_la_huella_de_la_puerta_1_solo_con_brief() -> None:
    con, novela_id = planificada()
    antes = vigencia.huella(con, novela_id, 1)
    con.execute("UPDATE personaje SET edad = edad + 1 WHERE novela_id = ? AND "
                "rol_narrativo = 'oponente'", (novela_id,))
    assert vigencia.huella(con, novela_id, 1) != antes

    con, ruta = nueva_bd()
    sin_brief = crear_novela(con)
    pipeline.planificar(contexto(con, puerto_falso(con), ruta, sin_brief))
    antes = vigencia.huella(con, sin_brief, 1)
    con.execute("UPDATE personaje SET edad = edad + 1 WHERE novela_id = ?", (sin_brief,))
    assert vigencia.huella(con, sin_brief, 1) == antes


def test_una_novela_con_brief_anterior_al_bloque_3_conserva_su_puerta_1() -> None:
    """Hallazgo 1 del validador: sin edades, la huella es la que registro el codigo del bloque 2,
    y la puerta no exige una edad que el elenco de entonces no declaraba."""
    import hashlib

    from tests.test_personalizacion import LECTURAS_PUERTA_1_ANTES_DE_SPEC3

    lecturas_del_bloque_2 = (
        *LECTURAS_PUERTA_1_ANTES_DE_SPEC3,
        "SELECT contenido FROM brief WHERE novela_id = :n",
        "SELECT id, nombre_clave FROM personaje WHERE novela_id = :n ORDER BY id",
        "SELECT dedicatoria FROM novela WHERE id = :n",
    )
    con, novela_id = planificada()
    con.execute("UPDATE personaje SET edad = NULL WHERE novela_id = ?", (novela_id,))
    filas: list[list[Any]] = []
    for sql in lecturas_del_bloque_2:
        filas.extend([list(f) for f in con.execute(sql, {"n": novela_id}).fetchall()])
        filas.append(["--"])
    esperada = hashlib.sha256(
        json.dumps(filas, ensure_ascii=False, default=str, separators=(",", ":")).encode()
    ).hexdigest()
    assert vigencia.huella(con, novela_id, 1) == esperada
    assert "edad_del_destinatario" not in comprobaciones(p_estructura.evaluar(con, novela_id))


def test_el_redactor_ve_la_edad_de_cada_personaje() -> None:
    con, ruta = nueva_bd()
    novela_id = crear(con, ruta, capitulos=3)
    ctx = contexto(con, puerto_falso(con), ruta, novela_id)
    pipeline.avanzar(ctx)
    entradas = [i["entrada"] for i in ctx.puerto.invocaciones if i["agente"] == "redaccion"]
    assert entradas
    assert all("**Marta Ibáñez** (protagonista, 34 años)" in e for e in entradas)


# --- RF3-BIB-08 a RF3-BIB-10: cronologia ------------------------------------------------------


def test_un_evento_dramatizado_sin_dia_no_valida() -> None:
    with pytest.raises(ValidationError, match="no trae dia"):
        EventoExtraido(fecha_interna="dia 3", orden_interno=3, descripcion="Se abre la esclusa")
    # Un evento que no se dramatiza puede no tenerlo, como el orden interno.
    EventoExtraido(fecha_interna="hace anos", descripcion="La estacion se construyo",
                   dramatizado=False)


def test_un_antecedente_no_puede_caer_despues_del_comienzo() -> None:
    with pytest.raises(ValidationError):
        EventoPrevio(fecha_interna="dentro de cinco dias", dia=5, descripcion="Llega el relevo")
    assert EventoPrevio(fecha_interna="hoy", dia=0, descripcion="Atraca el remolcador").dia == 0


def test_los_antecedentes_se_ordenan_por_su_dia_y_no_por_la_lista() -> None:
    con, _ = nueva_bd()
    novela_id = crear_novela(con)
    salida = demo.mundo("", "mundo")
    salida["eventos_previos"] = [
        {"fecha_interna": "hace diez dias", "dia": -10, "descripcion": "Se corta la radio"},
        {"fecha_interna": "hace diez meses", "dia": -300, "descripcion": "Llega el cargamento"},
    ]
    with transaccion(con):
        s_mundo.aplicar(con, novela_id, SalidaMundo.model_validate(salida))
    orden = [str(f[0]) for f in con.execute(
        "SELECT descripcion FROM evento WHERE novela_id = ? ORDER BY orden_interno", (novela_id,)
    )]
    assert orden == ["Llega el cargamento", "Se corta la radio"]


def _dia_contra_orden(con: sqlite3.Connection, g: fabrica.Grafo, capitulo: int) -> list[Any]:
    resultado = p_continuidad.evaluar(con, g.novela_id, capitulo)
    return [c for c in resultado.bloqueantes if c.comprobacion == "dia_contra_orden"]


def test_puerta_3_un_suceso_posterior_no_cae_en_un_dia_anterior() -> None:
    con, _ = nueva_bd()
    g = fabrica.novela_minima(con)
    assert _dia_contra_orden(con, g, 2) == []
    con.execute("UPDATE evento SET dia = 0 WHERE escena_id = ?", (g.escenas[(2, 1)],))
    conflictos = _dia_contra_orden(con, g, 2)
    # Contradice a los dos sucesos del capitulo 1, y cada par sale una sola vez.
    assert len(conflictos) == 2
    assert {c.escena_id for c in conflictos} == {g.escenas[(2, 1)]}


def test_puerta_3_un_suceso_colocado_antes_no_puede_caer_despues() -> None:
    """El capitulo 2 coloca un suceso antes de todo lo escrito, pero en un dia posterior."""
    con, _ = nueva_bd()
    g = fabrica.novela_minima(con)
    con.execute("UPDATE evento SET orden_interno = 0, dia = 10 WHERE escena_id = ?",
                (g.escenas[(2, 1)],))
    conflictos = _dia_contra_orden(con, g, 2)
    # El par con el capitulo 1: el evento de orden mayor es el viejo, y el conflicto se ancla en
    # la escena de este capitulo. (Tambien choca con el otro suceso del capitulo 2.)
    con_el_anterior = [c for c in conflictos if c.datos["capitulo_evento"] == 1]
    assert len(con_el_anterior) == 2
    assert {c.escena_id for c in con_el_anterior} == {g.escenas[(2, 1)]}


def test_puerta_3_un_recuerdo_no_choca_con_los_antecedentes_del_mundo() -> None:
    """Hallazgo 2 del validador: el extractor no ve el orden negativo de los antecedentes, asi
    que una analepsis anterior a ellos chocaba siempre. Como en `coherencia_temporal`, las
    analepsis y los antecedentes quedan fuera."""
    con, _ = nueva_bd()
    g = fabrica.novela_minima(con)
    con.execute(
        "INSERT INTO evento (novela_id, linea_de_tiempo_id, fecha_interna, dia, orden_interno,"
        " descripcion, dramatizado) VALUES (?, ?, 'hace ocho meses', -240, -1, 'Se calla', 0)",
        (g.novela_id, g.linea_id),
    )
    con.execute("UPDATE escena SET analepsis = 1 WHERE id = ?", (g.escenas[(2, 1)],))
    con.execute("UPDATE evento SET orden_interno = 5, dia = -300 WHERE escena_id = ?",
                (g.escenas[(2, 1)],))
    assert _dia_contra_orden(con, g, 2) == []


def test_puerta_3_dos_sucesos_simultaneos_caen_el_mismo_dia() -> None:
    con, _ = nueva_bd()
    g = fabrica.novela_minima(con)
    con.execute("UPDATE evento SET orden_interno = 3, dia = 3 WHERE escena_id = ?",
                (g.escenas[(2, 1)],))
    con.execute("UPDATE evento SET orden_interno = 3, dia = 9 WHERE escena_id = ?",
                (g.escenas[(2, 2)],))
    conflictos = _dia_contra_orden(con, g, 2)
    assert len(conflictos) == 1 and "simultaneos" in conflictos[0].descripcion


def test_romper_el_dia_en_la_demo_para_el_pipeline() -> None:
    def vuelve_atras_en_dias(s: dict[str, Any]) -> None:
        for e in s["eventos"]:
            e["dia"] = -5

    con, novela_id, final = _correr(_en_el_capitulo_2(vuelve_atras_en_dias))
    assert final == "parada"
    informe = json.loads(fallo.paradas_abiertas(con, novela_id)[0]["informe"])
    assert "dia_contra_orden" in {c["comprobacion"] for c in informe["conflictos"]}


def test_la_cronologia_ordena_por_dia_con_lugar_y_personajes(
    demo_entera: tuple[sqlite3.Connection, int, Path],
) -> None:
    con, novela_id, _ = demo_entera
    eventos = lectura.cronologia(con, novela_id)
    antecedente, *dramatizados = eventos
    assert (antecedente["dia"], antecedente["capitulo"], antecedente["lugar"],
            antecedente["personajes"]) == (-240, None, None, [])
    dias = [e["dia"] for e in dramatizados]
    assert dias == sorted(dias) and dias[0] == 1
    assert all(e["lugar"] in demo.LUGARES for e in dramatizados)
    # El punto de vista cuenta aunque no este en el reparto declarado.
    assert all({demo.PERSONAJES[0], demo.PERSONAJES[1]} <= set(e["personajes"])
               for e in dramatizados)


# --- RF3-BIB-11 a RF3-BIB-14: versiones -------------------------------------------------------


def test_completar_la_novela_publica_la_version_1(
    demo_entera: tuple[sqlite3.Connection, int, Path],
) -> None:
    con, novela_id, _ = demo_entera
    lista = lectura.versiones(con, novela_id)
    assert [(v["numero"], v["motivo"], v["capitulos_cambiados"]) for v in lista] == [
        (1, "primera", [1, 2, 3]),
    ]
    v1 = lectura.version(con, novela_id, 1)
    assert v1 is not None and all(c["texto"] for c in v1["capitulos"])
    assert not _nombres(verificar_integridad(con)) & {"version_desfasada", "uso_antes_del_hecho"}


def _reescribir_capitulo(con: sqlite3.Connection, novela_id: int, numero: int, texto: str) -> None:
    """Lo que deja un relanzamiento: el compilado anterior descartado y uno nuevo vigente."""
    cap = int(con.execute(
        "SELECT id FROM capitulo WHERE novela_id = ? AND numero = ?", (novela_id, numero)
    ).fetchone()[0])
    con.execute("UPDATE capitulo_compilado SET estado = 'descartada' WHERE capitulo_id = ?", (cap,))
    siguiente = contar(con, "SELECT MAX(version) + 1 FROM capitulo_compilado WHERE capitulo_id = ?",
                       cap)
    insertar(con, "capitulo_compilado", novela_id=novela_id, capitulo_id=cap, version=siguiente,
             texto=texto, palabras=len(texto.split()))


def test_una_version_nueva_solo_si_el_texto_cambia() -> None:
    con, novela_id, _ = _demo()
    original = (lectura.version(con, novela_id, 1) or {})["capitulos"][1]["texto"]
    with transaccion(con):
        assert versiones.publicar(con, novela_id) is None

        _reescribir_capitulo(con, novela_id, 2, "Otra forma de contar el capitulo dos.")
        assert "version_desfasada" in _nombres(verificar_integridad(con))
        assert versiones.publicar(con, novela_id) == 2

        con.execute("UPDATE novela SET dedicatoria = 'Para quien cuenta destellos' WHERE id = ?",
                    (novela_id,))
        assert versiones.publicar(con, novela_id, motivo="cambio_lector",
                                  detalle="La dedicatoria") == 3
    lista = lectura.versiones(con, novela_id)
    assert [(v["numero"], v["motivo"], v["capitulos_cambiados"]) for v in lista] == [
        (1, "primera", [1, 2, 3]), (2, "relanzamiento", [2]), (3, "cambio_lector", []),
    ]
    assert lista[2]["detalle"] == "La dedicatoria"
    # La version anterior conserva su texto aunque el capitulo ya no lo tenga.
    assert (lectura.version(con, novela_id, 1) or {})["capitulos"][1]["texto"] == original
    assert "version_desfasada" not in _nombres(verificar_integridad(con))


def test_la_integridad_ve_una_version_con_titulo_o_capitulos_desfasados() -> None:
    """Hallazgo 4 del validador: no bastaba con que cada capitulo vigente estuviera en ella."""
    con, novela_id, _ = _demo()
    con.execute("UPDATE novela SET titulo = 'Otro titulo' WHERE id = ?", (novela_id,))
    assert "version_desfasada" in _nombres(verificar_integridad(con))
    con.execute("UPDATE novela SET titulo = (SELECT titulo FROM novela_version WHERE numero = 1)"
                " WHERE id = ?", (novela_id,))
    assert "version_desfasada" not in _nombres(verificar_integridad(con))
    # Una escaleta rehecha con un capitulo menos: la version conserva uno que ya no existe.
    con.execute("DELETE FROM capitulo WHERE novela_id = ? AND numero = 3", (novela_id,))
    assert "version_desfasada" in _nombres(verificar_integridad(con))


def test_todo_tipo_de_evento_que_se_emite_esta_registrado() -> None:
    """Revalidacion del bloque 3: `version_publicada` falto en TIPOS_EVENTO y nada lo vio."""
    import re

    from compartido.tipos import TIPOS_EVENTO

    raiz = Path(__file__).resolve().parents[1]
    llamada = re.compile(r'emitir_(?:evento|traza)\(\s*(?:[\w.]+\s*,\s*){1,2}"([a-z_]+)"')
    emitidos = {
        tipo
        for fichero in raiz.rglob("*.py")
        if ".venv" not in fichero.parts and "tests" not in fichero.parts
        for tipo in llamada.findall(fichero.read_text(encoding="utf-8"))
    }
    assert "version_publicada" in emitidos
    assert emitidos - set(TIPOS_EVENTO) == set()


def test_relanzar_y_completar_con_el_mismo_texto_no_crea_version() -> None:
    con, novela_id, ruta = _demo()
    with transaccion(con):
        fallo.relanzar(con, novela_id, 2)
    assert pipeline.avanzar(contexto(con, puerto_falso(con), ruta, novela_id)) == "completada"
    assert [v["numero"] for v in lectura.versiones(con, novela_id)] == [1]


def test_la_migracion_publica_la_version_1_de_las_novelas_completadas() -> None:
    con = db.conectar(Path(tempfile.mkdtemp()) / "novela.db")
    db._aplicar_version(con, db.VERSION_ESQUEMA, db.RUTA_ESQUEMA.read_text(encoding="utf-8"))
    for m in db._migraciones():
        if m.numero < 6:
            db._aplicar_version(
                con, m.numero, m.sql.read_text(encoding="utf-8") if m.sql else "",
                db._paso_python(m.python) if m.python else None,
            )
    x = con.execute
    for titulo, estado in (("Terminada", "completada"), ("A medias", "generando")):
        n = x("INSERT INTO novela (titulo) VALUES (?)", (titulo,)).lastrowid
        x("INSERT INTO ejecucion (novela_id, estado) VALUES (?, ?)", (n, estado))
        acto = x("INSERT INTO acto (novela_id, numero) VALUES (?, 1)", (n,)).lastrowid
        cap = x("INSERT INTO capitulo (novela_id, acto_id, numero, estado) "
                "VALUES (?, ?, 1, 'completado')", (n, acto)).lastrowid
        x("INSERT INTO capitulo_compilado (novela_id, capitulo_id, version, texto, palabras) "
          "VALUES (?, ?, 1, 'Texto leido', 2)", (n, cap))
    con.commit()

    assert db.migrar(con) == [m.numero for m in db._migraciones() if m.numero >= 6]
    filas = con.execute(
        "SELECT n.titulo, v.numero, v.motivo, vc.texto FROM novela_version v "
        "JOIN novela n ON n.id = v.novela_id "
        "JOIN novela_version_capitulo vc ON vc.version_id = v.id"
    ).fetchall()
    assert [tuple(f) for f in filas] == [("Terminada", 1, "primera", "Texto leido")]
    assert "version_desfasada" not in _nombres(verificar_integridad(con))


# --- RF3-BIB-15: API ---------------------------------------------------------------------------


@pytest.fixture()
def api() -> Iterator[tuple[TestClient, int, int]]:
    con, novela_id, ruta = _demo()
    distancia = _hecho(con, novela_id, "distancia al puente")
    con.close()
    main.app.state.cfg = config.Config(
        db_path=ruta, claude_bin="claude", skills_dir=Path(".claude/skills"), poll_segundos=1,
        timeout_agente_segundos=60, presupuesto_tokens=100_000, puerto="falso",
        puerto_falso_dir=None, embedding_modelo="hash", vectores_activos=False,
    )
    with TestClient(main.app) as c:
        yield c, novela_id, distancia


def test_la_api_sirve_cronologia_usos_y_versiones(api: tuple[TestClient, int, int]) -> None:
    c, novela_id, distancia = api
    cronologia = c.get(f"/novelas/{novela_id}/cronologia").json()
    assert cronologia[0]["dia"] == -240 and cronologia[1]["personajes"]

    usos = c.get(f"/novelas/{novela_id}/hechos/{distancia}/usos").json()
    assert (usos[0]["capitulo"], usos[0]["escena_orden"], usos[0]["via"]) == (1, 1, "establece")
    assert {u["via"] for u in usos[1:]} == {"menciona"}

    assert [v["numero"] for v in c.get(f"/novelas/{novela_id}/versiones").json()] == [1]
    v1 = c.get(f"/novelas/{novela_id}/versiones/1").json()
    assert [cap["numero"] for cap in v1["capitulos"]] == [1, 2, 3]


def test_la_api_da_404_a_lo_que_no_existe(api: tuple[TestClient, int, int]) -> None:
    c, novela_id, _ = api
    assert c.get(f"/novelas/{novela_id}/versiones/9").status_code == 404
    assert c.get(f"/novelas/{novela_id}/hechos/99999/usos").status_code == 404
    assert c.get("/novelas/999/cronologia").status_code == 404
