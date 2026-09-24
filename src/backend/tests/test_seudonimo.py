"""Los nombres del encargo no salen de la maquina (specs/spec3.md, 3.13, RF3-SEU-01 a 05).

Con el puerto falso: lo que se envia al modelo lleva etiquetas, y lo que se guarda, los nombres.
Los nombres son los del brief de ejemplo del repositorio, ficticios.
"""

from __future__ import annotations

import re
from typing import Any

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
    texto = "La [NOMBRE_ANONIMIZADO] miro la antena. [silencio] Nadie contesto."
    r = p_oficio.evaluar(con, novela_id, 1, texto)
    [c] = [c for c in r.bloqueantes if c.comprobacion == "etiqueta_en_la_prosa"]
    assert c.datos["etiquetas"] == ["[NOMBRE_ANONIMIZADO]"]
    limpio = p_oficio.evaluar(con, novela_id, 1, "Nadie contesto. [silencio]")
    assert "etiqueta_en_la_prosa" not in {c.comprobacion for c in limpio.conflictos}
