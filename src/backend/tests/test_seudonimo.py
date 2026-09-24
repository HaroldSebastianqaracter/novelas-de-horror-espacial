"""Los nombres del encargo no salen de la maquina (specs/spec3.md, 3.13, RF3-SEU-01 a 05).

Con el puerto falso: lo que se envia al modelo lleva etiquetas, y lo que se guarda, los nombres.
Los nombres son los del brief de ejemplo del repositorio, ficticios.
"""

from __future__ import annotations

import re
from typing import Any

import pytest

from compartido.brief import Brief
from compartido.grafo import lectura
from compartido.grafo.escritura import normalizar
from compartido.puerto import demo as agentes_falsos
from orquestador import pipeline
from orquestador.seudonimo import Mascara
from tareas.oficio import puerta as p_oficio
from tests.entorno import cfg_de, nueva_bd, puerto_falso
from tests.test_brief import brief_ejemplo
from tests.test_personalizacion import crear

#: Las palabras de los nombres del brief de ejemplo, plegadas: ninguna puede salir.
NOMBRES = ("marta", "ibanez", "andres", "nala")


def _mascara() -> Mascara:
    return Mascara(Brief.model_validate(brief_ejemplo()))


def _nombres_en(texto: str) -> set[str]:
    palabras = set(re.findall(r"[^\W\d_]+", normalizar(texto)))
    return {n for n in NOMBRES if n in palabras}


def test_la_mascara_oculta_cada_forma_y_la_restaura_bien_escrita() -> None:
    m = _mascara()
    texto = "Marta Ibáñez miró a Andrés. Marta sonrió; Ibanez no. Nala ladró."
    oculto = m.ocultar(texto)
    assert _nombres_en(oculto) == set()
    assert oculto == ("[DESTINATARIO] miró a [ALLEGADO_2]. [DESTINATARIO_NOMBRE] sonrió; "
                      "[DESTINATARIO_APELLIDO] no. [ALLEGADO_1] ladró.")
    # El apellido sin tilde vuelve con ella: la restauracion escribe como el brief.
    assert m.restaurar(oculto) == "Marta Ibáñez miró a Andrés. Marta sonrió; Ibáñez no. Nala ladró."


def test_restaurar_recorre_claves_y_listas_y_deja_lo_que_no_es_del_encargo() -> None:
    m = _mascara()
    salida: dict[str, Any] = {"[destinatario_nombre]": ["con [ALLEGADO_1]", 3],
                              "nota": "[NOMBRE_ANONIMIZADO] y [DESTINATARIO_APODO]"}
    assert m.restaurar(salida) == {"Marta": ["con Nala", 3],
                                   "nota": "[NOMBRE_ANONIMIZADO] y [DESTINATARIO_APODO]"}


def test_la_leyenda_no_lleva_ningun_nombre_y_dice_quien_regala() -> None:
    leyenda = _mascara().leyenda()
    assert _nombres_en(leyenda) == set()
    assert "firma la dedicatoria: es [ALLEGADO_2]" in leyenda
    assert "[QUIEN_REGALA]" not in leyenda.split("Etiquetas validas:")[1]


def test_sin_brief_no_hay_mascara() -> None:
    m = Mascara(None)
    assert m.vacia and m.leyenda() == "" and m.ocultar("Marta") == "Marta"


def test_una_novela_entera_no_envia_ningun_nombre_y_guarda_los_nombres() -> None:
    con, ruta = nueva_bd()
    novela_id = crear(con, ruta, capitulos=3)
    puerto = puerto_falso(con)
    ctx = pipeline.Contexto(con=con, puerto=puerto, cfg=cfg_de(ruta), novela_id=novela_id)
    assert pipeline.avanzar(ctx) in ("completada", "completada_con_avisos")

    enviados = [i["entrada"] for i in puerto.invocaciones]
    assert enviados and all(_nombres_en(e) == set() for e in enviados)
    assert all(e.startswith("## NOMBRES DEL ENCARGO") for e in enviados)
    guardadas = con.execute("SELECT entrada FROM llamada_modelo").fetchall()
    assert all(_nombres_en(str(f[0])) == set() for f in guardadas)

    texto = " ".join(lectura.texto_capitulo(con, novela_id, n) for n in (1, 2, 3))
    assert "Marta" in texto and "[DESTINATARIO" not in texto
    assert "Marta Ibáñez" in str((lectura.novela(con, novela_id) or {}).get("dedicatoria"))


