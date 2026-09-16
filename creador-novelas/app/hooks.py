"""Lógica de los hooks H-01 a H-10 (spec técnica §13.3, RF-08.2, EX-09).

Los scripts de `scripts/hooks/` leen el payload por stdin y llaman a estas funciones; no tienen lógica
propia. Una `Decision` con `bloquear = True` se traduce en código de salida 2 y el motivo por stderr.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from app.agents import escritor
from app.config import cargar_config
from app.errores import EstadoInvalidoError, HarnessError
from app.orchestrator import checkpoint, cursor as cur
from app.rutas import Rutas, bajo, es_ruta_manuscrito, numero_capitulo
from app.schemas import LogContinuidad
from app.state import continuidad as cont
from app.state import repository as repo

HERRAMIENTAS_ESCRITURA = ("Write", "Edit", "MultiEdit", "NotebookEdit")
HERRAMIENTAS_LECTURA = ("Read", "Grep", "Glob")
ROLES = ("escritor", "extractor", "qa")


@dataclass
class Decision:
    bloquear: bool = False
    motivo: str = ""
    hook: str = ""
    detiene_tanda: bool = False  # EX-09: segundo choque del mismo agente con el mismo hook
    notas: list[str] | None = None

    def con_nota(self, nota: str) -> "Decision":
        self.notas = (self.notas or []) + [nota]
        return self


def _ruta_afectada(tool_input: dict) -> str | None:
    for clave in ("file_path", "path", "notebook_path"):
        valor = tool_input.get(clave)
        if valor:
            return str(valor)
    return None


def _capitulo_activo(raiz: Path) -> int:
    m = checkpoint.leer_manifest(raiz)
    return m.capitulo_actual() if m else 1


def _identidad(payload: dict) -> str:
    return payload.get("agent_id") or f"orquestador:{payload.get('session_id', 'sesion')}"


def registrar_choque(raiz: Path, payload: dict, hook: str) -> int:
    """EX-09: cuenta choques por (identidad del agente, hook). Devuelve el conteo acumulado."""
    rutas = Rutas(raiz)
    rutas.tanda.mkdir(parents=True, exist_ok=True)
    estado: dict = {}
    if rutas.hooks_estado.exists():
        try:
            estado = json.loads(rutas.hooks_estado.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            estado = {}
    clave = _identidad(payload)
    estado.setdefault(clave, {})
    estado[clave][hook] = estado[clave].get(hook, 0) + 1
    rutas.hooks_estado.write_text(json.dumps(estado, indent=2) + "\n", encoding="utf-8")
    return estado[clave][hook]


def _bloquear(raiz: Path, payload: dict, hook: str, motivo: str) -> Decision:
    choques = registrar_choque(raiz, payload, hook)
    decision = Decision(bloquear=True, motivo=f"[{hook}] {motivo}", hook=hook)
    if choques >= 2:
        agente = payload.get("agent_type") or "orquestador"
        texto = f"EX-09: {agente} chocó {choques} veces con {hook} en la misma invocación ({motivo}); la tanda se detiene"
        decision.detiene_tanda = True
        decision.motivo += f"\n{texto}"
        try:
            if checkpoint.leer_manifest(raiz) is not None:
                checkpoint.registrar_error(raiz, texto)
        except HarnessError:
            pass
        cur.borrar(raiz)
    return decision


# ---------- H-01 ----------

def contexto_session_start(raiz: Path) -> str:
    """H-01 (RF-08.3): la salida de `status` entra al contexto de la sesión."""
    return checkpoint.texto_status(raiz)


# ---------- PreToolUse: H-04, H-05, H-06, H-08, H-09 + copia previa para H-03 ----------

def decidir_pre_tool_use(payload: dict, raiz: Path) -> Decision:
    rutas = Rutas(raiz)
    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input") or {}
    agent_type = payload.get("agent_type")
    es_subagente = payload.get("agent_id") is not None
    ruta = _ruta_afectada(tool_input)
    rel = rutas.relativa(ruta) if ruta else None
    rel_posix = rel.as_posix() if rel else None

    # H-08: los subagentes no lanzan subagentes (INV-09).
    if tool == "Agent" and es_subagente:
        return _bloquear(raiz, payload, "H-08", f"{agent_type or 'un subagente'} intentó lanzar un subagente; la delegación tiene un solo nivel (INV-09)")

    # H-04: novela.json inmutable con capítulos cerrados (INV-04, EX-06).
    if tool in HERRAMIENTAS_ESCRITURA and rel_posix == "config/novela.json":
        m = checkpoint.leer_manifest(raiz)
        if m is not None and m.ultimo_capitulo_cerrado > 0:
            return _bloquear(raiz, payload, "H-04", f"config/novela.json es inmutable con {m.ultimo_capitulo_cerrado} capítulos cerrados (INV-04); cambiarlo invalida la escaleta")

    # H-05: el extractor lee un solo capítulo, el activo (INV-02, RF-06.1 b).
    if tool == "Read" and agent_type == "extractor":
        activo = _capitulo_activo(raiz)
        if es_ruta_manuscrito(rel) and numero_capitulo(rel) != activo:
            return _bloquear(raiz, payload, "H-05", f"el extractor solo puede leer 05_manuscrito/cap_{activo}.md (INV-02); pidió {rel_posix}")
        if rel_posix in ("04_estado/continuidad.json", "04_estado/resumen_rodante.md"):
            return _bloquear(raiz, payload, "H-05", f"el extractor no recibe {rel_posix} (RF-06.1): solo el capítulo y el registro de sujetos")
        if rel is None and ruta:
            return _bloquear(raiz, payload, "H-05", f"el extractor no lee fuera del proyecto: {ruta}")

    # H-06: escritura por agente (INV-01, INV-05, RF-07.5).
    if tool in HERRAMIENTAS_ESCRITURA and es_subagente and agent_type in ROLES:
        if agent_type == "escritor":
            activo = _capitulo_activo(raiz)
            permitido = f"05_manuscrito/cap_{activo}.md"
            if rel_posix != permitido:
                return _bloquear(raiz, payload, "H-06", f"el escritor solo escribe {permitido} (INV-01); intentó {rel_posix or ruta}")
        elif agent_type == "extractor":
            return _bloquear(raiz, payload, "H-06", "el extractor no escribe archivos: devuelve el delta en su mensaje final (RF-08.1)")
        elif agent_type == "qa":
            if not bajo(rel, "06_qa"):
                return _bloquear(raiz, payload, "H-06", f"QA solo escribe dentro de 06_qa/ (RF-07.5); intentó {rel_posix or ruta}")

    # H-09: el orquestador no lee ni toca el manuscrito (INV-08).
    if not es_subagente:
        if tool in HERRAMIENTAS_LECTURA and _toca_manuscrito(tool, tool_input, rel):
            return _bloquear(raiz, payload, "H-09", "el orquestador no lee 05_manuscrito/ (INV-08); usá `python -m app ensamblar` para leer lo generado")
        if tool in HERRAMIENTAS_ESCRITURA and es_ruta_manuscrito(rel):
            return _bloquear(raiz, payload, "H-09", "el orquestador no escribe prosa ni toca 05_manuscrito/ (INV-08)")

    # Copia previa para H-03: PostToolUse ve el archivo ya sobrescrito.
    decision = Decision()
    if tool in HERRAMIENTAS_ESCRITURA and rel_posix == "04_estado/continuidad.json":
        rutas.tanda.mkdir(parents=True, exist_ok=True)
        if rutas.continuidad.exists():
            shutil.copyfile(rutas.continuidad, rutas.continuidad_previa)
        else:
            rutas.continuidad_previa.write_text("[]\n", encoding="utf-8")
        decision.con_nota("copia previa de continuidad.json guardada para H-03")
    return decision


def _toca_manuscrito(tool: str, tool_input: dict, rel: Path | None) -> bool:
    if es_ruta_manuscrito(rel):
        return True
    if tool in ("Grep", "Glob"):
        patron = " ".join(str(tool_input.get(k, "")) for k in ("pattern", "glob"))
        if "05_manuscrito" in patron or "cap_" in patron:
            return True
        # búsqueda desde la raíz que alcanza .md: incluiría la novela
        if rel is None or rel == Path("."):
            if tool == "Glob" and patron.endswith(".md") and "**" in patron:
                return True
            if tool == "Grep" and (tool_input.get("type") == "md" or str(tool_input.get("glob", "")).endswith(".md")):
                return True
    return False


# ---------- PostToolUse: H-02, H-03 ----------

def verificar_post_tool_use(payload: dict, raiz: Path) -> Decision:
    rutas = Rutas(raiz)
    tool = payload.get("tool_name", "")
    if tool not in HERRAMIENTAS_ESCRITURA:
        return Decision()
    ruta = _ruta_afectada(payload.get("tool_input") or {})
    rel = rutas.relativa(ruta) if ruta else None
    if rel is None:
        return Decision()
    decision = Decision()

    # H-02: validación de esquema apenas se escribe (EX-01).
    if repo.esquema_para(rutas, rel) is not None or (rel.suffix == ".json" and (bajo(rel, "04_estado") or bajo(rel, "06_qa"))):
        try:
            esquema = repo.validar_archivo(rutas, rel)
            decision.con_nota(f"H-02: {rel.as_posix()} valida contra {esquema}")
        except EstadoInvalidoError as e:
            return _fallo_verificador(raiz, payload, "H-02", str(e))

    # H-03: continuidad.json append-only (INV-03, RF-06.3).
    if rel.as_posix() == "04_estado/continuidad.json":
        try:
            nuevo = repo.leer_json(rutas.continuidad, LogContinuidad) or LogContinuidad([])
            if rutas.continuidad_previa.exists():
                previa = repo.validar_texto(rutas.continuidad_previa.read_text(encoding="utf-8"), LogContinuidad, "continuidad.prev.json")
                ok, motivo = cont.es_superconjunto(previa, nuevo)
                if not ok:
                    return _fallo_verificador(raiz, payload, "H-03", f"continuidad.json dejó de ser superconjunto de su versión anterior: {motivo}")
                decision.con_nota("H-03: continuidad.json conserva todos los hechos previos")
            else:
                decision.con_nota("H-03: sin copia previa; no hay versión anterior contra la que comparar")
        except EstadoInvalidoError as e:
            return _fallo_verificador(raiz, payload, "H-03", str(e))
        finally:
            if rutas.continuidad_previa.exists():
                rutas.continuidad_previa.unlink()
    return decision


def _fallo_verificador(raiz: Path, payload: dict, hook: str, motivo: str) -> Decision:
    """Un hook verificador que falla detiene la tanda como EX-01 (RF-08.2)."""
    texto = f"[{hook}] {motivo}"
    try:
        if checkpoint.leer_manifest(raiz) is not None:
            checkpoint.registrar_error(raiz, f"EX-01 via {hook}: {motivo}")
    except HarnessError:
        pass
    cur.borrar(raiz)
    registrar_choque(raiz, payload, hook)
    return Decision(bloquear=True, motivo=texto, hook=hook, detiene_tanda=True)


# ---------- SubagentStop: H-07, H-10 ----------

def decidir_subagent_stop(payload: dict, raiz: Path) -> Decision:
    agent_type = payload.get("agent_type")
    if agent_type not in ROLES:
        return Decision()
    decision = Decision()

    if agent_type == "escritor":
        decision = _h07_escritor(payload, raiz)
        if decision.bloquear:
            return decision  # el subagente sigue; H-10 registra cuando termine de verdad

    nota = registrar_uso(payload, raiz)  # H-10
    if nota:
        decision.con_nota(nota)
    return decision


def _h07_escritor(payload: dict, raiz: Path) -> Decision:
    """H-07 (EX-07): cap_N.md existe y su longitud está en rango; primer fallo bloquea el cierre, segundo anota."""
    try:
        config = cargar_config(raiz)
    except HarnessError as e:
        return Decision().con_nota(f"H-07 sin configuración válida: {e}")
    n = _capitulo_activo(raiz)
    rutas = Rutas(raiz)
    segundo = bool(payload.get("stop_hook_active"))
    if not rutas.capitulo(n).exists():
        motivo = f"[H-07] no existe 05_manuscrito/cap_{n}.md: escribí el capítulo con Write antes de terminar y devolvé la línea de retorno"
        if segundo:
            return Decision().con_nota(motivo + " (segundo aviso; se deja terminar)")
        return Decision(bloquear=True, motivo=motivo, hook="H-07")
    palabras = escritor.contar_palabras(rutas.capitulo(n).read_text(encoding="utf-8"))
    ok, mensaje = escritor.evaluar_longitud(palabras, config)
    if ok:
        return Decision().con_nota(f"H-07: cap_{n}.md tiene {palabras} palabras, dentro de rango")
    if not segundo:
        return Decision(bloquear=True, hook="H-07",
                        motivo=f"[H-07] {mensaje} Reescribí 05_manuscrito/cap_{n}.md completo con Write y devolvé de nuevo la línea de retorno.")
    try:
        checkpoint.registrar_intentos(raiz, n, 2)
    except HarnessError:
        pass
    return Decision().con_nota(f"H-07: segundo intento fuera de rango ({palabras} palabras); se acepta con aviso (EX-07)")


def leer_uso_transcript(path: Path) -> dict:
    """Suma tokens y toma el modelo de los mensajes assistant del transcript JSONL del subagente."""
    total = {"tokens_entrada": 0, "tokens_salida": 0, "tokens_cache_lectura": 0, "tokens_cache_creacion": 0,
             "turnos": 0, "modelo": None}
    if not path.exists():
        return total
    vistos: set[str] = set()
    for linea in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            entrada = json.loads(linea)
        except json.JSONDecodeError:
            continue
        if entrada.get("type") != "assistant":
            continue
        mensaje = entrada.get("message") or {}
        uso = mensaje.get("usage") or {}
        mid = mensaje.get("id") or entrada.get("uuid")
        if mid in vistos or not uso:
            continue
        vistos.add(mid)
        total["turnos"] += 1
        total["tokens_entrada"] += int(uso.get("input_tokens") or 0)
        total["tokens_salida"] += int(uso.get("output_tokens") or 0)
        total["tokens_cache_lectura"] += int(uso.get("cache_read_input_tokens") or 0)
        total["tokens_cache_creacion"] += int(uso.get("cache_creation_input_tokens") or 0)
        if mensaje.get("model"):
            total["modelo"] = mensaje["model"]
    return total


def registrar_uso(payload: dict, raiz: Path) -> str:
    """H-10 (RF-CFG-06): una línea en 04_estado/uso.jsonl por invocación de subagente; suma la llamada al cursor."""
    rutas = Rutas(raiz)
    try:
        registrar = cargar_config(raiz).registrar_uso
    except HarnessError:
        registrar = True
    cur.sumar_llamada(raiz)
    if not registrar:
        return "H-10: registrar_uso = false; la llamada se contó pero no se registró"
    transcript = payload.get("agent_transcript_path")
    uso = leer_uso_transcript(Path(transcript)) if transcript else leer_uso_transcript(Path("/inexistente"))
    m = checkpoint.leer_manifest(raiz)
    capitulo = None
    if m is not None:
        capitulo = m.ultimo_capitulo_cerrado if payload.get("agent_type") == "qa" else m.capitulo_actual()
    registro = {
        "rol": payload.get("agent_type"),
        "capitulo": capitulo,
        "modelo": uso["modelo"],
        "tokens_entrada": uso["tokens_entrada"],
        "tokens_salida": uso["tokens_salida"],
        "tokens_cache_lectura": uso["tokens_cache_lectura"],
        "tokens_cache_creacion": uso["tokens_cache_creacion"],
        "turnos": uso["turnos"],
        "agent_id": payload.get("agent_id"),
        "stop_reason": payload.get("stop_reason"),
    }
    rutas.estado.mkdir(parents=True, exist_ok=True)
    with rutas.uso.open("a", encoding="utf-8") as f:
        f.write(json.dumps(registro, ensure_ascii=False) + "\n")
    return f"H-10: uso registrado para {registro['rol']} (modelo {registro['modelo']}, {registro['tokens_entrada']}+{registro['tokens_salida']} tokens)"
