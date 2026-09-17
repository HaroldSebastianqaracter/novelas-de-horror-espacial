"""Exportación del registro de una tanda a Langfuse (RF-09; spec técnica §16).

La traza no se emite durante la tanda: se construye después leyendo `07_registro/<tanda>/` (§5.1) y se publica
con `python -m app exportar-traza <tanda>`. El registro sigue siendo la fuente de verdad; Langfuse es una vista.

Decisión de §16.8, tomada contra la biblioteca instalable (langfuse 4.15.3): su API pública no permite fijar el
instante de inicio de una observación (solo `completion_start_time` y `end(end_time=...)`), así que las trazas de
hechos pasados saldrían apiladas en el instante de la exportación. Se usa la API de ingesta por HTTP
(`POST /api/public/ingestion`), que acepta `startTime` y `endTime` explícitos, `usageDetails` con las cuatro cifras
de tokens (§16.3) y hace upsert por `body.id`, que es lo que hace idempotente la reexportación (§16.5). Sin
dependencias: solo `urllib`.

Mapeo (§16.2): trace = tanda · span = capítulo · span anidado = verbo determinista del bucle con su duración real
(`ts - ms` → `ts`) · generation = invocación de subagente · event = bloqueo de hook, EX-10 o descarte EX-08 ·
score = métricas del corte de QA y de la tanda (§16.4).

Por defecto no sale prosa ni el cuerpo de ningún prompt (§16.6): todo texto libre que viaja se compara contra los
prompts, los borradores descartados y el manuscrito, y se omite si comparte con ellos una ventana de más de 30
caracteres. `--con-cuerpos` incluye prompts y retornos y desactiva ese filtro.
"""

from __future__ import annotations

import base64
import json
import os
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Protocol
from urllib import error as urlerror
from urllib import request as urlrequest

from app import registro
from app.config import VERSION_SPECS, cargar_config
from app.errores import ConfiguracionInvalidaError, HarnessError
from app.orchestrator import checkpoint
from app.rutas import Rutas
from app.state import repository as repo

VARIABLES_CREDENCIALES = ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY")
VARIABLES_HOST = ("LANGFUSE_HOST", "LANGFUSE_BASE_URL")  # los dos nombres que usa el SDK
HOST_DEFECTO = "https://cloud.langfuse.com"
RUTA_INGESTA = "/api/public/ingestion"
VENTANA_PRIVACIDAD = 31  # RF-09: ninguna subcadena de más de 30 caracteres del manuscrito ni de un prompt
MAX_EVENTOS_POR_LOTE = 100
MAX_BYTES_POR_LOTE = 3_000_000  # el servicio corta en 3,5 MB por petición
# §16.2: los verbos deterministas del bucle (§8.2, capa interna) que van como spans anidados en el span del capítulo.
# `tanda iniciar/siguiente` no tiene capítulo y los `validar-*` los corre el agente dentro de su propia generation.
VERBOS_DEL_BUCLE = ("preparar-capitulo", "preparar-extractor", "registrar-escritor", "aplicar-delta", "descartar-borrador",
                    "preparar-qa", "cerrar-qa")
_ESPACIO = uuid.UUID("6f1c2d3e-4b5a-4c6d-8e7f-90a1b2c3d4e5")  # namespace fijo: los ids son función de la tanda

# usageDetails con los nombres de tipo de uso que Langfuse define para los modelos de Anthropic; `total` lo suma.
CLAVES_USO = {
    "tokens_entrada": "input",
    "tokens_salida": "output",
    "tokens_cache_lectura": "cache_read_input_tokens",
    "tokens_cache_creacion": "cache_creation_input_tokens",
}


class ExportacionError(HarnessError):
    """RF-09: la publicación falló (red, credenciales rechazadas o errores del servicio)."""


@dataclass(frozen=True)
class Credenciales:
    host: str
    clave_publica: str
    clave_secreta: str


def credenciales_desde_entorno(entorno: dict | None = None) -> Credenciales:
    """§16.7: solo del entorno. Si faltan, se falla con el motivo y no se hace nada más."""
    env = os.environ if entorno is None else entorno
    faltan = [v for v in VARIABLES_CREDENCIALES if not env.get(v)]
    if faltan:
        raise ConfiguracionInvalidaError(
            f"RF-09: faltan en el entorno {', '.join(faltan)}; exportar-traza no publica sin credenciales "
            f"(nunca se leen de config/ ni de settings.json, §16.7)"
        )
    host = next((env[v] for v in VARIABLES_HOST if env.get(v)), HOST_DEFECTO).rstrip("/")
    return Credenciales(host=host, clave_publica=env["LANGFUSE_PUBLIC_KEY"], clave_secreta=env["LANGFUSE_SECRET_KEY"])


