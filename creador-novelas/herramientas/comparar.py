"""Compara las vueltas del loop de velocidad a partir de `09_archivo/corridas.csv`.

Una vuelta sola no dice nada: lo que decide es la media de su variante frente a la de la base, y si
esa diferencia es mayor que lo que el sistema varía consigo mismo. Por eso se imprime también la
dispersión, y por eso los guardarraíles van en la misma tabla que el reloj: una vuelta más rápida
que se contradice más no es una mejora, es un cambio de sitio del problema.

Uso: python herramientas/comparar.py [ruta/al/corridas.csv]
"""

from __future__ import annotations

import csv
import statistics
import sys
from collections import defaultdict
from pathlib import Path

NUMERICAS = ("minutos", "coste_usd", "escritor_tokens_salida", "extractor_tokens_salida",
             "qa_tokens_salida", "escritor_segundos", "extractor_segundos", "qa_segundos",
             "contradicciones", "correcciones", "capitulos")


def _num(fila: dict, clave: str) -> float | None:
    crudo = (fila.get(clave) or "").strip()
    if crudo == "":
        return None
    try:
        return float(crudo)
    except ValueError:
        return None


def leer(ruta: Path) -> list[dict]:
    with ruta.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def por_variante(filas: list[dict]) -> dict[str, list[dict]]:
    grupos: dict[str, list[dict]] = defaultdict(list)
    for f in filas:
        # Solo las completas entran en la media: una novela que paró a mitad tardó menos por no
        # haber escrito el final, y promediarla haría parecer rápida a la vuelta que más falla.
        if f.get("completa") == "1":
            grupos[f.get("variante") or "(sin variante)"].append(f)
    return dict(grupos)


def _resumen(valores: list[float]) -> str:
    if not valores:
        return "     -"
    media = statistics.mean(valores)
    if len(valores) < 2:
        return f"{media:7.1f}"
    return f"{media:7.1f} ±{statistics.stdev(valores):.1f}"


def informe(filas: list[dict]) -> str:
    grupos = por_variante(filas)
    incompletas = [f for f in filas if f.get("completa") != "1"]
    lineas = []
    for clave in ("minutos", "coste_usd", "escritor_tokens_salida", "extractor_tokens_salida",
                  "qa_tokens_salida", "contradicciones", "correcciones"):
        fila = [f"{clave:26}"]
        for variante, grupo in sorted(grupos.items()):
            valores = [v for v in (_num(f, clave) for f in grupo) if v is not None]
            fila.append(f"{variante}: {_resumen(valores)}")
        lineas.append("  ".join(fila))

    cabecera = " · ".join(f"{v} (n={len(g)})" for v, g in sorted(grupos.items()))
    salida = [f"Novelas completas por variante: {cabecera or 'ninguna'}", ""] + lineas

    base = grupos.get("base") or []
    for variante, grupo in sorted(grupos.items()):
        if variante == "base" or not base:
            continue
        m_base = statistics.mean([v for v in (_num(f, "minutos") for f in base) if v is not None] or [0])
        m_var = statistics.mean([v for v in (_num(f, "minutos") for f in grupo) if v is not None] or [0])
        if m_base:
            salida.append(f"\n{variante} frente a base: {(m_var - m_base) / m_base * 100:+.0f} % de reloj")

    if incompletas:
        salida.append("\nFuera de la media, por no haber terminado:")
        for f in incompletas:
            salida.append(f"  {f.get('variante')}/{f.get('novela')}: {f.get('fallo')}")
    return "\n".join(salida)


def main(argv: list[str]) -> int:
    ruta = Path(argv[1]) if len(argv) > 1 else Path("09_archivo/corridas.csv")
    if not ruta.is_file():
        print(f"no existe {ruta}")
        return 1
    print(informe(leer(ruta)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
