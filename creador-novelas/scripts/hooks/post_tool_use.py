"""H-02 y H-03: verificadores tras un Write. Si fallan, salen con 2 y la tanda se detiene como EX-01."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _comun import preparar, salir  # noqa: E402

raiz, payload = preparar()
from app import hooks  # noqa: E402

salir(hooks.verificar_post_tool_use(payload, raiz))