# ---------- identidad (§16.5) ----------

def id_traza(tanda: str) -> str:
    return uuid.uuid5(_ESPACIO, f"traza/{tanda}").hex  # 32 hex: válido como trace id


def id_observacion(tanda: str, clave: str) -> str:
    return uuid.uuid5(_ESPACIO, f"obs/{tanda}/{clave}").hex[:16]


def id_puntuacion(tanda: str, clave: str) -> str:
    return uuid.uuid5(_ESPACIO, f"score/{tanda}/{clave}").hex


# ---------- filtro de privacidad (§16.6) ----------

class FiltroPrivacidad:
    """Omite todo texto libre que comparta una ventana de 31+ caracteres con los prompts, los descartados o el manuscrito."""

    def __init__(self, corpus: str):
        self.corpus = _normalizar(corpus)

    @classmethod
    def desde_tanda(cls, raiz: Path, carpeta: Path) -> "FiltroPrivacidad":
        partes: list[str] = []
        for sub, patron in (("prompts", "*.md"), ("descartados", "*")):
            for p in sorted((carpeta / sub).glob(patron)) if (carpeta / sub).exists() else []:
                if p.is_file() and not p.name.endswith(".error.txt"):
                    partes.append(p.read_text(encoding="utf-8", errors="replace"))
        manuscrito = Rutas(raiz).manuscrito
        if manuscrito.exists():
            for p in sorted(manuscrito.glob("cap_*.md")):
                partes.append(p.read_text(encoding="utf-8", errors="replace"))
        return cls("\n".join(partes))

    def comparte(self, texto: str) -> bool:
        norm = _normalizar(texto)
        if len(norm) < VENTANA_PRIVACIDAD or not self.corpus:
            return False
        return any(norm[i:i + VENTANA_PRIVACIDAD] in self.corpus for i in range(len(norm) - VENTANA_PRIVACIDAD + 1))

    def limpiar(self, valor: Any) -> Any:
        if isinstance(valor, str):
            return f"[omitido: {len(valor)} caracteres que coinciden con un prompt o con el manuscrito, §16.6]" if self.comparte(valor) else valor
        if isinstance(valor, list):
            return [self.limpiar(v) for v in valor]
        if isinstance(valor, dict):
            return {k: self.limpiar(v) for k, v in valor.items()}
        return valor


def _normalizar(texto: str) -> str:
    return re.sub(r"\s+", " ", texto).lower()


# ---------- construcción de la traza ----------

@dataclass
class Generacion:
    rol: str
    capitulo: int | None
    agent_id: str | None
    inicio: str | None
    fin: str | None
    modelo: str | None
    uso: dict[str, int]
    turnos: int | None
    intentos_de_validacion: int | None
    stop_reason: str | None
    intento: int | None
    reextraccion: bool
    orden: int  # k-ésima invocación de este rol para este capítulo (para emparejar prompts/ y retornos/)
    id: str = ""


@dataclass
class Traza:
    tanda: str
    id: str
    lote: list[dict]  # eventos de ingesta, en orden
    generaciones: list[Generacion]
    capitulos: list[int]
    eventos: int
    puntuaciones: dict[str, Any]
    con_cuerpos: bool
    metadatos: dict


def resolver_tanda(raiz: Path, nombre: str) -> Path:
    """Acepta el nombre de la carpeta (`tanda_2026-...`), su ruta relativa o `ultima`."""
    base = Rutas(raiz).registro
    if nombre == "ultima":
        ultima = registro.ultima_tanda(raiz)
        if ultima is None:
            raise ConfiguracionInvalidaError("RF-09: no hay ninguna tanda registrada en 07_registro/")
        return ultima
    candidata = Path(nombre)
    if not candidata.is_absolute():
        candidata = base / candidata.name if candidata.parent == Path(".") else raiz / candidata
    if not candidata.is_dir() or not (candidata / "eventos.jsonl").exists():
        disponibles = ", ".join(p.name for p in registro.carpetas_tanda(raiz)) or "ninguna"
        raise ConfiguracionInvalidaError(f"RF-09: no existe la tanda {nombre} en 07_registro/ (disponibles: {disponibles})")
    return candidata


