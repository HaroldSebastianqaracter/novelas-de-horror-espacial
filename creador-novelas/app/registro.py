"""Registro de ejecución: `07_registro/` (RF-08.5; spec técnica §5.1).

El manifiesto dice dónde está la novela; el registro dice qué pasó para llegar ahí. Una carpeta por tanda:

    07_registro/tanda_<ts>/
    ├── eventos.jsonl     # append-only, una línea por evento, en orden
    ├── cursor.json       # copia final del cursor: tope, cerrados, motivo de salida
    ├── prompts/          # el contexto exacto entregado a cada agente en cada invocación
    ├── retornos/         # el mensaje final textual de cada subagente
    ├── descartados/      # borradores y deltas rechazados, con el error que los rechazó
    └── uso.jsonl         # consumo por invocación (H-10)

Lo escriben los scripts y los hooks, nunca el modelo. No es estado de la novela: borrarlo no cambia nada de
`04_estado/`. Los verbos que corren antes de la primera tanda (fases 0-4) registran en `07_registro/preludio/`.
"""

from __future__ import annotations

import json
import re
import shutil
import traceback
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from app.rutas import Rutas

PRELUDIO = "preludio"
_PATRON_TANDA = re.compile(r"^tanda_\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}")
TIPOS = ("verbo", "agente_inicio", "agente_fin", "hook", "validacion", "error")


def ahora() -> str:
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


def _puntero(raiz: Path) -> Path:
    return Rutas(raiz).tanda / "registro_actual"


def carpetas_tanda(raiz: Path) -> list[Path]:
    base = Rutas(raiz).registro
    if not base.exists():
        return []
    return sorted(p for p in base.iterdir() if p.is_dir() and _PATRON_TANDA.match(p.name))


