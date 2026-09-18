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
import re
import os
import shutil
import subprocess
import time
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from app import registro
from app.agents import escritor
from app.state import repository as repo
from app.config import CAMPOS_EJECUCION, CAMPOS_NOVELA, cargar_config
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
    "resolver-qa": "/resolver-qa",
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
FASES_DINAMICAS = ("reanudar", "corregir")

# Modelo del orquestador de las fases con agentes. No redacta: ejecuta verbos, lee la línea
# RESULTADO y despacha subagentes (INV-08). Cada subagente declara el suyo en `.claude/agents/`,
# de modo que este valor no influye en con qué modelo se escribe la novela.
# El entorno puede fijarlo para una corrida entera sin tocar el código, que es como el loop de
# velocidad prueba una vuelta: `HARNESS_MODELO_ORQUESTADOR=sonnet`.
MODELO_ORQUESTADOR = os.environ.get("HARNESS_MODELO_ORQUESTADOR") or "opus"
# El mismo modelo con su identificador completo. `--model` acepta el alias, pero `config/precios.json`
# y Langfuse se llevan por el nombre canónico: anotar «opus» en `uso.jsonl` dejaba el consumo del
# orquestador a 0,00 $ en el informe, que es peor que no contarlo, porque parece gratis.
_ID_POR_ALIAS = {"opus": "claude-opus-5", "sonnet": "claude-sonnet-5", "haiku": "claude-haiku-4-5-20251001"}
MODELO_ORQUESTADOR_ID = _ID_POR_ALIAS.get(MODELO_ORQUESTADOR, MODELO_ORQUESTADOR)

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


def git_bash() -> str | None:
    """Ruta de `bash.exe` de Git para Windows, que es con lo que Claude Code ejecuta los hooks.

    En Windows los comandos de hook corren a través de Git Bash. Si no se encuentra, los hooks **no
    fallan ruidosamente: no corren**, y la tanda entera se ejecuta sin la valla de invariantes (H-06
    confina las escrituras, H-10 registra el uso, H-11 confina la terminal). Pasó de verdad: una tanda
    de 28 minutos y 8 $ salió sin un solo evento de hook y nada lo delató.

    Fuera de Windows no hace falta: los hooks corren en el shell del sistema.
    """
    if os.name != "nt":
        return None
    puesto = os.environ.get("CLAUDE_CODE_GIT_BASH_PATH")
    if puesto and Path(puesto).exists():
        return puesto
    # Desde el git del PATH: `<raiz>/cmd/git.exe` y `<raiz>/bin/git.exe` son las dos disposiciones.
    git = shutil.which("git")
    if git:
        for padre in Path(git).resolve().parents[:2]:
            candidato = padre / "bin" / "bash.exe"
            if candidato.exists():
                return str(candidato)
    local = os.environ.get("LOCALAPPDATA", "")
    for c in (Path(r"C:\Program Files\Git\bin\bash.exe"),
              Path(local) / "Programs" / "Git" / "bin" / "bash.exe" if local else None):
        if c is not None and c.exists():
            return str(c)
    return None


def entorno_de_lanzamiento() -> dict[str, str]:
    """El entorno del proceso `claude`, con Git Bash señalado para que los hooks corran (RF-08.5).

    Se resuelve acá y no como variable de sistema para que funcione en cualquier máquina que clone el
    repositorio, sin depender de que alguien se acuerde de exportarla.
    """
    entorno = dict(os.environ)
    bash = git_bash()
    if bash:
        entorno["CLAUDE_CODE_GIT_BASH_PATH"] = bash
    return entorno


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
    _anotar_coste_de_fase(_EN_CURSO.get("raiz"), fin["fase"], _EN_CURSO.get("log"),
                          _EN_CURSO.get("desde"))
    _publicar_traza(_EN_CURSO.get("raiz"))
    _EN_CURSO.clear()
    _EN_CURSO["ultimo"] = fin
    return fin


# Las que no despachan subagentes: su coste entero es de la sesión y va a `fases.jsonl`.
CON_SUBAGENTES = ("escribir-tanda", "resolver-qa")
SIN_SUBAGENTES = tuple(f for f in SKILLS if f not in CON_SUBAGENTES)

