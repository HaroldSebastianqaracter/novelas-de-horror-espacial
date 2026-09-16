"""Observabilidad (RF-09, §16, §9): la traza refleja la tanda, las cuatro cifras de tokens viajan, reexportar no duplica
y por defecto no sale ninguna subcadena de más de 30 caracteres del manuscrito ni de los prompts. Sin red."""

import json
import re

import pytest

from app import cli, observabilidad, registro
from app.errores import ConfiguracionInvalidaError
from app.orchestrator import loop
from app.rutas import Rutas
from tests.conftest import AgentesDobles

USO_REAL = {"tokens_entrada": 6, "tokens_salida": 127, "tokens_cache_lectura": 42129, "tokens_cache_creacion": 26943}


class ClienteDoble:
    """Acumula lo enviado en vez de publicarlo (§9)."""

    def __init__(self):
        self.lotes: list[list[dict]] = []

    def enviar(self, lote):
        self.lotes.append(lote)
        return {"successes": [{"id": e["id"], "status": 201} for e in lote], "errors": []}

    @property
    def enviados(self) -> list[dict]:
        return [e for lote in self.lotes for e in lote]


def _tanda_con_dobles(proyecto, config, **kw):
    tope = kw.pop("tope", 3)
    loop.ejecutar_tanda(config, proyecto, AgentesDobles(proyecto, **kw), capitulos_por_tanda=tope)
    return registro.ultima_tanda(proyecto)


