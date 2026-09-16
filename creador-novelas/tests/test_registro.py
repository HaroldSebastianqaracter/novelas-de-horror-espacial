"""Registro de ejecución (RF-08.5, §5.1, §9): una tanda deja reconstruible lo que pasó, sin la conversación del orquestador."""

import json

import pytest

from app import cli, registro
from app.orchestrator import checkpoint, loop
from app.rutas import Rutas
from app.state import repository as repo
from tests.conftest import AgentesDobles, ejecutar_script_hook


def correr(capsys, *argv):
    codigo = cli.main(list(argv))
    salida = capsys.readouterr()
    return codigo, salida.out, salida.err


def eventos(raiz):
    return registro.leer_eventos(registro.ultima_tanda(raiz))


def _stop(raiz, rol, agent_id, n):
    """Simula el SubagentStop que Claude Code dispara al terminar un subagente (agente_fin + H-10)."""
    payload = {"hook_event_name": "SubagentStop", "agent_type": rol, "agent_id": agent_id, "stop_hook_active": False,
               "stop_reason": "end_turn"}
    r = ejecutar_script_hook("subagent_stop", payload, raiz)
    assert r.returncode == 0, r.stderr
    return r


# ---------- la tanda entera por los verbos del CLI, con dobles y con los scripts de hooks ----------

