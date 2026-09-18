"""`archivar`: cerrar una novela, quedarse con su medida y dejar el árbol listo para la siguiente.

Sin este verbo no hay diez novelas seguidas: hay una, y después alguien delante del teclado.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app import archivo, registro
from app.errores import EstadoInvalidoError
from app.orchestrator import checkpoint, cursor as cur
from app.rutas import Rutas
from app.state import repository as repo


def _novela_terminada(raiz: Path, *, capitulos: int = 3) -> None:
    """Deja el árbol como lo deja una tanda real: manuscrito, QA, registro y manifiesto cerrado."""
    rutas = Rutas(raiz)
    for n in range(1, capitulos + 1):
        repo.escribir_texto(rutas.capitulo(n), f"Texto del capítulo {n}. " + " ".join(f"p{i}" for i in range(50)))
        checkpoint.marcar_capitulo_cerrado(raiz, n)
        repo.escribir_texto(rutas.reporte_qa_md(n), f"# QA {n}\n")
    rutas.metricas_qa.parent.mkdir(parents=True, exist_ok=True)
    with rutas.metricas_qa.open("w", encoding="utf-8") as fh:
        for n in range(1, capitulos + 1):
            fh.write(json.dumps({"cap_corte": n, "contradicciones": 0, "hechos_vigentes": 10}) + "\n")

    registro.iniciar_tanda(raiz, {"total_capitulos": capitulos})
    for n in range(1, capitulos + 1):
        for rol in ("escritor", "extractor", "qa"):
            registro.evento(raiz, "agente_inicio", rol=rol, capitulo=n, intento=1)
            registro.evento(raiz, "agente_fin", rol=rol, capitulo=n, agent_id=f"{rol}-{n}",
                            modelo="claude-opus-5", turnos=3)
    carpeta = registro.dir_actual(raiz)
    with (carpeta / "uso.jsonl").open("w", encoding="utf-8") as fh:
        for n in range(1, capitulos + 1):
            fh.write(json.dumps({"rol": "extractor", "capitulo": n, "modelo": "claude-haiku-4-5-20251001",
                                 "tokens_salida": 8000, "agent_id": f"extractor-{n}"}) + "\n")
            fh.write(json.dumps({"rol": "escritor", "capitulo": n, "modelo": "claude-opus-5",
                                 "tokens_salida": 1500, "agent_id": f"escritor-{n}"}) + "\n")
    cur.borrar(raiz, "fin de tanda")

    fases = rutas.registro / "fases.jsonl"
    with fases.open("w", encoding="utf-8") as fh:
        for fase, segundos in (("generar-premisa", 56.0), ("generar-sinopsis", 62.0)):
            fh.write(json.dumps({"ts": "2026-09-18T12:58:09.161+02:00", "fase": fase,
                                 "coste_usd": 0.5, "turnos": 4, "tokens": 1000,
                                 "segundos": segundos}) + "\n")


def test_archivar_mueve_la_novela_y_deja_el_arbol_listo_para_la_siguiente(proyecto):
    _novela_terminada(proyecto)
    rutas = Rutas(proyecto)
    referencia = rutas.referencias / "una-referencia-del-usuario.md"
    referencia.write_text("material con derechos de autor\n", encoding="utf-8")

    r = archivo.archivar(proyecto)

    destino = proyecto / r["carpeta"]
    assert (destino / "05_manuscrito" / "cap_1.md").is_file()
    assert (destino / "06_qa" / "reportes" / "qa_cap_1.md").is_file()
    assert (destino / "04_estado" / "manifest.json").is_file()

    # El árbol queda vacío pero existente: el siguiente encargo escribe encima sin crear nada.
    assert not rutas.capitulo(1).is_file()
    assert checkpoint.leer_manifest(proyecto) is None
    assert rutas.manuscrito.is_dir() and rutas.estado.is_dir()

    # Lo del usuario no se toca: la config la necesita la novela siguiente y las referencias no se
    # podrían recuperar, porque están fuera de git.
    assert rutas.novela_json.is_file()
    assert referencia.read_text(encoding="utf-8") == "material con derechos de autor\n"


def test_el_resumen_guarda_reloj_agentes_y_guardarrailes(proyecto):
    _novela_terminada(proyecto)
    r = archivo.archivar(proyecto)
    resumen = json.loads((proyecto / r["carpeta"] / "resumen.json").read_text(encoding="utf-8"))

    assert resumen["capitulos"]["cerrados"] == 3
    assert resumen["reloj"]["preludio_s"] == pytest.approx(118.0)
    assert resumen["reloj"]["por_fase_s"]["generar-premisa"] == pytest.approx(56.0)
    assert resumen["reloj"]["total_s"] is not None

    # El extractor emite mucho más de lo que escribe, y esa columna es la que delata el cuello de
    # botella antes que el reloj: 24.000 tokens de salida para tres deltas.
    assert resumen["agentes"]["extractor"]["tokens_salida"] == 24000
    assert resumen["agentes"]["escritor"]["invocaciones"] == 3

    assert resumen["calidad"] == {"contradicciones": 0, "cortes_qa": 3, "reintentos_de_escritor": 0,
                                  "borradores_descartados": 0, "pausado_al_archivar": False}
    # La configuración viaja con el libro: sin ella, dos novelas con distinta cadencia de QA no son
    # comparables y nadie sabría por qué una tardó menos.
    assert resumen["config"]["novela.json"]["cadencia_qa"] == 3


def test_las_contradicciones_del_qa_se_cuentan_en_el_resumen(proyecto):
    _novela_terminada(proyecto)
    rutas = Rutas(proyecto)
    with rutas.metricas_qa.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"cap_corte": 3, "contradicciones": 2}) + "\n")

    r = archivo.archivar(proyecto)
    resumen = json.loads((proyecto / r["carpeta"] / "resumen.json").read_text(encoding="utf-8"))
    assert resumen["calidad"]["contradicciones"] == 2


def test_la_novela_ensamblada_se_guarda_suelta_para_que_gitignore_no_la_tape(proyecto):
    _novela_terminada(proyecto)
    entrega = proyecto / "08_entrega"
    entrega.mkdir(exist_ok=True)
    (entrega / "novela.md").write_text("# El silencio de Ceres\n", encoding="utf-8")

    r = archivo.archivar(proyecto)
    # `08_entrega/` está en .gitignore y el patrón tapa la carpeta a cualquier profundidad, así que
    # la copia archivada ahí dentro no se versionaría. Suelta en la raíz del archivo, sí.
    assert (proyecto / r["carpeta"] / "novela.md").read_text(encoding="utf-8") == "# El silencio de Ceres\n"


def test_se_niega_con_una_tanda_en_curso_y_cede_con_forzar(proyecto):
    _novela_terminada(proyecto)
    cur.escribir(proyecto, cur.Cursor(inicio=1, tope=3, max_llamadas=30))

    with pytest.raises(EstadoInvalidoError, match="tanda en curso"):
        archivo.archivar(proyecto)

    r = archivo.archivar(proyecto, forzar=True)
    assert (proyecto / r["carpeta"] / "05_manuscrito" / "cap_1.md").is_file()
    assert cur.leer(proyecto) is None  # el cursor es transitorio: no se archiva, se tira


def test_se_niega_con_el_manuscrito_pausado_por_qa(proyecto):
    _novela_terminada(proyecto)
    checkpoint.pausar_por_qa(proyecto, 3)

    with pytest.raises(EstadoInvalidoError, match="pausado por QA"):
        archivo.archivar(proyecto)


def test_se_niega_cuando_no_hay_novela(proyecto):
    for ruta in (Rutas(proyecto).manifest,):
        ruta.unlink(missing_ok=True)
    with pytest.raises(EstadoInvalidoError, match="no hay novela que archivar"):
        archivo.archivar(proyecto)


def test_dos_novelas_seguidas_no_se_pisan(proyecto):
    _novela_terminada(proyecto)
    primera = archivo.archivar(proyecto, nombre="primera")

    checkpoint.crear_manifest(proyecto, 3)
    _novela_terminada(proyecto)
    segunda = archivo.archivar(proyecto, nombre="segunda")

    assert primera["carpeta"] != segunda["carpeta"]
    assert (proyecto / primera["carpeta"] / "05_manuscrito" / "cap_1.md").is_file()
    assert (proyecto / segunda["carpeta"] / "05_manuscrito" / "cap_1.md").is_file()
    # Y el registro de la segunda no arrastra las tandas de la primera, que es lo que hasta ahora
    # hacía que a la tercera novela ya no quedara con qué comparar.
    assert len(list((proyecto / segunda["carpeta"] / "07_registro").glob("tanda_*"))) == 1


def test_los_tramos_de_agente_se_emparejan_por_rol_y_capitulo():
    eventos = [
        {"tipo": "agente_inicio", "rol": "escritor", "capitulo": 1, "ts": "2026-09-18T13:00:00+02:00"},
        {"tipo": "agente_inicio", "rol": "extractor", "capitulo": 1, "ts": "2026-09-18T13:01:00+02:00"},
        {"tipo": "agente_fin", "rol": "escritor", "capitulo": 1, "ts": "2026-09-18T13:02:00+02:00",
         "agent_id": "a1", "modelo": "claude-opus-5"},
        {"tipo": "agente_fin", "rol": "extractor", "capitulo": 1, "ts": "2026-09-18T13:04:00+02:00",
         "agent_id": "a2", "modelo": "claude-haiku-4-5-20251001"},
    ]
    tramos = {t["rol"]: t for t in archivo.tramos_de_agente(eventos)}
    # El inicio no lleva agent_id, se emite antes de que el agente exista; la pareja es por rol y
    # capítulo. Y los tramos se solapan, que es justo lo que hace que el reloj sume menos que ellos.
    assert tramos["escritor"]["segundos"] == 120.0
    assert tramos["extractor"]["segundos"] == 180.0
    assert tramos["extractor"]["agent_id"] == "a2"


def test_el_nombre_de_carpeta_sale_del_titulo_sin_acentos_ni_espacios(proyecto):
    _novela_terminada(proyecto)
    r = archivo.archivar(proyecto)
    assert r["carpeta"].endswith("_el-silencio-de-ceres")  # «Título: El silencio de Ceres» en la premisa
