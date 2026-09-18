"""Cerrar una novela y dejar el árbol listo para la siguiente.

El harness sostiene **una sola** novela: `01_concepto/`, `04_estado/`, `05_manuscrito/`, `06_qa/` y
`07_registro/` son del libro en curso, no de un libro cualquiera. Para escribir otro hay que
vaciarlos. Hasta ahora eso se hacía a mano, o con `web.borrar_novela`, que borra de verdad y por eso
exige que git ya tenga el trabajo confirmado.

`archivar` no borra: mueve el libro entero a `09_archivo/<sello>_<nombre>/`, junto a la
configuración con la que se escribió y un `resumen.json` con lo que tardó, lo que costó y cómo
salió. Eso es lo que permite encadenar novelas sin que nadie mire, y es además la unidad de medida:
sin archivar, cada libro pisa el registro del anterior y a la tercera no queda con qué comparar.
"""

from __future__ import annotations

import json
import re
import shutil
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any

from app import registro
from app.agents import escritor
from app.config import VERSION_SPECS
from app.errores import EstadoInvalidoError
from app.orchestrator import checkpoint, cursor as cur
from app.rutas import Rutas
from app.state import repository as repo

ARCHIVO = "09_archivo"

# Lo que se lleva el archivado. `config/` se copia aparte, no se mueve: la siguiente novela la
# necesita. `00_referencias/` no se toca nunca: son archivos del usuario, con derechos de autor,
# fuera de git, que no se podrían recuperar.
CARPETAS_DE_NOVELA = ("01_concepto", "04_estado", "05_manuscrito", "06_qa", "07_registro", "08_entrega")

# Transitorios: se vacían pero no se archivan. El cursor de tanda y el estado de hooks no significan
# nada fuera de la corrida, y los prompts y deltas son artefactos de trabajo (§8.2), no estado.
TRANSITORIOS = (".tanda", "04_estado/prompts", "04_estado/deltas")

CONFIG_ARCHIVADA = ("novela.json", "ejecucion.json")


# ---------- medidas ----------

def _lineas_jsonl(ruta: Path) -> list[dict]:
    if not ruta.is_file():
        return []
    filas = []
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea:
            continue
        try:
            filas.append(json.loads(linea))
        except json.JSONDecodeError:
            continue  # una línea rota no invalida la medición del resto
    return filas


def _instante(iso: str | None) -> datetime | None:
    if not iso:
        return None
    try:
        return datetime.fromisoformat(iso)
    except ValueError:
        return None


def _segundos(desde: str | None, hasta: str | None) -> float | None:
    a, b = _instante(desde), _instante(hasta)
    return round((b - a).total_seconds(), 1) if a and b else None


def tramos_de_agente(eventos: list[dict]) -> list[dict]:
    """Empareja cada `agente_fin` con su `agente_inicio`.

    El inicio no lleva `agent_id` --se emite antes de que el agente exista--, así que la pareja se
    hace por rol y capítulo tomando el inicio abierto más reciente. Es el mismo criterio con el que
    el plano de la nave decide quién está trabajando.
    """
    abiertos: dict[tuple, list[dict]] = {}
    tramos = []
    for ev in eventos:
        clave = (ev.get("rol"), ev.get("capitulo"))
        if ev.get("tipo") == "agente_inicio":
            abiertos.setdefault(clave, []).append(ev)
        elif ev.get("tipo") == "agente_fin":
            pila = abiertos.get(clave) or []
            inicio = pila.pop() if pila else {}
            tramos.append({"rol": ev.get("rol"), "capitulo": ev.get("capitulo"),
                           "agent_id": ev.get("agent_id"), "modelo": ev.get("modelo"),
                           "inicio": inicio.get("ts"), "fin": ev.get("ts"),
                           "segundos": _segundos(inicio.get("ts"), ev.get("ts"))})
    return tramos


def _carpetas_con_registro(raiz: Path) -> list[Path]:
    carpetas = list(registro.carpetas_tanda(raiz))
    preludio = Rutas(raiz).registro / "preludio"
    if preludio.is_dir():
        carpetas.append(preludio)
    return carpetas