# Qué campo del resumen de `claude -p` corresponde a cada columna de `uso.jsonl`.
_CAMPOS_USO = {"tokens_entrada": "input_tokens", "tokens_salida": "output_tokens",
               "tokens_cache_lectura": "cache_read_input_tokens",
               "tokens_cache_creacion": "cache_creation_input_tokens"}


def _uso_del_orquestador(raiz: Path, datos: dict) -> dict[str, int]:
    """Lo que consumió la sesión que orquesta, sin lo que ya anotaron sus subagentes.

    El resumen de `claude -p` viene agregado: incluye a la sesión y a todos los subagentes que
    despachó. H-10 ya anotó a los subagentes uno por uno, así que publicar el total entero los
    contaría dos veces. La resta deja lo que gastó el orquestador por su cuenta, que hasta ahora no
    aparecía en ninguna parte: en la tanda del 18/09 eran 4,21 $ de los 5,52 $ que costó de verdad, y
    Langfuse enseñaba 1,31 $ con toda confianza.
    """
    total = datos.get("usage") or {}
    ya_contado = {c: 0 for c in _CAMPOS_USO}
    for u in registro.leer_uso(registro.dir_actual(raiz)):
        for columna in _CAMPOS_USO:
            ya_contado[columna] += int(u.get(columna) or 0)
    return {columna: max(0, int(total.get(origen) or 0) - ya_contado[columna])
            for columna, origen in _CAMPOS_USO.items()}


def _anotar_coste_de_fase(raiz: Path | None, fase: str | None, log: str | None,
                          desde: float | None = None) -> None:
    """Guarda lo que costó una fase lanzada desde la pantalla. Nunca hace fallar el cierre.

    Deja dos rastros: la línea de `fases.jsonl` que alimenta el gasto de la pantalla, y --esto es lo
    nuevo-- el consumo del orquestador como una invocación más en `uso.jsonl`, con su `agente_inicio`
    y su `agente_fin`, para que el exportador lo publique junto a los agentes (§16.3). Sin ello el
    preludio entero no existía en Langfuse y cada tanda declaraba una cuarta parte de su coste.
    """
    if not raiz or not fase or not log:
        return
    if fase in VERBOS or fase in FASES_DINAMICAS:
        # Un verbo del CLI no deja el resumen JSON de `claude -p`: su log es texto. Intentar leerlo
        # como JSON solo servía para escupir «no se pudo anotar el coste de reanudar» en cada pausa.
        return
    try:
        datos = json.loads(Path(log).read_text(encoding="utf-8"))
        uso = datos.get("usage") or {}
        if fase in SIN_SUBAGENTES:
            fila = {"ts": datetime.now().astimezone().isoformat(timespec="milliseconds"),
                    "fase": fase, "coste_usd": float(datos.get("total_cost_usd") or 0),
                    "turnos": datos.get("num_turns"),
                    # El reloj de pared de la fase. Sin él, `fases.jsonl` solo decía cuándo terminó
                    # cada una, y la duración de la primera no se podía deducir de nada.
                    "segundos": round(time.time() - desde, 1) if desde else None,
                    "tokens": sum(int(uso.get(k) or 0) for k in _CAMPOS_USO.values())}
            destino = Rutas(raiz).registro / "fases.jsonl"
            destino.parent.mkdir(parents=True, exist_ok=True)
            with destino.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(fila, ensure_ascii=False) + "\n")

        propio = _uso_del_orquestador(raiz, datos)
        if not any(propio.values()):
            return
        agent_id = f"orq-{fase}-{int(desde or time.time())}"
        inicio = (datetime.fromtimestamp(desde).astimezone().isoformat(timespec="milliseconds")
                  if desde else None)
        if inicio:
            registro.evento(raiz, "agente_inicio", rol="orquestador", capitulo=None,
                            agent_id=agent_id, fase=fase, ts=inicio)
        registro.evento(raiz, "agente_fin", rol="orquestador", capitulo=None, agent_id=agent_id,
                        fase=fase, turnos=datos.get("num_turns"), modelo=MODELO_ORQUESTADOR_ID)
        with registro.ruta_uso(raiz).open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"rol": "orquestador", "capitulo": None, "fase": fase,
                                 "modelo": MODELO_ORQUESTADOR_ID, **propio,
                                 "turnos": datos.get("num_turns"), "agent_id": agent_id,
                                 "stop_reason": datos.get("subtype")}, ensure_ascii=False) + "\n")
    except Exception as e:  # noqa: BLE001
        print(f"[registro] no se pudo anotar el coste de {fase}: {e}")