def _leer_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _metadatos_tanda(raiz: Path, carpeta: Path) -> dict:
    """§16.2: los tres prompts_hash y el dimensionamiento con los que corrió ESTA tanda (tanda.json, escrito por `tanda iniciar`)."""
    datos = _leer_json(carpeta / "tanda.json")
    origen = "tanda.json"
    if not datos:  # tanda anterior a tanda.json: lo mejor disponible es el manifiesto y la configuración actuales
        origen = "manifest_y_config_actuales"
        m = checkpoint.leer_manifest(raiz)
        datos = {"prompts_hash": dict(m.prompts_hash) if m else {}}
        try:
            config = cargar_config(raiz)
            datos.update(total_capitulos=config.total_capitulos, capitulos_por_tanda=config.capitulos_por_tanda,
                         cadencia_qa=config.cadencia_qa, palabras_por_capitulo=config.palabras_por_capitulo)
        except HarnessError:
            pass
    cursor = _leer_json(carpeta / "cursor.json")
    meta = {
        "total_capitulos": datos.get("total_capitulos"),
        "capitulos_por_tanda": cursor.get("tope", datos.get("capitulos_por_tanda")),
        "cadencia_qa": datos.get("cadencia_qa"),
        "palabras_por_capitulo": datos.get("palabras_por_capitulo"),
        "prompts_hash": datos.get("prompts_hash") or {},
        "version_specs": datos.get("version_specs", VERSION_SPECS),
        "metadatos_origen": origen,
        "motivo_salida": cursor.get("motivo_salida"),
        "capitulos_cerrados_en_la_tanda": cursor.get("cerrados"),
        "llamadas": cursor.get("llamadas"),
    }
    return {k: v for k, v in meta.items() if v is not None}


_CODIGO_REGLA = re.compile(r"^\s*((?:RF|INV|EX)-[0-9]+(?:\.[0-9]+)*)")


def _reglas_incumplidas(errores: list[str]) -> list[str]:
    """Los codigos de regla de una validacion fallida, sin el texto: los mensajes citan el manuscrito (§16.6)."""
    codigos: list[str] = []
    for error in errores:
        m = _CODIGO_REGLA.match(str(error))
        codigo = m.group(1) if m else "sin-codigo"
        if codigo not in codigos:
            codigos.append(codigo)
    return codigos


def _uso_por_agent_id(carpeta: Path) -> dict[str, dict]:
    return {str(u.get("agent_id")): u for u in registro.leer_uso(carpeta) if u.get("agent_id")}


def _emparejar_generaciones(eventos: list[dict], uso: dict[str, dict]) -> list[Generacion]:
    """Cada `agente_fin` cierra el `agente_inicio` más reciente sin cerrar de su (rol, capítulo) (LIFO: un
    agente que murió sin fin no absorbe el fin del reintento). Un inicio sin fin queda como generación abierta.

    Dos defensas contra lo que el registro trae de fábrica, porque el hook estampa el `agente_fin` con el
    cursor vivo y no con el estado del agente que termina:

    - Un `agent_id` no puede cerrarse dos veces. El hook emite el fin más de una vez para el mismo subagente
      (visto en tanda_2026-09-16T19-30-34: el extractor `a1adf…` cierra en el cap. 5 y diez segundos después
      vuelve a cerrar en el cap. 6). Sin esta guarda el duplicado genera una observación con el mismo `id`
      —que se deriva del `agent_id`— y el upsert de Langfuse pisa la buena con la mala: el duplicado no
      encuentra su `inicio`, así que su `startTime` cae sobre el `endTime` y la latencia queda en cero.
    - El capítulo lo pone el `inicio`, no el `fin`. Un fin que llega después de que el cursor avanzara trae el
      capítulo siguiente, y llega a inventarse capítulos que no existen (el `extractor:cap_7` de esa tanda es
      en realidad el extractor del 6). El inicio sí tiene el capítulo con el que se lanzó el agente.

    Las dos solo actúan cuando el emparejamiento directo falla, así que un registro sano pasa por aquí intacto.
    La causa está en el hook y hay que arreglarla allí; esto es lo que impide que un registro torcido se
    publique como si fuera bueno."""
    pendientes: dict[tuple, list[dict]] = {}
    generaciones: list[Generacion] = []
    orden: dict[tuple, int] = {}
    cerrados: set[str] = set()
    for e in eventos:
        if e.get("tipo") == "agente_inicio":
            pendientes.setdefault((e.get("rol"), e.get("capitulo")), []).append(e)
        elif e.get("tipo") == "agente_fin":
            agent_id = e.get("agent_id")
            if agent_id and str(agent_id) in cerrados:
                continue
            if agent_id:
                cerrados.add(str(agent_id))
            rol = e.get("rol")
            clave = (rol, e.get("capitulo"))
            if not pendientes.get(clave):
                abiertas = [k for k, v in pendientes.items() if k[0] == rol and v]
                if abiertas:
                    clave = max(abiertas, key=lambda k: pendientes[k][-1].get("ts") or "")
            inicio = pendientes[clave].pop() if pendientes.get(clave) else None
            orden[clave] = orden.get(clave, 0) + 1
            u = uso.get(str(agent_id), {})
            generaciones.append(Generacion(
                rol=rol, capitulo=inicio.get("capitulo") if inicio else e.get("capitulo"), agent_id=agent_id,
                inicio=inicio.get("ts") if inicio else None, fin=e.get("ts"),
                modelo=u.get("modelo") or e.get("modelo"),
                uso={campo: int(u.get(campo) or 0) for campo in CLAVES_USO},
                turnos=u.get("turnos", e.get("turnos")), intentos_de_validacion=e.get("intentos_de_validacion"),
                stop_reason=u.get("stop_reason", e.get("stop_reason")),
                intento=inicio.get("intento") if inicio else None,
                reextraccion=bool(inicio.get("reextraccion")) if inicio else False, orden=orden[clave],
            ))
    for clave, restantes in pendientes.items():
        for inicio in restantes:
            orden[clave] = orden.get(clave, 0) + 1
            generaciones.append(Generacion(
                rol=clave[0], capitulo=clave[1], agent_id=None, inicio=inicio.get("ts"), fin=None, modelo=None,
                uso={campo: 0 for campo in CLAVES_USO}, turnos=None, intentos_de_validacion=None, stop_reason=None,
                intento=inicio.get("intento"), reextraccion=bool(inicio.get("reextraccion")), orden=orden[clave],
            ))
    generaciones.sort(key=lambda g: (g.inicio or g.fin or ""))
    return generaciones


