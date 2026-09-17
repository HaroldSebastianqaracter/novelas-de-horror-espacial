"""H-11, el hook crítico (§9, §13.3, RF-08.4): `Bash` en los tres agentes sirve solo para su validador.

Cada caso ejecuta scripts/hooks/pre_tool_use.py con un payload simulado. Todos los casos de bloqueo que lista
§9 deben salir con código 2; el validador exacto del rol con el capítulo correcto sale con 0.
"""

import pytest

from app.config import comando_validador
from app.orchestrator import checkpoint, cursor as cur, loop
from app.orchestrator.cursor import Cursor
from tests.conftest import AgentesDobles, ejecutar_script_hook

CANONICO = ".venv/Scripts/python.exe -m app"


def bash(comando, agent_type, raiz, agent_id="ag-h11"):
    payload = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": comando, "description": "x"},
               "agent_type": agent_type, "agent_id": agent_id}
    return ejecutar_script_hook("pre_tool_use", payload, raiz)


@pytest.fixture
def con_cinco(proyecto, config):
    """Cuatro capítulos cerrados: el capítulo de la invocación del escritor y el extractor es el 5; el de QA es el 4."""
    loop.ejecutar_tanda(config, proyecto, AgentesDobles(proyecto), capitulos_por_tanda=4)
    return proyecto


# ---------- casos de bloqueo de §9: todos con código 2 ----------

@pytest.mark.parametrize("comando", [
    "cat 05_manuscrito/cap_1.md",
    "python -m app validar-capitulo 3",  # otro N y, además, `python` a secas
    f"{CANONICO} validar-capitulo 3",  # el capítulo de la invocación es el 5
    f"{CANONICO} validar-capitulo 5; cat cap_1.md",
    f"{CANONICO} validar-capitulo 5 && ls",
    "echo $(cat cap_1.md)",
    f"{CANONICO} validar-delta 5",  # el validador de otro rol
    f"{CANONICO} status",
    "python -m app validar-capitulo 5",  # forma no canónica: `python` a secas no se acepta (§13.3)
    f"{CANONICO} validar-capitulo 5 | tee salida.txt",
    f"{CANONICO} validar-capitulo 5 > salida.txt",
    f"`{CANONICO} validar-capitulo 5`",
    f"{CANONICO} validar-capitulo 5 --raiz ..",
    f"{CANONICO}  validar-capitulo 5",  # doble espacio: no es el comando exacto
    "",
])
def test_h11_bloquea_todo_lo_que_no_es_el_validador_del_escritor(con_cinco, comando):
    r = bash(comando, "escritor", con_cinco, agent_id=f"e-{abs(hash(comando))}")
    assert r.returncode == 2, (comando, r.stdout, r.stderr)
    assert "H-11" in r.stderr and "validar-capitulo 5" in r.stderr


@pytest.mark.parametrize("comando", [
    f"{CANONICO} validar-capitulo 5",  # el validador de otro rol
    f"{CANONICO} validar-delta 4",
    "cat 05_manuscrito/cap_5.md",
    f"{CANONICO} validar-delta 5; {CANONICO} validar-delta 5",
])
def test_h11_bloquea_en_el_extractor(con_cinco, comando):
    r = bash(comando, "extractor", con_cinco, agent_id=f"x-{abs(hash(comando))}")
    assert r.returncode == 2 and "H-11" in r.stderr and "validar-delta 5" in r.stderr


@pytest.mark.parametrize("comando", [
    f"{CANONICO} validar-reporte 5",  # el corte evalúa el último cerrado (4), no el siguiente
    f"{CANONICO} validar-capitulo 4",
    "rm -rf 06_qa",
    f"{CANONICO} validar-reporte 4 && cat 05_manuscrito/cap_1.md",
])
def test_h11_bloquea_en_qa(con_cinco, comando):
    r = bash(comando, "qa", con_cinco, agent_id=f"q-{abs(hash(comando))}")
    assert r.returncode == 2 and "H-11" in r.stderr and "validar-reporte 4" in r.stderr


# ---------- lo único que pasa: el validador exacto del rol con el capítulo de la invocación ----------

def test_h11_deja_pasar_exactamente_el_validador_de_cada_rol(con_cinco):
    assert bash(f"{CANONICO} validar-capitulo 5", "escritor", con_cinco).returncode == 0
    assert bash(f"{CANONICO} validar-delta 5", "extractor", con_cinco).returncode == 0
    assert bash(f"{CANONICO} validar-reporte 4", "qa", con_cinco).returncode == 0
    assert comando_validador("escritor", 5) == f"{CANONICO} validar-capitulo 5"


def test_h11_tolera_solo_espacios_alrededor(con_cinco):
    assert bash(f"  {CANONICO} validar-capitulo 5\n", "escritor", con_cinco).returncode == 0


