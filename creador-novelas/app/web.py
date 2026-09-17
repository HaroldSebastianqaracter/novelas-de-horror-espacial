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

from app.agents import escritor
from app.state import repository as repo
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
# `--salida` va explícito aunque §8.2 diga que tiene valor por defecto: el CLI todavía lo exige.
# Pasarlo aquí funciona con las dos versiones del verbo, así que no hay que esperar a nadie.
VERBOS: dict[str, list[str]] = {"ensamblar": ["ensamblar", "--salida", "08_entrega/novela.md"],
                                # Paso 3 de RF-07.4: cierra la resolucion y devuelve el manifiesto a activo.
                                "cerrar-resolucion": ["resolver", "--cerrar"]}

# `reanudar` es el unico verbo que la pantalla arma en el momento, porque lleva dentro el nombre del
# reporte pendiente y ese lo dice el manifiesto. Es `resolver --sin-cambios`, es decir: acepto el
# veredicto tal como esta y sigo. No existe una variante desde la web que afirme haber corregido
# capitulos, porque el harness no puede comprobarlo y seria una mentira anotada en el registro.
FASES_DINAMICAS = ("reanudar",)

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
    if fase not in SKILLS and fase not in VERBOS and fase not in FASES_DINAMICAS:
        raise ValueError(f"Fase desconocida: {fase}")
    _cerrar_proceso()
    if proceso_vivo():
        raise RuntimeError("Ya hay una ejecución en marcha. Una sola cada vez: dos sobre el mismo "
                           "estado lo corromperían.")

    if fase == "reanudar":
        m = checkpoint.leer_manifest(raiz)
        pendiente = getattr(m, "reporte_qa_pendiente", None) if m else None
        if getattr(m, "estado", None) != "pausado_por_qa" or not pendiente:
            raise RuntimeError("No hay ninguna pausa por QA que reanudar.")
        cmd = [_python(raiz), "-m", "app", "resolver", "--reporte", pendiente, "--sin-cambios"]
    elif fase in VERBOS:
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

    # Titulo de la novela y del capitulo en curso: la consola los enseña y salen del mismo sitio
    # que usa `ensamblar`, para que la portada de la web y la del manuscrito no discrepen.
    premisa = repo.leer_premisa(raiz) or ""
    from app.cli import _titulo_desde_premisa  # tarde: cli importa web, y al reves seria un ciclo
    outline = _json(rutas.capitulos)
    entradas = outline.get("root") if isinstance(outline, dict) else outline
    entrada = next((e for e in (entradas if isinstance(entradas, list) else [])
                    if isinstance(e, dict) and e.get("num") == activo), {})

    return {
        "estado": vista,
        "titulo": _titulo_desde_premisa(premisa),
        "logline": next((l.split(":", 1)[1].strip() for l in premisa.splitlines()
                         if l.lower().startswith("logline:")), None),
        "titulo_capitulo": entrada.get("titulo"),
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
    pref = f"Capítulo {cap}: " if isinstance(cap, int) else ""
    rol = ev.get("rol") or "agente"
    if tipo == "agente_inicio":
        return f"{pref}{rol} en marcha"
    if tipo == "agente_fin":
        turnos = ev.get("turnos")
        return f"{pref}{rol} terminado" + (f" en {turnos} turnos" if turnos else "")
    if tipo == "validacion":
        if ev.get("valido"):
            # Solo las cifras: los booleanos del artefacto ("tiene_contradicciones: True") no se leen
            # bien en una línea de bitácora y el estado ya lo dice la insignia de la cabecera.
            datos = {k: v for k, v in (ev.get("datos") or {}).items() if isinstance(v, int) and not isinstance(v, bool)}
            detalle = ", ".join(f"{v} {k}" for k, v in datos.items())
            return f"{pref}{rol} validado" + (f": {detalle}" if detalle else "")
        return f"{pref}validación rechazada: {'; '.join(ev.get('errores') or []) or 'sin detalle'}"
    if tipo == "verbo":
        # El resultado correcto es el caso normal y no aporta nada escribirlo en cada línea;
        # lo que hay que ver de un vistazo es lo que NO salió bien.
        res = ev.get("resultado")
        return f"{pref}{ev.get('verbo')}" + (f", {res}" if res and res != "ok" else "")
    if tipo == "error":
        return f"{pref}error: {ev.get('mensaje') or ev.get('error') or 'sin mensaje'}"
    if tipo == "hook" and ev.get("decision") != "permitido":
        return f"{ev.get('id', 'hook')} bloqueó {_corto(ev.get('motivo') or ev.get('accion', ''))}"
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


# ---------- lectura (RF-UI-05): la novela escrita, capítulo a capítulo ----------
#
# Esta capa lee 05_manuscrito/ y eso puede chirriar contra INV-01 e INV-08, así que conviene dejar
# escrito por qué no lo es. INV-01 prohíbe que el **escritor** relea el manuscrito, e INV-08 que lo
# haga el **orquestador**: los dos son invariantes sobre agentes, porque un agente que lee lo ya
# escrito lo imita. H-09 los hace cumplir bloqueando lecturas por `agent_type`. Aquí no hay ningún
# agente: es el servidor enseñándole al usuario lo que ha pagado, que es RF-UI y el motivo de que
# exista `ensamblar`. Ningún texto de esta capa vuelve a entrar en un prompt.

def indice(raiz: Path) -> dict[str, Any]:
    """La cinta de capítulos: cuáles están escritos, cuál cortó QA y dónde se quedó la novela."""
    rutas = Rutas(raiz)
    m = checkpoint.leer_manifest(raiz)
    novela = _json(rutas.novela_json)
    outline = _json(rutas.capitulos)
    entradas = outline.get("root") if isinstance(outline, dict) else outline
    entradas = entradas if isinstance(entradas, list) else []
    titulos = {e.get("num"): e.get("titulo") for e in entradas if isinstance(e, dict)}

    cerrados = m.ultimo_capitulo_cerrado if m else 0
    total = novela.get("total_capitulos") or len(entradas) or 0
    hallazgos = set(_capitulos_con_hallazgos(rutas))
    # El titulo y el logline viven en la premisa (fase 1), no en la configuracion: los decide el
    # harness al destilar, no el usuario al encargar. Se usa el mismo extractor que `ensamblar`
    # para que la portada de la web y la del manuscrito no puedan discrepar.
    premisa = repo.leer_premisa(raiz) or ""
    from app.cli import _titulo_desde_premisa  # tarde: cli importa web, y al reves seria un ciclo
    titulo = _titulo_desde_premisa(premisa)
    logline = next((l.split(":", 1)[1].strip() for l in premisa.splitlines()
                    if l.lower().startswith("logline:")), None)

    capitulos = []
    for n in range(1, total + 1):
        escrito = rutas.capitulo(n).exists()
        capitulos.append({
            "num": n,
            # El título de la escaleta es una previsión; el capítulo escrito puede no haberlo usado.
            # Se enseña igual, porque es lo único que hay: el escritor no escribe encabezados (EX-07).
            "titulo": titulos.get(n),
            "escrito": escrito,
            "cerrado": n <= cerrados,
            "corte_qa": n in hallazgos,
        })
    return {
        "titulo": titulo or "Sin título",
        "logline": logline,
        "total_capitulos": total,
        "capitulos_cerrados": cerrados,
        "estado": getattr(m, "estado", None) if m else None,
        "capitulos": capitulos,
    }


def _hechos_de(raiz: Path, n: int) -> list[dict[str, Any]]:
    """Los hechos que el extractor fijó EN este capítulo, con el conflicto de QA si lo hay.

    Un hecho superado por otro posterior se marca en vez de ocultarse: que un dato dejara de ser
    cierto es parte de lo que el lector está viendo, no ruido.
    """
    rutas = Rutas(raiz)
    crudo = _json(rutas.continuidad)
    hechos = crudo.get("root") if isinstance(crudo, dict) else crudo
    hechos = hechos if isinstance(hechos, list) else []

    en_conflicto: dict[int, str] = {}
    if rutas.reportes_qa.is_dir():
        for informe in sorted(rutas.reportes_qa.glob("*.json")):
            datos = _json(informe)
            for h in datos.get("hallazgos") or []:
                if h.get("tipo") == "contradiccion" and isinstance(h.get("cap_origen"), int):
                    en_conflicto.setdefault(h["cap_origen"], h.get("descripcion") or "")

    salida = []
    for h in hechos:
        if not isinstance(h, dict) or h.get("cap_origen") != n:
            continue
        salida.append({
            "sujeto": h.get("sujeto"),
            "categoria": h.get("categoria"),
            "hecho": h.get("hecho"),
            "superado_por": h.get("superado_por"),
            "conflicto": en_conflicto.get(n),
        })
    return salida


def capitulo(raiz: Path, n: int) -> dict[str, Any] | None:
    """El texto de un capítulo con lo que el extractor fijó al margen. `None` si aún no existe."""
    rutas = Rutas(raiz)
    archivo = rutas.capitulo(n)
    if not archivo.is_file():
        return None
    texto = archivo.read_text(encoding="utf-8")
    outline = _json(rutas.capitulos)
    entradas = outline.get("root") if isinstance(outline, dict) else outline
    entrada = next((e for e in (entradas if isinstance(entradas, list) else [])
                    if isinstance(e, dict) and e.get("num") == n), {})
    return {
        "num": n,
        "titulo": entrada.get("titulo"),
        "locacion": entrada.get("locacion"),
        "palabras": escritor.contar_palabras(texto),
        "texto": texto,
        "hechos": _hechos_de(raiz, n),
    }


# ---------- coste (RF-UI): lo que llevas gastado, contado en casa ----------

def _precios(raiz: Path) -> dict[str, Any]:
    return _json(raiz / "config" / "precios.json")


def coste(raiz: Path) -> dict[str, Any]:
    """Suma en dinero todo el uso registrado, recorriendo las tandas de 07_registro/.

    Los precios salen de config/precios.json, derivados de los `costDetails` de Langfuse. Un modelo
    sin precio NO se estima: se cuenta aparte y la web lo dice, porque un coste incompleto que se
    presenta como completo es peor que no enseñar ninguno.
    """
    tabla = _precios(raiz)
    por_millon = tabla.get("por_millon") or {}
    total = 0.0
    tokens = 0
    sin_precio: set[str] = set()
    por_rol: dict[str, float] = {}

    registro = Rutas(raiz).registro
    # Todas las carpetas con uso, no solo las `tanda_*`: el preludio (fases 0 a 3) tambien cuesta.
    carpetas = sorted(c for c in registro.iterdir() if (c / "uso.jsonl").is_file()) if registro.is_dir() else []
    vistos: set[str] = set()
    for carpeta in carpetas:
        for fila in _lineas_jsonl(carpeta / "uso.jsonl"):
            # Mismo deduplicado que el exportador de trazas: H-10 anota el fin de un subagente mas de
            # una vez, y sin esta guarda la misma invocacion se cobra dos veces.
            agente = str(fila.get("agent_id") or "")
            if agente and agente in vistos:
                continue
            if agente:
                vistos.add(agente)
            modelo = fila.get("modelo")
            campos = {k: int(fila.get(k) or 0) for k in
                      ("tokens_entrada", "tokens_salida", "tokens_cache_lectura", "tokens_cache_creacion")}
            tokens += sum(campos.values())
            precio = por_millon.get(modelo)
            if not precio:
                if modelo:
                    sin_precio.add(str(modelo))
                continue
            gasto = sum(campos[k] * (precio.get(k) or 0) / 1_000_000 for k in campos)
            total += gasto
            por_rol[fila.get("rol") or "?"] = por_rol.get(fila.get("rol") or "?", 0.0) + gasto

    return {
        "moneda": tabla.get("moneda") or "USD",
        "total": round(total, 4),
        "tokens": tokens,
        "por_rol": {k: round(v, 4) for k, v in sorted(por_rol.items(), key=lambda x: -x[1])},
        "modelos_sin_precio": sorted(sin_precio),
        "carpetas_con_uso": len(carpetas),
    }
