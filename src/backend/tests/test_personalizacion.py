"""El brief dentro del pipeline (specs/spec3.md, RF3-PER-03, RF3-PER-04), con el puerto falso.

La pasada completa demuestra que una novela personalizada llega al final con los agentes de
demostracion, que leen el encargo del paquete igual que el agente real. Las mutaciones rompen
una cosa cada vez sobre un grafo correcto y exigen que la puerta la detecte: es la unica forma
de saber que cada comprobacion nueva sirve de algo (validators.md, mutation testing).
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import worker
from compartido.db import transaccion
from compartido.grafo import lectura, normalizar
from compartido.puerto import PuertoFalso
from orquestador import cola, pipeline
from tareas.continuidad import puerta as p_continuidad
from tareas.escaleta import puerta as p_escaleta
from tareas.estructura import puerta as p_estructura
from tests.entorno import cfg_de, contar, nueva_bd, puerto_falso
from tests.test_brief import brief_ejemplo


def crear(con: sqlite3.Connection, ruta: Path, **cambios: Any) -> int:
    brief = {**brief_ejemplo(), **cambios}
    w = worker.Worker(cfg_de(ruta), con=con)
    with transaccion(con):
        iid = cola.encolar(con, "crear_novela", None, brief=brief)
    w._crear_novela(cola.Intencion(id=iid, tipo="crear_novela", novela_id=None,
                                   payload={"brief": brief}))
    return int(con.execute("SELECT MAX(id) FROM novela").fetchone()[0])


def contexto(con: sqlite3.Connection, ruta: Path, novela_id: int) -> pipeline.Contexto:
    puerto: PuertoFalso = puerto_falso(con)
    return pipeline.Contexto(con=con, puerto=puerto, cfg=cfg_de(ruta), novela_id=novela_id)


def comprobaciones(resultado: Any) -> set[str]:
    return {c.comprobacion for c in resultado.bloqueantes}


def id_destinatario(con: sqlite3.Connection, novela_id: int) -> int:
    return int(con.execute(
        "SELECT id FROM personaje WHERE novela_id = ? AND nombre_clave = ?",
        (novela_id, normalizar("Marta Ibáñez")),
    ).fetchone()["id"])


# --- La pasada completa -----------------------------------------------------------------------


def test_una_novela_personalizada_llega_al_final_con_el_puerto_falso() -> None:
    con, ruta = nueva_bd()
    novela_id = crear(con, ruta)
    final = pipeline.avanzar(contexto(con, ruta, novela_id))
    assert final in ("completada", "completada_con_avisos"), final

    assert "Marta Ibáñez" in str((lectura.novela(con, novela_id) or {})["dedicatoria"])
    assert contar(con, "SELECT COUNT(*) FROM capitulo WHERE novela_id = ? AND "
                       "estado = 'completado'", novela_id) == 10
    sin_escena = contar(con, """
        SELECT COUNT(*) FROM elemento_personal ep WHERE ep.novela_id = ? AND ep.obligatorio = 1
          AND NOT EXISTS (SELECT 1 FROM escena_elemento ee WHERE ee.elemento_id = ep.id)
    """, novela_id)
    assert sin_escena == 0
    veredictos = {
        int(f["puerta"]): str(f["veredicto"]) for f in con.execute(
            "SELECT puerta, veredicto FROM resultado_puerta WHERE novela_id = ? AND puerta IN "
            "(1, 2) ORDER BY id", (novela_id,)
        )
    }
    assert veredictos[1] != "falla" and veredictos[2] != "falla"


def test_el_paquete_del_redactor_lleva_los_elementos_de_cada_escena() -> None:
    con, ruta = nueva_bd()
    novela_id = crear(con, ruta, capitulos=4)
    ctx = contexto(con, ruta, novela_id)
    pipeline.avanzar(ctx)
    assert isinstance(ctx.puerto, PuertoFalso)
    entradas = [i["entrada"] for i in ctx.puerto.invocaciones if i["agente"] == "redaccion"]
    assert any("Elementos personales que integra" in e and "): REC1" in e for e in entradas)
    assert all("DESTINATARIO (protagonista, nombre exacto): Marta Ibáñez" in e for e in entradas)


# --- Puerta 1 -----------------------------------------------------------------------------------


def planificada(**cambios: Any) -> tuple[sqlite3.Connection, int]:
    con, ruta = nueva_bd()
    novela_id = crear(con, ruta, capitulos=3, **cambios)
    pipeline.planificar(contexto(con, ruta, novela_id))
    assert comprobaciones(p_estructura.evaluar(con, novela_id)) == set()
    return con, novela_id


def test_puerta_1_el_destinatario_tiene_que_ser_el_protagonista() -> None:
    con, novela_id = planificada()
    con.execute("UPDATE personaje SET rol_narrativo = 'aliado' WHERE id = ?",
                (id_destinatario(con, novela_id),))
    assert "destinatario_protagonista" in comprobaciones(p_estructura.evaluar(con, novela_id))


def test_puerta_1_cada_allegado_obligatorio_esta_en_el_elenco() -> None:
    con, novela_id = planificada()
    con.execute("DELETE FROM personaje WHERE novela_id = ? AND nombre = 'Nala'", (novela_id,))
    assert "allegado_en_elenco" in comprobaciones(p_estructura.evaluar(con, novela_id))


def test_puerta_1_la_dedicatoria_nombra_al_destinatario_tal_cual() -> None:
    con, novela_id = planificada()
    con.execute("UPDATE novela SET dedicatoria = 'Para Marta Ibanez' WHERE id = ?", (novela_id,))
    assert "dedicatoria_nombra_al_destinatario" in comprobaciones(
        p_estructura.evaluar(con, novela_id)
    )


def test_puerta_1_el_subgenero_fijado_se_respeta() -> None:
    con, novela_id = planificada(subgenero="ia_hostil")
    con.execute("UPDATE novela SET subgenero_dominante = 'supervivencia' WHERE id = ?",
                (novela_id,))
    assert "subgenero_del_brief" in comprobaciones(p_estructura.evaluar(con, novela_id))


def test_puerta_1_un_subgenero_corporal_no_cabe_en_atmosferico() -> None:
    con, novela_id = planificada(intensidad="atmosferico")
    con.execute("UPDATE novela SET subgenero_dominante = 'slasher_espacial' WHERE id = ?",
                (novela_id,))
    assert "subgenero_exige_intensidad" in comprobaciones(p_estructura.evaluar(con, novela_id))


# --- Puerta 2 -----------------------------------------------------------------------------------


def escaletada() -> tuple[sqlite3.Connection, int]:
    con, ruta = nueva_bd()
    novela_id = crear(con, ruta, capitulos=4)
    ctx = contexto(con, ruta, novela_id)
    pipeline.planificar(ctx)
    pipeline.escaletar(ctx)
    assert comprobaciones(p_escaleta.evaluar(con, novela_id)) == set()
    return con, novela_id


def test_puerta_2_cada_elemento_obligatorio_esta_planificado() -> None:
    con, novela_id = escaletada()
    con.execute("""
        DELETE FROM escena_elemento WHERE elemento_id IN
          (SELECT id FROM elemento_personal WHERE novela_id = ? AND codigo = 'REC2')
    """, (novela_id,))
    resultado = p_escaleta.evaluar(con, novela_id)
    assert "elemento_sin_escena" in comprobaciones(resultado)
    assert any(c.datos.get("codigo") == "REC2" for c in resultado.bloqueantes)


def test_puerta_2_el_destinatario_es_el_pov_de_mas_de_la_mitad() -> None:
    con, novela_id = escaletada()
    otro = int(con.execute(
        "SELECT id FROM personaje WHERE novela_id = ? AND rol_narrativo = 'oponente'",
        (novela_id,),
    ).fetchone()["id"])
    total = contar(con, "SELECT COUNT(*) FROM escena WHERE novela_id = ?", novela_id)
    con.execute(
        "UPDATE escena SET pov_id = ? WHERE id IN (SELECT id FROM escena WHERE novela_id = ? "
        "ORDER BY id LIMIT ?)", (otro, novela_id, total // 2),
    )
    assert "pov_del_destinatario" in comprobaciones(p_escaleta.evaluar(con, novela_id))


def test_puerta_2_la_escaleta_tiene_los_capitulos_del_encargo() -> None:
    con, novela_id = escaletada()
    con.execute("DELETE FROM capitulo WHERE novela_id = ? AND numero = 4", (novela_id,))
    assert "numero_de_capitulos" in comprobaciones(p_escaleta.evaluar(con, novela_id))


def test_un_codigo_de_elemento_desconocido_queda_en_la_traza() -> None:
    from tareas.escaleta import servicio as s_escaleta
    from tareas.escaleta.esquemas import SalidaEscaleta

    con, novela_id = escaletada()
    salida = json.loads(
        con.execute("SELECT salida_cruda FROM llamada_modelo WHERE agente = 'escaleta' "
                    "ORDER BY id DESC LIMIT 1").fetchone()["salida_cruda"]
    )["structured_output"]
    salida["capitulos"][0]["escenas"][0]["elementos"].append("REC99")
    con.execute("DELETE FROM capitulo WHERE novela_id = ?", (novela_id,))
    con.execute("DELETE FROM secuencia WHERE novela_id = ?", (novela_id,))
    with transaccion(con):
        s_escaleta.aplicar(con, novela_id, SalidaEscaleta.model_validate(salida))
    fila = con.execute(
        "SELECT payload FROM traza_evento WHERE tipo = 'elemento_desconocido'"
    ).fetchone()
    assert fila is not None and "REC99" in fila["payload"]


# --- Puerta 3 -----------------------------------------------------------------------------------


def test_puerta_3_el_destinatario_nunca_muere() -> None:
    con, ruta = nueva_bd()
    novela_id = crear(con, ruta, capitulos=3)
    pipeline.avanzar(contexto(con, ruta, novela_id))
    assert "destinatario_muere" not in comprobaciones(p_continuidad.evaluar(con, novela_id, 3))

    escena = int(con.execute(
        "SELECT e.id FROM escena e JOIN capitulo c ON c.id = e.capitulo_id "
        "WHERE e.novela_id = ? AND c.numero = 3 ORDER BY e.orden LIMIT 1", (novela_id,),
    ).fetchone()["id"])
    con.execute(
        "INSERT INTO estado_personaje (novela_id, personaje_id, escena_id, condicion, "
        "salud_fisica) VALUES (?,?,?, 'muerto', 'sin constantes')",
        (novela_id, id_destinatario(con, novela_id), escena),
    )
    assert "destinatario_muere" in comprobaciones(p_continuidad.evaluar(con, novela_id, 3))


# --- Vigencia por huella (RF3-PER-07; hallazgos 3 y 4 del validador) ----------------------------

#: Las lecturas de la puerta 1 tal como estaban antes de spec3. Una novela sin brief tiene que
#: dar exactamente esta huella, o toda novela ya generada perderia la vigencia al migrar.
LECTURAS_PUERTA_1_ANTES_DE_SPEC3 = (
    "SELECT id, numero, funcion_narrativa FROM acto WHERE novela_id = :n ORDER BY id",
    "SELECT id, tipo, conflicto_central FROM hilo WHERE novela_id = :n ORDER BY id",
    "SELECT g.id, g.hilo_id, g.tipo, g.posicion FROM punto_de_giro g "
    "JOIN hilo h ON h.id = g.hilo_id WHERE h.novela_id = :n ORDER BY g.id",
    "SELECT id, rol_narrativo, tipo_arco FROM personaje WHERE novela_id = :n ORDER BY id",
    "SELECT subgenero_dominante, tipo_final FROM novela WHERE id = :n",
)


def test_una_novela_sin_brief_conserva_la_huella_de_antes() -> None:
    import hashlib

    from orquestador import vigencia
    from tests.entorno import crear_novela

    con, ruta = nueva_bd()
    novela_id = crear_novela(con)
    pipeline.planificar(contexto(con, ruta, novela_id))
    filas: list[list[Any]] = []
    for sql in LECTURAS_PUERTA_1_ANTES_DE_SPEC3:
        filas.extend([list(f) for f in con.execute(sql, {"n": novela_id}).fetchall()])
        filas.append(["--"])
    esperada = hashlib.sha256(
        json.dumps(filas, ensure_ascii=False, default=str, separators=(",", ":")).encode()
    ).hexdigest()
    assert vigencia.huella(con, novela_id, 1) == esperada


def test_cambiar_lo_que_lee_la_puerta_1_del_encargo_le_quita_la_vigencia() -> None:
    from orquestador import vigencia

    con, novela_id = planificada()
    assert vigencia.puerta_vigente(con, novela_id, 1)
    con.execute("UPDATE novela SET dedicatoria = 'Otra dedicatoria' WHERE id = ?", (novela_id,))
    assert not vigencia.puerta_vigente(con, novela_id, 1)


def test_cambiar_los_elementos_planificados_le_quita_la_vigencia_a_la_puerta_2() -> None:
    from orquestador import vigencia

    con, novela_id = escaletada()
    assert vigencia.puerta_vigente(con, novela_id, 2)
    con.execute("DELETE FROM escena_elemento WHERE id = (SELECT MIN(id) FROM escena_elemento)")
    assert not vigencia.puerta_vigente(con, novela_id, 2)


# --- Rehacer una parada de estructura vuelve a la fase culpable (hallazgo 5) ---------------------


def test_una_dedicatoria_mal_escrita_se_rehace_desde_el_arquitecto() -> None:
    from compartido.puerto import demo as agentes_falsos
    from orquestador import fallo

    con, ruta = nueva_bd()
    novela_id = crear(con, ruta, capitulos=3)
    ctx = contexto(con, ruta, novela_id)
    assert isinstance(ctx.puerto, PuertoFalso)
    entradas: list[str] = []

    def arquitecto(entrada: str, agente: str) -> dict[str, Any]:
        entradas.append(entrada)
        salida = agentes_falsos.arquitecto(entrada, agente)
        if len(entradas) == 1:
            salida["dedicatoria"] = "Para Marta, con carino."  # sin el nombre completo
        return salida

    ctx.puerto.registrar("arquitecto", arquitecto)
    assert pipeline.avanzar(ctx) == "parada"
    assert fallo.fase_a_rehacer(con, novela_id) == "arquitecto"

    parada_id = int(fallo.paradas_abiertas(con, novela_id)[0]["id"])
    with transaccion(con):
        fallo.rehacer_estructura(con, novela_id, parada_id)
    final = pipeline.avanzar(ctx)
    assert final in ("completada", "completada_con_avisos"), final
    assert len(entradas) == 2
    assert "dedicatoria_nombra_al_destinatario" in entradas[1]


def test_un_rechazo_solo_de_la_estructura_no_toca_el_elenco() -> None:
    from orquestador import fallo

    con, novela_id = planificada()
    con.execute(
        "INSERT INTO resultado_puerta (novela_id, puerta, veredicto, detalle) VALUES (?, 1, "
        "'falla', ?)",
        (novela_id, json.dumps({"conflictos": [{"comprobacion": "orden_de_giros"}]})),
    )
    assert fallo.fase_a_rehacer(con, novela_id) == "estructura"
