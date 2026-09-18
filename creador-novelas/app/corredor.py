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
                  aviso: Callable[[str], None] = print,
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
    fila = {
        "nombre": nombre, "carpeta": r["carpeta"], "completa": bool(completa and fallo is None),
        "fallo": fallo, "cuando": datetime.now().astimezone().isoformat(timespec="seconds"),
        "reloj_corredor_s": round(time.monotonic() - inicio, 1),
        "reloj_s": resumen["reloj"]["total_s"], "fases": fases,
        "capitulos": resumen["capitulos"]["cerrados"], "palabras": resumen["capitulos"]["palabras"],
        "agentes": resumen["agentes"], "calidad": resumen["calidad"],
        "coste_usd": (resumen.get("coste") or {}).get("total"),
        "config": resumen["config"].get("novela.json"),
    }
    destino = raiz / archivo.ARCHIVO / CORRIDAS
    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(fila, ensure_ascii=False) + "\n")

    estado = "completa" if fila["completa"] else f"FALLÓ ({fallo})"
    aviso(f"  {estado} · {(fila['reloj_corredor_s'] or 0) / 60:.1f} min · {r['carpeta']}")
    return fila


def correr(raiz: Path, encargos: list[dict[str, Any]], *, tope_fase_s: float = 3600,
           aviso: Callable[[str], None] = print, **kwargs) -> list[dict[str, Any]]:
    """Encadena varias novelas. Una que falla no detiene a las siguientes."""
    filas = []
    for i, encargo in enumerate(encargos, 1):
        aviso(f"[{i}/{len(encargos)}] {encargo.get('nombre')}")
        try:
            filas.append(correr_novela(raiz, encargo, tope_fase_s=tope_fase_s, aviso=aviso, **kwargs))
        except Exception as e:
            aviso(f"  ABORTADA: {type(e).__name__}: {e}")
            filas.append({"nombre": encargo.get("nombre"), "completa": False,
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
    p.add_argument("--listar", action="store_true", help="enseña las novelas y no escribe nada")
    args = p.parse_args(argv)

    raiz = raiz_desde_entorno()
    encargos = cargar_encargos(Path(args.encargos))[args.desde - 1:args.hasta]
    if args.listar:
        for i, e in enumerate(encargos, args.desde):
            print(f"{i:2}. {e.get('nombre')}: {e['idea'].splitlines()[0][:90]}")
        return 0

    print(f"{len(encargos)} novelas, tope de {args.tope_fase:.0f} min por fase")
    filas = correr(raiz, encargos, tope_fase_s=args.tope_fase * 60)
    print("\n" + informe(filas))
    return 0 if all(f.get("completa") for f in filas) else 1


if __name__ == "__main__":
    sys.exit(main())