def _uso(carpeta, agent_id, rol, capitulo, modelo="claude-opus-5", **cifras):
    linea = {"rol": rol, "capitulo": capitulo, "modelo": modelo, **USO_REAL, **cifras, "turnos": 3, "agent_id": agent_id, "stop_reason": "end_turn"}
    with (carpeta / "uso.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(linea) + "\n")


def _cadenas(valor):
    if isinstance(valor, str):
        yield valor
    elif isinstance(valor, dict):
        for v in valor.values():
            yield from _cadenas(v)
    elif isinstance(valor, list):
        for v in valor:
            yield from _cadenas(v)


def _comparte_ventana(texto: str, corpus: str, ventana: int = 31) -> bool:
    t = re.sub(r"\s+", " ", texto).lower()
    return any(t[i:i + ventana] in corpus for i in range(max(0, len(t) - ventana + 1)))


# ---------- mapeo §16.2 ----------

def test_la_traza_refleja_la_tanda(proyecto, config):
    carpeta = _tanda_con_dobles(proyecto, config)
    _uso(carpeta, "doble-escritor-1", "escritor", 1)
    traza = observabilidad.construir_traza(proyecto, carpeta)
    tipos = [e["type"] for e in traza.lote]
    assert tipos.count("trace-create") == 1
    trace = next(e["body"] for e in traza.lote if e["type"] == "trace-create")
    assert trace["id"] == traza.id and len(trace["id"]) == 32 and trace["name"] == carpeta.name
    # metadata: dimensionamiento, los tres prompts_hash de ESA tanda (tanda.json) y la versión de las specs
    assert trace["metadata"]["total_capitulos"] == 30 and trace["metadata"]["capitulos_por_tanda"] == 3 and trace["metadata"]["cadencia_qa"] == 3
    assert set(trace["metadata"]["prompts_hash"]) == {"escritor", "extractor", "qa"} and trace["metadata"]["metadatos_origen"] == "tanda.json"
    assert trace["metadata"]["version_specs"] == "v1.8" and trace["metadata"]["motivo_salida"] == "tope_de_tanda"
    # un span por capítulo, con inicio y fin explícitos tomados del registro, no de "ahora"
    spans = [e["body"] for e in traza.lote if e["type"] == "span-create"]
    assert [s["name"] for s in spans] == ["cap_1", "cap_2", "cap_3"]
    assert all(s["startTime"] <= s["endTime"] and s["traceId"] == traza.id for s in spans)
    assert spans[2]["metadata"]["corte_qa"] is True and spans[0]["metadata"]["cerrado"] is True
    # una generation por invocación, colgada de su capítulo
    gens = [e["body"] for e in traza.lote if e["type"] == "generation-create"]
    assert [g["name"] for g in gens] == ["escritor:cap_1", "extractor:cap_1", "escritor:cap_2", "extractor:cap_2", "escritor:cap_3", "extractor:cap_3", "qa:cap_3"]
    por_span = {s["id"]: s["name"] for s in spans}
    assert por_span[gens[0]["parentObservationId"]] == "cap_1" and por_span[gens[-1]["parentObservationId"]] == "cap_3"
    assert all(g["startTime"] <= g["endTime"] for g in gens)
    # por defecto no viajan cuerpos
    assert all("input" not in g and "output" not in g for g in gens)


def test_las_cuatro_cifras_de_tokens_viajan(proyecto, config):
    carpeta = _tanda_con_dobles(proyecto, config)
    _uso(carpeta, "doble-escritor-1", "escritor", 1)
    traza = observabilidad.construir_traza(proyecto, carpeta)
    escritor_1 = next(e["body"] for e in traza.lote if e["type"] == "generation-create" and e["body"]["name"] == "escritor:cap_1")
    assert escritor_1["model"] == "claude-opus-5"
    assert escritor_1["usageDetails"] == {
        "input": 6, "output": 127, "cache_read_input_tokens": 42129, "cache_creation_input_tokens": 26943,
        "total": 6 + 127 + 42129 + 26943,
    }
    # el caso de §16.3: mapear solo entrada/salida diría que el capítulo costó 133 tokens
    assert escritor_1["usageDetails"]["total"] > 60000
    assert observabilidad.tabla_consumo(traza).count("42129") == 1


def test_puntuaciones_del_corte_y_de_la_tanda(proyecto, config):
    carpeta = _tanda_con_dobles(proyecto, config, contradiccion_en={3}, personaje_extra={2: 1}, tope=5)
    traza = observabilidad.construir_traza(proyecto, carpeta)
    scores = {e["body"]["name"]: e["body"] for e in traza.lote if e["type"] == "score-create"}
    assert scores["qa_contradicciones"]["value"] == 1 and scores["qa_contradicciones"]["dataType"] == "NUMERIC"
    assert scores["qa_repeticiones"]["value"] == 0
    assert scores["qa_pasa"]["value"] == 0 and scores["qa_pasa"]["dataType"] == "BOOLEAN"
    assert scores["desvio_longitud"]["value"] == 0.0  # los dobles escriben exactamente 1500 palabras
    assert scores["borradores_descartados"]["value"] == 1  # el capítulo 2 se regeneró una vez (EX-08)
    assert traza.metadatos["motivo_salida"] == "pausado_por_qa"
    eventos = [e["body"] for e in traza.lote if e["type"] == "event-create"]
    assert any(ev["name"] == "EX-08:descarte_de_borrador" and ev["metadata"]["capitulo"] == 2 for ev in eventos)
    # el score del corte cuelga del span de su capítulo
    span_3 = next(e["body"]["id"] for e in traza.lote if e["type"] == "span-create" and e["body"]["name"] == "cap_3")
    assert scores["qa_pasa"]["observationId"] == span_3


def test_bloqueos_de_hook_y_errores_son_eventos(proyecto, config):
    carpeta = _tanda_con_dobles(proyecto, config)
    registro.evento(proyecto, "hook", id="H-11", evento="PreToolUse", agent_type="escritor", agent_id="e-9",
                    accion="Bash cat 05_manuscrito/cap_1.md", decision="bloqueado", motivo="el escritor solo puede ejecutar el validador")
    registro.evento(proyecto, "error", excepcion="AutovalidacionFallidaError", mensaje="EX-10: el escritor no consiguió validar", capitulo=3)
    traza = observabilidad.construir_traza(proyecto, carpeta)
    eventos = {e["body"]["name"]: e["body"] for e in traza.lote if e["type"] == "event-create"}
    assert eventos["hook:H-11"]["level"] == "WARNING" and eventos["hook:H-11"]["metadata"]["agent_type"] == "escritor"
    assert "validador" in eventos["hook:H-11"]["statusMessage"]
    assert eventos["error:EX-10"]["level"] == "ERROR" and "EX-10" in eventos["error:EX-10"]["statusMessage"]
    span_3 = next(e["body"]["id"] for e in traza.lote if e["type"] == "span-create" and e["body"]["name"] == "cap_3")
    assert eventos["error:EX-10"]["parentObservationId"] == span_3


# ---------- idempotencia §16.5 ----------

def test_exportar_dos_veces_no_duplica(proyecto, config):
    carpeta = _tanda_con_dobles(proyecto, config)
    cliente = ClienteDoble()
    r1 = observabilidad.exportar(proyecto, carpeta, cliente)
    r2 = observabilidad.exportar(proyecto, carpeta, cliente)
    assert r1.aceptados == r2.aceptados == len(r1.traza.lote) and len(cliente.lotes) == 2
    primera, segunda = cliente.lotes
    # una sola traza: el mismo body.id en las dos exportaciones, y lo mismo para cada observación y puntuación
    assert {e["body"]["id"] for e in primera if e["type"] == "trace-create"} == {e["body"]["id"] for e in segunda if e["type"] == "trace-create"}
    assert len({e["body"]["id"] for e in primera if e["type"] == "trace-create"}) == 1
    assert [(e["type"], e["body"]["id"]) for e in primera] == [(e["type"], e["body"]["id"]) for e in segunda]
    # el id del sobre sí cambia: el servicio deduplica sobres, no cuerpos
    assert {e["id"] for e in primera}.isdisjoint({e["id"] for e in segunda})
    # el agent_id es la identidad de la generation (§16.5)
    gen = next(e["body"] for e in primera if e["type"] == "generation-create")
    assert gen["id"] == observabilidad.id_observacion(carpeta.name, f"agente/{gen['metadata']['agent_id']}")


# ---------- privacidad §16.6 ----------

def test_por_defecto_no_sale_prosa_ni_prompts(proyecto, config):
    carpeta = _tanda_con_dobles(proyecto, config)
    rutas = Rutas(proyecto)
    prompt = (carpeta / "prompts" / "001_escritor_cap_1.md").read_text(encoding="utf-8")
    oracion_del_prompt = prompt.strip().splitlines()[2][:80]
    registro.evento(proyecto, "error", excepcion="EstadoInvalidoError", mensaje=f"falló con {oracion_del_prompt} y más", capitulo=1)
    registro.evento(proyecto, "hook", id="H-06", evento="PreToolUse", agent_type="qa", decision="bloqueado",
                    accion="Write 04_estado/x.json", motivo=rutas.capitulo(2).read_text(encoding="utf-8")[:200])
    cliente = ClienteDoble()
    observabilidad.exportar(proyecto, carpeta, cliente)
    corpus = re.sub(r"\s+", " ", "\n".join(
        [p.read_text(encoding="utf-8") for p in (carpeta / "prompts").iterdir()]
        + [p.read_text(encoding="utf-8") for p in rutas.manuscrito.glob("cap_*.md")]
    )).lower()
    for texto in _cadenas(cliente.enviados):
        assert not _comparte_ventana(texto, corpus), texto[:120]
    eventos = {e["body"]["name"]: e["body"] for e in cliente.enviados if e["type"] == "event-create"}
    assert eventos["error:EstadoInvalidoError"]["statusMessage"].startswith("[omitido:")
    assert eventos["hook:H-06"]["statusMessage"].startswith("[omitido:")
    assert "H-06" in eventos["hook:H-06"]["metadata"]["hook"]  # lo estructural sigue viajando


def test_con_cuerpos_incluye_prompt_y_retorno(proyecto, config):
    carpeta = _tanda_con_dobles(proyecto, config)
    traza = observabilidad.construir_traza(proyecto, carpeta, con_cuerpos=True)
    gen = next(e["body"] for e in traza.lote if e["type"] == "generation-create" and e["body"]["name"] == "escritor:cap_2")
    assert gen["input"] == (carpeta / "prompts" / "003_escritor_cap_2.md").read_text(encoding="utf-8")
    assert "· validado" in gen["output"]


# ---------- credenciales §16.7 y CLI ----------

def test_sin_credenciales_falla_con_el_motivo_y_no_hace_nada(proyecto, config, monkeypatch, capsys):
    carpeta = _tanda_con_dobles(proyecto, config)
    for v in observabilidad.VARIABLES_CREDENCIALES + observabilidad.VARIABLES_HOST:
        monkeypatch.delenv(v, raising=False)
    with pytest.raises(ConfiguracionInvalidaError, match="LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY"):
        observabilidad.credenciales_desde_entorno({})
    codigo = cli.main(["exportar-traza", carpeta.name])
    err = capsys.readouterr().err
    assert codigo == 1 and "ConfiguracionInvalidaError" in err and "LANGFUSE_SECRET_KEY" in err
    # el host por defecto y las dos variables de host que entiende el SDK
    c = observabilidad.credenciales_desde_entorno({"LANGFUSE_PUBLIC_KEY": "pk-test", "LANGFUSE_SECRET_KEY": "sk-test"})
    assert c.host == observabilidad.HOST_DEFECTO
    c = observabilidad.credenciales_desde_entorno({"LANGFUSE_PUBLIC_KEY": "pk-test", "LANGFUSE_SECRET_KEY": "sk-test", "LANGFUSE_BASE_URL": "http://127.0.0.1:3000/"})
    assert c.host == "http://127.0.0.1:3000"


def test_cli_volcado_local_sin_red(proyecto, config, capsys, tmp_path):
    carpeta = _tanda_con_dobles(proyecto, config)
    _uso(carpeta, "doble-escritor-1", "escritor", 1)
    destino = tmp_path / "lote.json"
    codigo = cli.main(["exportar-traza", "ultima", "--solo-volcar", "--volcar", str(destino)])
    out = capsys.readouterr().out
    assert codigo == 0 and "RESULTADO: volcado" in out and "42129" in out and "qa_pasa[cap_3]=1" in out
    datos = json.loads(destino.read_text(encoding="utf-8"))
    assert datos["tanda"] == carpeta.name and len(datos["batch"]) > 10
    # el exportador no toca el registro de la tanda salvo por el evento `verbo` que deja el CLI
    assert registro.leer_eventos(carpeta)[-1]["verbo"] == "exportar-traza"


def test_tanda_inexistente(proyecto, config):
    with pytest.raises(ConfiguracionInvalidaError, match="no hay ninguna tanda"):
        observabilidad.resolver_tanda(proyecto, "ultima")
    _tanda_con_dobles(proyecto, config)
    with pytest.raises(ConfiguracionInvalidaError, match="no existe la tanda"):
        observabilidad.resolver_tanda(proyecto, "tanda_1999-01-01T00-00-00")


def test_lotes_grandes_se_parten(proyecto, config):
    carpeta = _tanda_con_dobles(proyecto, config)
    traza = observabilidad.construir_traza(proyecto, carpeta)
    lotes = observabilidad._partir_en_lotes(traza.lote * 30)
    assert sum(len(l) for l in lotes) == len(traza.lote) * 30 and all(len(l) <= observabilidad.MAX_EVENTOS_POR_LOTE for l in lotes)


def test_generacion_sin_fin_queda_marcada(proyecto, config):
    carpeta = _tanda_con_dobles(proyecto, config, tope=1)
    registro.evento(proyecto, "agente_inicio", rol="escritor", capitulo=2, agent_id=None, intento=1)
    traza = observabilidad.construir_traza(proyecto, carpeta)
    abierta = next(e["body"] for e in traza.lote if e["type"] == "generation-create" and e["body"]["name"] == "escritor:cap_2")
    assert abierta["level"] == "WARNING" and "endTime" not in abierta
