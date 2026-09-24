"""Cada elemento obligatorio del encargo aparece en la novela (specs/spec3.md, RF3-ELE-01 a 03).

El extractor registra lo que la prosa integra, con una cita que el codigo comprueba; la puerta 4
devuelve el capitulo si falta lo que la escaleta puso en el, y la puerta 5 avisa de lo que no
aparece en ningun capitulo. Con el puerto falso y el brief de ejemplo, ficticio.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from compartido.grafo import lectura
from compartido.puerto import demo
from orquestador import fallo, pipeline
from orquestador import puerta_global as p_global
from tareas.extraccion import servicio as s_extraccion
from tareas.extraccion.esquemas import SalidaExtraccion
from tareas.oficio import puerta as p_oficio
from tests.entorno import cfg_de, nueva_bd, puerto_falso
from tests.test_personalizacion import crear, escaletada

RESUMEN = {"resumen": "La cuadrilla baja al pozo y encuentra la luz que late.",
           "resumen_breve": "Bajan al pozo."}


def _planificado(con: sqlite3.Connection, novela_id: int) -> dict[str, Any]:
    """Un rasgo o un recuerdo obligatorio que la escaleta puso en el capitulo 1."""
    fila = con.execute(
        "SELECT ep.id, ep.codigo, e.id AS escena_id, e.orden FROM escena_elemento ee "
        "JOIN elemento_personal ep ON ep.id = ee.elemento_id JOIN escena e ON e.id = ee.escena_id "
        "JOIN capitulo c ON c.id = e.capitulo_id WHERE ep.novela_id = ? AND c.numero = 1 "
        "AND ep.tipo IN ('rasgo', 'recuerdo') AND ep.obligatorio = 1 ORDER BY e.orden LIMIT 1",
        (novela_id,)).fetchone()
    assert fila is not None, "la escaleta falsa no puso ningun rasgo ni recuerdo en el cap. 1"
    return dict(fila)


def _extraer(con: sqlite3.Connection, novela_id: int, orden: int, escena_id: int,
             elementos: list[dict[str, Any]], texto: str) -> Any:
    salida = SalidaExtraccion.model_validate({**RESUMEN, "elementos": elementos})
    return s_extraccion.aplicar(con, novela_id, 1, salida, {orden: escena_id}, {orden: texto})


def test_una_novela_falsa_registra_lo_que_integra_y_no_avisa() -> None:
    con, ruta = nueva_bd()
    novela_id = crear(con, ruta, capitulos=3)
    ctx = pipeline.Contexto(con=con, puerto=puerto_falso(con), cfg=cfg_de(ruta),
                            novela_id=novela_id)
    assert pipeline.avanzar(ctx) in ("completada", "completada_con_avisos")
    assert con.execute("SELECT COUNT(*) FROM elemento_integrado").fetchone()[0] > 0
    assert lectura.elementos_sin_integrar(con, novela_id) == []


def test_solo_entra_un_elemento_con_codigo_escena_y_cita_de_la_escena() -> None:
    con, novela_id = escaletada()
    x = _planificado(con, novela_id)
    texto = "Contaba los destellos del faro para dormirse, como de nina."
    descartes = _extraer(con, novela_id, x["orden"], x["escena_id"], [
        {"escena_orden": x["orden"], "codigo": "REC99", "cita": "Contaba los destellos"},
        {"escena_orden": x["orden"], "codigo": x["codigo"], "cita": "una frase inventada"},
        {"escena_orden": x["orden"], "codigo": x["codigo"].lower(),
         "cita": "contaba los destellos del faro"},
    ], texto)
    assert descartes.recuento["elementos"] == {"codigo_o_escena_desconocidos": 1,
                                               "cita_que_no_esta_en_la_escena": 1}
    filas = con.execute("SELECT elemento_id, cita FROM elemento_integrado").fetchall()
    assert [tuple(f) for f in filas] == [(x["id"], "contaba los destellos del faro")]


def test_un_elemento_planificado_sin_integrar_devuelve_el_capitulo() -> None:
    con, novela_id = escaletada()
    x = _planificado(con, novela_id)
    faltan = {c.datos["codigo"] for c in p_oficio.evaluar(con, novela_id, 1, "Texto.").bloqueantes
              if c.comprobacion == "elemento_sin_integrar"}
    assert x["codigo"] in faltan
    _extraer(con, novela_id, x["orden"], x["escena_id"],
             [{"escena_orden": x["orden"], "codigo": x["codigo"], "cita": "los destellos"}],
             "Contaba los destellos.")
    faltan = {c.datos["codigo"] for c in p_oficio.evaluar(con, novela_id, 1, "Texto.").bloqueantes
              if c.comprobacion == "elemento_sin_integrar"}
    assert x["codigo"] not in faltan


def test_un_elemento_no_obligatorio_o_un_allegado_no_devuelven_el_capitulo() -> None:
    con, novela_id = escaletada()
    x = _planificado(con, novela_id)
    con.execute("UPDATE elemento_personal SET obligatorio = 0 WHERE id = ?", (x["id"],))
    faltan = {c.datos.get("codigo") for c in p_oficio.evaluar(con, novela_id, 1, "T.").conflictos
              if c.comprobacion == "elemento_sin_integrar"}
    assert x["codigo"] not in faltan
    # Los allegados van por su nombre (RF3-VAL-02): la escaleta falsa los pone en el cap. 4.
    del_4 = {c.datos.get("codigo") for c in p_oficio.evaluar(con, novela_id, 4, "T.").conflictos
             if c.comprobacion == "elemento_sin_integrar"}
    assert not any(str(c).startswith("ALL") for c in del_4)
    assert con.execute(
        "SELECT COUNT(*) FROM escena_elemento ee JOIN elemento_personal ep "
        "ON ep.id = ee.elemento_id JOIN escena e ON e.id = ee.escena_id JOIN capitulo c "
        "ON c.id = e.capitulo_id WHERE ep.tipo = 'allegado' AND c.numero = 4").fetchone()[0]


def test_la_puerta_5_avisa_del_obligatorio_que_no_aparece_en_ningun_capitulo() -> None:
    con, novela_id = escaletada()
    x = _planificado(con, novela_id)
    con.execute("UPDATE capitulo SET estado = 'completado' WHERE novela_id = ?", (novela_id,))
    avisos = {c.datos["codigo"] for c in p_global.evaluar(con, novela_id).conflictos
              if c.comprobacion == "elemento_obligatorio_ausente"}
    assert x["codigo"] in avisos
    assert all(c.aviso for c in p_global.evaluar(con, novela_id).conflictos
               if c.comprobacion == "elemento_obligatorio_ausente")


def test_revertir_el_capitulo_borra_lo_que_registro() -> None:
    con, novela_id = escaletada()
    x = _planificado(con, novela_id)
    _extraer(con, novela_id, x["orden"], x["escena_id"],
             [{"escena_orden": x["orden"], "codigo": x["codigo"], "cita": "los destellos"}],
             "Contaba los destellos.")
    fallo.revertir_grafo(con, novela_id, 1, motivo="oficio")
    assert con.execute("SELECT COUNT(*) FROM elemento_integrado").fetchone()[0] == 0


def test_si_el_extractor_no_lo_encuentra_el_capitulo_vuelve_al_redactor() -> None:
    con, ruta = nueva_bd()
    novela_id = crear(con, ruta, capitulos=3)
    puerto = puerto_falso(con)
    vistos: list[int] = []

    def extraccion(entrada: str, agente: str) -> dict[str, Any]:
        salida = demo.extraccion(entrada, agente)
        if demo._capitulo(entrada) == 1 and not vistos:
            vistos.append(1)
            salida["elementos"] = []
        return salida

    puerto.registrar("extraccion", extraccion)
    ctx = pipeline.Contexto(con=con, puerto=puerto, cfg=cfg_de(ruta), novela_id=novela_id)
    assert pipeline.avanzar(ctx) in ("completada", "completada_con_avisos")
    detalles = [str(f[0]) for f in con.execute(
        "SELECT detalle FROM resultado_puerta WHERE puerta = 4 AND capitulo = 1 ORDER BY id")]
    assert "elemento_sin_integrar" in detalles[0] and "elemento_sin_integrar" not in detalles[-1]


REGLA_DE_LOS_ELEMENTOS = (
    "**Elementos del encargo.** Si te llegan los elementos personales que la escaleta puso en el "
    "capítulo (rasgos y recuerdos del destinatario, con su código), registra en `elementos` cada "
    "uno que la prosa integra: el código, la escena y una cita literal de esa escena que lo "
    "muestre. Cuenta aunque la prosa lo diga con otras palabras, siempre que se reconozca; no "
    "cuenta si solo lo roza. La cita se comprueba contra la escena."
)


def test_la_skill_del_extractor_pide_los_elementos() -> None:
    from compartido.puerto.terminal import PuertoTerminal
    from config import raiz_repo

    skill = PuertoTerminal(skills_dir=raiz_repo() / ".claude" / "skills").ruta_skill(
        "extraccion").read_text(encoding="utf-8")
    seccion = "**Elementos del encargo.**" + skill.split("**Elementos del encargo.**")[1].split(
        "\n\n")[0]
    assert seccion.strip() == REGLA_DE_LOS_ELEMENTOS
    assert skill.count("**Elementos del encargo.**") == 1


def test_el_cambio_del_lector_no_exige_elementos_que_no_volvio_a_extraer() -> None:
    """Una novela anterior a la migracion 013 no tiene registros: el cambio tiene que poder
    reescribir igual (validador de 73d4723)."""
    from tests import test_cambio_lector as tcl

    con, ruta, novela_id = tcl._completa()
    con.execute("DELETE FROM elemento_integrado")
    antes = tcl._textos(con, novela_id)
    reyes = tcl._id(con, "personaje", tcl.SOLO_EN_EL_DOS)
    intencion = tcl._pedir(con, ruta, novela_id, "Que se llame «Oriol»",
                           {"tipo": "entidad", "entidad": "personajes", "id": reyes})
    cambio = lectura.cambio(con, novela_id, intencion["resultado"]["cambio_id"]) or {}
    assert cambio["estado"] == "aplicado", cambio
    assert tcl._textos(con, novela_id)[2] != antes[2]


def test_lo_integrado_en_otro_capitulo_no_cuenta_para_este() -> None:
    con, novela_id = escaletada()
    x = _planificado(con, novela_id)
    otra = con.execute(
        "SELECT e.id FROM escena e JOIN capitulo c ON c.id = e.capitulo_id "
        "WHERE e.novela_id = ? AND c.numero = 2 LIMIT 1", (novela_id,)).fetchone()[0]
    con.execute("INSERT INTO elemento_integrado (novela_id, escena_id, elemento_id, cita) "
                "VALUES (?, ?, ?, 'otra cita')", (novela_id, otra, x["id"]))
    faltan = {c.datos["codigo"] for c in p_oficio.evaluar(con, novela_id, 1, "T.").bloqueantes
              if c.comprobacion == "elemento_sin_integrar"}
    assert x["codigo"] in faltan


def test_lo_integrado_en_un_capitulo_sin_completar_no_cuenta_para_la_puerta_5() -> None:
    con, novela_id = escaletada()
    x = _planificado(con, novela_id)
    _extraer(con, novela_id, x["orden"], x["escena_id"],
             [{"escena_orden": x["orden"], "codigo": x["codigo"], "cita": "los destellos"}],
             "Contaba los destellos.")
    avisos = {c.datos["codigo"] for c in p_global.evaluar(con, novela_id).conflictos
              if c.comprobacion == "elemento_obligatorio_ausente"}
    assert x["codigo"] in avisos
    con.execute("UPDATE capitulo SET estado = 'completado' WHERE novela_id = ?", (novela_id,))
    avisos = {c.datos["codigo"] for c in p_global.evaluar(con, novela_id).conflictos
              if c.comprobacion == "elemento_obligatorio_ausente"}
    assert x["codigo"] not in avisos


def test_el_bloque_de_elementos_del_extractor_no_se_recorta() -> None:
    import config
    from compartido.contexto import Presupuesto

    con, novela_id = escaletada()
    paquete = s_extraccion.paquete(con, novela_id, 1, {1: "Texto."}, presupuesto=Presupuesto(
        bloques=config.PRESUPUESTO_BLOQUES, techo=config.PRESUPUESTO_PAQUETE))
    bloques = [b for b in paquete.bloques if b.titulo.startswith("ELEMENTOS DEL ENCARGO")]
    assert bloques and all(e.obligatorio for b in bloques for e in b.elementos)
