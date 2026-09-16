"""Antirrepetición (RF-05.5, §17, §9): una repetición literal se rechaza nombrando la frase y su capítulo de origen,
una secuencia solo de palabras vacías no dispara, y los recursos agotados llegan al prompt con su conteo. Sin modelo."""

import json

from app import antirrepeticion, cli, validacion
from app.orchestrator import checkpoint, loop
from app.rutas import Rutas
from app.schemas import DeltaExtraccion, RecursoNarrativo, RecursosNarrativos
from app.state import recursos as rec
from app.state import repository as repo
from tests.conftest import AgentesDobles


def _relleno(n: int, cantidad: int) -> str:
    """Prosa sin repeticiones posibles entre capítulos: cada palabra lleva el número del capítulo."""
    return " ".join(f"v{n}x{i}" for i in range(cantidad))


def _capitulo(proyecto, n: int, frase: str, cantidad: int = 1490) -> None:
    repo.guardar_capitulo(proyecto, n, f"Kovacs {frase} {_relleno(n, cantidad)}\n", reemplazar_borrador=True)


def _cerrar(proyecto, n: int) -> None:
    for k in range(checkpoint.exigir_manifest(proyecto).ultimo_capitulo_cerrado + 1, n + 1):
        checkpoint.marcar_capitulo_cerrado(proyecto, k)


# ---------- capa determinista §17.1 ----------

def test_coincidencia_literal_se_rechaza_con_frase_y_origen(proyecto, config, capsys):
    _capitulo(proyecto, 1, "El metal estaba frío bajo la palma, y no había nadie más en el puente.")
    _cerrar(proyecto, 1)
    _capitulo(proyecto, 2, "Apoyó la mano. El metal estaba frío bajo la palma, otra vez.")
    r = validacion.validar_capitulo(proyecto, config, 2)
    assert not r.valido and len(r.errores) == 1
    assert "RF-05.5" in r.errores[0] and "«El metal estaba frío bajo la palma" in r.errores[0] and "(cap. 1" in r.errores[0]
    assert r.datos["repeticiones_literales"] == 1
    # el agente ve lo mismo por el CLI, con código 1
    codigo = cli.main(["validar-capitulo", "2"])
    out = capsys.readouterr().out
    assert codigo == 1 and "RESULTADO: invalido" in out and "El metal estaba frío" in out


def test_secuencia_solo_de_palabras_vacias_no_dispara(proyecto, config):
    _capitulo(proyecto, 1, "Se quedó en el interior de la sala, sin decir nada de lo que había visto.")
    _cerrar(proyecto, 1)
    _capitulo(proyecto, 2, "Algo se movía en el interior de la cámara, y no era lo que había esperado.")
    r = validacion.validar_capitulo(proyecto, config, 2)
    assert r.valido, r.errores
    assert r.datos["repeticiones_literales"] == 0


def test_los_nombres_del_registro_son_neutrales(proyecto, config):
    # «Kovacs miró a Ilse» vuelve en cada capítulo: nombrar personajes no es repetirse (solo `miró` tiene contenido)
    _capitulo(proyecto, 1, "Kovacs miró a Ilse y siguió por el pasillo de la Bodega 4 hacia babor.")
    _cerrar(proyecto, 1)
    _capitulo(proyecto, 2, "Kovacs miró a Ilse y no dijo nada; la Bodega 4 seguía cerrada.")
    assert validacion.validar_capitulo(proyecto, config, 2).valido
    # pero con dos palabras con contenido en la secuencia sí cuenta, aunque haya nombres en medio
    _capitulo(proyecto, 2, "Kovacs miró a Ilse y siguió por el pasillo de la Bodega 4 hacia la enfermería.")
    r = validacion.validar_capitulo(proyecto, config, 2)
    assert not r.valido and "siguió por el pasillo" in r.errores[0]


def test_solo_compara_con_capitulos_anteriores(proyecto, config):
    _capitulo(proyecto, 1, "La escarcha blanca ramificada crecía sobre el mamparo.")
    _cerrar(proyecto, 1)
    _capitulo(proyecto, 2, "Nada que ver con lo anterior en este borrador.")
    _capitulo(proyecto, 3, "La escarcha blanca ramificada crecía sobre el mamparo.")  # borrador futuro, no cuenta para el 2
    assert validacion.validar_capitulo(proyecto, config, 2).valido
    r = validacion.validar_capitulo(proyecto, config, 3)  # el 3 sí choca con el 1
    assert not r.valido and "(cap. 1" in r.errores[0]


def test_coincidencias_funde_ngramas_consecutivos_y_ordena():
    previo = {4: "Cerró la escotilla con las dos manos y contó tres respiraciones antes de girar la llave."}
    texto = ("Al final cerró la escotilla con las dos manos y contó tres respiraciones, "
             "y más tarde volvió a girar la llave del reactor.")
    hallazgos = antirrepeticion.coincidencias(texto, previo, set())
    assert [h.cap_origen for h in hallazgos] == [4]
    assert hallazgos[0].frase.lower().startswith("cerró la escotilla con las dos manos y contó tres respiraciones")
    assert hallazgos[0].palabras >= 10
    # «girar la llave» son solo tres palabras: no llega al n-grama
    assert all("girar" not in h.frase for h in hallazgos)
    assert "4 o más palabras" in antirrepeticion.describir(hallazgos) and "cap. 4" in antirrepeticion.describir(hallazgos)