def _archivo_k(carpeta: Path, sub: str, rol: str, n: int | None, k: int, extension: str) -> str | None:
    """El k-ésimo archivo `NNN_<rol>_cap_<n>.<ext>` de prompts/ o retornos/, en orden de numeración."""
    patron = re.compile(rf"^\d{{3}}_{re.escape(rol)}_cap_{n if n is not None else 'x'}{re.escape(extension)}$")
    archivos = sorted(p for p in (carpeta / sub).glob("*") if patron.match(p.name)) if (carpeta / sub).exists() else []
    if k - 1 < len(archivos):
        return archivos[k - 1].read_text(encoding="utf-8", errors="replace")
    return None


def _envolver(tipo: str, cuerpo: dict) -> dict:
    """El sobre de ingesta: su `id` es único por petición (así el servicio no deduplica una reexportación);
    el `body.id` es el estable que hace upsert (§16.5)."""
    return {"id": str(uuid.uuid4()), "type": tipo, "timestamp": datetime.now(timezone.utc).isoformat(), "body": cuerpo}


def _palabras_por_capitulo(eventos: list[dict], carpeta: Path) -> dict[int, int]:
    """La última cuenta de palabras conocida de cada capítulo: del evento `validacion` del escritor (datos.palabras)
    o, si falta, de la línea de retorno `cap_N.md · N palabras · ...`."""
    palabras: dict[int, int] = {}
    for e in eventos:
        if e.get("tipo") == "validacion" and e.get("rol") == "escritor" and e.get("capitulo") is not None:
            datos = e.get("datos") or {}
            if isinstance(datos.get("palabras"), int):
                palabras[e["capitulo"]] = datos["palabras"]
            else:
                for texto in e.get("errores") or []:
                    m = re.search(r"tiene (\d+) palabras", str(texto))
                    if m:
                        palabras[e["capitulo"]] = int(m.group(1))
    retornos = carpeta / "retornos"
    if retornos.exists():
        for p in sorted(retornos.glob("*_escritor_cap_*.txt")):
            m = re.search(r"cap_(\d+)\.md\s*[·|\-–,]\s*([\d.,\s]+?)\s*palabras", p.read_text(encoding="utf-8", errors="replace"), re.IGNORECASE)
            if m:
                n = int(m.group(1))
                palabras.setdefault(n, int(re.sub(r"[^\d]", "", m.group(2)) or 0))
    return palabras


def _hubo_fin(evs: list[dict], rol: str) -> bool:
    return any(e.get("tipo") == "agente_fin" and e.get("rol") == rol for e in evs)


def _inicio_de(e: dict) -> str:
    """El instante en que empezó un evento: un `verbo` se anota al terminar con su duración en `ms`, así que su
    inicio es `ts - ms`; el resto de los eventos empiezan y terminan en su `ts`."""
    ts = str(e.get("ts") or "")
    if e.get("tipo") != "verbo" or not isinstance(e.get("ms"), int):
        return ts
    try:
        momento = datetime.fromisoformat(ts)
    except ValueError:
        return ts
    return (momento - timedelta(milliseconds=e["ms"])).isoformat(timespec="milliseconds")