NOMBRE_DE_FASE = {
    "destilar-estilo": "Destilando el estilo", "generar-premisa": "Generando la premisa",
    "generar-sinopsis": "Generando la sinopsis", "generar-escaleta": "Generando la escaleta",
    "inicializar-estado": "Inicializando el estado", "escribir-tanda": "Escribiendo la tanda",
    "ensamblar": "Montando el manuscrito", "reanudar": "Reanudando", "cerrar-resolucion": "Cerrando la resolución",
}


def _ultimo_paso(raiz: Path) -> str | None:
    """Lo último que tocó la fase en marcha, para que se vea que avanza.

    Las fases del preludio no despachan subagentes, así que el plano no tenía nada que encender y la
    pantalla se quedaba muda. Pero sí dejan rastro: cada herramienta que usan pasa por un hook, y de
    ahí sale una línea legible sin leer una sola palabra de la novela.
    """
    carpeta = registro.dir_actual(raiz)
    for ev in reversed(_lineas_jsonl(carpeta / "eventos.jsonl", limite=60)):
        if ev.get("tipo") == "hook" and ev.get("accion"):
            return _corto(ev["accion"], tope=48)
        if ev.get("tipo") == "verbo" and ev.get("verbo"):
            return str(ev["verbo"])
    return None


def _fase_en_curso(raiz: Path) -> dict[str, Any]:
    """La fase que lanzó esta pantalla, si sigue viva: nombre, segundos y último paso."""
    proc = _EN_CURSO.get("proc")
    fase = _EN_CURSO.get("fase")
    if proc is None or fase is None or proc.poll() is not None:
        return {"fase_en_curso": None, "fase_nombre": None, "fase_segundos": None, "fase_paso": None}
    return {
        "fase_en_curso": fase,
        "fase_nombre": NOMBRE_DE_FASE.get(fase, fase),
        "fase_segundos": int(time.time() - float(_EN_CURSO.get("desde") or time.time())),
        "fase_paso": _ultimo_paso(raiz),
    }


_ULTIMA_EXPORTACION: dict[str, Any] = {}