def test_el_reintento_por_error_de_validacion_tampoco_envia_nombres() -> None:
    """El error cita la respuesta ya restaurada: vuelve a salir con etiquetas."""
    con, ruta = nueva_bd()
    novela_id = crear(con, ruta, capitulos=3)
    puerto = puerto_falso(con)
    vueltas: list[int] = []

    def arquitecto(entrada: str, agente: str) -> dict[str, Any]:
        salida = agentes_falsos.arquitecto(entrada, agente)
        vueltas.append(1)
        if len(vueltas) == 1:
            salida["premisa"] = "[DESTINATARIO]"  # demasiado corta: no pasa el modelo
        return salida

    puerto.registrar("arquitecto", arquitecto)
    ctx = pipeline.Contexto(con=con, puerto=puerto, cfg=cfg_de(ruta), novela_id=novela_id)
    pipeline.avanzar(ctx)
    segundas = [i["entrada"] for i in puerto.invocaciones if i["agente"] == "arquitecto"]
    assert len(segundas) >= 2 and "ERROR DEL INTENTO ANTERIOR" in segundas[1]
    assert _nombres_en(segundas[1]) == set()


def test_una_etiqueta_en_la_prosa_devuelve_el_capitulo() -> None:
    con, ruta = nueva_bd()
    novela_id = crear(con, ruta, capitulos=3)
    texto = "La [NOMBRE_ANONIMIZADO] miro a [destinatario_apodo]. [ALERTA] Nadie contesto."
    r = p_oficio.evaluar(con, novela_id, 1, texto)
    [c] = [c for c in r.bloqueantes if c.comprobacion == "etiqueta_en_la_prosa"]
    assert c.datos["etiquetas"] == ["[NOMBRE_ANONIMIZADO]", "[destinatario_apodo]"]


@pytest.mark.parametrize("texto", ["[ALERTA]", "[FIN]", "[SOS]", "[REDACTADO]", "[ERROR 404]",
                                   "[silencio]", "[ALLEGADO]"])
def test_el_texto_legitimo_entre_corchetes_no_para(texto: str) -> None:
    """Solo las etiquetas del encargo o de anonimizacion (validador de cd8ab12)."""
    con, ruta = nueva_bd()
    novela_id = crear(con, ruta, capitulos=3)
    r = p_oficio.evaluar(con, novela_id, 1, f"Nadie contesto. {texto} Otra vez.")
    assert "etiqueta_en_la_prosa" not in {c.comprobacion for c in r.conflictos}


@pytest.mark.parametrize("etiqueta", ["[DNI_OCULTO]", "[EMAIL_ELIMINADO]", "[EMPRESA_OCULTA]",
                                      "[ALLEGADO_3_NOMBRE]", "[QUIEN_REGALA]"])
def test_toda_etiqueta_del_encargo_o_de_anonimizacion_para(etiqueta: str) -> None:
    from compartido.texto import ETIQUETA_SIN_NOMBRE

    assert ETIQUETA_SIN_NOMBRE.search(f"y {etiqueta} dijo")


# --- Lo que encontro el validador de cd8ab12 -----------------------------------------------------


def test_el_cambio_del_lector_no_envia_ni_el_nombre_viejo_ni_el_nuevo() -> None:
    """El brief del cambio es el simulado, con el nombre nuevo; el viejo sale como anterior."""
    from tests import test_cambio_lector as tcl

    con, ruta, novela_id = tcl._completa()
    ultima = con.execute("SELECT MAX(id) FROM llamada_modelo").fetchone()[0]
    nala = tcl._id(con, "personaje", "Nala")
    intencion = tcl._pedir(con, ruta, novela_id, "La perra se llama «Kira»",
                           {"tipo": "entidad", "entidad": "personajes", "id": nala})
    assert intencion["estado"] == "hecha", intencion
    filas = con.execute("SELECT agente, entrada FROM llamada_modelo WHERE id > ? "
                        "AND agente IN ('revision', 'oficio')", (ultima,)).fetchall()
    assert {f[0] for f in filas} == {"revision", "oficio"}
    for agente, entrada in filas:
        palabras = set(re.findall(r"[^\W\d_]+", normalizar(str(entrada))))
        assert not {"nala", "kira"} & palabras, agente
    revision = next(str(e) for a, e in filas if a == "revision")
    assert "«[NOMBRE_ANTERIOR]» se llama ahora «[ALLEGADO_1]»" in revision
    alcance = [int(c) for c in intencion["resultado"]["capitulos"]]
    assert all("Kira" in lectura.texto_capitulo(con, novela_id, n) for n in alcance)