def _descartes_de_borrador(carpeta: Path) -> list[tuple[str, int | None, str]]:
    """Un descarte EX-08 por cada borrador del escritor que `descartar-borrador` mandó a descartados/ (§5.1).
    Vale tanto para la tanda por CLI como para la corrida con dobles, que no pasa por el verbo."""
    descartados = carpeta / "descartados"
    if not descartados.exists():
        return []
    resultado = []
    for p in sorted(descartados.glob("*_escritor_cap_*.error.txt")):
        if "descartar-borrador" not in p.read_text(encoding="utf-8", errors="replace"):
            continue
        m = re.search(r"_escritor_cap_(\d+)_", p.name)
        ts = datetime.fromtimestamp(p.stat().st_mtime).astimezone().isoformat(timespec="milliseconds")
        resultado.append((ts, int(m.group(1)) if m else None, p.name[: -len(".error.txt")]))
    return resultado


def construir_traza(raiz: Path, carpeta: Path, *, con_cuerpos: bool = False) -> Traza:
    """Lee la carpeta de la tanda y devuelve el lote de ingesta completo, sin enviar nada."""
    tanda = carpeta.name
    eventos = registro.leer_eventos(carpeta)
    if not eventos:
        raise ConfiguracionInvalidaError(f"RF-09: {carpeta.name}/eventos.jsonl está vacío; no hay nada que exportar")
    filtro = None if con_cuerpos else FiltroPrivacidad.desde_tanda(raiz, carpeta)
    limpiar = (lambda v: v) if filtro is None else filtro.limpiar
    metadatos = _metadatos_tanda(raiz, carpeta)
    trace_id = id_traza(tanda)
    lote: list[dict] = []

    # trace = la tanda
    ts_inicio = eventos[0].get("ts")
    lote.append(_envolver("trace-create", {
        "id": trace_id, "name": tanda, "timestamp": ts_inicio, "metadata": metadatos,
        "tags": ["creador-novelas", f"specs-{metadatos.get('version_specs', VERSION_SPECS)}"],
        "version": metadatos.get("version_specs", VERSION_SPECS),
    }))

    # span = un capítulo: abarca todos los eventos con ese `capitulo` (verbos, agentes, validaciones)
    por_capitulo: dict[int, list[dict]] = {}
    # El `capitulo` de un `agente_fin` lo pone el cursor vivo y no el agente que termina, así que puede
    # nombrar un capítulo que nunca se escribió (el `cap_7` de tanda_2026-09-16T19-30-34). Un fin no abre
    # capítulo por sí solo: se suma al de un capítulo que algún otro evento haya declarado.
    declarados = {e.get("capitulo") for e in eventos
                  if isinstance(e.get("capitulo"), int) and e.get("tipo") != "agente_fin"}
    for e in eventos:
        n = e.get("capitulo")
        if isinstance(n, int) and n in declarados:
            por_capitulo.setdefault(n, []).append(e)
    capitulos = sorted(por_capitulo)
    verbos_ok = {(e.get("verbo"), e.get("capitulo")) for e in eventos if e.get("tipo") == "verbo" and e.get("resultado") == "ok"}
    spans: dict[int, str] = {}
    for n in capitulos:
        evs = por_capitulo[n]
        spans[n] = id_observacion(tanda, f"cap_{n}")
        lote.append(_envolver("span-create", {
            "id": spans[n], "traceId": trace_id, "name": f"cap_{n}",
            "startTime": min(_inicio_de(e) for e in evs), "endTime": evs[-1].get("ts"),
            "metadata": {
                "capitulo": n,
                "cerrado": ("aplicar-delta", n) in verbos_ok or _hubo_fin(evs, "extractor"),
                "corte_qa": ("cerrar-qa", n) in verbos_ok or _hubo_fin(evs, "qa"),
                "invocaciones_escritor": sum(1 for e in evs if e.get("tipo") == "agente_fin" and e.get("rol") == "escritor"),
                "validaciones_invalidas": sum(1 for e in evs if e.get("tipo") == "validacion" and not e.get("valido")),
            },
        }))

    # span anidado = un verbo determinista del bucle, con su duración real (§16.2): son el flujo; sin ellos la traza
    # enseña tres llamadas a modelo sueltas y no se ve en qué paso murió una tanda que se cortó a mitad.
    verbos_mapeados = 0
    for i, e in enumerate(eventos):
        if e.get("tipo") != "verbo" or e.get("verbo") not in VERBOS_DEL_BUCLE or not isinstance(e.get("capitulo"), int):
            continue
        verbos_mapeados += 1
        resultado = str(e.get("resultado") or "")
        cuerpo_verbo: dict[str, Any] = {
            "id": id_observacion(tanda, f"verbo/{i}"), "traceId": trace_id, "name": f"verbo:{e.get('verbo')}",
            "parentObservationId": spans.get(e["capitulo"]), "startTime": _inicio_de(e), "endTime": e.get("ts"),
            "metadata": {"verbo": e.get("verbo"), "capitulo": e["capitulo"], "args": limpiar(e.get("args")),
                         "resultado": resultado, "ms": e.get("ms")},
        }
        if resultado.startswith("error") or resultado.startswith("codigo"):
            cuerpo_verbo["level"] = "ERROR" if resultado.startswith("error") else "WARNING"
            cuerpo_verbo["statusMessage"] = resultado
        lote.append(_envolver("span-create", cuerpo_verbo))

    # generation = una invocación de subagente, con las CUATRO cifras de tokens (§16.3)
    generaciones = _emparejar_generaciones(eventos, _uso_por_agent_id(carpeta))
    for g in generaciones:
        clave = f"agente/{g.agent_id}" if g.agent_id else f"agente/{g.rol}/cap_{g.capitulo}/{g.orden}"
        g.id = id_observacion(tanda, clave)
        uso = {CLAVES_USO[campo]: g.uso[campo] for campo in CLAVES_USO}
        uso["total"] = sum(g.uso.values())
        cuerpo: dict[str, Any] = {
            "id": g.id, "traceId": trace_id, "name": f"{g.rol}:cap_{g.capitulo}",
            "parentObservationId": spans.get(g.capitulo) if g.capitulo is not None else None,
            "startTime": g.inicio or g.fin, "endTime": g.fin,
            "model": g.modelo, "usageDetails": uso,
            "metadata": {
                "rol": g.rol, "capitulo": g.capitulo, "agent_id": g.agent_id, "turnos": g.turnos,
                "intentos_de_validacion": g.intentos_de_validacion, "stop_reason": g.stop_reason,
                "intento": g.intento, "reextraccion": g.reextraccion,
                "tokens_por_campo_del_registro": dict(g.uso),
            },
        }
        if g.fin is None:
            cuerpo["level"] = "WARNING"
            cuerpo["statusMessage"] = "agente_inicio sin agente_fin: la invocación no terminó registrada"
        if con_cuerpos:
            cuerpo["input"] = _archivo_k(carpeta, "prompts", g.rol, g.capitulo, g.orden, ".md")
            cuerpo["output"] = _archivo_k(carpeta, "retornos", g.rol, g.capitulo, g.orden, ".txt")
        lote.append(_envolver("generation-create", {k: v for k, v in cuerpo.items() if v is not None}))

    # event = bloqueo de hook, fallo de autovalidación (EX-10), descarte de borrador (EX-08) y demás errores
    capitulo_en_curso: int | None = None
    total_eventos = 0
    descartes = _descartes_de_borrador(carpeta)
    for j, (ts, n_descarte, nombre_archivo) in enumerate(descartes):
        total_eventos += 1
        lote.append(_envolver("event-create", {
            "id": id_observacion(tanda, f"descarte/{j}"), "traceId": trace_id, "name": "EX-08:descarte_de_borrador",
            "startTime": ts, "level": "WARNING", "parentObservationId": spans.get(n_descarte),
            "statusMessage": f"borrador del capítulo {n_descarte} descartado para regenerar",
            "metadata": {"capitulo": n_descarte, "archivo": nombre_archivo},
        }))
    for i, e in enumerate(eventos):
        if isinstance(e.get("capitulo"), int):
            capitulo_en_curso = e["capitulo"]
        tipo = e.get("tipo")
        cuerpo_evento: dict[str, Any] | None = None
        if tipo == "hook" and e.get("decision") in ("bloqueado", "falla"):
            cuerpo_evento = {
                "name": f"hook:{e.get('id')}", "level": "WARNING", "statusMessage": limpiar(e.get("motivo") or ""),
                "metadata": {"hook": e.get("id"), "evento": e.get("evento"), "agent_type": e.get("agent_type"),
                             "agent_id": e.get("agent_id"), "accion": limpiar(e.get("accion")), "decision": e.get("decision"),
                             "detiene_tanda": e.get("detiene_tanda")},
            }
        elif tipo == "validacion" and e.get("valido") is False:
            # X-01.2: por que fallo la autovalidacion, no solo que fallo. Sin esto no se puede saber si un
            # cambio en el prompt del escritor reduce los reintentos, que son el gasto evitable de la tanda.
            # Los mensajes de error citan pasajes del manuscrito, asi que a la traza solo viajan los codigos
            # de regla y los recuentos: §16.6 prohibe que salga prosa de la novela.
            datos = e.get("datos") or {}
            cuerpo_evento = {
                "name": f"validacion:{e.get('rol')}", "level": "WARNING",
                "statusMessage": ", ".join(_reglas_incumplidas(e.get("errores") or [])) or "sin codigo de regla",
                "metadata": {"rol": e.get("rol"), "reglas": _reglas_incumplidas(e.get("errores") or []),
                             "errores": len(e.get("errores") or []),
                             "palabras": datos.get("palabras"),
                             "repeticiones_literales": datos.get("repeticiones_literales")},
            }
        elif tipo == "error":
            excepcion = str(e.get("excepcion"))
            nombre = "EX-10" if excepcion == "AutovalidacionFallidaError" else excepcion
            cuerpo_evento = {
                "name": f"error:{nombre}", "level": "ERROR", "statusMessage": limpiar(str(e.get("mensaje") or "")),
                "metadata": {"excepcion": excepcion, "verbo": e.get("verbo"), "agent_type": e.get("agent_type"),
                             "agent_id": e.get("agent_id")},
            }
        if cuerpo_evento is None:
            continue
        total_eventos += 1
        n = e.get("capitulo") if isinstance(e.get("capitulo"), int) else capitulo_en_curso
        cuerpo_evento.update({
            "id": id_observacion(tanda, f"evento/{i}"), "traceId": trace_id, "startTime": e.get("ts"),
            "parentObservationId": spans.get(n) if n is not None else None,
        })
        cuerpo_evento["metadata"] = {k: v for k, v in cuerpo_evento["metadata"].items() if v is not None}
        lote.append(_envolver("event-create", {k: v for k, v in cuerpo_evento.items() if v is not None}))

    # scores (§16.4): por corte de QA cerrado en la tanda, y los de la tanda entera
    puntuaciones: dict[str, Any] = {}
    cortes = sorted({e.get("capitulo") for e in eventos if isinstance(e.get("capitulo"), int) and (
        (e.get("tipo") == "verbo" and e.get("verbo") == "cerrar-qa" and e.get("resultado") == "ok")
        or (e.get("tipo") == "agente_fin" and e.get("rol") == "qa"))})
    ts_fin = eventos[-1].get("ts")
    for n in cortes:
        reporte = None
        try:
            reporte = repo.leer_reporte_qa(raiz, n)
        except HarnessError:
            reporte = None
        if reporte is None:
            continue
        conteo = reporte.conteo_por_tipo()
        valores = {"qa_contradicciones": (conteo["contradiccion"], "NUMERIC"), "qa_repeticiones": (conteo["repeticion"], "NUMERIC"),
                   "qa_pasa": (0 if reporte.tiene_contradicciones else 1, "BOOLEAN")}
        for nombre, (valor, tipo_dato) in valores.items():
            puntuaciones[f"{nombre}[cap_{n}]"] = valor
            lote.append(_envolver("score-create", {
                "id": id_puntuacion(tanda, f"{nombre}/cap_{n}"), "traceId": trace_id, "observationId": spans.get(n),
                "name": nombre, "value": valor, "dataType": tipo_dato, "comment": f"corte de QA en el capítulo {n}",
            }))
    objetivo = metadatos.get("palabras_por_capitulo")
    palabras = _palabras_por_capitulo(eventos, carpeta)
    if objetivo and palabras:
        desvio = max(abs(p - objetivo) / objetivo for p in palabras.values())
        puntuaciones["desvio_longitud"] = round(desvio, 4)
        lote.append(_envolver("score-create", {
            "id": id_puntuacion(tanda, "desvio_longitud"), "traceId": trace_id, "name": "desvio_longitud",
            "value": round(desvio, 4), "dataType": "NUMERIC",
            "comment": f"mayor desvío relativo respecto de {objetivo} palabras entre {len(palabras)} capítulos",
        }))
    puntuaciones["borradores_descartados"] = len(descartes)
    lote.append(_envolver("score-create", {
        "id": id_puntuacion(tanda, "borradores_descartados"), "traceId": trace_id, "name": "borradores_descartados",
        "value": len(descartes), "dataType": "NUMERIC", "comment": "borradores descartados para regenerar (EX-08) en la tanda",
    }))
    return Traza(tanda=tanda, id=trace_id, lote=lote, generaciones=generaciones, capitulos=capitulos,
                 eventos=total_eventos, puntuaciones=puntuaciones, con_cuerpos=con_cuerpos, metadatos=metadatos)