def _publicar_traza(raiz: Path | None) -> None:
    """Publica en Langfuse el registro de la fase recién terminada, si se puede y si se quiere (RF-09).

    Era un paso manual y por eso no había nada que mirar salvo que alguien se acordara. Se hace aquí,
    al cerrar la fase y nunca dentro de ella (§16): la tanda ya terminó, así que publicar no compite
    con nada. Tres condiciones, y si alguna falta simplemente no se publica:

    - `exportar_trazas` en `config/ejecucion.json`. La traza sale de la máquina, así que se apaga.
    - Credenciales en el entorno (§16.7). Sin ellas ni se intenta.
    - Nunca con cuerpos: viajan métricas y códigos de regla, jamás la prosa de la novela (§16.6).

    Corre en un hilo aparte y se traga cualquier fallo: la observabilidad no puede tumbar el cierre de
    una fase ni dejar la pantalla esperando a que responda un servicio ajeno.
    """
    if raiz is None:
        return

    def _trabajo() -> None:
        try:
            from app import observabilidad as obs
            if not cargar_config(raiz).exportar_trazas:
                return
            cliente = obs.ClienteHTTP(obs.credenciales_desde_entorno())
            carpeta = registro.dir_actual(raiz)  # preludio o tanda en curso, lo que toque
            r = obs.exportar(raiz, carpeta, cliente, con_cuerpos=False)
            _ULTIMA_EXPORTACION.update({"tanda": r.traza.tanda, "trace_id": r.traza.id,
                                        "objetos": r.aceptados, "error": None})
            print(f"[langfuse] {r.traza.tanda} -> {r.traza.id} ({r.aceptados} objetos)")
        except Exception as e:  # noqa: BLE001
            _ULTIMA_EXPORTACION.update({"error": str(e)[:200]})
            print(f"[langfuse] no se publicó la traza: {str(e)[:200]}")

    threading.Thread(target=_trabajo, daemon=True, name="publicar-traza").start()


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
    elif fase == "corregir":
        # La otra salida de una pausa de QA, y la única que arregla algo: marca el capítulo del corte
        # para rehacerlo. Después va `/resolver-qa`, que ahora manda al escritor a reescribirlo con el
        # hallazgo delante, y al final `resolver --cerrar`.
        m = checkpoint.leer_manifest(raiz)
        pendiente = getattr(m, "reporte_qa_pendiente", None) if m else None
        if getattr(m, "estado", None) != "pausado_por_qa" or not pendiente:
            raise RuntimeError("No hay ninguna pausa por QA que corregir.")
        cmd = [_python(raiz), "-m", "app", "resolver", "--reporte", pendiente,
               "--capitulos", pendiente.rsplit("_", 1)[-1]]
    elif fase in VERBOS:
        cmd = [_python(raiz), "-m", "app", *VERBOS[fase]]
    else:
        exe = ejecutable_claude()
        if exe is None:
            raise RuntimeError("No encuentro el ejecutable `claude`. La pantalla no puede lanzar fases "
                               "sin él; desde la terminal siguen funcionando igual.")
        # Sin Git Bash los hooks no corren y la fase se ejecutaría sin la valla de invariantes. Antes
        # eso pasaba en silencio; ahora no se lanza. Vale más una fase que no arranca que una tanda de
        # media hora sin H-06, H-10 ni H-11.
        if os.name == "nt" and git_bash() is None:
            raise RuntimeError(
                "No encuentro Git Bash (`bash.exe`), y en Windows Claude Code ejecuta los hooks con él. "
                "Sin hooks la tanda correría sin sus invariantes (H-06, H-10, H-11) y sin registro de "
                "uso, así que no se lanza. Instalá Git para Windows o apuntá CLAUDE_CODE_GIT_BASH_PATH "
                "a tu `bash.exe`."
            )
        # El prompt es el cuerpo del SKILL.md con sus directivas ya resueltas, no `/nombre-de-skill`:
        # en modo `-p` un comando con barra no ejecuta nada (ver `prompt_de_fase`).
        prompt, herramientas = prompt_de_fase(raiz, fase)
        # `--permission-prompts none` deniega en vez de quedarse esperando una respuesta que no llega
        # (§15.4), asi que hay que autorizar a mano lo que la fase necesita; se toma de su propio
        # `allowed-tools`, para que la pantalla no pueda conceder mas de lo que la skill declara.
        # Nunca `--bare`: saltaria hooks, subagentes, skills y CLAUDE.md.
        # El orquestador no escribe prosa: llama verbos, lee la línea RESULTADO y despacha subagentes
        # (INV-08). Sin fijar modelo heredaba el de la cuenta, y en la tanda del 17/09 eso fueron
        # 5,76 $ de 8,05 -el 72 %- para un trabajo mecánico, más que todo lo que costó escribir la
        # novela. Se fija explícitamente; cada subagente declara el suyo en .claude/agents/, así que
        # esto no toca con qué modelo se escribe el texto.
        cmd = [exe, "-p", prompt, "--output-format", "json", "--permission-prompts", "none",
               "--model", MODELO_ORQUESTADOR, "--allowed-tools", *herramientas]

    log = raiz / ".tanda" / "ultimo_lanzamiento.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    fh = log.open("wb")
    proc = subprocess.Popen(cmd, cwd=str(raiz), stdout=fh, stderr=subprocess.STDOUT,
                            stdin=subprocess.DEVNULL, env=entorno_de_lanzamiento())
    _EN_CURSO.clear()
    _EN_CURSO.update({"proc": proc, "fase": fase, "desde": time.time(), "log": str(log), "raiz": raiz})
    return {"lanzada": fase, "pid": proc.pid, "log": str(log)}