def test_tanda_de_tres_capitulos_deja_el_registro_completo_y_en_orden(proyecto, config, capsys):
    rutas = Rutas(proyecto)
    dobles = AgentesDobles(proyecto)
    assert registro.ultima_tanda(proyecto) is None
    codigo, out, _ = correr(capsys, "tanda", "iniciar")
    assert codigo == 0 and "seguir siguiente=1" in out
    tanda = registro.ultima_tanda(proyecto)
    assert tanda is not None and tanda.name.startswith("tanda_") and (tanda / "prompts").is_dir()
    n = 1
    while True:
        correr(capsys, "preparar-capitulo", str(n))
        # el escritor escribe y valida su capítulo (Bash acotado por H-11), y termina
        repo.guardar_capitulo(proyecto, n, dobles.generar_capitulo(rutas.prompt_escritor(n).read_text(encoding="utf-8")))
        bash = {"tool_name": "Bash", "tool_input": {"command": f".venv/Scripts/python.exe -m app validar-capitulo {n}"},
                "agent_type": "escritor", "agent_id": f"e-{n}"}
        assert ejecutar_script_hook("pre_tool_use", bash, proyecto).returncode == 0
        correr(capsys, "validar-capitulo", str(n))
        _stop(proyecto, "escritor", f"e-{n}", n)
        codigo, out, _ = correr(capsys, "registrar-escritor", str(n), f"cap_{n}.md · 1500 palabras · personajes: Kovacs · validado")
        assert "borrador_aceptado" in out
        # el extractor escribe y valida su delta, y termina
        rutas.delta(n).write_text(dobles.extraer(f"05_manuscrito/cap_{n}.md"), encoding="utf-8")
        correr(capsys, "validar-delta", str(n))
        _stop(proyecto, "extractor", f"x-{n}", n)
        codigo, out, _ = correr(capsys, "aplicar-delta", str(n), "--retorno", f"delta_cap_{n}.json · 2 hechos · 1 personajes · validado")
        assert "capitulo_cerrado" in out
        if "toca_qa=true" in out:
            correr(capsys, "preparar-qa", str(n))
            dobles.ejecutar_corte(rutas.prompt_qa(n).read_text(encoding="utf-8"))
            _stop(proyecto, "qa", f"q-{n}", n)
            codigo, out, _ = correr(capsys, "cerrar-qa", str(n), "--retorno", "tiene_contradicciones: false\ncontradicciones: 0 · repeticiones: 0\nreporte: x\nvalidado")
            assert "qa_sin_contradicciones" in out
        codigo, out, _ = correr(capsys, "tanda", "siguiente")
        if "tope_de_tanda" in out:
            break
        n += 1
    assert n == 3

    evs = eventos(proyecto)
    tipos = [e["tipo"] for e in evs]
    assert set(tipos) <= set(registro.TIPOS) and all("ts" in e for e in evs)
    # en orden: los verbos, sin huecos (cada verbo del CLI dejó su línea)
    verbos = [e["verbo"] for e in evs if e["tipo"] == "verbo"]
    assert verbos[0] == "tanda" and verbos[-1] == "tanda"
    assert verbos.count("preparar-capitulo") == 3 and verbos.count("registrar-escritor") == 3 and verbos.count("aplicar-delta") == 3
    assert verbos.count("validar-capitulo") == 3 and verbos.count("validar-delta") == 3 and "cerrar-qa" in verbos
    assert all(e["resultado"] == "ok" and isinstance(e["ms"], int) for e in evs if e["tipo"] == "verbo")
    # los pares agente_inicio / agente_fin de los siete subagentes (3 escritor + 3 extractor + 1 qa), en orden
    inicios = [(e["rol"], e["capitulo"]) for e in evs if e["tipo"] == "agente_inicio"]
    fines = [(e["rol"], e["capitulo"]) for e in evs if e["tipo"] == "agente_fin"]
    assert inicios == fines == [("escritor", 1), ("extractor", 1), ("escritor", 2), ("extractor", 2), ("escritor", 3), ("extractor", 3), ("qa", 3)]
    for inicio, fin in zip([i for i, e in enumerate(evs) if e["tipo"] == "agente_inicio"], [i for i, e in enumerate(evs) if e["tipo"] == "agente_fin"]):
        assert inicio < fin
    fin_escritor = next(e for e in evs if e["tipo"] == "agente_fin" and e["rol"] == "escritor")
    assert fin_escritor["agent_id"] == "e-1" and fin_escritor["intentos_de_validacion"] == 1  # H-11 dejó pasar el validador una vez
    # los hooks disparados, con id, agente, acción y decisión
    hooks = [e for e in evs if e["tipo"] == "hook"]
    assert {h["id"] for h in hooks} >= {"H-11", "H-10"} and all(h["decision"] in ("permitido", "bloqueado", "verificado", "falla") for h in hooks)
    assert any(h["id"] == "H-11" and h["agent_type"] == "escritor" and h["decision"] == "permitido" and "validar-capitulo 1" in h["accion"] for h in hooks)
    # las validaciones
    validaciones = [e for e in evs if e["tipo"] == "validacion"]
    assert len(validaciones) == 6 and all(v["valido"] for v in validaciones)
    # prompts/ y retornos/: un archivo por invocación
    assert len(list((tanda / "prompts").iterdir())) == 7
    assert len(list((tanda / "retornos").iterdir())) == 7
    assert sorted(p.name for p in (tanda / "prompts").iterdir())[0] == "001_escritor_cap_1.md"
    assert "Capítulo 1:" in (tanda / "prompts" / "001_escritor_cap_1.md").read_text(encoding="utf-8")
    assert "· validado" in (tanda / "retornos" / "001_escritor_cap_1.txt").read_text(encoding="utf-8")
    # uso.jsonl vive en la tanda, no en 04_estado/
    assert len(registro.leer_uso(tanda)) == 7 and not rutas.uso.exists()
    # la copia final del cursor dice cómo salió la tanda
    cursor = json.loads((tanda / "cursor.json").read_text(encoding="utf-8"))
    assert cursor["motivo_salida"] == "tope_de_tanda" and cursor["cerrados"] == 3 and cursor["llamadas"] == 7
    assert list((tanda / "descartados").iterdir()) == []
    # status lee el registro de la última tanda
    codigo, out, _ = correr(capsys, "status")
    assert tanda.name in out and "salida de la tanda: tope_de_tanda" in out and "eventos" in out


