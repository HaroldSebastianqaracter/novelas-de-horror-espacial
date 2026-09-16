"""Lógica de los hooks H-01 a H-11 (spec técnica §13.3, RF-08.2, EX-09).

Los scripts de `scripts/hooks/` leen el payload por stdin y llaman a estas funciones; no tienen lógica
propia. Una `Decision` con `bloquear = True` se traduce en código de salida 2 y el motivo por stderr.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from app import registro
from app.agents import escritor
from app.config import cargar_config
from app.errores import EstadoInvalidoError, HarnessError
from app.orchestrator import checkpoint, cursor as cur
from app.rutas import Rutas, bajo, es_ruta_manuscrito, numero_capitulo
from app.schemas import LogContinuidad
from app.state import continuidad as cont
from app.state import repository as repo
from app.validacion import ROLES, capitulo_de_invocacion, comando_validador

HERRAMIENTAS_ESCRITURA = ("Write", "Edit", "MultiEdit", "NotebookEdit")
HERRAMIENTAS_LECTURA = ("Read", "Grep", "Glob")


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


def _capitulo_activo(raiz: Path, rol: str | None = None) -> int:
    """La única resolución de N para H-05, H-06, H-07, H-10 y H-11 (§13.3): `validacion.capitulo_de_invocacion`."""
    return capitulo_de_invocacion(raiz, rol)


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
        registro.evento(raiz, "error", excepcion="EX-09", mensaje=texto, traza=f"hook {hook}; agent_id {payload.get('agent_id')}",
                        agent_type=payload.get("agent_type"), agent_id=payload.get("agent_id"))
        cur.borrar(raiz, "EX-09")
    return decision


# ---------- H-01 ----------

def h11_declarado(raiz: Path) -> bool:
    """§13.6: True si .claude/settings.json declara un hook PreToolUse cuyo matcher alcanza `Bash`."""
    path = Rutas(raiz).raiz / ".claude" / "settings.json"
    if not path.exists():
        return False
    try:
        settings = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    for entrada in (settings.get("hooks") or {}).get("PreToolUse") or []:
        matcher = str(entrada.get("matcher") or "")
        if matcher == "" or "Bash" in matcher.split("|"):
            return bool(entrada.get("hooks"))
    return False


def aviso_h11(raiz: Path) -> str | None:
    if h11_declarado(raiz):
        return None
    return ("- ATENCIÓN: H-11 no está declarado en .claude/settings.json (PreToolUse sin matcher `Bash`); "
            "los tres agentes tendrían shell libre (§13.6). No lanzar ninguna tanda hasta corregirlo.")


def contexto_session_start(raiz: Path) -> str:
    """H-01 (RF-08.3): la salida de `status` entra al contexto de la sesión."""
    texto = checkpoint.texto_status(raiz)
    aviso = aviso_h11(raiz)
    return texto + (f"\n{aviso}" if aviso else "") + "\n" + registro.texto_status(raiz)


# ---------- PreToolUse: H-04, H-05, H-06, H-08, H-09, H-11 + copia previa para H-03 ----------

def decidir_h11(payload: dict, raiz: Path) -> Decision | None:
    """H-11 (RF-08.4): `Bash` en los tres agentes sirve solo para su validador, con el capítulo de la invocación.

    Compara el comando completo contra la forma canónica exacta (§13.3): un solo intérprete (el del entorno
    virtual), el verbo del rol y el N resuelto por `capitulo_de_invocacion`. Todo lo demás se bloquea:
    encadenamientos, tuberías, sustituciones, redirecciones, otro verbo, otro N u otro intérprete.
    """
    agent_type = payload.get("agent_type")
    if payload.get("tool_name") != "Bash" or payload.get("agent_id") is None or agent_type not in ROLES:
        return None
    comando = str((payload.get("tool_input") or {}).get("command") or "").strip()
    esperado = comando_validador(agent_type, _capitulo_activo(raiz, agent_type))
    if comando == esperado:
        return Decision().con_nota(f"H-11: {agent_type} ejecuta su validador ({esperado})")
    return _bloquear(raiz, payload, "H-11",
                     f"el {agent_type} solo puede ejecutar exactamente `{esperado}` (RF-08.4); intentó `{comando[:120]}`")


def decidir_pre_tool_use(payload: dict, raiz: Path) -> Decision:
    rutas = Rutas(raiz)
    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input") or {}
    agent_type = payload.get("agent_type")
    es_subagente = payload.get("agent_id") is not None
    ruta = _ruta_afectada(tool_input)
    rel = rutas.relativa(ruta) if ruta else None
    rel_posix = rel.as_posix() if rel else None

    # H-11: Bash acotado al validador del rol (INV-01, INV-02, RF-08.4). Va primero: es la capa crítica (§13.6).
    h11 = decidir_h11(payload, raiz)
    if h11 is not None:
        return h11

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
        activo = _capitulo_activo(raiz, "extractor")
        if es_ruta_manuscrito(rel) and numero_capitulo(rel) != activo:
            return _bloquear(raiz, payload, "H-05", f"el extractor solo puede leer 05_manuscrito/cap_{activo}.md (INV-02); pidió {rel_posix}")
        if rel_posix in ("04_estado/continuidad.json", "04_estado/resumen_rodante.md"):
            return _bloquear(raiz, payload, "H-05", f"el extractor no recibe {rel_posix} (RF-06.1): solo el capítulo y el registro de sujetos")
        if rel is None and ruta:
            return _bloquear(raiz, payload, "H-05", f"el extractor no lee fuera del proyecto: {ruta}")

    # H-06: escritura por agente (INV-01, INV-05, RF-07.5).
    if tool in HERRAMIENTAS_ESCRITURA and es_subagente and agent_type in ROLES:
        if agent_type == "escritor":
            activo = _capitulo_activo(raiz, "escritor")
            permitido = f"05_manuscrito/cap_{activo}.md"
            if rel_posix != permitido:
                return _bloquear(raiz, payload, "H-06", f"el escritor solo escribe {permitido} (INV-01); intentó {rel_posix or ruta}")
        elif agent_type == "extractor":
            activo = _capitulo_activo(raiz, "extractor")
            permitido = f"04_estado/deltas/delta_cap_{activo}.json"
            if rel_posix != permitido:
                return _bloquear(raiz, payload, "H-06", f"el extractor solo escribe {permitido}, su propio delta (RF-08.4); intentó {rel_posix or ruta}")
        elif agent_type == "qa":
            if not bajo(rel, "06_qa"):
                return _bloquear(raiz, payload, "H-06", f"QA solo escribe dentro de 06_qa/ (RF-07.5); intentó {rel_posix or ruta}")

    # H-09: el orquestador no lee ni toca el manuscrito (INV-08) ni el registro de ejecución (RF-08.5, §5.1).
    if not es_subagente:
        if tool in HERRAMIENTAS_LECTURA and _toca_manuscrito(tool, tool_input, rel):
            return _bloquear(raiz, payload, "H-09", "el orquestador no lee 05_manuscrito/ (INV-08); usá `python -m app ensamblar` para leer lo generado")
        if tool in HERRAMIENTAS_LECTURA and _toca_registro(tool, tool_input, rel):
            return _bloquear(raiz, payload, "H-09", "el orquestador no lee 07_registro/ (RF-08.5); `python -m app status` lo resume")
        if tool in HERRAMIENTAS_ESCRITURA and es_ruta_manuscrito(rel):
            return _bloquear(raiz, payload, "H-09", "el orquestador no escribe prosa ni toca 05_manuscrito/ (INV-08)")
        if tool in HERRAMIENTAS_ESCRITURA and bajo(rel, "07_registro"):
            return _bloquear(raiz, payload, "H-09", "el orquestador no escribe en 07_registro/: lo escriben los scripts y los hooks (RF-08.5)")

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


def _toca_registro(tool: str, tool_input: dict, rel: Path | None) -> bool:
    if bajo(rel, "07_registro"):
        return True
    if tool in ("Grep", "Glob"):
        patron = " ".join(str(tool_input.get(k, "")) for k in ("pattern", "glob", "path"))
        return "07_registro" in patron
    return False


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
    registro.evento(raiz, "error", excepcion="EX-01", mensaje=f"via {hook}: {motivo}", traza=f"hook {hook}; agent_id {payload.get('agent_id')}",
                    agent_type=payload.get("agent_type"), agent_id=payload.get("agent_id"))
    cur.borrar(raiz, f"EX-01 via {hook}")
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

    nota, uso = registrar_uso(payload, raiz)  # H-10
    if nota:
        decision.con_nota(nota)
    # §5.1: agente_fin lo escribe subagent_stop.py, con los turnos del transcript y los intentos de validación (H-11).
    registro.evento(raiz, "agente_fin", rol=agent_type, capitulo=_capitulo_activo(raiz, agent_type),
                    agent_id=payload.get("agent_id"), turnos=uso.get("turnos"), modelo=uso.get("modelo"),
                    intentos_de_validacion=registro.intentos_de_validacion(raiz, payload.get("agent_id")),
                    stop_reason=payload.get("stop_reason"))
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


_CAMPOS_USO = {"tokens_entrada": "input_tokens", "tokens_salida": "output_tokens",
               "tokens_cache_lectura": "cache_read_input_tokens", "tokens_cache_creacion": "cache_creation_input_tokens"}


def leer_uso_transcript(path: Path) -> dict:
    """H-10 (§13.3): suma los tokens de TODOS los mensajes del asistente del transcript JSONL, no solo del último.

    Un mismo mensaje aparece en varias líneas (una por bloque de contenido), con el mismo `message.id` y un
    `usage` que crece hasta el valor final. Por cada mensaje se toma el máximo de cada campo entre sus líneas, y
    los mensajes se suman. `turnos` es la cantidad de mensajes distintos.
    """
    total = {"tokens_entrada": 0, "tokens_salida": 0, "tokens_cache_lectura": 0, "tokens_cache_creacion": 0,
             "turnos": 0, "modelo": None}
    if not path.exists():
        return total
    por_mensaje: dict[str, dict[str, int]] = {}
    orden: list[str] = []
    for linea in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            entrada = json.loads(linea)
        except json.JSONDecodeError:
            continue
        if entrada.get("type") != "assistant":
            continue
        mensaje = entrada.get("message") or {}
        uso = mensaje.get("usage") or {}
        mid = str(mensaje.get("id") or entrada.get("uuid") or len(orden))
        if mid not in por_mensaje:
            por_mensaje[mid] = {campo: 0 for campo in _CAMPOS_USO}
            orden.append(mid)
        for campo, clave in _CAMPOS_USO.items():
            por_mensaje[mid][campo] = max(por_mensaje[mid][campo], int(uso.get(clave) or 0))
        if mensaje.get("model"):
            total["modelo"] = mensaje["model"]
    for mid in orden:
        total["turnos"] += 1
        for campo in _CAMPOS_USO:
            total[campo] += por_mensaje[mid][campo]
    return total


def registrar_uso(payload: dict, raiz: Path) -> tuple[str, dict]:
    """H-10 (RF-CFG-06): una línea en 07_registro/<tanda>/uso.jsonl por invocación de subagente; suma la llamada al cursor."""
    try:
        registrar = cargar_config(raiz).registrar_uso
    except HarnessError:
        registrar = True
    cur.sumar_llamada(raiz)
    transcript = payload.get("agent_transcript_path")
    uso = leer_uso_transcript(Path(transcript)) if transcript else leer_uso_transcript(Path("/inexistente"))
    if not registrar:
        return "H-10: registrar_uso = false; la llamada se contó pero no se registró", uso
    capitulo = _capitulo_activo(raiz, payload.get("agent_type")) if checkpoint.leer_manifest(raiz) is not None else None
    linea_uso = {
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
    with registro.ruta_uso(raiz).open("a", encoding="utf-8") as f:
        f.write(json.dumps(linea_uso, ensure_ascii=False) + "\n")
    return (f"H-10: uso registrado para {linea_uso['rol']} (modelo {linea_uso['modelo']}, "
            f"{linea_uso['tokens_entrada']}+{linea_uso['tokens_salida']} tokens, {linea_uso['turnos']} turnos)"), uso
