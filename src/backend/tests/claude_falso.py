"""Un ejecutable `claude` de mentira para probar PuertoTerminal sin gastar dinero.

Escribe un script que ignora sus argumentos, lee la entrada por stdin como haria el CLI y
devuelve el sobre JSON que se le pida. En Windows se envuelve en un `.cmd`, que es lo que
`subprocess` sabe lanzar sin shell.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any

RAIZ_REPO = Path(__file__).resolve().parents[3]
SKILLS = RAIZ_REPO / ".claude" / "skills"


def sobre(salida: dict[str, Any], **metadatos: Any) -> dict[str, Any]:
    """El JSON que devuelve `claude -p --output-format json` en una llamada correcta."""
    base: dict[str, Any] = {
        "type": "result", "subtype": "success", "is_error": False,
        "result": json.dumps(salida), "structured_output": salida,
        # Una llamada real con --json-schema y sin herramientas da dos turnos: la salida
        # estructurada consume uno (verificado contra el CLI 2.1.274).
        "num_turns": 2, "permission_denials": [], "total_cost_usd": 0.0,
        "usage": {"input_tokens": 10, "output_tokens": 10},
    }
    base.update(metadatos)
    return base


def ejecutable(respuesta: dict[str, Any]) -> Path:
    carpeta = Path(tempfile.mkdtemp(prefix="claude-falso-"))
    salida = carpeta / "respuesta.json"
    salida.write_text(json.dumps(respuesta, ensure_ascii=False), encoding="utf-8")
    script = carpeta / "claude_falso.py"
    argv = carpeta / "argv.json"
    script.write_text(
        "import json, sys\n"
        "sys.stdin.read()\n"
        f"open(r'{argv}', 'w', encoding='utf-8').write(json.dumps(sys.argv[1:]))\n"
        f"sys.stdout.write(open(r'{salida}', encoding='utf-8').read())\n",
        encoding="utf-8",
    )
    if sys.platform.startswith("win"):
        envoltorio = carpeta / "claude.cmd"
        envoltorio.write_text(f'@"{sys.executable}" "{script}" %*\r\n', encoding="utf-8")
    else:
        envoltorio = carpeta / "claude"
        envoltorio.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n',
                              encoding="utf-8")
        envoltorio.chmod(0o755)
    return envoltorio


def argumentos(ejecutable_falso: Path) -> list[str]:
    """Los argumentos con que el puerto lanzo el ejecutable falso la ultima vez."""
    return json.loads((ejecutable_falso.parent / "argv.json").read_text(encoding="utf-8"))