def test_h11_respeta_capitulo_activo_en_reextraccion(con_cinco):
    checkpoint.fijar_capitulo_activo(con_cinco, 2)  # /resolver-qa: H-05 y H-11 resuelven N con la misma función
    assert bash(f"{CANONICO} validar-delta 2", "extractor", con_cinco).returncode == 0
    assert bash(f"{CANONICO} validar-delta 5", "extractor", con_cinco, agent_id="x-reex").returncode == 2


def test_h11_no_alcanza_al_orquestador_ni_a_otros_subagentes(con_cinco):
    orquestador = {"tool_name": "Bash", "tool_input": {"command": f"{CANONICO} status"}}
    assert ejecutar_script_hook("pre_tool_use", orquestador, con_cinco).returncode == 0
    otro = {"tool_name": "Bash", "tool_input": {"command": "ls"}, "agent_type": "Explore", "agent_id": "ex-1"}
    assert ejecutar_script_hook("pre_tool_use", otro, con_cinco).returncode == 0


def test_h11_segundo_choque_es_ex09(con_cinco):
    cur.escribir(con_cinco, Cursor(inicio=5, tope=3, max_llamadas=None))
    r1 = bash("cat 05_manuscrito/cap_1.md", "escritor", con_cinco, agent_id="e-ex09")
    assert r1.returncode == 2 and "EX-09" not in r1.stderr
    r2 = bash("ls", "escritor", con_cinco, agent_id="e-ex09")
    assert r2.returncode == 2 and "EX-09" in r2.stderr
    assert "EX-09" in checkpoint.leer_manifest(con_cinco).ultimo_error


def test_h11_declarado_en_settings_del_proyecto():
    """§13.6: si H-11 no está declarado, hay shell libre. El settings.json real del repo debe alcanzar `Bash`."""
    import json

    from tests.conftest import RAIZ_REAL

    settings = json.loads((RAIZ_REAL / ".claude" / "settings.json").read_text(encoding="utf-8"))
    matchers = [e.get("matcher", "") for e in settings["hooks"]["PreToolUse"]]
    assert any("Bash" in m.split("|") for m in matchers)


def test_status_avisa_si_h11_no_esta_declarado(proyecto, capsys):
    import json

    from app import cli

    settings_dir = proyecto / ".claude"
    settings_dir.mkdir(exist_ok=True)
    (settings_dir / "settings.json").write_text(json.dumps({"hooks": {"PreToolUse": [{"matcher": "Write|Read", "hooks": [{"type": "command", "command": "x"}]}]}}), encoding="utf-8")
    assert cli.main(["status"]) == 0
    assert "H-11 no está declarado" in capsys.readouterr().out
    (settings_dir / "settings.json").write_text(json.dumps({"hooks": {"PreToolUse": [{"matcher": "Write|Bash", "hooks": [{"type": "command", "command": "x"}]}]}}), encoding="utf-8")
    assert cli.main(["status"]) == 0
    assert "H-11 no está declarado" not in capsys.readouterr().out


def terminal(comando, agent_type, raiz, herramienta="PowerShell", agent_id="ag-h11-ps"):
    payload = {"hook_event_name": "PreToolUse", "tool_name": herramienta,
               "tool_input": {"command": comando, "description": "x"},
               "agent_type": agent_type, "agent_id": agent_id}
    return ejecutar_script_hook("pre_tool_use", payload, raiz)


def test_h11_vigila_tambien_powershell(con_cinco):
    """La terminal no se llama igual en todas las plataformas: en Windows es `PowerShell`.

    Los agentes declaraban `tools: ... Bash` y en Windows se quedaban sin terminal, asi que no
    podian autovalidarse y la tanda moria con EX-10. Darles `PowerShell` sin que H-11 la mirara
    habria sido peor que el fallo: un agente con una terminal que el hook no vigila puede ejecutar
    cualquier cosa, y H-11 existe para que solo pueda ejecutar su validador.
    """
    assert terminal("python -c 'print(1)'", "escritor", con_cinco).returncode != 0
    assert terminal(f"{CANONICO} validar-capitulo 5; rm -rf .", "escritor", con_cinco).returncode != 0
    assert terminal(f"{CANONICO} validar-reporte 4", "escritor", con_cinco).returncode != 0  # verbo de otro rol
    assert terminal(f"{CANONICO} validar-capitulo 5", "escritor", con_cinco).returncode == 0


def test_h11_acepta_el_validador_con_barras_de_windows(con_cinco):
    r"""El agente escribe la ruta con `` y la forma canonica lleva `/`.

    El separador no cambia lo que hace el comando, y bloquear por eso dejaba al escritor sin poder
    ejecutar el unico comando que tiene permitido.
    """
    con_barras = CANONICO.replace("/", "\\")
    assert con_barras != CANONICO
    assert terminal(f"{con_barras} validar-capitulo 5", "escritor", con_cinco).returncode == 0
    assert bash(f"{con_barras} validar-capitulo 5", "escritor", con_cinco).returncode == 0