def ejecutar_fase(raiz: Path, fase: str, *, tope_s: float = 3600, latido: float = 2.0) -> dict[str, Any]:
    """Lanza una fase y espera a que termine. La versión de un paso de lo que la pantalla hace en dos.

    La pantalla lanza y vuelve enseguida, porque tiene a alguien mirando que pregunta por el estado.
    Una corrida encadenada no tiene a nadie, así que necesita esperar aquí mismo --y por el mismo
    camino, no por uno paralelo: si la corrida midiera un lanzamiento distinto del que usa el usuario,
    estaría midiendo otra cosa.

    `tope_s` es el seguro: una fase colgada se lleva por delante la noche entera si nadie la corta.
    """
    inicio = time.monotonic()
    lanzada = lanzar_fase(raiz, fase)
    while proceso_vivo():
        if time.monotonic() - inicio > tope_s:
            proc = _EN_CURSO.get("proc")
            if proc is not None:
                proc.kill()
            _cerrar_proceso()
            raise TimeoutError(f"la fase {fase} pasó de {tope_s / 60:.0f} min sin terminar y se cortó")
        time.sleep(latido)
    fin = _cerrar_proceso() or {}
    return {**lanzada, **fin, "segundos": round(time.monotonic() - inicio, 1)}


def _python(raiz: Path) -> str:
    venv = raiz / ".venv" / "Scripts" / "python.exe"
    if venv.exists():
        return str(venv)
    venv = raiz / ".venv" / "bin" / "python"
    return str(venv) if venv.exists() else "python"


# ------------------------------------------------------------------------------------- estado

def _agentes_activos(eventos: list[dict[str, Any]]) -> list[tuple[str, str | None, int | None]]:
    """Los agentes que están trabajando **ahora**, para encender su cubierta en el plano.

    Un `agente_inicio` abierto no basta por dos razones, las dos medidas en la tanda del 18/09:

    - `preparar-capitulo` deja listos los prompts del escritor y del extractor de una vez, así que
      ambos abren en el mismo segundo aunque el extractor no arranque hasta dos minutos después. La
      cubierta del extractor se encendía mientras escribía el escritor.
    - Desde que el corte de QA se solapa con el capítulo siguiente hay **dos** agentes a la vez, y
      devolver uno solo dejaba la otra cubierta apagada.

    Lo que desempata es el orden del propio bucle: el extractor de un capítulo no puede empezar hasta
    que el escritor de ESE capítulo termina, porque lee lo que el escritor acaba de escribir (INV-02).
    Así que un extractor abierto cuyo escritor sigue abierto no está trabajando: solo tiene el prompt
    esperándolo. La actividad de hooks no sirve para esto, porque el escritor pasa casi todo su turno
    redactando y no toca una herramienta hasta el final.
    """
    abierto: dict[tuple[str, Any], dict[str, Any]] = {}
    for ev in eventos:
        tipo, rol, cap = ev.get("tipo"), ev.get("rol"), ev.get("capitulo")
        if tipo == "agente_inicio" and rol:
            abierto[(rol, cap)] = ev
        elif tipo == "agente_fin" and rol:
            abierto.pop((rol, cap), None)

    activos = []
    for (rol, cap), ev in abierto.items():
        if rol == "extractor" and ("escritor", cap) in abierto:
            continue  # su capítulo todavía se está escribiendo
        activos.append((rol, ev.get("ts"), cap))
    activos.sort(key=lambda a: a[1] or "")
    return activos


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
    activos = _agentes_activos(eventos_crudos)
    # El primero es el que lleva más tiempo trabajando: es el que da el rótulo y el reloj.
    rol, desde, cap_agente = activos[0] if activos else (None, None, None)

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
        # Desde que el corte de QA se solapa con el capítulo siguiente puede haber más de uno.
        "agentes_activos": [a[0] for a in activos] if en_marcha else [],
        "agente_desde": desde if en_marcha else None,
        # Qué fase lanzó la pantalla y desde cuándo. Sin esto, pulsar «Generar la premisa» dejaba la
        # consola idéntica durante dos minutos y solo se sabía que había terminado por el visto: las
        # fases del preludio no tienen subagentes, así que no encendían nada del plano.
        **_fase_en_curso(raiz),
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
    # Un hook deja cuatro decisiones: `permitido`/`bloqueado` en PreToolUse y `verificado`/`falla`
    # en PostToolUse. Solo las dos malas son noticia. Filtrar por «distinto de permitido» metía en la
    # bitácora cada verificación correcta anunciada como bloqueo: en la tanda del 18/09 la pantalla
    # enseñaba siete «H-02 bloqueó» sin que se hubiera bloqueado nada.
    if tipo == "hook" and ev.get("decision") in ("bloqueado", "falla"):
        verbo = "bloqueó" if ev.get("decision") == "bloqueado" else "rechazó"
        return f"{ev.get('id', 'hook')} {verbo} {_corto(ev.get('motivo') or ev.get('accion', ''))}"
    return None  # hooks en orden: son la mayoría del registro y no dicen nada al usuario


