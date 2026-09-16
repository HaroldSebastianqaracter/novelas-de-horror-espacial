"""Hooks H-01 a H-10 (§13.3, RF-08.2, EX-09): cada script con payload JSON por stdin, sin modelo."""

import json

import pytest

from harness.orchestrator import checkpoint, cursor as cur, loop
from harness.orchestrator.cursor import Cursor
from harness.rutas import Rutas
from harness.state import repository as repo
from tests.conftest import AgentesDobles, ejecutar_script_hook


def pre(payload, raiz):
    return ejecutar_script_hook("pre_tool_use", payload, raiz)


def post(payload, raiz):
    return ejecutar_script_hook("post_tool_use", payload, raiz)


def stop(payload, raiz):
    return ejecutar_script_hook("subagent_stop", payload, raiz)


def con_cerrados(proyecto, config, n):
    loop.ejecutar_tanda(config, proyecto, AgentesDobles(proyecto), capitulos_por_tanda=n)


# ---------- H-01 ----------

def test_h01_session_start_inyecta_status(proyecto, config):
    con_cerrados(proyecto, config, 1)
    r = ejecutar_script_hook("session_start", {"hook_event_name": "SessionStart", "source": "startup"}, proyecto)
    assert r.returncode == 0
    assert "ESTADO DE LA NOVELA" in r.stdout and "ultimo_capitulo_cerrado: 1" in r.stdout


# ---------- H-05 ----------

def test_h05_extractor_lee_solo_el_capitulo_actual(proyecto, config):
    con_cerrados(proyecto, config, 4)  # actual = 5
    base = {"hook_event_name": "PreToolUse", "tool_name": "Read", "agent_type": "extractor", "agent_id": "ag-1"}
    r = pre(dict(base, tool_input={"file_path": str(Rutas(proyecto).capitulo(3))}), proyecto)
    assert r.returncode == 2 and "H-05" in r.stderr and "cap_5.md" in r.stderr
    assert pre(dict(base, tool_input={"file_path": str(Rutas(proyecto).capitulo(5))}), proyecto).returncode == 0
    assert pre(dict(base, tool_input={"file_path": "04_estado/continuidad.json"}), proyecto).returncode == 2
    assert pre(dict(base, tool_input={"file_path": "04_estado/resumen_rodante.md"}), proyecto).returncode == 2
    assert pre(dict(base, tool_input={"file_path": "CLAUDE.md"}), proyecto).returncode == 0


def test_h05_respeta_capitulo_activo_en_reextraccion(proyecto, config):
    con_cerrados(proyecto, config, 3)
    checkpoint.fijar_capitulo_activo(proyecto, 2)
    base = {"tool_name": "Read", "agent_type": "extractor", "agent_id": "ag-2"}
    assert pre(dict(base, tool_input={"file_path": "05_manuscrito/cap_2.md"}), proyecto).returncode == 0
    assert pre(dict(base, tool_input={"file_path": "05_manuscrito/cap_4.md"}), proyecto).returncode == 2


# ---------- H-06 ----------

def test_h06_escritura_por_agente(proyecto, config):
    con_cerrados(proyecto, config, 2)  # actual = 3
    escritor = {"tool_name": "Write", "agent_type": "escritor", "agent_id": "e-1"}
    assert pre(dict(escritor, tool_input={"file_path": "05_manuscrito/cap_3.md", "content": "x"}), proyecto).returncode == 0
    r = pre(dict(escritor, tool_input={"file_path": "05_manuscrito/cap_2.md", "content": "x"}), proyecto)
    assert r.returncode == 2 and "H-06" in r.stderr
    assert pre(dict(escritor, tool_input={"file_path": "04_estado/continuidad.json", "content": "x"}), proyecto).returncode == 2
    extractor = {"tool_name": "Write", "agent_type": "extractor", "agent_id": "x-1"}
    assert pre(dict(extractor, tool_input={"file_path": "04_estado/deltas/delta_cap_3.json", "content": "x"}), proyecto).returncode == 2
    qa = {"tool_name": "Write", "agent_type": "qa", "agent_id": "q-1"}
    assert pre(dict(qa, tool_input={"file_path": "06_qa/reportes/qa_cap_3.json", "content": "x"}), proyecto).returncode == 0
    assert pre(dict(qa, tool_input={"file_path": "06_qa/recursos_usados.json", "content": "x"}), proyecto).returncode == 0
    r = pre(dict(qa, tool_input={"file_path": "05_manuscrito/cap_1.md", "content": "x"}), proyecto)
    assert r.returncode == 2 and "06_qa" in r.stderr
    # el orquestador (sin agent_id) escribe deltas y estado vía CLI; H-06 no lo alcanza
    assert pre({"tool_name": "Write", "tool_input": {"file_path": "04_estado/deltas/delta_cap_3.json", "content": "{}"}}, proyecto).returncode == 0


# ---------- H-08 ----------