def iniciar_tanda(raiz: Path, metadatos: dict[str, Any] | None = None) -> Path:
    """`tanda iniciar`: crea la carpeta de la tanda y deja el puntero para que hooks y verbos la encuentren.

    `metadatos` (prompts_hash y dimensionamiento con los que arranca ESTA tanda) queda en `tanda.json`: es lo que
    el exportador pone en la traza (§16.2), porque el manifiesto solo conserva el hash de la última tanda.
    """
    base = Rutas(raiz).registro
    nombre = "tanda_" + datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    carpeta = base / nombre
    sufijo = 1
    while carpeta.exists():  # dos tandas en el mismo segundo: no se pisa la anterior
        sufijo += 1
        carpeta = base / f"{nombre}_{sufijo}"
    for sub in ("prompts", "retornos", "descartados"):
        (carpeta / sub).mkdir(parents=True, exist_ok=True)
    if metadatos is not None:
        datos = {"tanda": carpeta.name, "ts_inicio": ahora(), **metadatos}
        (carpeta / "tanda.json").write_text(json.dumps(datos, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    _puntero(raiz).parent.mkdir(parents=True, exist_ok=True)
    _puntero(raiz).write_text(carpeta.relative_to(raiz).as_posix(), encoding="utf-8")
    return carpeta


def dir_actual(raiz: Path) -> Path:
    """La carpeta donde se registra ahora: la tanda en curso, si no la última tanda, si no el preludio."""
    rutas = Rutas(raiz)
    puntero = _puntero(raiz)
    if puntero.exists():
        candidata = raiz / puntero.read_text(encoding="utf-8").strip()
        if candidata.is_dir():
            return candidata
    tandas = carpetas_tanda(raiz)
    if tandas:
        return tandas[-1]
    return rutas.registro / PRELUDIO


def ultima_tanda(raiz: Path) -> Path | None:
    """La última tanda registrada (por nombre, que es su marca de tiempo), o None si nunca hubo una."""
    tandas = carpetas_tanda(raiz)
    return tandas[-1] if tandas else None


def _asegurar(carpeta: Path) -> None:
    for sub in ("prompts", "retornos", "descartados"):
        (carpeta / sub).mkdir(parents=True, exist_ok=True)


# ---------- eventos ----------

def evento(raiz: Path, tipo: str, **campos: Any) -> dict:
    """Una línea en eventos.jsonl. Siempre `ts` y `tipo`; `capitulo` cuando aplique (§5.1)."""
    assert tipo in TIPOS, tipo
    carpeta = dir_actual(raiz)
    _asegurar(carpeta)
    registro = {"ts": ahora(), "tipo": tipo}
    registro.update({k: v for k, v in campos.items() if v is not None or k == "capitulo"})
    with (carpeta / "eventos.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(registro, ensure_ascii=False, default=str) + "\n")
    return registro


def evento_error(raiz: Path, excepcion: BaseException, **campos: Any) -> dict:
    """Quien detiene la tanda deja `excepcion`, `mensaje` y `traza`."""
    return evento(raiz, "error", excepcion=type(excepcion).__name__, mensaje=str(excepcion),
                  traza="".join(traceback.format_exception(type(excepcion), excepcion, excepcion.__traceback__)), **campos)


def leer_eventos(carpeta: Path) -> list[dict]:
    path = carpeta / "eventos.jsonl"
    if not path.exists():
        return []
    eventos = []
    for linea in path.read_text(encoding="utf-8").splitlines():
        try:
            eventos.append(json.loads(linea))
        except json.JSONDecodeError:
            eventos.append({"ts": "?", "tipo": "?", "linea_corrupta": linea})
    return eventos


# ---------- copias: prompts, retornos, descartados, cursor, uso ----------

def _siguiente_nombre(carpeta: Path, base: str, extension: str) -> Path:
    n = len(list(carpeta.iterdir())) + 1 if carpeta.exists() else 1
    return carpeta / f"{n:03d}_{base}{extension}"


def guardar_prompt(raiz: Path, rol: str, n: int, texto: str) -> Path:
    """La copia del contexto exacto entregado al agente; el archivo de trabajo de 04_estado/prompts/ se pisa después."""
    carpeta = dir_actual(raiz)
    _asegurar(carpeta)
    destino = _siguiente_nombre(carpeta / "prompts", f"{rol}_cap_{n}", ".md")
    destino.write_text(texto, encoding="utf-8")
    return destino


def guardar_retorno(raiz: Path, rol: str, n: int | None, texto: str) -> Path:
    """El mensaje final textual del subagente, tal como lo recibió el orquestador."""
    carpeta = dir_actual(raiz)
    _asegurar(carpeta)
    destino = _siguiente_nombre(carpeta / "retornos", f"{rol}_cap_{n if n is not None else 'x'}", ".txt")
    destino.write_text(texto if texto.endswith("\n") else texto + "\n", encoding="utf-8")
    return destino


def descartar(raiz: Path, rol: str, n: int, origen: Path, error: str) -> Path | None:
    """Copia un borrador o delta rechazado junto con el error que lo rechazó (EX-07, EX-08, EX-10, EX-01)."""
    if not origen.exists():
        return None
    carpeta = dir_actual(raiz)
    _asegurar(carpeta)
    destino = _siguiente_nombre(carpeta / "descartados", f"{rol}_cap_{n}_{origen.name}", "")
    shutil.copyfile(origen, destino)
    destino.with_name(destino.name + ".error.txt").write_text(error + "\n", encoding="utf-8")
    return destino


def copiar_cursor_final(raiz: Path, cursor: Any, motivo: str) -> None:
    """Copia final del cursor al terminar la tanda (por tope, pausa, fin de novela o error)."""
    carpeta = dir_actual(raiz)
    _asegurar(carpeta)
    datos = asdict(cursor) if hasattr(cursor, "__dataclass_fields__") else dict(cursor)
    datos["motivo_salida"] = motivo
    datos["ts_fin"] = ahora()
    (carpeta / "cursor.json").write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def ruta_uso(raiz: Path) -> Path:
    """H-10 escribe aquí (§5.1): `uso.jsonl` es evidencia de la ejecución, no memoria de la obra."""
    carpeta = dir_actual(raiz)
    _asegurar(carpeta)
    return carpeta / "uso.jsonl"


def leer_uso(carpeta: Path) -> list[dict]:
    path = carpeta / "uso.jsonl"
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def intentos_de_validacion(raiz: Path, agent_id: str | None) -> int:
    """Cuántas veces H-11 dejó pasar el validador a esta invocación (RF-08.4)."""
    if not agent_id:
        return 0
    return sum(1 for e in leer_eventos(dir_actual(raiz))
               if e.get("tipo") == "hook" and e.get("id") == "H-11" and e.get("agent_id") == agent_id
               and e.get("decision") == "permitido")


# ---------- status ----------

def _resumen_evento(e: dict) -> str:
    tipo = e.get("tipo")
    if tipo == "verbo":
        return f"verbo {e.get('verbo')} -> {e.get('resultado')} ({e.get('ms')} ms)"
    if tipo in ("agente_inicio", "agente_fin"):
        return f"{tipo} {e.get('rol')} cap. {e.get('capitulo')}"
    if tipo == "hook":
        return f"hook {e.get('id')} {e.get('decision')} ({e.get('agent_type') or 'orquestador'}: {e.get('accion')})"
    if tipo == "validacion":
        return f"validacion {e.get('rol')} {e.get('artefacto')} -> {'valido' if e.get('valido') else 'invalido'}"
    if tipo == "error":
        return f"error {e.get('excepcion')}: {str(e.get('mensaje'))[:120]}"
    return str(e)


def texto_status(raiz: Path, ultimos: int = 5) -> str:
    """Lo que `status` añade bajo el manifiesto: la última tanda, sus últimos eventos y cualquier error sin cerrar."""
    carpeta = ultima_tanda(raiz)
    if carpeta is None:
        return "- registro: sin tandas registradas en 07_registro/"
    eventos = leer_eventos(carpeta)
    lineas = [f"- registro: {carpeta.relative_to(raiz).as_posix()} ({len(eventos)} eventos, {len(leer_uso(carpeta))} invocaciones en uso.jsonl)"]
    cursor = carpeta / "cursor.json"
    if cursor.exists():
        try:
            datos = json.loads(cursor.read_text(encoding="utf-8"))
            lineas.append(f"- salida de la tanda: {datos.get('motivo_salida')} (cerrados {datos.get('cerrados')}, llamadas {datos.get('llamadas')})")
        except json.JSONDecodeError:
            pass
    else:
        lineas.append("- salida de la tanda: sin cursor final; la tanda sigue en curso o murió a mitad")
    for e in eventos[-ultimos:]:
        lineas.append(f"  · {e.get('ts', '?')[11:23]} {_resumen_evento(e)}")
    errores = [e for e in eventos if e.get("tipo") == "error"]
    if errores:
        ultimo = errores[-1]
        lineas.append(f"- último error registrado: {ultimo.get('excepcion')}: {ultimo.get('mensaje')}")
    return "\n".join(lineas)