def _corto(texto: Any, tope: int = 64) -> str:
    """La bitácora es una columna estrecha: una ruta absoluta la llena entera y no dice nada."""
    limpio = " ".join(str(texto).split())
    # Una ruta absoluta se reduce a su nombre de archivo. No vale partir por espacios: esta misma
    # novela vive bajo «Nueva carpeta», y así «...\Desktop\Nueva carpeta\...\qa_cap_2.json» salía en
    # pantalla como «Nueva qa_cap_2.json». Se toma la ruta entera, espacios incluidos, hasta el final.
    m = re.search(r"(?:[A-Za-z]:[\\/]|\\\\)\S.*$", limpio)
    if m:
        base = m.group(0).replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
        limpio = (limpio[: m.start()] + base).strip()
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
    idea = (repo.leer_texto(rutas.idea) or "").strip() if rutas.idea.exists() else ""
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
        # Que exista una novela no lo decide `config/novela.json`, que conserva los ajustes aunque
        # se borre todo: lo decide que haya manifiesto, premisa o algun capitulo en el disco.
        "hay_novela": bool(m or titulo or idea or any(c["escrito"] for c in capitulos)),
        "idea": idea,
        "titulo": titulo or None,
        "logline": logline,
        "total_capitulos": total,
        "capitulos_cerrados": cerrados,
        "cadencia_qa": novela.get("cadencia_qa"),
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

    salida = []
    for h in hechos:
        if not isinstance(h, dict) or h.get("cap_origen") != n:
            continue
        salida.append({
            "sujeto": h.get("sujeto"),
            "categoria": h.get("categoria"),
            "hecho": h.get("hecho"),
            "superado_por": h.get("superado_por"),
        })
    return salida


def _conflicto_de(raiz: Path, n: int) -> str | None:
    """Lo que QA discute del capítulo N, una sola vez.

    Antes se estampaba el mismo texto en cada hecho del capítulo, así que un capítulo con cuatro
    hechos repetía cuatro veces el mismo párrafo rojo y la pantalla de lectura crecía sin motivo. La
    contradicción es del capítulo, no de un hecho: QA no dice cuál de ellos la provoca.
    """
    rutas = Rutas(raiz)
    if not rutas.reportes_qa.is_dir():
        return None
    for informe in sorted(rutas.reportes_qa.glob("*.json")):
        for h in _json(informe).get("hallazgos") or []:
            if h.get("tipo") == "contradiccion" and h.get("cap_origen") == n:
                return h.get("descripcion") or None
    return None


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
        # El conflicto es del capítulo y va una sola vez, no repetido bajo cada hecho.
        "conflicto": _conflicto_de(raiz, n),
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

    # Las fases del preludio no pasan por H-10; su coste lo anota la pantalla al cerrar el proceso.
    fases = _lineas_jsonl(registro / "fases.jsonl") if registro.is_dir() else []
    for fila in fases:
        gasto = float(fila.get("coste_usd") or 0)
        total += gasto
        tokens += int(fila.get("tokens") or 0)
        por_rol["preludio"] = por_rol.get("preludio", 0.0) + gasto

    return {
        "moneda": tabla.get("moneda") or "USD",
        "total": round(total, 4),
        "tokens": tokens,
        "por_rol": {k: round(v, 4) for k, v in sorted(por_rol.items(), key=lambda x: -x[1])},
        "modelos_sin_precio": sorted(sin_precio),
        "carpetas_con_uso": len(carpetas),
    }


# ---------- borrar la novela (RF-UI): empezar otra sin arrastrar la anterior ----------