def test_h08_agent_dentro_de_subagente(proyecto):
    r = pre({"tool_name": "Agent", "tool_input": {"prompt": "x", "subagent_type": "extractor"}, "agent_type": "escritor", "agent_id": "e-9"}, proyecto)
    assert r.returncode == 2 and "H-08" in r.stderr and "INV-09" in r.stderr
    assert pre({"tool_name": "Agent", "tool_input": {"prompt": "x", "subagent_type": "escritor"}}, proyecto).returncode == 0


# ---------- H-09 ----------

def test_h09_orquestador_no_lee_manuscrito(proyecto, config):
    con_cerrados(proyecto, config, 1)
    assert pre({"tool_name": "Read", "tool_input": {"file_path": "05_manuscrito/cap_1.md"}}, proyecto).returncode == 2
    assert pre({"tool_name": "Grep", "tool_input": {"pattern": "Kovacs", "path": "05_manuscrito"}}, proyecto).returncode == 2
    assert pre({"tool_name": "Glob", "tool_input": {"pattern": "05_manuscrito/*.md"}}, proyecto).returncode == 2
    assert pre({"tool_name": "Write", "tool_input": {"file_path": "05_manuscrito/cap_2.md", "content": "prosa"}}, proyecto).returncode == 2
    assert pre({"tool_name": "Read", "tool_input": {"file_path": "04_estado/prompts/escritor_cap_2.md"}}, proyecto).returncode == 0
    assert pre({"tool_name": "Grep", "tool_input": {"pattern": "def ", "path": "harness"}}, proyecto).returncode == 0
    # QA sí puede leer varios
    assert pre({"tool_name": "Read", "tool_input": {"file_path": "05_manuscrito/cap_1.md"}, "agent_type": "qa", "agent_id": "q"}, proyecto).returncode == 0


# ---------- H-04 ----------

def test_h04_novela_json_inmutable_con_cerrados(proyecto, config):
    payload = {"tool_name": "Edit", "tool_input": {"file_path": "config/novela.json", "old_string": "30", "new_string": "40"}}
    assert pre(payload, proyecto).returncode == 0  # sin capítulos cerrados se puede
    con_cerrados(proyecto, config, 1)
    r = pre(payload, proyecto)
    assert r.returncode == 2 and "H-04" in r.stderr and "INV-04" in r.stderr
    assert pre({"tool_name": "Write", "tool_input": {"file_path": "config/ejecucion.json", "content": "{}"}}, proyecto).returncode == 0


# ---------- H-02 / H-03 ----------

def test_h02_valida_esquema_tras_escritura(proyecto):
    rutas = Rutas(proyecto)
    payload = {"tool_name": "Write", "tool_input": {"file_path": str(rutas.personajes), "content": "..."}}
    assert post(payload, proyecto).returncode == 0
    rutas.personajes.write_text('{"Kovacs": {"estado_fisico": 3}}', encoding="utf-8")
    r = post(payload, proyecto)
    assert r.returncode == 2 and "H-02" in r.stderr and "FichaPersonajes" in r.stderr
    assert "EX-01" in checkpoint.leer_manifest(proyecto).ultimo_error
    rutas.delta(1).write_text('{"personajes": {}, "hechos_nuevos": [], "resumen_corto": "a"}', encoding="utf-8")
    assert post({"tool_name": "Write", "tool_input": {"file_path": str(rutas.delta(1))}}, proyecto).returncode == 0
    rutas.reporte_qa_json(3).write_text('{"cap_corte": 3, "hallazgos": [], "tiene_contradicciones": true}', encoding="utf-8")
    assert post({"tool_name": "Write", "tool_input": {"file_path": str(rutas.reporte_qa_json(3))}}, proyecto).returncode == 2


def test_h03_continuidad_que_pierde_un_hecho_falla(proyecto):
    rutas = Rutas(proyecto)
    payload = {"tool_name": "Write", "tool_input": {"file_path": str(rutas.continuidad), "content": "..."}}
    assert pre(payload, proyecto).returncode == 0  # guarda la copia previa
    assert rutas.continuidad_previa.exists()
    log = json.loads(rutas.continuidad.read_text(encoding="utf-8"))
    rutas.continuidad.write_text(json.dumps(log[:2]), encoding="utf-8")  # se pierde un hecho
    r = post(payload, proyecto)
    assert r.returncode == 2 and "H-03" in r.stderr and "superconjunto" in r.stderr
    assert not rutas.continuidad_previa.exists()
    # una escritura que solo agrega o marca superado pasa
    rutas.continuidad.write_text(json.dumps(log), encoding="utf-8")
    assert pre(payload, proyecto).returncode == 0
    nuevo = log + [{"sujeto": "mundo", "categoria": "mundo", "hecho": "nuevo", "cap_origen": 1}]
    nuevo[0]["superado_por"] = 0
    rutas.continuidad.write_text(json.dumps(nuevo), encoding="utf-8")
    assert post(payload, proyecto).returncode == 0
    # modificar el texto de un hecho también falla
    assert pre(payload, proyecto).returncode == 0
    nuevo[1]["hecho"] = "otro texto"
    rutas.continuidad.write_text(json.dumps(nuevo), encoding="utf-8")
    assert post(payload, proyecto).returncode == 2