def test_ejecutar_tanda_con_dobles_tambien_registra(proyecto, config):
    loop.ejecutar_tanda(config, proyecto, AgentesDobles(proyecto), capitulos_por_tanda=3)
    tanda = registro.ultima_tanda(proyecto)
    evs = registro.leer_eventos(tanda)
    assert [e["rol"] for e in evs if e["tipo"] == "agente_inicio"] == ["escritor", "extractor"] * 3 + ["qa"]
    assert [e["rol"] for e in evs if e["tipo"] == "agente_fin"] == ["escritor", "extractor"] * 3 + ["qa"]
    assert len(list((tanda / "prompts").iterdir())) == 7 and len(list((tanda / "retornos").iterdir())) == 7
    assert json.loads((tanda / "cursor.json").read_text(encoding="utf-8"))["motivo_salida"] == "tope_de_tanda"


def test_tanda_interrumpida_deja_error_con_traza_y_el_descartado(proyecto, config, capsys):
    rutas = Rutas(proyecto)
    correr(capsys, "tanda", "iniciar")
    correr(capsys, "preparar-capitulo", "1")
    repo.guardar_capitulo(proyecto, 1, "Kovacs " * 1500)
    rutas.delta(1).write_text("{ esto no es json", encoding="utf-8")
    codigo, _, err = correr(capsys, "aplicar-delta", "1")
    assert codigo == 1 and "EstadoInvalidoError" in err
    evs = eventos(proyecto)
    error = [e for e in evs if e["tipo"] == "error"][-1]
    assert error["excepcion"] == "EstadoInvalidoError" and "no es JSON válido" in error["mensaje"] and "Traceback" in error["traza"]
    assert error["capitulo"] == 1 and error["verbo"] == "aplicar-delta"
    verbo = [e for e in evs if e["tipo"] == "verbo"][-1]
    assert verbo["verbo"] == "aplicar-delta" and verbo["resultado"] == "error EstadoInvalidoError"
    descartados = sorted(p.name for p in (registro.ultima_tanda(proyecto) / "descartados").iterdir())
    assert descartados == ["001_extractor_cap_1_delta_cap_1.json", "001_extractor_cap_1_delta_cap_1.json.error.txt"]
    assert "no es JSON válido" in (registro.ultima_tanda(proyecto) / "descartados" / descartados[1]).read_text(encoding="utf-8")
    codigo, out, _ = correr(capsys, "status")
    assert "último error registrado: EstadoInvalidoError" in out and "sin cursor final" in out


def test_ex10_del_escritor_manda_el_borrador_a_descartados(proyecto, config, capsys):
    rutas = Rutas(proyecto)
    correr(capsys, "tanda", "iniciar")
    correr(capsys, "preparar-capitulo", "1")
    repo.guardar_capitulo(proyecto, 1, "Kovacs " * 300)
    codigo, _, err = correr(capsys, "registrar-escritor", "1", "cap_1.md · NO VALIDADO · El borrador tiene 300 palabras")
    assert codigo == 1 and "AutovalidacionFallidaError" in err and "EX-10" in err
    tanda = registro.ultima_tanda(proyecto)
    nombres = sorted(p.name for p in (tanda / "descartados").iterdir())
    assert nombres == ["001_escritor_cap_1_cap_1.md", "001_escritor_cap_1_cap_1.md.error.txt"]
    assert "EX-10" in (tanda / "descartados" / nombres[1]).read_text(encoding="utf-8")
    assert "NO VALIDADO" in (tanda / "retornos" / "001_escritor_cap_1.txt").read_text(encoding="utf-8")  # el retorno se guarda igual
    assert rutas.capitulo(1).exists()  # descartar no borra: eso lo hace `descartar-borrador`
    correr(capsys, "descartar-borrador", "1")
    assert not rutas.capitulo(1).exists() and len(list((tanda / "descartados").iterdir())) == 4


