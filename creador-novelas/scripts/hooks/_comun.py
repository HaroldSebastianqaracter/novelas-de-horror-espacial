"""Arranque compartido por los scripts de hooks: raíz del proyecto, import de app/ y lectura del payload.

`salir` traduce la Decision a código de salida (2 = bloquear/fallar, 0 = permitir) y deja el evento `hook` en el
registro de ejecución (RF-08.5, §5.1): id, agente, acción, decisión y motivo.
"""

from __future__ import annotations

import json
import os
import re
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
    sys.path.insert(0, str(raiz_defecto))  # el paquete app/ vive junto a scripts/, no necesariamente en la raíz de datos
    crudo = sys.stdin.read()
    try:
        payload = json.loads(crudo) if crudo.strip() else {}
    except json.JSONDecodeError:
        payload = {}
    return raiz, payload


def _accion(payload: dict) -> str:
    tool = payload.get("tool_name") or payload.get("hook_event_name") or "?"
    entrada = payload.get("tool_input") or {}
    detalle = entrada.get("file_path") or entrada.get("path") or entrada.get("command") or entrada.get("pattern") or ""
    return f"{tool} {str(detalle)[:160]}".strip()


def _id_hook(decision, evento: str) -> str:
    if getattr(decision, "hook", ""):
        return decision.hook
    for nota in getattr(decision, "notas", None) or []:
        m = re.match(r"(H-\d\d)", nota)
        if m:
            return m.group(1)
    return {"PreToolUse": "pre_tool_use", "PostToolUse": "post_tool_use", "SubagentStop": "subagent_stop"}.get(evento, evento)


def registrar(decision, payload: dict, raiz: Path, evento: str) -> None:
    """Evento `hook` (§5.1): decision es permitido/bloqueado en PreToolUse, verificado/falla en PostToolUse."""
    try:
        from app import registro

        if evento == "PostToolUse":
            resultado = "falla" if decision.bloquear else "verificado"
        else:
            resultado = "bloqueado" if decision.bloquear else "permitido"
        registro.evento(
            raiz, "hook", id=_id_hook(decision, evento), evento=evento, agent_type=payload.get("agent_type"),
            agent_id=payload.get("agent_id"), accion=_accion(payload), decision=resultado,
            motivo=decision.motivo or None, detiene_tanda=True if getattr(decision, "detiene_tanda", False) else None,
            notas=getattr(decision, "notas", None) or None,
        )
    except Exception as e:  # el registro nunca debe impedir que el hook decida
        print(f"[registro] no se pudo anotar el evento hook: {e}", file=sys.stderr)


def salir(decision, payload: dict | None = None, raiz: Path | None = None, evento: str = "") -> None:
    if payload is not None and raiz is not None:
        registrar(decision, payload, raiz, evento)
    if decision.bloquear:
        print(decision.motivo, file=sys.stderr)
        sys.exit(2)
    sys.exit(0)