# Lo que se lleva por delante un borrado. `config/` no entra: los ajustes son del usuario y los
# vuelve a tocar en el encargo. `00_referencias/` tampoco, y esa es la exclusion importante: son
# archivos suyos, con derechos de autor, que estan fuera de git y no se podrian recuperar.
CARPETAS_DE_NOVELA = ("01_concepto", "04_estado", "05_manuscrito", "06_qa", "07_registro",
                      "08_entrega", ".tanda")


def _hay_cambios_sin_guardar(raiz: Path) -> list[str]:
    """Archivos de la novela modificados o sin seguimiento que git todavia no conoce."""
    try:
        salida = subprocess.run(["git", "status", "--porcelain", "--", *CARPETAS_DE_NOVELA],
                                cwd=str(raiz), capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return []  # sin git no se puede comprobar; el aviso de la pantalla ya advierte
    if salida.returncode != 0:
        return []
    sucios = []
    for linea in salida.stdout.splitlines():
        # El formato porcelain son DOS columnas fijas: indice y arbol de trabajo. Una modificacion
        # sin indexar es « M ruta», con un espacio delante, asi que partir por el primer espacio
        # devuelve un estado vacio y se cuela justo el caso que hay que detener.
        estado_git, ruta = linea[:2], linea[3:].strip().strip('"')
        if estado_git.strip() and estado_git != "!!":
            sucios.append(ruta)
    return sucios


def borrar_novela(raiz: Path, *, forzar: bool = False) -> dict[str, Any]:
    """Vacia el estado de la novela para poder encargar otra.

    Se niega si hay algo en marcha, y se niega si hay trabajo que git no tenga: el manuscrito, el
    informe de QA y el registro estan versionados, asi que borrarlos es recuperable con `git
    restore`, pero solo mientras esten confirmados. Borrar lo que solo existe en disco seria
    destruir horas de maquina pagadas, y esa es exactamente la clase de error que no se deshace.
    """
    _cerrar_proceso()
    if proceso_vivo():
        raise RuntimeError("Hay una ejecución en marcha. Espera a que termine antes de borrar.")

    sucios = _hay_cambios_sin_guardar(raiz)
    if sucios and not forzar:
        raise RuntimeError(
            "Hay cambios sin confirmar en la novela, así que borrarla perdería trabajo que git no "
            f"puede devolver ({len(sucios)} archivo(s), el primero {sucios[0]}). Confirma o descarta "
            "esos cambios y vuelve a intentarlo.")

    borrados = 0
    for nombre in CARPETAS_DE_NOVELA:
        carpeta = raiz / nombre
        if not carpeta.is_dir():
            continue
        for hijo in sorted(carpeta.iterdir(), reverse=True):
            if hijo.name == ".gitkeep":
                continue
            if hijo.is_dir():
                shutil.rmtree(hijo, ignore_errors=True)
            else:
                hijo.unlink(missing_ok=True)
            borrados += 1
    _EN_CURSO.clear()
    return {"borrado": True, "entradas": borrados, "carpetas": list(CARPETAS_DE_NOVELA),
            "conservado": ["config/", "00_referencias/"]}


# ---------- lanzar una fase sin depender de los comandos con barra ----------
#
# La pantalla lanzaba `claude -p "/generar-premisa"` y no pasaba nada: en modo `-p` un comando con
# barra se reconoce como comando local, se resuelve y la sesion termina sin llamar al modelo
# (`num_turns: 0`, `local_command: "custom"`, resultado vacio, y encima `is_error: false`, asi que
# ni siquiera se notaba). Pedirle al modelo que invoque la skill tampoco vale: las de fase llevan
# `disable-model-invocation`, que existe para que no se disparen solas.
#
# Asi que el harness arma el prompt el mismo: lee el SKILL.md, resuelve sus directivas y manda el
# cuerpo como un encargo normal, que es lo unico que funciona en no interactivo. De paso deja de
# depender del shell: las directivas `!` usan `2>/dev/null` y `||`, que PowerShell rechaza, y por
# eso las skills ni siquiera cargaban en esta maquina.

_DIRECTIVA = re.compile(r"!`([^`]+)`")
_ALTERNATIVA = re.compile(r'^(?P<orden>.*?)\s*\|\|\s*echo\s+"(?P<si_falla>[^"]*)"\s*$')


def _resolver_directiva(raiz: Path, orden: str) -> str:
    """Ejecuta una directiva de SKILL.md sin shell. Solo hay tres formas y las tres son portables."""
    alternativa = ""
    m = _ALTERNATIVA.match(orden.strip())
    if m:
        orden, alternativa = m.group("orden"), m.group("si_falla")
    orden = orden.replace("2>/dev/null", "").strip()

    if orden.startswith("cat "):
        archivo = raiz / orden[4:].strip()
        return archivo.read_text(encoding="utf-8") if archivo.is_file() else alternativa
    if orden.startswith("ls -1 "):
        carpeta = raiz / orden[6:].strip()
        if not carpeta.is_dir():
            return alternativa
        nombres = sorted(p.name for p in carpeta.iterdir() if p.name != ".gitkeep")
        return "\n".join(nombres) if nombres else alternativa
    try:
        salida = subprocess.run(orden.split(), cwd=str(raiz), capture_output=True,
                                text=True, timeout=60, encoding="utf-8", errors="replace")
        return salida.stdout.strip() or alternativa
    except (OSError, subprocess.SubprocessError):
        return alternativa


def _herramientas(cabecera: str) -> list[str]:
    """`allowed-tools` del frontmatter, respetando los parentesis: `Bash(... -m app:*)` es una sola."""
    linea = next((l for l in cabecera.splitlines() if l.startswith("allowed-tools:")), "")
    resto, nivel, actual = linea[len("allowed-tools:"):].strip(), 0, ""
    fuera: list[str] = []
    for c in resto:
        if c == "," and nivel == 0:
            fuera.append(actual.strip()); actual = ""
            continue
        nivel += (c == "(") - (c == ")")
        actual += c
    if actual.strip():
        fuera.append(actual.strip())
    herramientas = [h for h in fuera if h]
    # En Windows la herramienta de shell de Claude Code es `PowerShell`, no `Bash`, asi que una
    # skill que solo autoriza `Bash(...)` se queda sin poder ejecutar su propio paso de persistencia.
    # Se autoriza la equivalente con el mismo alcance: no amplia el permiso, lo traduce.
    for h in list(herramientas):
        if h.startswith("Bash(") and h.endswith(")"):
            patron = h[len("Bash("):-1]
            # Y con las dos formas de separador: la skill escribe `.venv/Scripts/python.exe`, pero
            # en Windows el comando sale con `\`, y el permiso casa por prefijo literal.
            for variante in {patron, patron.replace("/", "\\")}:
                herramientas.append(f"PowerShell({variante})")
    return herramientas


def prompt_de_fase(raiz: Path, fase: str) -> tuple[str, list[str]]:
    """El cuerpo del SKILL.md con sus directivas ya resueltas, y las herramientas que declara."""
    archivo = raiz / ".claude" / "skills" / fase / "SKILL.md"
    if not archivo.is_file():
        raise RuntimeError(f"No existe la skill {fase}: falta {archivo.relative_to(raiz).as_posix()}")
    texto = archivo.read_text(encoding="utf-8")

    cabecera, cuerpo = "", texto
    if texto.startswith("---"):
        fin = texto.find("\n---", 3)
        if fin != -1:
            cabecera, cuerpo = texto[3:fin], texto[fin + 4:]

    cuerpo = _DIRECTIVA.sub(lambda m: _resolver_directiva(raiz, m.group(1)), cuerpo)
    encabezado = (
        f"Ejecutá esta fase del harness de principio a fin, ahora, sin pedir confirmación y sin "
        f"preguntar nada: no hay nadie mirando esta sesión. Las instrucciones son las de la fase "
        f"`{fase}` y los datos que necesita ya vienen resueltos abajo. Terminá cuando el artefacto "
        f"esté persistido; si un paso falla, corregilo y repetilo.\n\n"
        f"Para ejecutar comandos usá la herramienta **Bash** y escribí las rutas con barras "
        f"normales, tal como aparecen abajo. El permiso casa por prefijo literal: otra forma de "
        f"shell, u otro separador, se deniega sin preguntar y la fase se queda a medias con el "
        f"borrador escrito y sin persistir.\n\n"
    )
    return encabezado + cuerpo.strip(), _herramientas(cabecera)
