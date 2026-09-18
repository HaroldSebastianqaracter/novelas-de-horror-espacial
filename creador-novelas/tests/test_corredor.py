"""El corredor: diez novelas seguidas sin nadie delante, y una medida por cada una.

Las fases no se lanzan de verdad aquí: se sustituye `ejecutar` por un doble que deja en disco lo que
dejaría la fase real. Lo que se prueba es el encadenado y, sobre todo, qué hace el corredor cuando
una novela sale mal, que es lo que decide si la corrida de una noche sirve o se pierde entera.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app import corredor
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


def test_una_novela_pausada_por_qa_cuenta_como_fallida_y_no_espera_a_nadie(vacio):
    doble = FaseDoble(vacio, pausar=True)
    fila = corredor.correr_novela(vacio, ENCARGO, ejecutar=doble, aviso=lambda _: None)

    # Reanudar es intervención, y que una novela pare a mitad es justo uno de los guardarraíles: no
    # puede promediarse con las que salieron solas, ni dejar al corredor esperando a que alguien mire.
    assert fila["completa"] is False
    assert "pausado" in fila["fallo"]
    assert "ensamblar" not in doble.llamadas
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


def test_el_informe_resume_la_corrida():
    filas = [{"nombre": "capsula", "completa": True, "reloj_corredor_s": 1032.0, "capitulos": 3,
              "calidad": {"contradicciones": 0}, "coste_usd": 5.8},
             {"nombre": "faro", "completa": False, "fallo": "QA dejó el manuscrito pausado"}]
    texto = corredor.informe(filas)
    assert "capsula" in texto and "17.2" in texto
    assert "QA dejó el manuscrito pausado" in texto
    assert "1 de 2 completas" in texto