def test_la_leyenda_no_saca_un_nombre_por_la_relacion() -> None:
    datos = brief_ejemplo()
    datos["allegados"][1]["relacion"] = "hermano de Marta, bromista"
    m = Mascara(Brief.model_validate(datos))
    leyenda = m.leyenda()
    assert _nombres_en(leyenda) == set()
    assert "(pronombres: ella)" in leyenda and "[DESTINATARIO_NOMBRE]" in leyenda


def test_la_leyenda_lleva_los_pronombres_y_cada_relacion() -> None:
    leyenda = _mascara().leyenda()
    assert "(pronombres: ella)" in leyenda
    assert "[ALLEGADO_1]: allegado del destinatario (su perra)." in leyenda
    assert "[ALLEGADO_2]: allegado del destinatario (su hermano)." in leyenda


def test_un_nombre_que_es_palabra_corriente_no_toca_la_palabra() -> None:
    datos = brief_ejemplo()
    datos["destinatario"]["nombre"] = "Luz Luna"
    m = Mascara(Brief.model_validate(datos))
    texto = "La luz del pasillo y la luna llena."
    assert m.ocultar(texto) == texto
    assert m.ocultar("Luz Luna llego.") == "[DESTINATARIO] llego."


def test_un_brief_en_minusculas_vuelve_con_mayuscula() -> None:
    datos = brief_ejemplo()
    datos["destinatario"]["nombre"] = "marta de la vega"
    m = Mascara(Brief.model_validate(datos))
    assert m.restaurar("[DESTINATARIO] abrio; [DESTINATARIO_NOMBRE] no.") == \
        "Marta de la Vega abrio; Marta no."


def test_las_etiquetas_que_un_modelo_escribiria_por_analogia_vuelven() -> None:
    m = _mascara()
    assert m.restaurar("[ALLEGADO_1_NOMBRE] y [QUIEN_REGALA]") == "Nala y Andrés"


def test_una_firma_generica_no_se_oculta() -> None:
    datos = brief_ejemplo()
    datos["quien_regala"] = "tu hermano"
    m = Mascara(Brief.model_validate(datos))
    assert m.ocultar("Dijo que tu hermano vendria. Tu hermano llamo.") == \
        "Dijo que tu hermano vendria. Tu hermano llamo."
    datos["quien_regala"] = "Sus compañeros del instituto"
    m = Mascara(Brief.model_validate(datos))
    assert m.ocultar("Sus compañeros del instituto firmaron.") == \
        "Sus compañeros del instituto firmaron."


def test_dos_claves_que_vuelven_iguales_no_se_pisan() -> None:
    assert _mascara().restaurar({"[DESTINATARIO_NOMBRE]": 1, "Marta": 2}) == \
        {"Marta": 1, "Marta #2": 2}


def test_una_etiqueta_en_la_dedicatoria_o_en_un_nombre_para_la_planificacion() -> None:
    from tareas.estructura import puerta as p_estructura
    from tests.test_personalizacion import contexto

    con, ruta = nueva_bd()
    novela_id = crear(con, ruta, capitulos=3)
    pipeline.planificar(contexto(con, ruta, novela_id))
    con.execute("UPDATE novela SET dedicatoria = dedicatoria || ' [QUIEN_REGALA_2]' WHERE id = ?",
                (novela_id,))
    con.execute("UPDATE lugar SET nombre = '[NOMBRE_ANONIMIZADO]' WHERE id = "
                "(SELECT MIN(id) FROM lugar WHERE novela_id = ?)", (novela_id,))
    [c] = [c for c in p_estructura.evaluar(con, novela_id).bloqueantes
           if c.comprobacion == "etiqueta_en_el_canon"]
    assert len(c.datos["textos"]) == 2


# --- Lo que encontro el validador de 7e88879 -----------------------------------------------------


def test_un_brief_en_minusculas_tampoco_envia_ningun_nombre() -> None:
    """Asi viaja el nombre en los paquetes: se oculta en cualquier grafia."""
    datos = brief_ejemplo()
    datos["destinatario"]["nombre"] = "marta ibáñez"
    datos["quien_regala"] = "andrés"
    datos["allegados"][1]["nombre"] = "andrés"
    m = Mascara(Brief.model_validate(datos))
    oculto = m.ocultar("Para marta ibáñez, de andrés. Marta sonrio; Andrés no.")
    assert _nombres_en(oculto) == set()
    assert m.restaurar(oculto) == "Para Marta Ibáñez, de Andrés. Marta sonrio; Andrés no."


