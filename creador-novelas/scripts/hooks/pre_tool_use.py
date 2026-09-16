"""H-04, H-05, H-06, H-08, H-09 y la copia previa de continuidad.json para H-03. Bloquea con código 2."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _comun import preparar, salir  # noqa: E402

raiz, payload = preparar()
from app import hooks  # noqa: E402

salir(hooks.decidir_pre_tool_use(payload, raiz))