# ---------- H-07 / H-10 ----------

def test_h07_longitud_del_escritor(proyecto, config):
    rutas = Rutas(proyecto)
    base = {"hook_event_name": "SubagentStop", "agent_type": "escritor", "agent_id": "e-7", "stop_hook_active": False}
    r = stop(base, proyecto)
    assert r.returncode == 2 and "no existe 05_manuscrito/cap_1.md" in r.stderr
    rutas.capitulo(1).write_text("corto " * 300, encoding="utf-8")
    r = stop(base, proyecto)
    assert r.returncode == 2 and "300 palabras" in r.stderr and "Reescribí" in r.stderr
    assert checkpoint.leer_manifest(proyecto).intentos_por_capitulo == {}
    r = stop(dict(base, stop_hook_active=True), proyecto)  # segundo fallo: se deja terminar y se anota
    assert r.returncode == 0
    assert checkpoint.leer_manifest(proyecto).intentos_por_capitulo == {"1": 2}
    rutas.capitulo(1).write_text("bien " * 1500, encoding="utf-8")
    assert stop(dict(base, agent_id="e-8"), proyecto).returncode == 0


def test_h10_registra_uso_desde_el_transcript(proyecto, tmp_path):
    rutas = Rutas(proyecto)
    cur.escribir(proyecto, Cursor(inicio=1, tope=3, max_llamadas=None))
    transcript = tmp_path / "agent-abc.jsonl"
    lineas = [
        {"type": "user", "message": {"role": "user", "content": "x"}},
        {"type": "assistant", "uuid": "u1", "message": {"id": "m1", "model": "modelo-de-prueba-a", "usage": {"input_tokens": 1000, "output_tokens": 200, "cache_read_input_tokens": 50}}},
        {"type": "assistant", "uuid": "u2", "message": {"id": "m1", "model": "modelo-de-prueba-a", "usage": {"input_tokens": 1000, "output_tokens": 200}}},  # mismo mensaje, no se duplica
        {"type": "assistant", "uuid": "u3", "message": {"id": "m2", "model": "modelo-de-prueba-a", "usage": {"input_tokens": 1500, "output_tokens": 800}}},
    ]
    transcript.write_text("\n".join(json.dumps(l) for l in lineas), encoding="utf-8")
    payload = {"hook_event_name": "SubagentStop", "agent_type": "extractor", "agent_id": "abc", "stop_hook_active": False,
               "agent_transcript_path": str(transcript), "stop_reason": "end_turn"}
    assert stop(payload, proyecto).returncode == 0
    registros = [json.loads(l) for l in rutas.uso.read_text(encoding="utf-8").splitlines()]
    assert len(registros) == 1
    r = registros[0]
    assert (r["rol"], r["capitulo"], r["modelo"], r["tokens_entrada"], r["tokens_salida"], r["turnos"]) == ("extractor", 1, "modelo-de-prueba-a", 2500, 1000, 2)
    assert cur.leer(proyecto).llamadas == 1  # RF-CFG-06: una llamada por invocación


def test_h10_no_registra_dos_veces_si_h07_bloqueo(proyecto):
    rutas = Rutas(proyecto)
    base = {"agent_type": "escritor", "agent_id": "e-x", "stop_hook_active": False}
    assert stop(base, proyecto).returncode == 2  # bloqueado por H-07: no registra
    assert not rutas.uso.exists()
    rutas.capitulo(1).write_text("bien " * 1500, encoding="utf-8")
    assert stop(dict(base, stop_hook_active=True), proyecto).returncode == 0
    assert len(rutas.uso.read_text(encoding="utf-8").splitlines()) == 1


# ---------- EX-09 ----------

def test_ex09_segundo_choque_detiene_la_tanda(proyecto, config):
    con_cerrados(proyecto, config, 1)
    cur.escribir(proyecto, Cursor(inicio=2, tope=3, max_llamadas=None))
    payload = {"tool_name": "Read", "tool_input": {"file_path": "05_manuscrito/cap_1.md"}, "agent_type": "extractor", "agent_id": "ag-ex09"}
    r1 = pre(payload, proyecto)
    assert r1.returncode == 2 and "EX-09" not in r1.stderr
    assert checkpoint.leer_manifest(proyecto).ultimo_error is None
    r2 = pre(payload, proyecto)
    assert r2.returncode == 2 and "EX-09" in r2.stderr
    assert "EX-09" in checkpoint.leer_manifest(proyecto).ultimo_error
    assert not Rutas(proyecto).cursor.exists()
    # otra invocación (otro agent_id) arranca de cero
    r3 = pre(dict(payload, agent_id="ag-nuevo"), proyecto)
    assert r3.returncode == 2 and "EX-09" not in r3.stderr
