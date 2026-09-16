"""Arranque compartido por los scripts de hooks: raíz del proyecto, import de harness/ y lectura del payload."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def preparar() -> tuple[Path, dict]:
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8")
        except Exception:
            pass
    raiz_defecto = Path(__file__).resolve().parents[2]
    raiz = Path(os.environ.get("HARNESS_RAIZ") or os.environ.get("CLAUDE_PROJECT_DIR") or raiz_defecto).resolve()
    sys.path.insert(0, str(raiz_defecto))  # el paquete harness/ vive junto a scripts/, no necesariamente en la raíz de datos
    crudo = sys.stdin.read()
    try:
        payload = json.loads(crudo) if crudo.strip() else {}
    except json.JSONDecodeError:
        payload = {}
    return raiz, payload


def salir(decision) -> None:
    if decision.bloquear:
        print(decision.motivo, file=sys.stderr)
        sys.exit(2)
    sys.exit(0)