# ---------- envío ----------

class Cliente(Protocol):
    def enviar(self, lote: list[dict]) -> dict: ...


class ClienteHTTP:
    """POST {host}/api/public/ingestion con autenticación básica (clave pública:clave secreta)."""

    def __init__(self, credenciales: Credenciales, tiempo_maximo: float = 30.0):
        self.credenciales = credenciales
        self.tiempo_maximo = tiempo_maximo

    def enviar(self, lote: list[dict]) -> dict:
        cuerpo = json.dumps({"batch": lote, "metadata": {"origen": "creador-novelas exportar-traza", "specs": VERSION_SPECS}},
                            ensure_ascii=False).encode("utf-8")
        token = base64.b64encode(f"{self.credenciales.clave_publica}:{self.credenciales.clave_secreta}".encode("utf-8")).decode("ascii")
        peticion = urlrequest.Request(
            self.credenciales.host + RUTA_INGESTA, data=cuerpo, method="POST",
            headers={"Content-Type": "application/json", "Authorization": f"Basic {token}", "User-Agent": "creador-novelas/exportar-traza"},
        )
        try:
            with urlrequest.urlopen(peticion, timeout=self.tiempo_maximo) as respuesta:
                texto = respuesta.read().decode("utf-8", errors="replace")
                estado = respuesta.status
        except urlerror.HTTPError as e:
            detalle = e.read().decode("utf-8", errors="replace")[:500]
            raise ExportacionError(f"RF-09: el servicio respondió {e.code} al ingerir el lote: {detalle}") from e
        except (urlerror.URLError, TimeoutError, OSError) as e:
            raise ExportacionError(f"RF-09: no se pudo conectar con {self.credenciales.host}: {e}") from e
        try:
            datos = json.loads(texto) if texto.strip() else {}
        except json.JSONDecodeError:
            datos = {"crudo": texto[:500]}
        datos["_estado_http"] = estado
        return datos


