"""El corredor: diez novelas seguidas sin nadie delante, y una medida por cada una.

Las fases no se lanzan de verdad aquí: se sustituye `ejecutar` por un doble que deja en disco lo que
dejaría la fase real. Lo que se prueba es el encadenado y, sobre todo, qué hace el corredor cuando
una novela sale mal, que es lo que decide si la corrida de una noche sirve o se pierde entera.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app import corredor, registro
from app.orchestrator import checkpoint
from app.rutas import Rutas
from app.state import repository as repo
from tests.conftest import construir_proyecto

ENCARGO = {"nombre": "capsula", "idea": "Un remolcador recoge una cápsula con alguien que no consta.",
           "config": {"total_capitulos": 3, "palabras_por_capitulo": 400, "cadencia_qa": 1,
                      "capitulos_por_tanda": 3, "idioma": "es-ES",
                      "persona_narrativa": "tercera_limitada", "tiempo_verbal": "pasado",
                      "ventana_resumen_rodante": 2, "max_tokens_contexto_escritor": 12000,
                      "max_hechos_por_capitulo": 4, "max_llamadas_por_tanda": 30}}


@pytest.fixture
def vacio(tmp_path, monkeypatch) -> Path:
    raiz = construir_proyecto(tmp_path / "novela", con_estado=False)
    monkeypatch.setenv("HARNESS_RAIZ", str(raiz))
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    return raiz


class FaseDoble:
    """Hace lo que harían las fases reales en disco, sin modelo y en microsegundos."""

    def __init__(self, raiz: Path, *, pausar: bool = False, fallar_en: str | None = None,
                 capitulos: int = 3):
        self.raiz, self.pausar, self.fallar_en, self.capitulos = raiz, pausar, fallar_en, capitulos
        self.llamadas: list[str] = []

    def __call__(self, raiz: Path, fase: str, **kwargs) -> dict:
        self.llamadas.append(fase)
        if fase == self.fallar_en:
            return {"fase": fase, "codigo": 1, "segundos": 1.0}
        if fase == "inicializar-estado":
            checkpoint.crear_manifest(raiz, self.capitulos)
        elif fase == "escribir-tanda":
            rutas = Rutas(raiz)
            for n in range(1, self.capitulos + 1):
                repo.escribir_texto(rutas.capitulo(n), f"Capítulo {n}. " + " ".join(f"p{i}" for i in range(40)))
                checkpoint.marcar_capitulo_cerrado(raiz, n)
            if self.pausar:
                checkpoint.pausar_por_qa(raiz, self.capitulos)
        return {"fase": fase, "codigo": 0, "segundos": 12.0}


def test_una_novela_entera_se_encadena_y_se_archiva(vacio):
    doble = FaseDoble(vacio)
    fila = corredor.correr_novela(vacio, ENCARGO, ejecutar=doble, aviso=lambda _: None)

    assert doble.llamadas == [*corredor.PRELUDIO, "escribir-tanda", "ensamblar"]
    assert fila["completa"] is True and fila["fallo"] is None
    assert fila["capitulos"] == 3

    # El árbol queda vacío, que es la condición para que la siguiente novela pueda empezar sola.
    assert checkpoint.leer_manifest(vacio) is None
    assert (vacio / fila["carpeta"] / "05_manuscrito" / "cap_1.md").is_file()

    corridas = (vacio / "09_archivo" / corredor.CORRIDAS).read_text(encoding="utf-8").splitlines()
    assert json.loads(corridas[0])["nombre"] == "capsula"


def test_una_pausa_de_qa_se_resuelve_sola_y_la_novela_sigue(vacio):
    class PausaYReanuda(FaseDoble):
        def __call__(self, raiz, fase, **kwargs):
            if fase == "reanudar":
                self.llamadas.append(fase)
                checkpoint.limpiar_error(raiz)
                checkpoint._actualizar(raiz, estado="en_progreso", reporte_qa_pendiente=None)
                self.pausar = False  # el revisor ya dio su veredicto y se aceptó
                return {"fase": fase, "codigo": 0, "segundos": 2.0}
            return super().__call__(raiz, fase, **kwargs)

    doble = PausaYReanuda(vacio, pausar=True)
    fila = corredor.correr_novela(vacio, ENCARGO, ejecutar=doble, aviso=lambda _: None)

    # `reanudar` es lo que hace el botón de la pantalla: aceptar el veredicto y seguir. Contarlo como
    # fallo dejaba casi todas las novelas sin terminar --hay una contradicción cada dos cortes-- y
    # sin novelas completas no hay velocidad que medir. La calidad no se pierde: se anota.
    assert "reanudar" in doble.llamadas
    assert fila["completa"] is True
    assert fila["resoluciones"] == 1
    assert corredor.fila_csv(fila)["resoluciones"] == 1


def test_una_pausa_que_no_se_deja_resolver_no_deja_al_corredor_dando_vueltas(vacio):
    doble = FaseDoble(vacio, pausar=True)  # reanudar no arregla nada: sigue pausada
    fila = corredor.correr_novela(vacio, ENCARGO, ejecutar=doble, aviso=lambda _: None)

    assert fila["completa"] is False
    assert "seguía abierta" in fila["fallo"]
    assert checkpoint.leer_manifest(vacio) is None  # archivada igual: el árbol queda listo


def test_una_fase_que_falla_corta_esa_novela_pero_no_la_corrida(vacio):
    llamadas: list[str] = []

    def ejecutar(raiz, fase, **kwargs):
        doble = FaseDoble(raiz, fallar_en="generar-escaleta" if len(llamadas) < 4 else None)
        llamadas.append(fase)
        return doble(raiz, fase, **kwargs)

    filas = corredor.correr(vacio, [dict(ENCARGO, nombre="primera"), dict(ENCARGO, nombre="segunda")],
                            ejecutar=ejecutar, aviso=lambda _: None)

    assert [f["nombre"] for f in filas] == ["primera", "segunda"]
    assert filas[0]["completa"] is False and "preludio" in filas[0]["fallo"]
    assert filas[1]["completa"] is True  # una noche no se pierde entera por una novela


def test_una_tanda_que_no_cierra_capitulos_no_deja_al_corredor_dando_vueltas(vacio):
    class SinAvance(FaseDoble):
        def __call__(self, raiz, fase, **kwargs):
            if fase == "escribir-tanda":
                self.llamadas.append(fase)
                return {"fase": fase, "codigo": 0, "segundos": 5.0}
            return super().__call__(raiz, fase, **kwargs)

    doble = SinAvance(vacio)
    fila = corredor.correr_novela(vacio, ENCARGO, ejecutar=doble, aviso=lambda _: None)

    assert fila["completa"] is False
    assert "sin cerrar ningún capítulo" in fila["fallo"]
    assert doble.llamadas.count("escribir-tanda") == 1


def test_el_encargo_llega_al_arbol_con_su_idea_y_su_configuracion(vacio):
    corredor.correr_novela(vacio, ENCARGO, ejecutar=FaseDoble(vacio), aviso=lambda _: None)
    novela = json.loads((vacio / "config" / "novela.json").read_text(encoding="utf-8"))
    assert novela["palabras_por_capitulo"] == 400 and novela["cadencia_qa"] == 1


def test_los_booleanos_viajan_como_los_manda_el_formulario():
    campos = corredor.campos_de_encargo({"idea": "x", "config": {"registrar_uso": True,
                                                                 "exportar_trazas": False,
                                                                 "total_capitulos": 3}})
    # El formulario manda «on» para una casilla marcada y no manda nada para una desmarcada; el
    # corredor tiene que hablar ese idioma o la configuración llegaría al revés.
    assert campos["registrar_uso"] == "on"
    assert campos["exportar_trazas"] == ""
    assert campos["total_capitulos"] == "3"


def test_la_configuracion_comun_se_reparte_a_las_diez(tmp_path):
    ruta = tmp_path / "premisas.json"
    ruta.write_text(json.dumps({
        "config": {"total_capitulos": 3, "palabras_por_capitulo": 400},
        "novelas": [{"nombre": "a", "idea": "una"}, {"nombre": "b", "idea": "otra",
                                                     "config": {"cadencia_qa": 3}}],
    }), encoding="utf-8")

    encargos = corredor.cargar_encargos(ruta)
    # Que las diez compartan tamaño de novela es la condición para que sean comparables; repetirlo
    # diez veces en el archivo serían diez ocasiones de que una se desvíe sin que nadie lo vea.
    assert encargos[0]["config"]["palabras_por_capitulo"] == 400
    assert encargos[1]["config"]["palabras_por_capitulo"] == 400
    assert encargos[1]["config"]["cadencia_qa"] == 3


def test_las_diez_premisas_del_repositorio_son_comparables():
    ruta = Path(__file__).resolve().parents[1] / "herramientas" / "premisas-velocidad.json"
    encargos = corredor.cargar_encargos(ruta)
    assert len(encargos) == 10
    assert len({e["nombre"] for e in encargos}) == 10
    for e in encargos:
        # Mismo tamaño de libro en las diez: cambiar el trabajo cambia el reloj, y entonces la
        # comparación entre novelas no mediría la eficiencia sino el argumento.
        assert e["config"]["total_capitulos"] == 3
        assert e["config"]["palabras_por_capitulo"] == 400
        assert 150 < len(e["idea"]) < 500


def test_el_juego_de_premisas_viaja_con_cada_novela(tmp_path):
    ruta = tmp_path / "premisas.json"
    ruta.write_text(json.dumps({"version": 2, "config": {"total_capitulos": 3},
                                "novelas": [{"nombre": "a", "idea": "una"}]}), encoding="utf-8")
    encargos = corredor.cargar_encargos(ruta)
    # El juego 1 fallaba en dos de cada tres novelas por una contradicción del clímax; promediar sus
    # tiempos con los del juego 2 sería mezclar dos poblaciones distintas en la misma columna.
    assert encargos[0]["premisas"] == 2


def test_el_informe_resume_la_corrida():
    filas = [{"nombre": "capsula", "completa": True, "reloj_corredor_s": 1032.0, "capitulos": 3,
              "calidad": {"contradicciones": 0}, "coste_usd": 5.8},
             {"nombre": "faro", "completa": False, "fallo": "QA dejó el manuscrito pausado"}]
    texto = corredor.informe(filas)
    assert "capsula" in texto and "17.2" in texto
    assert "QA dejó el manuscrito pausado" in texto
    assert "1 de 2 completas" in texto


# ---------- la tabla para el análisis ----------

def test_cada_novela_deja_una_fila_plana_con_su_variante(vacio):
    corredor.correr_novela(vacio, ENCARGO, ejecutar=FaseDoble(vacio), aviso=lambda _: None,
                           variante="extractor-effort-low")

    import csv
    with (vacio / "09_archivo" / corredor.CORRIDAS_CSV).open(encoding="utf-8", newline="") as fh:
        filas = list(csv.DictReader(fh))

    assert len(filas) == 1
    fila = filas[0]
    # `variante` es la columna que manda: sin ella no se puede agrupar por vuelta y el resto de los
    # números no dicen gran cosa.
    assert fila["variante"] == "extractor-effort-low"
    assert fila["novela"] == "capsula" and fila["completa"] == "1"
    assert fila["capitulos"] == "3"
    # La configuración con la que se escribió viaja en la misma fila: es la variable independiente.
    assert fila["cadencia_qa"] == "1" and fila["palabras_por_capitulo"] == "400"
    assert "extractor_tokens_salida" in fila and "extractor_segundos" in fila


def test_las_columnas_no_cambian_aunque_falte_un_rol(vacio):
    corredor.correr_novela(vacio, dict(ENCARGO, nombre="una"), ejecutar=FaseDoble(vacio), aviso=lambda _: None)
    primera = (vacio / "09_archivo" / corredor.CORRIDAS_CSV).read_text(encoding="utf-8").splitlines()[0]

    corredor.correr_novela(vacio, dict(ENCARGO, nombre="otra"), ejecutar=FaseDoble(vacio), aviso=lambda _: None)
    lineas = (vacio / "09_archivo" / corredor.CORRIDAS_CSV).read_text(encoding="utf-8").splitlines()

    # Una tabla cuyas columnas cambian según lo que salió en cada corrida no se lee con pandas sin
    # pelearse con ella. Cabecera una sola vez y siempre la misma.
    assert lineas[0] == primera
    assert len([l for l in lineas if l.startswith("variante,")]) == 1
    assert len(lineas) == 3


def test_el_csv_se_puede_rehacer_desde_el_registro_que_manda(vacio):
    corredor.correr_novela(vacio, ENCARGO, ejecutar=FaseDoble(vacio), aviso=lambda _: None)
    csv_ = vacio / "09_archivo" / corredor.CORRIDAS_CSV
    csv_.unlink()

    # El JSONL es el registro; el CSV es una vista. Una corrida que se quedó sin fila --porque el
    # CSV no existía aún, o porque se añadió una columna-- se recupera sin repetir la novela.
    corredor.reconstruir_csv(vacio, variante="base")
    filas = csv_.read_text(encoding="utf-8").splitlines()
    assert len(filas) == 2 and filas[1].split(",")[0] == "base" and "capsula" in filas[1]


def test_una_novela_abortada_por_un_hook_se_cuenta_en_la_tabla(vacio):
    doble = FaseDoble(vacio)

    def con_aborto(raiz, fase, **kwargs):
        if fase == "escribir-tanda":
            registro.iniciar_tanda(raiz, {"total_capitulos": 3})
        r = doble(raiz, fase, **kwargs)
        if fase == "escribir-tanda":
            registro.evento(raiz, "error", excepcion="EX-01",
                            mensaje="via H-02: delta_cap_2.json no es JSON válido", capitulo=2)
        return r

    fila = corredor.correr_novela(vacio, ENCARGO, ejecutar=con_aborto, aviso=lambda _: None)
    # Cada aborto obliga a relanzar, y relanzar es una sesión de orquestador entera releyendo todo:
    # es tiempo y dinero que hay que poder ver en la tabla junto al resto.
    assert fila["calidad"]["tandas_abortadas"] == 1
    assert corredor.fila_csv(fila)["tandas_abortadas"] == 1
