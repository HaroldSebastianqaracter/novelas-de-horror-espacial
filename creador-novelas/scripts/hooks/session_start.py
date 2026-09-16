"""H-01 (RF-08.3): al abrir la sesión, la salida de `status` entra al contexto."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _comun import preparar  # noqa: E402

raiz, payload = preparar()
from harness import hooks  # noqa: E402

print(hooks.contexto_session_start(raiz))
sys.exit(0)