def test_describir_recorta_la_lista():
    hallazgos = [antirrepeticion.Coincidencia(frase=f"frase repetida número {i} con contenido", cap_origen=1, palabras=5) for i in range(12)]
    texto = antirrepeticion.describir(hallazgos)
    assert "12 pasaje(s)" in texto and "y 4 más" in texto


# ---------- capa semántica §17.2 ----------

def test_acumular_y_reextraer_recursos():
    estado = RecursosNarrativos([])
    estado = rec.acumular(estado, [RecursoNarrativo(recurso="El zumbido de los ventiladores", veces=2)], 1)
    estado = rec.acumular(estado, [RecursoNarrativo(recurso="el zumbido de los ventiladores", veces=1),
                                   RecursoNarrativo(recurso="Palparse las costillas", veces=1)], 2)
    assert [(r.recurso, r.veces, r.caps) for r in estado.root] == [("El zumbido de los ventiladores", 3, [1, 2]), ("Palparse las costillas", 1, [2])]
    # la reextracción del capítulo 2 retira primero lo que ese capítulo había aportado
    estado = rec.acumular(estado, [RecursoNarrativo(recurso="el zumbido de los ventiladores", veces=1)], 2, reextraccion=True)
    assert [(r.recurso, r.veces, r.caps) for r in estado.root] == [("El zumbido de los ventiladores", 3, [1, 2])]
    # dentro de un delta, el mismo recurso dos veces se funde
    fusion = rec.fusionar([RecursoNarrativo(recurso="Mesa dice «Sin datos»", veces=2), RecursoNarrativo(recurso="mesa dice sin datos", veces=3)])
    assert len(fusion) == 1 and fusion[0].veces == 5
    assert rec.formatear_agotados(RecursosNarrativos([])).startswith("(todavía no hay recursos")
    assert "· 3 veces · cap. 1, 2" in rec.formatear_agotados(estado)


def test_el_delta_admite_recursos_y_sigue_valido_sin_ellos(proyecto, config):
    sin = DeltaExtraccion.model_validate({"personajes": {}, "hechos_nuevos": [], "resumen_corto": "x\ny\nz"})
    assert sin.recursos_narrativos == []
    con = DeltaExtraccion.model_validate({"personajes": {}, "hechos_nuevos": [], "resumen_corto": "x\ny\nz",
                                          "recursos_narrativos": [{"recurso": "coda de ventiladores", "veces": 2}, {"recurso": "Coda de ventiladores"}]})
    from app.agents import extractor
    validado = extractor.validar_delta(con, {"Kovacs"}, config, 1)
    assert [(r.recurso, r.veces) for r in validado.delta.recursos_narrativos] == [("coda de ventiladores", 3)]
    # H-02 conoce el artefacto acumulado
    from pathlib import Path
    assert repo.esquema_para(Rutas(proyecto), Path("04_estado/recursos_narrativos.json")) is RecursosNarrativos


def test_tres_capitulos_y_el_cuarto_recibe_los_recursos_con_su_conteo(proyecto, config):
    """Criterio de aceptación de RF-05.5: dada una novela de tres capítulos, el prompt del cuarto lista los recursos usados."""
    loop.ejecutar_tanda(config, proyecto, AgentesDobles(proyecto), capitulos_por_tanda=3)
    rutas = Rutas(proyecto)
    estado = repo.leer_recursos_narrativos(proyecto)
    zumbido = next(r for r in estado.root if "zumbido" in r.recurso)
    assert zumbido.veces == 3 and zumbido.caps == [1, 2, 3] and len(estado) == 4
    contexto = loop.preparar_capitulo(proyecto, config, 4)
    prompt = rutas.prompt_escritor(4).read_text(encoding="utf-8")
    assert "## Recursos narrativos ya agotados" in prompt
    assert "- el zumbido de los ventiladores como coda de escena · 3 veces · cap. 1, 2, 3" in prompt
    assert "- imagen propia del capítulo 2 · 2 veces · cap. 2" in prompt
    assert contexto.recursos_inyectados == 4
    # el primer capítulo de la tanda no tenía recursos todavía, y su prompt lo dice
    assert "(todavía no hay recursos registrados" in (registro_prompts(proyecto) / "001_escritor_cap_1.md").read_text(encoding="utf-8")


def registro_prompts(proyecto):
    from app import registro

    return registro.ultima_tanda(proyecto) / "prompts"


def test_preparar_capitulo_informa_los_recursos_en_el_cli(proyecto, config, capsys):
    repo.escribir_recursos_narrativos(proyecto, RecursosNarrativos([
        {"recurso": "contar respiraciones para sostenerse", "apariciones": {"1": 1, "2": 1, "3": 2}},
    ]))
    assert cli.main(["preparar-capitulo", "1"]) == 0
    out = capsys.readouterr().out
    assert "1 recursos narrativos agotados (RF-05.5)" in out
    assert "contar respiraciones para sostenerse · 4 veces · cap. 1, 2, 3" in Rutas(proyecto).prompt_escritor(1).read_text(encoding="utf-8")
