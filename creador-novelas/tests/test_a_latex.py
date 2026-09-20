"""Tests del conversor a LaTeX (`herramientas/a_latex.py`).

Lo que se protege aquí es lo que falla en silencio. Un `.tex` mal escapado no da error: compila y
sale un libro con una frase menos, y nadie lo mira hasta que ya está impreso. Por eso el grueso de
los casos es escapado y diálogo, y por eso hay una prueba de punta a punta que exige que los tres
capítulos de una novela entera aparezcan en el documento.

No se compila nada: en la máquina de desarrollo puede no haber motor LaTeX, y un test que dependa
de eso sería un test que casi nunca corre. Lo que se comprueba del documento es estructural
—llaves equilibradas, ningún carácter especial suelto en el cuerpo— que es donde están los fallos
que el conversor puede provocar.
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]

# El módulo tiene guion bajo pero vive en `herramientas/`, que no es un paquete: se carga por ruta
# en vez de añadir un `__init__.py` a una carpeta que no lo quiere.
_spec = importlib.util.spec_from_file_location("a_latex", RAIZ / "herramientas" / "a_latex.py")
a_latex = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(a_latex)


# ---------------------------------------------------------------------------
# Escapado
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("entrada, esperado", [
    ("100% del aire", r"100\% del aire"),
    ("Sein & Okonjo", r"Sein \& Okonjo"),
    ("cuesta $40", r"cuesta \$40"),
    ("bodega #3", r"bodega \#3"),
    ("cap_1", r"cap\_1"),
    ("{llaves}", r"\{llaves\}"),
    ("a~b", r"a\textasciitilde{}b"),
    ("2^10", r"2\textasciicircum{}10"),
    ("C:\\ruta", r"C:\textbackslash{}ruta"),
])
def test_escapa_los_especiales_de_latex(entrada, esperado):
    assert a_latex.escapar(entrada) == esperado


def test_la_barra_invertida_no_se_come_sus_propias_llaves():
    """El orden del escapado importa: `\\` se traduce a una macro que lleva llaves dentro.

    Si las llaves se procesaran después, se escaparían las de la macro recién puesta y el resultado
    sería `\\textbackslash\\{\\}`, que imprime basura.
    """
    assert a_latex.escapar("\\") == r"\textbackslash{}"


def test_el_porcentaje_no_comenta_el_resto_de_la_linea():
    """El peor fallo posible: un `%` sin escapar borra en silencio el resto del párrafo."""
    salida = a_latex.convertir_capitulo("El filtro iba al 80% y nadie miró la curva.")
    assert r"80\%" in salida
    assert "y nadie miró la curva" in salida


def test_los_acentos_y_las_angulares_sobreviven():
    texto = "Mirén oyó «venga, venga» en el conducto; había una señal."
    assert a_latex.escapar(texto) == texto


def test_puntos_suspensivos_y_espacio_duro():
    assert a_latex.escapar("espera\u2026") == r"espera\dots{}"
    assert a_latex.escapar("3\u00a0km") == "3~km"


# ---------------------------------------------------------------------------
# Diálogo
# ---------------------------------------------------------------------------

def test_la_raya_de_apertura_queda_pegada_a_la_palabra():
    assert a_latex.normalizar_dialogo("— Sin registro") == "—Sin registro"


@pytest.mark.parametrize("entrada", ["- Sin registro", "-- Sin registro", "– Sin registro"])
def test_el_guion_ingles_al_abrir_se_convierte_en_raya(entrada):
    """El modelo a veces abre con guión. En un libro en castellano eso se ve, y se corrige."""
    assert a_latex.normalizar_dialogo(entrada) == "—Sin registro"


def test_un_guion_a_mitad_de_frase_sigue_siendo_un_guion():
    """La corrección anterior solo vale al principio del párrafo: `teórico-práctico` no es diálogo."""
    assert a_latex.normalizar_dialogo("un turno teórico-práctico") == "un turno teórico-práctico"


def test_la_raya_que_abre_inciso_se_pega_a_lo_que_sigue():
    assert a_latex.normalizar_dialogo("—Se fueron — dijo Reder.") == "—Se fueron —dijo Reder."


def test_la_raya_que_cierra_inciso_se_pega_a_lo_anterior():
    assert a_latex.normalizar_dialogo("—Se fueron —dijo Reder —. Andando.") \
        == "—Se fueron —dijo Reder—. Andando."


def test_el_parrafo_de_dialogo_sale_marcado_y_con_raya_irrompible():
    salida = a_latex.convertir_capitulo("—Sin registro —dijo—. No figura.")
    assert salida == r"\dialogo{\raya Sin registro —dijo—. No figura.}"


def test_la_prosa_normal_no_se_marca_como_dialogo():
    salida = a_latex.convertir_capitulo("Vasari anotó la cifra en el parte.")
    assert "\\dialogo" not in salida


def test_las_cursivas_de_markdown_pasan_a_emph():
    salida = a_latex.convertir_capitulo("El *Amanecer Tardío* atracó al undécimo día.")
    assert r"\emph{Amanecer Tardío}" in salida


def test_un_asterisco_solo_es_un_corte_de_escena():
    salida = a_latex.convertir_capitulo("Primero.\n\n*\n\nDespués.")
    assert r"\escena" in salida
    # Sin línea en blanco detrás: el \noindent que deja \escena moriría con ella.
    assert "\\escena\nDespués." in salida


def test_un_asterisco_desparejado_no_se_traga_el_texto():
    salida = a_latex.convertir_capitulo("Un 5 * 3 y luego nada.")
    assert r"\emph" not in salida


# ---------------------------------------------------------------------------
# Una novela entera
# ---------------------------------------------------------------------------

def cuerpo(doc: str) -> str:
    """Solo el texto del libro.

    La plantilla nombra `\\capitulo` en sus propios comentarios, así que contar sobre el documento
    entero daría uno de más y el test mentiría en la dirección cómoda.
    """
    return doc.split("\\mainmatter", 1)[1]


CAPITULOS = [
    {"num": 1, "titulo": "La baliza sin registro"},
    {"num": 2, "titulo": "La voz en el conducto"},
    {"num": 3, "titulo": "Seis versiones de la misma mujer"},
]


@pytest.fixture
def novela(tmp_path: Path) -> Path:
    """Una novela de tres capítulos con la misma forma que las de `09_archivo`."""
    raiz = tmp_path / "2026-09-18T13-03-10_el-pasajero-del-vacio"
    (raiz / "01_concepto").mkdir(parents=True)
    (raiz / "04_estado").mkdir()
    (raiz / "05_manuscrito").mkdir()
    (raiz / "01_concepto" / "premisa.md").write_text(
        "Título: El pasajero del vacío\n\n"
        "Logline: Algo sube a bordo del Nereida y la nave deja de ser suya.\n\n"
        "Premisa: Un carguero de mineral responde a una baliza que no debía responder.\n",
        encoding="utf-8")
    (raiz / "04_estado" / "capitulos.json").write_text(
        json.dumps(CAPITULOS, ensure_ascii=False), encoding="utf-8")
    (raiz / "04_estado" / "manifest.json").write_text(
        json.dumps({"ultimo_capitulo_cerrado": 3}), encoding="utf-8")
    # Con CRLF, como los escribe el harness en Windows.
    for n in (1, 2, 3):
        (raiz / "05_manuscrito" / f"cap_{n}.md").write_text(
            f"Capítulo {n}: el aire del Nereida olía a metal tibio al 90% de carga.\r\n"
            f"\r\n"
            f"—Sin registro —dijo Mirén—. No figura en ninguna parte.\r\n",
            encoding="utf-8")
    return raiz


def test_la_novela_produce_un_tex_con_todos_sus_capitulos(novela):
    doc, titulo = a_latex.construir_documento(novela)
    assert titulo == "El pasajero del vacío"
    for cap in CAPITULOS:
        assert f"\\capitulo{{{cap['num']}}}{{{cap['titulo']}}}" in cuerpo(doc)
    assert cuerpo(doc).count("\\capitulo{") == 3
    # Y el texto de los tres está dentro, no solo sus cabeceras.
    assert doc.count("olía a metal tibio al 90") == 3


def test_el_documento_es_completo_y_lleva_portada(novela):
    doc, _ = a_latex.construir_documento(novela)
    assert doc.startswith("%")
    assert "\\documentclass" in doc
    assert "\\begin{document}" in doc
    assert doc.rstrip().endswith("\\end{document}")
    assert "El pasajero del vacío" in doc
    assert "Algo sube a bordo del Nereida" in doc
    assert "{{" not in doc.split("\\documentclass")[1]


def test_no_queda_ningun_especial_suelto_en_el_cuerpo(novela):
    """Barrido mecánico: en el cuerpo, todo `%`, `&`, `$`... tiene que venir de una macro nuestra.

    Es la comprobación que sustituye a compilar. Un especial suelto aquí es exactamente el fallo
    que no daría error en LaTeX.
    """
    doc, _ = a_latex.construir_documento(novela)
    sin_comentarios = re.sub(r"(?<!\\)%.*", "", cuerpo(doc))
    sin_macros = re.sub(r"\\[a-zA-Z]+|\\[{}&%$#_~^]", "", sin_comentarios)
    assert not re.findall(r"[&%$#_^]", sin_macros)


def test_las_llaves_del_documento_estan_equilibradas(novela):
    doc, _ = a_latex.construir_documento(novela)
    sin_comentarios = re.sub(r"(?<!\\)%.*", "", doc)
    sin_escapadas = re.sub(r"\\[{}]", "", sin_comentarios)
    assert sin_escapadas.count("{") == sin_escapadas.count("}")


# ---------------------------------------------------------------------------
# Lo que falta o viene roto
# ---------------------------------------------------------------------------

def test_sin_capitulos_json_el_libro_sale_igual(novela):
    (novela / "04_estado" / "capitulos.json").unlink()
    doc, _ = a_latex.construir_documento(novela)
    assert cuerpo(doc).count("\\capitulo{") == 3
    assert "\\capitulo{1}{}" in cuerpo(doc)  # sin título, pero con su número


def test_un_capitulos_json_corrupto_no_revienta(novela):
    (novela / "04_estado" / "capitulos.json").write_text("{esto no es json", encoding="utf-8")
    doc, _ = a_latex.construir_documento(novela)
    assert cuerpo(doc).count("\\capitulo{") == 3


def test_sin_titulo_se_usa_el_nombre_de_la_carpeta(novela):
    (novela / "01_concepto" / "premisa.md").unlink()
    _, titulo = a_latex.construir_documento(novela)
    assert titulo == "El pasajero del vacio"


def test_un_capitulo_vacio_no_desaparece_ni_rompe(novela):
    (novela / "05_manuscrito" / "cap_2.md").write_text("", encoding="utf-8")
    doc, _ = a_latex.construir_documento(novela)
    assert cuerpo(doc).count("\\capitulo{") == 3
    assert "Capítulo sin texto" in doc


def test_sin_manuscrito_falla_con_mensaje_y_no_con_traceback(tmp_path):
    (tmp_path / "01_concepto").mkdir()
    with pytest.raises(a_latex.ErrorDeConversion) as exc:
        a_latex.construir_documento(tmp_path)
    assert "manuscrito" in str(exc.value)


def test_la_cli_devuelve_1_y_no_traza_cuando_la_carpeta_no_existe(tmp_path, capsys):
    codigo = a_latex.main([str(tmp_path / "no-existe"), "--salida", str(tmp_path / "x.tex")])
    assert codigo == 1
    assert "error:" in capsys.readouterr().err


def test_la_cli_escribe_el_tex(novela, tmp_path):
    destino = tmp_path / "salida" / "libro.tex"
    assert a_latex.main([str(novela), "--salida", str(destino)]) == 0
    assert "\\end{document}" in destino.read_text(encoding="utf-8")


def test_la_plantilla_tiene_un_unico_marcador_de_cuerpo():
    """Guardarraíl de la plantilla: dos `{{CUERPO}}` meterían el libro dentro de un comentario."""
    plantilla = a_latex.PLANTILLA_POR_DEFECTO.read_text(encoding="utf-8")
    assert plantilla.count("{{CUERPO}}") == 1


def test_el_pie_de_portada_es_la_fecha_y_no_el_nombre_de_la_carpeta(tmp_path):
    """En la primera compilación real la cubierta imprimió el slug entero del archivo."""
    from herramientas.a_latex import pie_de_portada
    assert pie_de_portada(tmp_path / "2026-09-18T13-03-10_el-pasajero-del-vacio") == "2026-09-18"
    assert pie_de_portada(tmp_path / "una-carpeta-cualquiera") == ""
