"""Comprueba que el corte de QA caza una contradicción puesta a mano.

Toda la comparación entre variantes cuelga de la columna `contradicciones` del CSV, y esa columna
vale lo que valga el corte de QA. Nunca lo habíamos comprobado: sabemos que a veces marca, no que
marque cuando debe. Anthropic llama a esto el problema de la victoria temprana --un verificador que
aprueba tras mirar lo mínimo-- y un «cero contradicciones» de un verificador así no significa nada.

El test tiene dos lados, y los dos hacen falta:

- **control**: la novela archivada tal cual, sin tocar, tiene que salir `tiene_contradicciones: false`.
  Sin esta mitad, un QA que dijera «sí» siempre aprobaría el test.
- **inyectado**: la misma novela con un párrafo que niega a la cara un hecho del log de continuidad
  tiene que salir `true` y dejar el manifiesto en `pausado_por_qa`.

Corre sobre una copia en un árbol aparte, así que no toca la novela archivada ni el árbol de trabajo.

Uso:
    python herramientas/contradiccion-inyectada.py 09_archivo/2026-...-enjambre
    python herramientas/contradiccion-inyectada.py <novela> --solo inyectado
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import web  # noqa: E402
from app.orchestrator import checkpoint  # noqa: E402

# `corte-qa` no está en el mapa de fases de la pantalla porque nadie la lanza a mano desde la web:
# vive para casos como este. Se registra aquí, en la herramienta, y no en `app/web.py`, para no
# añadirle a la pantalla un botón que nadie debería pulsar durante una novela normal.
web.SKILLS.setdefault("corte-qa", "/corte-qa")
if "corte-qa" not in web.CON_SUBAGENTES:
    web.CON_SUBAGENTES = (*web.CON_SUBAGENTES, "corte-qa")


def elegir_hecho(raiz: Path, cap: int) -> dict:
    """Un hecho anterior al capítulo del corte, concreto y todavía vigente.

    Se prefiere uno con número dentro: negar «menos de cuatro horas» es inequívoco, y no depende de
    que QA entienda un matiz. Se descartan los superados, que ya no obligan a nada.
    """
    hechos = json.loads((raiz / "04_estado" / "continuidad.json").read_text(encoding="utf-8"))
    vivos = [h for h in hechos
             if h.get("superado_por") in (None, "")
             and (h.get("cap_origen") or 0) < cap
             and len(h.get("hecho", "")) > 60]
    if not vivos:
        raise SystemExit("no hay ningún hecho vigente anterior al corte que negar")
    con_numero = [h for h in vivos if any(c.isdigit() for c in h["hecho"])]
    return (con_numero or vivos)[0]


def parrafo_que_niega(hecho: dict) -> str:
    """La negación literal del hecho, dicha sin rodeos.

    No se intenta escribir una contradicción sutil a propósito. Si QA no caza la evidente, la sutil
    da igual; y si la caza, el siguiente test puede afinar. Empezar por lo grueso hace que un fallo
    signifique algo.
    """
    texto = hecho["hecho"].rstrip(".")
    texto = texto[0].lower() + texto[1:]
    return (
        "\n\nY había una cosa más, que nadie en la estación se molestaba ya en discutir: "
        f"era falso que {texto}. Nunca había sido cierto. Los registros decían exactamente lo "
        "contrario desde el primer día, y todos a bordo lo sabían.\n"
    )


# Lo que hace falta para que el árbol copiado sea un harness y no solo una novela. `app` es el que se
# olvidó la primera vez: sin él `python -m app` no existe, la fase muere al arrancar y el test lo
# contaba como que QA no había detectado nada.
DEL_HARNESS = ("app", "scripts", ".claude", "config", "herramientas", "CLAUDE.md", "pyproject.toml")


def preparar_copia(origen: Path, destino: Path) -> int:
    shutil.copytree(origen, destino, dirs_exist_ok=True)
    # Las novelas archivadas guardan su estado y su manuscrito, no el harness que las escribió.
    raiz_trabajo = Path(__file__).resolve().parents[1]
    for pieza in DEL_HARNESS:
        fuente = raiz_trabajo / pieza
        if fuente.is_dir():
            shutil.copytree(fuente, destino / pieza, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        elif fuente.is_file():
            shutil.copy2(fuente, destino / pieza)
    faltan = [p for p in DEL_HARNESS if not (destino / p).exists()]
    if faltan:
        raise SystemExit(f"el árbol de prueba quedó incompleto, falta: {', '.join(faltan)}")
    (destino / ".venv").mkdir(exist_ok=True)
    venv = raiz_trabajo / ".venv"
    if venv.is_dir() and not (destino / ".venv" / "Scripts").exists():
        # Un symlink evita copiar cientos de megas; si el sistema no lo permite, se copia.
        try:
            (destino / ".venv").rmdir()
            os.symlink(venv, destino / ".venv", target_is_directory=True)
        except OSError:
            shutil.copytree(venv, destino / ".venv", dirs_exist_ok=True)

    m = checkpoint.exigir_manifest(destino)
    cap = m.ultimo_capitulo_cerrado
    if not cap:
        raise SystemExit("la novela no tiene ningún capítulo cerrado: no hay nada que auditar")
    return cap


def volver_a_en_progreso(raiz: Path, cap: int) -> None:
    """El corte ya corrió cuando la novela se escribió; hay que dejar el manifiesto como lo espera.

    `corte-qa` exige `en_progreso`: una novela archivada está terminada o pausada. Se reescribe solo
    ese campo, y se borra el reporte del capítulo para que QA no pueda limitarse a releer el suyo.
    """
    ruta = raiz / "04_estado" / "manifest.json"
    m = json.loads(ruta.read_text(encoding="utf-8"))
    m["estado"] = "en_progreso"
    m["reporte_qa_pendiente"] = None
    ruta.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
    for nombre in (f"qa_cap_{cap}.json", f"qa_cap_{cap}.md"):
        (raiz / "06_qa" / "reportes" / nombre).unlink(missing_ok=True)


def correr(raiz: Path, cap: int, tope_s: float) -> dict:
    # H-06 resuelve las rutas permitidas contra `HARNESS_RAIZ`, y la fase la hereda del proceso. Si
    # queda apuntando al árbol de trabajo, el hook bloquea escrituras a `06_qa/` del árbol de prueba
    # --que están dentro de `06_qa/`, solo que del otro árbol-- y el corte muere sin dejar reporte.
    # Se fija aquí, que es el único sitio que sabe cuál es el árbol bueno.
    os.environ["HARNESS_RAIZ"] = str(raiz)
    fin = web.ejecutar_fase(raiz, "corte-qa", tope_s=tope_s)
    reporte = raiz / "06_qa" / "reportes" / f"qa_cap_{cap}.json"
    if not reporte.is_file():
        # Sin reporte no se sabe nada de QA: la fase no llegó a producir veredicto. Esto tiene que
        # salir como error del test y no como «QA no detectó», que es la lectura que más daño hace.
        salida = str(fin.get("salida") or fin.get("stderr") or fin)[-400:]
        return {"error": f"la fase corte-qa no dejó reporte: {salida}", "marca": None}
    d = json.loads(reporte.read_text(encoding="utf-8"))
    estado = json.loads((raiz / "04_estado" / "manifest.json").read_text(encoding="utf-8")).get("estado")
    return {"marca": bool(d.get("tiene_contradicciones")), "estado": estado,
            "hallazgos": [h.get("descripcion", "")[:160] for h in d.get("hallazgos", [])]}


def una_vuelta(novela: Path, etiqueta: str, inyectar: bool, tope_s: float) -> dict:
    # `resolve()` no es cosmético: en Windows `mkdtemp` devuelve la forma corta 8.3
    # (`C:\\Users\\HAROLD~1.ROD\\...`) y el hook H-06 compara la ruta escrita contra la raíz como
    # texto. Con las dos formas mezcladas, una escritura que está dentro de `06_qa/` se ve fuera de
    # la raíz y el corte muere sin dejar reporte.
    base = Path(tempfile.mkdtemp(prefix=f"qa-{etiqueta}-")).resolve()
    destino = base / "novela"
    cap = preparar_copia(novela, destino)
    volver_a_en_progreso(destino, cap)

    inyectado = None
    if inyectar:
        hecho = elegir_hecho(destino, cap)
        inyectado = parrafo_que_niega(hecho)
        manuscrito = destino / "05_manuscrito" / f"cap_{cap}.md"
        manuscrito.write_text(manuscrito.read_text(encoding="utf-8") + inyectado, encoding="utf-8")
        print(f"  hecho negado (cap {hecho.get('cap_origen')}): {hecho['hecho'][:120]}")

    print(f"  corriendo el corte sobre el capítulo {cap} en {destino}")
    r = correr(destino, cap, tope_s)
    r.update({"etiqueta": etiqueta, "capitulo": cap, "arbol": str(destino), "inyectado": inyectado})
    return r


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("novela", type=Path, help="carpeta de una novela archivada")
    ap.add_argument("--solo", choices=("control", "inyectado"), default=None)
    ap.add_argument("--tope-min", type=float, default=20.0)
    a = ap.parse_args(argv[1:])

    if not (a.novela / "04_estado" / "manifest.json").is_file():
        print(f"no parece una novela: falta {a.novela}/04_estado/manifest.json")
        return 1

    vueltas = [("control", False), ("inyectado", True)]
    if a.solo:
        vueltas = [v for v in vueltas if v[0] == a.solo]

    salida = []
    for etiqueta, inyectar in vueltas:
        print(f"\n== {etiqueta} ==")
        salida.append(una_vuelta(a.novela, etiqueta, inyectar, a.tope_min * 60))
        r = salida[-1]
        print(f"  tiene_contradicciones: {r.get('marca')}  ·  manifiesto: {r.get('estado')}")
        for h in r.get("hallazgos") or []:
            print(f"    - {h}")

    print("\n== veredicto ==")
    por = {r["etiqueta"]: r for r in salida}

    # Primero, si el corte no llegó a correr. Un test que dijera «QA no detectó» cuando en realidad
    # la fase ni arrancó estaría acusando al verificador de lo que es un fallo suyo, y esa lectura es
    # la que mandaría a rehacer medidas que están bien.
    rotas = [r for r in salida if r.get("error")]
    if rotas:
        for r in rotas:
            print(f"  SIN VEREDICTO ({r['etiqueta']}): {r['error']}")
        print("  El test no dice nada sobre QA: lo que falló es el test.")
        return 3

    fallos = []
    if "control" in por and por["control"].get("marca") is not False:
        fallos.append("el control marcó contradicciones en una novela que salió limpia: QA es ruidoso "
                      "y los ceros del CSV no son mérito suyo")
    if "inyectado" in por and por["inyectado"].get("marca") is not True:
        fallos.append("QA NO cazó una contradicción puesta a la cara: la columna `contradicciones` "
                      "del CSV no mide lo que creemos y las comparaciones entre variantes hay que rehacerlas")
    if fallos:
        for f in fallos:
            print(f"  FALLA: {f}")
        return 2
    print("  QA distingue: calla con la novela limpia y pausa con la contradicción puesta.")
    print("  Los árboles quedan sin borrar por si hay que mirarlos; son temporales del sistema.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