def _partir_en_lotes(eventos: list[dict]) -> list[list[dict]]:
    lotes: list[list[dict]] = []
    actual: list[dict] = []
    tamano = 0
    for e in eventos:
        peso = len(json.dumps(e, ensure_ascii=False).encode("utf-8"))
        if actual and (len(actual) >= MAX_EVENTOS_POR_LOTE or tamano + peso > MAX_BYTES_POR_LOTE):
            lotes.append(actual)
            actual, tamano = [], 0
        actual.append(e)
        tamano += peso
    if actual:
        lotes.append(actual)
    return lotes


@dataclass
class ResultadoExportacion:
    traza: Traza
    lotes: int
    aceptados: int
    errores: list[dict] = field(default_factory=list)
    volcado: Path | None = None


def exportar(raiz: Path, carpeta: Path, cliente: Cliente | None, *, con_cuerpos: bool = False,
             volcar: Path | None = None) -> ResultadoExportacion:
    """Construye la traza y la publica en lotes. Con `volcar`, además deja el lote completo en un archivo local.
    Sin cliente (solo volcado) no sale nada de la máquina."""
    traza = construir_traza(raiz, carpeta, con_cuerpos=con_cuerpos)
    if volcar is not None:
        volcar.parent.mkdir(parents=True, exist_ok=True)
        volcar.write_text(json.dumps({"tanda": traza.tanda, "trace_id": traza.id, "batch": traza.lote}, ensure_ascii=False, indent=2) + "\n",
                          encoding="utf-8")
    if cliente is None:
        return ResultadoExportacion(traza=traza, lotes=0, aceptados=0, volcado=volcar)
    lotes = _partir_en_lotes(traza.lote)
    aceptados = 0
    errores: list[dict] = []
    for lote in lotes:
        respuesta = cliente.enviar(lote)
        aceptados += len(respuesta.get("successes") or [])
        errores.extend(respuesta.get("errors") or [])
    if errores:
        raise ExportacionError(f"RF-09: el servicio rechazó {len(errores)} de {len(traza.lote)} eventos; el primero: "
                               f"{json.dumps(errores[0], ensure_ascii=False)[:400]}")
    return ResultadoExportacion(traza=traza, lotes=len(lotes), aceptados=aceptados, errores=errores, volcado=volcar)


# ---------- resumen legible ----------

def tabla_consumo(traza: Traza) -> str:
    """Las cuatro cifras por invocación, para mirar el registro sin abrir Langfuse (§16.3)."""
    filas = [f"{'rol':<10}{'cap':>4}  {'modelo':<28}{'entrada':>9}{'salida':>8}{'cache_lec':>11}{'cache_cre':>11}{'turnos':>7}"]
    for g in traza.generaciones:
        filas.append(f"{g.rol:<10}{str(g.capitulo):>4}  {str(g.modelo or '?'):<28}{g.uso['tokens_entrada']:>9}{g.uso['tokens_salida']:>8}"
                     f"{g.uso['tokens_cache_lectura']:>11}{g.uso['tokens_cache_creacion']:>11}{str(g.turnos if g.turnos is not None else '?'):>7}")
    return "\n".join(filas)
