"""Consola de puente: estado en vivo, registro y lanzamiento de fases (§15.3, §15.4; RF-UI-03, RF-UI-04).

Extiende el frontend de `ui.py`, que hasta ahora solo recogía requisitos. Tres reglas que no son
negociables y que explican casi todas las decisiones de este módulo:

- **No orquesta.** Para lanzar una fase arranca una sesión de Claude Code en modo no interactivo. El
  orquestador sigue siendo Claude Code, con sus hooks, sus subagentes y su `CLAUDE.md`: pulsar un botón
  equivale exactamente a que el usuario teclee esa orden (RF-UI-03). Nunca `--bare`, que saltaría justo
  eso.
- **No lee el manuscrito.** INV-08 vale también para esta pantalla: no sirve capítulos, no los resume y
  no cuenta sus palabras mientras se escriben. El progreso se lee del estado en disco, no de la prosa.
- **No resuelve el informe de QA.** Lo enseña y se detiene ahí (RF-UI-04, §15.6): cerrarlo exige declarar
  qué capítulos se corrigieron, y esa declaración solo tiene sentido después de editarlos a mano.

Solo biblioteca estándar, como el resto de `ui.py`.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from app.config import CAMPOS_EJECUCION, CAMPOS_NOVELA
from app.orchestrator import checkpoint
from app.rutas import Rutas

# Las seis fases son skills del orquestador; `ensamblar` es un verbo determinista y no necesita modelo.
SKILLS: dict[str, str] = {
    "destilar-estilo": "/destilar-estilo",
    "generar-premisa": "/generar-premisa",
    "generar-sinopsis": "/generar-sinopsis",
    "generar-escaleta": "/generar-escaleta",
    "inicializar-estado": "/inicializar-estado",
    "escribir-tanda": "/escribir-tanda",
}
VERBOS: dict[str, list[str]] = {"ensamblar": ["ensamblar"]}

# Una tanda lanzada desde la terminal no deja proceso hijo aquí; se la reconoce porque su registro
# sigue creciendo. Por debajo de este margen se considera viva.
MARGEN_VIVA_S = 180

_EN_CURSO: dict[str, Any] = {}  # el proceso que lanzó esta pantalla; una ejecución a la vez (§15.3)


# --------------------------------------------------------------------------- utilidades de lectura

def _json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _lineas_jsonl(path: Path, limite: int | None = None) -> list[dict[str, Any]]:
    try:
        crudas = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    if limite is not None:
        crudas = crudas[-limite:]
    salida = []
    for linea in crudas:
        linea = linea.strip()
        if not linea:
            continue
        try:
            salida.append(json.loads(linea))
        except ValueError:
            continue  # una línea a medio escribir mientras corre la tanda no es un error
    return salida


def _segundos_desde(iso: str | None) -> float:
    if not iso:
        return float("inf")
    try:
        return max(0.0, datetime.now(datetime.fromisoformat(iso).tzinfo).timestamp()
                   - datetime.fromisoformat(iso).timestamp())
    except ValueError:
        return float("inf")


def tanda_actual(raiz: Path) -> Path | None:
    """El directorio de §5.1 de la tanda en curso o de la última. `registro_actual` lo fija el harness."""
    rutas = Rutas(raiz)
    puntero = raiz / ".tanda" / "registro_actual"
    if puntero.exists():
        try:
            candidato = raiz / puntero.read_text(encoding="utf-8").strip()
            if candidato.is_dir():
                return candidato
        except OSError:
            pass
    if not rutas.registro.is_dir():
        return None
    tandas = sorted((p for p in rutas.registro.iterdir() if p.is_dir() and p.name.startswith("tanda_")),
                    key=lambda p: p.name)
    return tandas[-1] if tandas else None


# ------------------------------------------------------------------------------- proceso lanzado

def ejecutable_claude() -> str | None:
    """`claude` no siempre está en el PATH del proceso que sirve la pantalla."""
    hallado = shutil.which("claude")
    if hallado:
        return hallado
    candidatos = [
        Path.home() / ".local" / "bin" / "claude.exe",
        Path.home() / ".local" / "bin" / "claude",
        Path(os.environ.get("APPDATA", "")) / "npm" / "claude.cmd",
    ]
    for c in candidatos:
        if c.exists():
            return str(c)
    return None


def proceso_vivo() -> bool:
    proc = _EN_CURSO.get("proc")
    return proc is not None and proc.poll() is None


def _cerrar_proceso() -> dict[str, Any] | None:
    """Si el proceso terminó, devuelve cómo terminó y libera el hueco."""
    proc = _EN_CURSO.get("proc")
    if proc is None or proc.poll() is None:
        return None
    fh = _EN_CURSO.pop("fh", None)
    if fh is not None:
        try:
            fh.close()
        except OSError:
            pass
    fin = {"fase": _EN_CURSO.get("fase"), "codigo": proc.returncode, "log": _EN_CURSO.get("log")}
    _EN_CURSO.clear()
    _EN_CURSO["ultimo"] = fin
    return fin


def lanzar_fase(raiz: Path, fase: str) -> dict[str, Any]:
    """Arranca la fase en segundo plano. No espera: la pantalla consulta el estado por su cuenta."""
    if fase not in SKILLS and fase not in VERBOS:
        raise ValueError(f"Fase desconocida: {fase}")
    _cerrar_proceso()
    if proceso_vivo():
        raise RuntimeError("Ya hay una ejecución en marcha. Una sola cada vez: dos sobre el mismo "
                           "estado lo corromperían.")

    if fase in VERBOS:
        cmd = [_python(raiz), "-m", "app", *VERBOS[fase]]
    else:
        exe = ejecutable_claude()
        if exe is None:
            raise RuntimeError("No encuentro el ejecutable `claude`. La pantalla no puede lanzar fases "
                               "sin él; desde la terminal siguen funcionando igual.")
        # `--permission-prompts none` deniega en vez de quedarse esperando una respuesta que no llega
        # (§15.4). Nunca `--bare`: saltaría hooks, subagentes, skills y CLAUDE.md.
        cmd = [exe, "-p", SKILLS[fase], "--output-format", "json", "--permission-prompts", "none"]

    log = raiz / ".tanda" / "ultimo_lanzamiento.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    fh = log.open("wb")
    proc = subprocess.Popen(cmd, cwd=str(raiz), stdout=fh, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
    _EN_CURSO.clear()
    _EN_CURSO.update({"proc": proc, "fase": fase, "desde": time.time(), "log": str(log)})
    return {"lanzada": fase, "pid": proc.pid, "log": str(log)}


def _python(raiz: Path) -> str:
    venv = raiz / ".venv" / "Scripts" / "python.exe"
    if venv.exists():
        return str(venv)
    venv = raiz / ".venv" / "bin" / "python"
    return str(venv) if venv.exists() else "python"


# ------------------------------------------------------------------------------------- estado

def _agente_activo(eventos: list[dict[str, Any]]) -> tuple[str | None, str | None, int | None]:
    """El último `agente_inicio` sin su `agente_fin`. Es lo que la consola pinta encendido."""
    abierto: dict[tuple[str, Any], dict[str, Any]] = {}
    for ev in eventos:
        rol, cap = ev.get("rol"), ev.get("capitulo")
        if ev.get("tipo") == "agente_inicio" and rol:
            abierto[(rol, cap)] = ev
        elif ev.get("tipo") == "agente_fin" and rol:
            abierto.pop((rol, cap), None)
    if not abierto:
        return None, None, None
    ultimo = list(abierto.values())[-1]
    return ultimo.get("rol"), ultimo.get("ts"), ultimo.get("capitulo")


def _capitulos_con_hallazgos(rutas: Rutas) -> list[int]:
    """Los cortes de QA que encontraron contradicciones. Alimenta la cinta de capítulos de la consola.

    Se marca el **capítulo del corte**, no el `cap_origen` de cada hallazgo. `cap_origen` señala dónde se
    estableció el hecho que se violó, que casi nunca es donde está el error: marcarlo pintaría de ámbar
    un capítulo correcto. El corte sí es un dato sin ambigüedad: ahí QA encontró algo.
    """
    caps: set[int] = set()
    if not rutas.reportes_qa.is_dir():
        return []
    for informe in rutas.reportes_qa.glob("*.json"):
        datos = _json(informe)
        corte = datos.get("cap_corte")
        if datos.get("tiene_contradicciones") and isinstance(corte, int) and corte >= 1:
            caps.add(corte)
    return sorted(caps)


def estado(raiz: Path) -> dict[str, Any]:
    """Todo lo que la consola necesita para pintarse. Se lee del disco, nunca de la salida del modelo."""
    rutas = Rutas(raiz)
    m = checkpoint.leer_manifest(raiz)
    cursor = _json(raiz / ".tanda" / "cursor.json")
    tanda = tanda_actual(raiz)
    meta = _json(tanda / "tanda.json") if tanda else {}
    eventos_crudos = _lineas_jsonl(tanda / "eventos.jsonl", limite=400) if tanda else []
    rol, desde, cap_agente = _agente_activo(eventos_crudos)

    fin = _cerrar_proceso()
    ultimo_ts = eventos_crudos[-1].get("ts") if eventos_crudos else None
    en_marcha = bool(cursor) and (proceso_vivo() or _segundos_desde(ultimo_ts) < MARGEN_VIVA_S)

    cerrados = m.ultimo_capitulo_cerrado if m else 0
    manifiesto_estado = getattr(m, "estado", None) if m else None
    ultimo_error = getattr(m, "ultimo_error", None) if m else None

    if manifiesto_estado == "pausado_por_qa":
        vista = "pausado_por_qa"
    elif ultimo_error:
        vista = "error"
    elif en_marcha:
        vista = "en_progreso"
    else:
        vista = "inactivo"

    novela = _json(rutas.novela_json)
    ejecucion = _json(rutas.ejecucion_json)
    config = {k: v for k, v in {**novela, **ejecucion}.items() if k in CAMPOS_NOVELA or k in CAMPOS_EJECUCION}

    total = novela.get("total_capitulos") or meta.get("total_capitulos") or 0
    activo = cursor.get("capitulo_en_curso") or cap_agente or (cerrados + 1 if cerrados < total else total)

    return {
        "estado": vista,
        "tanda": tanda.name if tanda else None,
        "tanda_numero": _numero_de_tanda(rutas, tanda),
        "capitulo_actual": activo,
        "capitulos_cerrados": cerrados,
        "total_capitulos": total,
        "capitulos_por_tanda": ejecucion.get("capitulos_por_tanda") or meta.get("capitulos_por_tanda"),
        "max_llamadas_por_tanda": ejecucion.get("max_llamadas_por_tanda") or meta.get("max_llamadas_por_tanda"),
        "cadencia_qa": novela.get("cadencia_qa") or meta.get("cadencia_qa"),
        "palabras_objetivo": novela.get("palabras_por_capitulo") or meta.get("palabras_por_capitulo"),
        # No hay `palabras_actual`: el capítulo no existe en disco hasta que el escritor termina de
        # escribirlo entero, así que cualquier porcentaje sería inventado. La consola enseña el reloj.
        "agente_activo": rol if en_marcha else None,
        "agente_desde": desde if en_marcha else None,
        "capitulos_con_hallazgos": _capitulos_con_hallazgos(rutas),
        "tiene_referencias": bool(_referencias(rutas)),
        "origen_estilo": ejecucion.get("origen_estilo", "referencias"),
        "artefactos": {
            "idea": rutas.idea.exists(),
            "premisa": rutas.premisa.exists(),
            "tres_actos": rutas.tres_actos.exists(),
            "capitulos": rutas.capitulos.exists(),
            "style_guide": rutas.style_guide.exists(),
            "estado_inicializado": rutas.continuidad.exists() and rutas.personajes.exists(),
        },
        "config": config,
        "ultimo_error": ultimo_error,
        "ruta_registro": str(tanda.relative_to(raiz)) if tanda else None,
        "lanzamiento": fin or _EN_CURSO.get("ultimo"),
        "huerfana": bool(cursor) and not en_marcha,
    }


def _referencias(rutas: Rutas) -> list[str]:
    if not rutas.referencias.exists():
        return []
    return [p.name for p in rutas.referencias.iterdir() if p.is_file() and p.name != ".gitkeep"]


def _numero_de_tanda(rutas: Rutas, tanda: Path | None) -> int | None:
    if tanda is None or not rutas.registro.is_dir():
        return None
    nombres = sorted(p.name for p in rutas.registro.iterdir() if p.is_dir() and p.name.startswith("tanda_"))
    return nombres.index(tanda.name) + 1 if tanda.name in nombres else None


# ------------------------------------------------------------------------------------ registro

def _frase(ev: dict[str, Any]) -> str | None:
    """Una línea corta de bitácora. Devuelve None para el ruido que no aporta al que mira la pantalla."""
    tipo, cap = ev.get("tipo"), ev.get("capitulo")
    pref = f"Cap {cap:02d} · " if isinstance(cap, int) else ""
    if tipo == "agente_inicio":
        return f"{pref}{ev.get('rol', 'agente')} en marcha"
    if tipo == "agente_fin":
        turnos = ev.get("turnos")
        return f"{pref}{ev.get('rol', 'agente')} terminado" + (f" · {turnos} turnos" if turnos else "")
    if tipo == "validacion":
        if ev.get("valido"):
            # Solo las cifras: los booleanos del artefacto ("tiene_contradicciones: True") no se leen
            # bien en una línea de bitácora y el estado ya lo dice la insignia de la cabecera.
            datos = {k: v for k, v in (ev.get("datos") or {}).items() if isinstance(v, int) and not isinstance(v, bool)}
            detalle = " · ".join(f"{v} {k}" for k, v in datos.items()) if datos else "válido"
            return f"{pref}{ev.get('rol', '')} validado · {detalle}".replace("  ", " ")
        return f"{pref}validación RECHAZADA · {'; '.join(ev.get('errores') or []) or 'sin detalle'}"
    if tipo == "verbo":
        return f"{pref}{ev.get('verbo')} · {ev.get('resultado', '')}".strip(" ·")
    if tipo == "error":
        return f"{pref}ERROR · {ev.get('mensaje') or ev.get('error') or 'sin mensaje'}"
    if tipo == "hook" and ev.get("decision") != "permitido":
        return f"{ev.get('id', 'hook')} BLOQUEÓ · {_corto(ev.get('motivo') or ev.get('accion', ''))}"
    return None  # hooks permitidos: son la mayoría del registro y no dicen nada al usuario


def _corto(texto: Any, tope: int = 64) -> str:
    """La bitácora es una columna estrecha: una ruta absoluta la llena entera y no dice nada."""
    limpio = " ".join(str(texto).split())
    if "\\" in limpio or "/" in limpio:
        limpio = " ".join(p.rsplit("\\", 1)[-1].rsplit("/", 1)[-1] for p in limpio.split(" "))
    return limpio if len(limpio) <= tope else limpio[: tope - 1] + "…"


def eventos(raiz: Path, limite: int = 40) -> list[dict[str, str]]:
    tanda = tanda_actual(raiz)
    if tanda is None:
        return []
    salida: list[dict[str, str]] = []
    for ev in reversed(_lineas_jsonl(tanda / "eventos.jsonl", limite=600)):
        texto = _frase(ev)
        if texto is None:
            continue
        salida.append({"ts": str(ev.get("ts", ""))[11:19], "tipo": str(ev.get("tipo", "")), "texto": texto})
        if len(salida) >= limite:
            break
    return salida


def informe_qa(raiz: Path) -> dict[str, Any] | None:
    """El informe que tiene la novela pausada. Solo se enseña: cerrarlo no se hace desde aquí (§15.6)."""
    m = checkpoint.leer_manifest(raiz)
    pendiente = getattr(m, "reporte_qa_pendiente", None) if m else None
    if not pendiente:
        return None
    datos = _json(Rutas(raiz).reportes_qa / f"{pendiente}.json")
    if not datos:
        return None
    datos["reporte"] = pendiente
    return datos