def _reloj(raiz: Path) -> dict[str, Any]:
    """Reloj de pared por tramo. Es la métrica que manda: lo que de verdad se espera sentado."""
    rutas = Rutas(raiz)
    fases = _lineas_jsonl(rutas.registro / "fases.jsonl")
    con_duracion = [f for f in fases if f.get("segundos") is not None]
    por_fase = {str(f.get("fase")): f.get("segundos") for f in con_duracion}

    tandas = []
    for carpeta in registro.carpetas_tanda(raiz):
        meta: dict = {}
        ruta_meta = carpeta / "tanda.json"
        if ruta_meta.is_file():
            try:
                meta = json.loads(ruta_meta.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                meta = {}
        eventos = registro.leer_eventos(carpeta)
        fin = eventos[-1].get("ts") if eventos else None
        tandas.append({"tanda": carpeta.name, "inicio": meta.get("ts_inicio"), "fin": fin,
                       "segundos": _segundos(meta.get("ts_inicio"), fin)})

    s_preludio = round(sum(f["segundos"] for f in con_duracion), 1) if con_duracion else None
    medidas_tanda = [t["segundos"] for t in tandas if t["segundos"] is not None]
    s_tandas = round(sum(medidas_tanda), 1) if medidas_tanda else None
    total = None
    if s_preludio is not None or s_tandas is not None:
        total = round((s_preludio or 0) + (s_tandas or 0), 1)
    return {"preludio_s": s_preludio, "por_fase_s": por_fase, "tandas": tandas,
            "tandas_s": s_tandas, "total_s": total}


def _agentes(raiz: Path) -> dict[str, Any]:
    """Trabajo por rol: cuántas veces corrió, cuánto duró y cuánto emitió.

    Los tokens de salida importan tanto como los segundos, porque se generan en serie: para un
    agente son casi la misma cosa. El extractor del 18/09 emitía entre 7.000 y 11.000 tokens para
    dejar un delta de 1.200, y el cuello de botella se vio antes en esta columna que en el reloj.
    """
    por_rol: dict[str, dict[str, Any]] = {}

    def fila_de(rol: Any) -> dict[str, Any]:
        return por_rol.setdefault(str(rol), {"invocaciones": 0, "segundos": 0.0,
                                             "tokens_salida": 0, "modelos": []})

    for carpeta in _carpetas_con_registro(raiz):
        for tramo in tramos_de_agente(registro.leer_eventos(carpeta)):
            fila = fila_de(tramo["rol"])
            fila["invocaciones"] += 1
            fila["segundos"] += tramo["segundos"] or 0
            if tramo["modelo"] and tramo["modelo"] not in fila["modelos"]:
                fila["modelos"].append(tramo["modelo"])
        vistos: set[str] = set()
        for uso in registro.leer_uso(carpeta):
            agente = str(uso.get("agent_id") or "")
            if agente and agente in vistos:
                continue  # H-10 anota el fin de un subagente más de una vez
            if agente:
                vistos.add(agente)
            fila_de(uso.get("rol"))["tokens_salida"] += int(uso.get("tokens_salida") or 0)

    for fila in por_rol.values():
        fila["segundos"] = round(fila["segundos"], 1)
    return dict(sorted(por_rol.items(), key=lambda par: -par[1]["segundos"]))


def _calidad(raiz: Path) -> dict[str, Any]:
    """Los guardarraíles. Una novela más rápida que falle aquí no cuenta como mejora."""
    metricas = _lineas_jsonl(Rutas(raiz).metricas_qa)
    contradicciones = sum(int(m.get("contradicciones") or 0) for m in metricas)

    reintentos = descartes = 0
    for carpeta in registro.carpetas_tanda(raiz):
        for ev in registro.leer_eventos(carpeta):
            if ev.get("tipo") == "agente_inicio" and int(ev.get("intento") or 1) > 1:
                reintentos += 1
            if ev.get("tipo") == "verbo" and ev.get("verbo") == "descartar-borrador":
                descartes += 1

    m = checkpoint.leer_manifest(raiz)
    return {"contradicciones": contradicciones, "cortes_qa": len(metricas),
            "reintentos_de_escritor": reintentos, "borradores_descartados": descartes,
            "pausado_al_archivar": bool(m is not None and m.estado == "pausado_por_qa")}


def _capitulos(raiz: Path) -> dict[str, Any]:
    m = checkpoint.leer_manifest(raiz)
    cerrados = m.ultimo_capitulo_cerrado if m else 0
    palabras: list[int | None] = []
    for n in range(1, cerrados + 1):
        try:
            palabras.append(escritor.contar_palabras(repo.leer_manuscrito(raiz, n)))
        except Exception:
            palabras.append(None)
    return {"cerrados": cerrados, "esperados": m.total_capitulos_esperado if m else None,
            "estado": m.estado if m else None, "palabras": palabras}


def medidas(raiz: Path) -> dict[str, Any]:
    """Todo lo que hace falta para comparar esta novela con la siguiente."""
    rutas = Rutas(raiz)
    config: dict[str, Any] = {}
    for nombre in CONFIG_ARCHIVADA:
        ruta = rutas.config / nombre
        if ruta.is_file():
            try:
                config[nombre] = json.loads(ruta.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                config[nombre] = None
    try:
        from app.web import coste
        gasto = coste(raiz)
    except Exception:
        gasto = None  # el coste es informativo: sin precios.json la medición del reloj sigue valiendo
    return {"version_specs": VERSION_SPECS, "config": config, "capitulos": _capitulos(raiz),
            "reloj": _reloj(raiz), "agentes": _agentes(raiz), "calidad": _calidad(raiz),
            "coste": gasto}


# ---------- archivado ----------

def _sello() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%dT%H-%M-%S")


def nombre_corto(texto: str, tope: int = 48) -> str:
    """Nombre de carpeta a partir del título: sin acentos, sin espacios, sin sorpresas."""
    plano = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode("ascii")
    limpio = re.sub(r"[^a-zA-Z0-9]+", "-", plano).strip("-").lower()
    return limpio[:tope].strip("-") or "sin-titulo"


def _titulo(raiz: Path) -> str:
    try:
        from app.cli import _titulo_desde_premisa
        return _titulo_desde_premisa(repo.leer_premisa(raiz)) or ""
    except Exception:
        return ""


def _vaciar(ruta: Path) -> None:
    if ruta.is_dir():
        shutil.rmtree(ruta, ignore_errors=True)
    else:
        ruta.unlink(missing_ok=True)


def _mover_contenido(origen: Path, destino: Path, *, excluir: set[str]) -> int:
    if not origen.is_dir():
        return 0
    movidos = 0
    for hijo in sorted(origen.iterdir()):
        if hijo.name == ".gitkeep":
            continue
        if hijo.name in excluir:
            _vaciar(hijo)
            continue
        destino.mkdir(parents=True, exist_ok=True)
        shutil.move(str(hijo), str(destino / hijo.name))
        movidos += 1
    return movidos


def _excluidos_de(carpeta: str) -> set[str]:
    return {t.split("/", 1)[1] for t in TRANSITORIOS if t.startswith(carpeta + "/")}


def _hay_algo_que_archivar(raiz: Path) -> bool:
    """Cualquier rastro de novela cuenta, no solo un libro terminado.

    Una novela que se cayó en el preludio no tiene manifiesto ni capítulos, pero sí dejó la idea y la
    premisa en `01_concepto/` y su registro en `07_registro/`. Si archivar se negara por no encontrar
    manifiesto, esos restos se quedarían en el árbol y la novela siguiente arrancaría encima de ellos.
    """
    # Cuentan los archivos, no las carpetas: `crear_carpetas` deja el esqueleto vacío en pie
    # (`04_estado/prompts`, `06_qa/reportes`...) y con ese criterio un árbol recién archivado
    # parecería tener novela.
    for nombre in CARPETAS_DE_NOVELA:
        carpeta = raiz / nombre
        if carpeta.is_dir() and any(h.is_file() and h.name != ".gitkeep" for h in carpeta.rglob("*")):
            return True
    return False


def archivar(raiz: Path, *, nombre: str | None = None, forzar: bool = False) -> dict[str, Any]:
    """Mueve la novela a `09_archivo/` con su resumen y deja el árbol en blanco.

    Se niega con una tanda a medias o con el manuscrito pausado por QA: archivar entonces congela un
    libro sin terminar y encima se lleva por delante el cursor con el que se podría retomar.
    `forzar` existe para cuando eso es justo lo que se quiere.
    """
    rutas = Rutas(raiz)
    m = checkpoint.leer_manifest(raiz)
    if not _hay_algo_que_archivar(raiz):
        raise EstadoInvalidoError("no hay novela que archivar: el árbol ya está vacío")
    if not forzar:
        if cur.leer(raiz) is not None:
            raise EstadoInvalidoError("hay una tanda en curso; ciérrala o archiva con forzar")
        if m is not None and m.estado == "pausado_por_qa":
            raise EstadoInvalidoError("el manuscrito está pausado por QA; resuélvelo o archiva con forzar")

    resumen = medidas(raiz)  # antes de mover nada: se calcula sobre el árbol vivo
    titulo = _titulo(raiz)
    carpeta = raiz / ARCHIVO / f"{_sello()}_{nombre_corto(nombre or titulo)}"
    if carpeta.exists():
        raise EstadoInvalidoError(f"{carpeta.name} ya existe en {ARCHIVO}/")
    carpeta.mkdir(parents=True)

    # La novela ensamblada va suelta en la raíz del archivo: `08_entrega/` está en .gitignore y ese
    # patrón taparía también la copia archivada, que es justo la que interesa conservar.
    entrega = raiz / "08_entrega" / "novela.md"
    if entrega.is_file():
        shutil.copy2(entrega, carpeta / "novela.md")

    movidos = 0
    for nombre_carpeta in CARPETAS_DE_NOVELA:
        excluir = _excluidos_de(nombre_carpeta)
        movidos += _mover_contenido(raiz / nombre_carpeta, carpeta / nombre_carpeta, excluir=excluir)
    for transitorio in TRANSITORIOS:
        if "/" not in transitorio:
            _vaciar(raiz / transitorio)

    destino_config = carpeta / "config"
    destino_config.mkdir(exist_ok=True)
    for nombre_config in CONFIG_ARCHIVADA:
        origen = rutas.config / nombre_config
        if origen.is_file():
            shutil.copy2(origen, destino_config / nombre_config)

    resumen.update({"nombre": carpeta.name, "titulo": titulo,
                    "archivado": datetime.now().astimezone().isoformat(timespec="seconds")})
    (carpeta / "resumen.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=2) + "\n",
                                          encoding="utf-8")

    rutas.crear_carpetas()  # el árbol queda vacío pero existente, listo para el siguiente encargo
    return {"carpeta": str(carpeta.relative_to(raiz)), "entradas": movidos, "resumen": resumen}