def test_pausa_por_qa_y_ex09_copian_el_cursor_con_su_motivo(proyecto, config):
    loop.ejecutar_tanda(config, proyecto, AgentesDobles(proyecto, contradiccion_en={3}), capitulos_por_tanda=5)
    tanda = registro.ultima_tanda(proyecto)
    assert json.loads((tanda / "cursor.json").read_text(encoding="utf-8"))["motivo_salida"] == "pausado_por_qa"
    assert checkpoint.leer_manifest(proyecto).estado == "pausado_por_qa"


def test_h09_bloquea_al_orquestador_sobre_el_registro(proyecto, config):
    loop.ejecutar_tanda(config, proyecto, AgentesDobles(proyecto), capitulos_por_tanda=1)
    tanda = registro.ultima_tanda(proyecto).relative_to(proyecto).as_posix()
    r = ejecutar_script_hook("pre_tool_use", {"tool_name": "Read", "tool_input": {"file_path": f"{tanda}/eventos.jsonl"}}, proyecto)
    assert r.returncode == 2 and "H-09" in r.stderr and "07_registro" in r.stderr
    assert ejecutar_script_hook("pre_tool_use", {"tool_name": "Grep", "tool_input": {"pattern": "error", "path": "07_registro"}}, proyecto).returncode == 2
    assert ejecutar_script_hook("pre_tool_use", {"tool_name": "Write", "tool_input": {"file_path": f"{tanda}/eventos.jsonl", "content": "x"}}, proyecto).returncode == 2
    # y el bloqueo mismo quedó registrado como evento hook
    ultimo = eventos(proyecto)[-1]
    assert ultimo["tipo"] == "hook" and ultimo["id"] == "H-09" and ultimo["decision"] == "bloqueado"


def test_verbos_antes_de_la_primera_tanda_van_al_preludio(tmp_path, monkeypatch, capsys):
    from tests.conftest import construir_proyecto

    raiz = construir_proyecto(tmp_path / "nueva", con_estado=False)
    monkeypatch.setenv("HARNESS_RAIZ", str(raiz))
    correr(capsys, "status")
    evs = registro.leer_eventos(Rutas(raiz).registro / registro.PRELUDIO)
    assert evs and evs[-1]["tipo"] == "verbo" and evs[-1]["verbo"] == "status"
    assert registro.ultima_tanda(raiz) is None


def test_h10_suma_todos_los_mensajes_del_asistente(tmp_path):
    from app.hooks import leer_uso_transcript

    transcript = tmp_path / "t.jsonl"
    lineas = [
        {"type": "user", "message": {"role": "user", "content": "x"}},
        # un mensaje partido en tres líneas (una por bloque), con usage creciente: cuenta una vez, con el máximo
        {"type": "assistant", "uuid": "a", "message": {"id": "m1", "model": "modelo-a", "usage": {"input_tokens": 1000, "output_tokens": 5}}},
        {"type": "assistant", "uuid": "b", "message": {"id": "m1", "model": "modelo-a", "usage": {"input_tokens": 1000, "output_tokens": 900}}},
        {"type": "assistant", "uuid": "c", "message": {"id": "m1", "model": "modelo-a", "usage": {"input_tokens": 1000, "output_tokens": 2100, "cache_read_input_tokens": 40}}},
        # un segundo mensaje: se suma, no se reemplaza
        {"type": "assistant", "uuid": "d", "message": {"id": "m2", "model": "modelo-a", "usage": {"input_tokens": 50, "output_tokens": 30}}},
        # y un tercero sin id: cuenta por uuid
        {"type": "assistant", "uuid": "e", "message": {"model": "modelo-a", "usage": {"input_tokens": 10, "output_tokens": 20}}},
    ]
    transcript.write_text("\n".join(json.dumps(l) for l in lineas), encoding="utf-8")
    uso = leer_uso_transcript(transcript)
    assert (uso["turnos"], uso["tokens_entrada"], uso["tokens_salida"], uso["tokens_cache_lectura"], uso["modelo"]) == (3, 1060, 2150, 40, "modelo-a")
