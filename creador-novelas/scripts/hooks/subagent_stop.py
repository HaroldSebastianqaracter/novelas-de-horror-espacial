"""H-07 (EX-07, solo escritor) y H-10 (registro de uso, los tres roles)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _comun import preparar, salir  # noqa: E402

raiz, payload = preparar()
from harness import hooks  # noqa: E402

salir(hooks.decidir_subagent_stop(payload, raiz))
