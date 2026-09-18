"""Encadena novelas enteras sin nadie delante, para medir cuánto se tarda en escribir una.

Una corrida es: encargo -> preludio -> tandas -> ensamblar -> archivar, y otra vez. Cada novela deja
su carpeta en `09_archivo/` con su `resumen.json`, y la corrida entera deja una línea por novela en
`09_archivo/corridas.jsonl`. Eso es todo lo que hace falta para comparar diez libros escritos con
distintos ajustes.

Dos decisiones que no son obvias:

**Va por el mismo camino que la pantalla** (`web.ejecutar_fase`), no por uno propio. Una corrida que
lanzara las fases de otra manera mediría otra cosa, y la cifra no valdría para decidir nada.

**Una novela que necesita que alguien intervenga cuenta como fallida, no como lenta.** Si QA deja el
manuscrito pausado, el corredor la archiva y sigue con la siguiente en vez de esperar: que pare a
mitad es precisamente uno de los guardarraíles, y una media calculada sobre novelas rescatadas a mano
no diría la verdad.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from app import archivo, web
from app.orchestrator import checkpoint
from app.rutas import Rutas, raiz_desde_entorno

# El preludio en el orden en que se encadena. `destilar-estilo` solo corre si hay referencias: sin
# ellas la skill se detiene por diseño (RF-00.2), y sumarla en vacío costaría una fase por novela.
PRELUDIO = ("generar-premisa", "generar-sinopsis", "generar-escaleta", "inicializar-estado")

# Techo de tandas por novela. Con 3 capítulos y 3 por tanda basta una; el tope solo existe para que
# un manifiesto que no avanza no deje al corredor dando vueltas hasta que alguien lo vea.
MAX_TANDAS = 12

CORRIDAS = "corridas.jsonl"
CORRIDAS_CSV = "corridas.csv"

# Los roles con columna propia en el CSV. Fijos a propósito: una tabla cuyas columnas cambian según
# lo que salió en cada corrida no se puede leer con pandas sin pelearse con ella.
ROLES = ("escritor", "extractor", "qa", "orquestador")


def campos_de_encargo(encargo: dict[str, Any]) -> dict[str, str]:
    """Traduce un encargo a los campos del formulario, que es lo que sabe validar `ui`."""
    campos: dict[str, str] = {"idea": encargo["idea"]}
    for clave, valor in (encargo.get("config") or {}).items():
        campos[clave] = "on" if valor is True else ("" if valor is False else str(valor))
    campos.setdefault("registrar_uso", "on")
    campos.setdefault("exportar_trazas", "on")
    return campos


def _completa(raiz: Path) -> bool:
    m = checkpoint.leer_manifest(raiz)
    return bool(m and m.ultimo_capitulo_cerrado >= m.total_capitulos_esperado)


def _pausada(raiz: Path) -> bool:
    m = checkpoint.leer_manifest(raiz)
    return bool(m and m.estado == "pausado_por_qa")


def correr_novela(raiz: Path, encargo: dict[str, Any], *, tope_fase_s: float = 3600,
                  variante: str = "base", aviso: Callable[[str], None] = print,
                  ejecutar: Callable[..., dict] = web.ejecutar_fase) -> dict[str, Any]:
    """Escribe una novela de punta a punta y la archiva. Devuelve cómo fue."""
    from app import ui  # import tardío: `ui` arrastra el formulario y aquí no hace falta antes

    if checkpoint.leer_manifest(raiz) is not None:
        raise RuntimeError("hay una novela en el árbol; archívala antes de encargar otra")

    nombre = encargo.get("nombre") or "sin-nombre"
    inicio = time.monotonic()
    fases: list[dict[str, Any]] = []
    fallo: str | None = None

    def paso(fase: str) -> bool:
        aviso(f"  · {fase}")
        try:
            r = ejecutar(raiz, fase, tope_s=tope_fase_s)
        except Exception as e:  # una fase que revienta no debe llevarse la corrida entera
            fases.append({"fase": fase, "error": f"{type(e).__name__}: {e}"})
            return False
        fases.append({"fase": fase, "segundos": r.get("segundos"), "codigo": r.get("codigo")})
        if r.get("codigo") not in (0, None):
            fases[-1]["error"] = f"la fase terminó con código {r['codigo']}"
            return False
        return True

    ui.procesar_guardado(raiz, campos_de_encargo(encargo))
    aviso(f"novela «{nombre}»")

    for fase in PRELUDIO:
        if not paso(fase):
            fallo = f"preludio: {fases[-1].get('error')}"
            break

    if fallo is None:
        for _ in range(MAX_TANDAS):
            if _completa(raiz):
                break
            antes = (checkpoint.leer_manifest(raiz) or None)
            cerrados_antes = antes.ultimo_capitulo_cerrado if antes else 0
            if not paso("escribir-tanda"):
                fallo = f"tanda: {fases[-1].get('error')}"
                break
            if _pausada(raiz):
                # Reanudar a mano es intervención, y eso es justo lo que el guardarraíl mide.
                fallo = "QA dejó el manuscrito pausado"
                break
            despues = checkpoint.leer_manifest(raiz)
            if (despues.ultimo_capitulo_cerrado if despues else 0) <= cerrados_antes:
                fallo = "la tanda terminó sin cerrar ningún capítulo"
                break
        else:
            fallo = f"no terminó en {MAX_TANDAS} tandas"

    completa = _completa(raiz)
    if completa and fallo is None:
        paso("ensamblar")

    r = archivo.archivar(raiz, nombre=nombre, forzar=True)
    resumen = r["resumen"]
    reloj = resumen["reloj"]
    fila = {
        "variante": variante, "premisas": encargo.get("premisas"),
        "nombre": nombre, "carpeta": r["carpeta"], "completa": bool(completa and fallo is None),
        "fallo": fallo, "cuando": datetime.now().astimezone().isoformat(timespec="seconds"),
        "reloj_corredor_s": round(time.monotonic() - inicio, 1),
        "reloj_s": reloj["total_s"], "preludio_s": reloj["preludio_s"],
        "tandas_s": reloj["tandas_s"], "n_tandas": len(reloj["tandas"]), "fases": fases,
        "capitulos": resumen["capitulos"]["cerrados"], "palabras": resumen["capitulos"]["palabras"],
        "agentes": resumen["agentes"], "calidad": resumen["calidad"],
        "coste_usd": (resumen.get("coste") or {}).get("total"),
        "config": resumen["config"].get("novela.json"),
    }
    destino = raiz / archivo.ARCHIVO / CORRIDAS
    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(fila, ensure_ascii=False) + "\n")

    escribir_csv(raiz, fila)

    estado = "completa" if fila["completa"] else f"FALLÓ ({fallo})"
    aviso(f"  {estado} · {(fila['reloj_corredor_s'] or 0) / 60:.1f} min · {r['carpeta']}")
    return fila


def fila_csv(fila: dict[str, Any]) -> dict[str, Any]:
    """Aplana una corrida a una fila de tabla: una novela, una línea, columnas siempre iguales.

    El JSONL guarda todo, incluida la lista de motivos de aborto y el desglose por fase. Esto es lo
    otro: lo que se abre con pandas sin desanidar nada. La columna que manda es `variante`, porque
    sin ella no se puede agrupar por vuelta y el resto de números no significan gran cosa.
    """
    agentes = fila.get("agentes") or {}
    calidad = fila.get("calidad") or {}
    config = fila.get("config") or {}
    palabras = [p for p in (fila.get("palabras") or []) if p]
    plano: dict[str, Any] = {
        "variante": fila.get("variante"),
        # El juego de premisas es parte del diseño del experimento: el juego 1 fallaba en dos de
        # cada tres novelas por una contradicción del clímax, así que mezclar sus filas con las del
        # juego 2 en la misma media sería comparar dos poblaciones distintas.
        "premisas": fila.get("premisas"),
        "novela": fila.get("nombre"),
        "cuando": fila.get("cuando"),
        "completa": int(bool(fila.get("completa"))),
        "fallo": fila.get("fallo") or "",
        "minutos": round((fila.get("reloj_corredor_s") or 0) / 60, 2),
        "reloj_corredor_s": fila.get("reloj_corredor_s"),
        "reloj_registro_s": fila.get("reloj_s"),
        "preludio_s": fila.get("preludio_s"),
        "tandas_s": fila.get("tandas_s"),
        "n_tandas": fila.get("n_tandas"),
        "capitulos": fila.get("capitulos"),
        "palabras_total": sum(palabras) or None,
        "palabras_media": round(sum(palabras) / len(palabras), 1) if palabras else None,
        "coste_usd": fila.get("coste_usd"),
    }
    for rol in ROLES:
        datos = agentes.get(rol) or {}
        plano[f"{rol}_invocaciones"] = datos.get("invocaciones") or 0
        plano[f"{rol}_segundos"] = datos.get("segundos") or 0
        plano[f"{rol}_tokens_salida"] = datos.get("tokens_salida") or 0
        plano[f"{rol}_modelo"] = (datos.get("modelos") or [None])[0]
    for clave in ("contradicciones", "cortes_qa", "reintentos_de_escritor",
                  "borradores_descartados", "tandas_abortadas"):
        plano[clave] = calidad.get(clave)
    for clave in ("total_capitulos", "palabras_por_capitulo", "cadencia_qa",
                  "ventana_resumen_rodante", "max_tokens_contexto_escritor",
                  "max_hechos_por_capitulo"):
        plano[clave] = config.get(clave)
    plano["modelo_orquestador"] = web.MODELO_ORQUESTADOR_ID
    plano["carpeta"] = fila.get("carpeta")
    return plano


def escribir_csv(raiz: Path, fila: dict[str, Any]) -> Path:
    """Añade la corrida al CSV, con cabecera si es la primera."""
    destino = raiz / archivo.ARCHIVO / CORRIDAS_CSV
    destino.parent.mkdir(parents=True, exist_ok=True)
    plano = fila_csv(fila)
    nuevo = not destino.exists()
    with destino.open("a", encoding="utf-8", newline="") as fh:
        escritor = csv.DictWriter(fh, fieldnames=list(plano), extrasaction="ignore")
        if nuevo:
            escritor.writeheader()
        escritor.writerow(plano)
    return destino


def _completar_desde_el_archivo(raiz: Path, fila: dict[str, Any]) -> dict[str, Any]:
    """Rellena lo que la fila no traiga leyendo el `resumen.json` de la novela archivada.

    Una columna que se añade hoy no existe en las corridas de ayer, pero el dato sí: está en el
    archivo de cada novela, que es lo que nunca se pisa. Así una tabla nueva no obliga a repetir
    novelas que costaron veinte minutos cada una.
    """
    if fila.get("n_tandas") is not None and (fila.get("calidad") or {}).get("tandas_abortadas") is not None:
        return fila
    resumen_json = raiz / str(fila.get("carpeta") or "") / "resumen.json"
    if not fila.get("carpeta") or not resumen_json.is_file():
        return fila
    try:
        resumen = json.loads(resumen_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fila
    reloj = resumen.get("reloj") or {}
    completa = dict(fila)
    completa.setdefault("preludio_s", reloj.get("preludio_s"))
    completa.setdefault("tandas_s", reloj.get("tandas_s"))
    completa.setdefault("n_tandas", len(reloj.get("tandas") or []))
    completa["calidad"] = {**(resumen.get("calidad") or {}), **(fila.get("calidad") or {})}
    completa.setdefault("agentes", resumen.get("agentes") or {})
    return completa


def reconstruir_csv(raiz: Path, *, variante: str | None = None) -> Path:
    """Rehace el CSV entero desde `corridas.jsonl`, que es el registro que manda.

    El CSV es una vista: si se añade una columna, o una corrida vieja se quedó sin fila porque el
    CSV no existía todavía, se rehace desde el JSONL y no se pierde nada.
    """
    origen = raiz / archivo.ARCHIVO / CORRIDAS
    destino = raiz / archivo.ARCHIVO / CORRIDAS_CSV
    filas = []
    if origen.is_file():
        for linea in origen.read_text(encoding="utf-8").splitlines():
            if linea.strip():
                fila = json.loads(linea)
                if variante and not fila.get("variante"):
                    fila["variante"] = variante
                filas.append(fila_csv(_completar_desde_el_archivo(raiz, fila)))
    destino.parent.mkdir(parents=True, exist_ok=True)
    if not filas:
        destino.write_text("", encoding="utf-8")
        return destino
    with destino.open("w", encoding="utf-8", newline="") as fh:
        escritor = csv.DictWriter(fh, fieldnames=list(filas[0]), extrasaction="ignore")
        escritor.writeheader()
        escritor.writerows(filas)
    return destino


def correr(raiz: Path, encargos: list[dict[str, Any]], *, tope_fase_s: float = 3600,
           variante: str = "base", aviso: Callable[[str], None] = print,
           **kwargs) -> list[dict[str, Any]]:
    """Encadena varias novelas. Una que falla no detiene a las siguientes."""
    filas = []
    for i, encargo in enumerate(encargos, 1):
        aviso(f"[{i}/{len(encargos)}] {encargo.get('nombre')}")
        try:
            filas.append(correr_novela(raiz, encargo, tope_fase_s=tope_fase_s, variante=variante,
                                       aviso=aviso, **kwargs))
        except Exception as e:
            aviso(f"  ABORTADA: {type(e).__name__}: {e}")
            filas.append({"variante": variante, "nombre": encargo.get("nombre"), "completa": False,
                          "fallo": f"{type(e).__name__}: {e}"})
    return filas


def informe(filas: list[dict[str, Any]]) -> str:
    """Una tabla corta: es lo que se mira al día siguiente para saber si la vuelta sirvió."""
    lineas = [f"{'novela':28} {'min':>7} {'caps':>5} {'contra':>7} {'$':>7}  estado"]
    completas = [f for f in filas if f.get("completa")]
    for f in filas:
        minutos = (f.get("reloj_corredor_s") or 0) / 60
        contra = (f.get("calidad") or {}).get("contradicciones")
        coste = f.get("coste_usd")
        lineas.append(f"{str(f.get('nombre'))[:28]:28} {minutos:7.1f} {f.get('capitulos') or 0:5} "
                      f"{contra if contra is not None else '-':>7} "
                      f"{coste if coste is not None else '-':>7}  "
                      f"{'ok' if f.get('completa') else f.get('fallo')}")
    if completas:
        medias = sum((f.get("reloj_corredor_s") or 0) for f in completas) / len(completas) / 60
        lineas.append(f"\n{len(completas)} de {len(filas)} completas · media {medias:.1f} min")
    return "\n".join(lineas)


def cargar_encargos(ruta: Path) -> list[dict[str, Any]]:
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    encargos = datos["novelas"] if isinstance(datos, dict) else datos
    version = datos.get("version") if isinstance(datos, dict) else None
    if version is not None:
        for e in encargos:
            e.setdefault("premisas", version)
    base = datos.get("config") if isinstance(datos, dict) else None
    if base:
        # La config común va una sola vez en el archivo: que las diez compartan tamaño de novela es
        # la condición para que sean comparables, y repetirla diez veces es diez ocasiones de que una
        # se desvíe sin que nadie lo note.
        for e in encargos:
            e["config"] = {**base, **(e.get("config") or {})}
    return encargos


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="corredor", description="Encadena novelas y mide cuánto tardan")
    p.add_argument("encargos", help="JSON con las novelas a escribir")
    p.add_argument("--desde", type=int, default=1, help="primera novela de la lista (1 es la primera)")
    p.add_argument("--hasta", type=int, help="última novela de la lista")
    p.add_argument("--tope-fase", type=float, default=60, help="minutos máximos por fase antes de cortarla")
    p.add_argument("--variante", default="base",
                   help="etiqueta de la vuelta (base, extractor-effort-low, cadencia-qa-3...); es la "
                        "columna por la que se agrupa en el análisis")
    p.add_argument("--listar", action="store_true", help="enseña las novelas y no escribe nada")
    p.add_argument("--rehacer-csv", action="store_true",
                   help="rehace corridas.csv desde corridas.jsonl y no escribe ninguna novela")
    args = p.parse_args(argv)

    raiz = raiz_desde_entorno()
    if args.rehacer_csv:
        destino = reconstruir_csv(raiz, variante=args.variante)
        print(f"reescrito {destino}")
        return 0
    encargos = cargar_encargos(Path(args.encargos))[args.desde - 1:args.hasta]
    if args.listar:
        for i, e in enumerate(encargos, args.desde):
            print(f"{i:2}. {e.get('nombre')}: {e['idea'].splitlines()[0][:90]}")
        return 0

    print(f"{len(encargos)} novelas, variante «{args.variante}», tope de {args.tope_fase:.0f} min por fase")
    filas = correr(raiz, encargos, tope_fase_s=args.tope_fase * 60, variante=args.variante)
    print("\n" + informe(filas))
    return 0 if all(f.get("completa") for f in filas) else 1


if __name__ == "__main__":
    sys.exit(main())