def test_una_novela_con_el_brief_en_minusculas_no_envia_ningun_nombre() -> None:
    con, ruta = nueva_bd()
    novela_id = crear(con, ruta, capitulos=3, destinatario={
        **brief_ejemplo()["destinatario"], "nombre": "marta ibáñez"})
    puerto = puerto_falso(con)
    ctx = pipeline.Contexto(con=con, puerto=puerto, cfg=cfg_de(ruta), novela_id=novela_id)
    pipeline.avanzar(ctx)
    assert all(_nombres_en(i["entrada"]) & {"marta", "ibanez"} == set()
               for i in puerto.invocaciones)


def test_una_firma_que_es_un_nombre_en_minuscula_se_oculta() -> None:
    datos = brief_ejemplo()
    datos["quien_regala"] = "julia"
    m = Mascara(Brief.model_validate(datos))
    assert m.ocultar("Para ti, de Julia. julia.") == "Para ti, de [QUIEN_REGALA]. [QUIEN_REGALA]."
    assert "firma la dedicatoria" in m.leyenda()


def test_la_firma_generica_vuelve_tal_cual_y_la_leyenda_la_dice() -> None:
    datos = brief_ejemplo()
    datos["quien_regala"] = "tu hermano"
    m = Mascara(Brief.model_validate(datos))
    assert m.restaurar("Con carino, [QUIEN_REGALA].") == "Con carino, tu hermano."
    assert "firma la dedicatoria como «tu hermano»" in m.leyenda()


def test_la_grafia_respeta_guiones_y_apostrofos() -> None:
    datos = brief_ejemplo()
    datos["destinatario"]["nombre"] = "JEAN-LUC O'NEILL"
    m = Mascara(Brief.model_validate(datos))
    assert m.restaurar("[DESTINATARIO]") == "Jean-Luc O'Neill"


def test_el_apellido_por_analogia_tambien_vuelve() -> None:
    datos = brief_ejemplo()
    datos["allegados"][1]["nombre"] = "Andrés Ibarra"
    m = Mascara(Brief.model_validate(datos))
    # El destinatario reclama sus formas primero; el apellido del allegado vuelve igual.
    assert m.restaurar("[ALLEGADO_1_APELLIDO] y [ALLEGADO_2_APELLIDO]") == "Nala y Ibarra"


@pytest.mark.parametrize("texto", ["[ARCHIVO_ELIMINADO]", "[TRANSMISION_OCULTA]", "[oculto]",
                                   "[ELIMINADO]"])
def test_lo_eliminado_u_oculto_del_genero_no_para(texto: str) -> None:
    from compartido.texto import ETIQUETA_SIN_NOMBRE

    assert not ETIQUETA_SIN_NOMBRE.search(texto)


def test_una_etiqueta_con_varios_sufijos_para() -> None:
    from compartido.texto import ETIQUETA_SIN_NOMBRE

    assert ETIQUETA_SIN_NOMBRE.search("Y [DESTINATARIO_NOMBRE_COMPLETO] miro.")


@pytest.mark.parametrize("sql", [
    "UPDATE novela SET titulo = '[DESTINATARIO] y la luz' WHERE id = ?",
    "UPDATE personaje SET nombre = '[ALLEGADO_3]' WHERE id = "
    "(SELECT MAX(id) FROM personaje WHERE novela_id = ?)",
    "UPDATE objeto SET nombre = 'Radio de [QUIEN_REGALA]' WHERE id = "
    "(SELECT MIN(id) FROM objeto WHERE novela_id = ?)",
])
def test_la_puerta_1_mira_titulo_personajes_y_objetos(sql: str) -> None:
    from orquestador import fallo
    from tareas.estructura import puerta as p_estructura
    from tests.test_personalizacion import contexto

    con, ruta = nueva_bd()
    novela_id = crear(con, ruta, capitulos=3)
    pipeline.planificar(contexto(con, ruta, novela_id))
    con.execute(sql, (novela_id,))
    assert "etiqueta_en_el_canon" in {
        c.comprobacion for c in p_estructura.evaluar(con, novela_id).bloqueantes}
    # El titulo y la dedicatoria los escribe el arquitecto: se rehace desde el.
    assert fallo.FASE_DE_COMPROBACION["etiqueta_en_el_canon"] == "arquitecto"
