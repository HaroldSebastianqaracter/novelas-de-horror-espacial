"""La revision humana con la misma rubrica que el juez, y su comparacion con el LLM.

    python -m evals.rubrica_humana --db copia.db --novela 1 --plantilla mis_notas.csv
    python -m evals.rubrica_humana --db copia.db --novela 1 --importar mis_notas.csv
    python -m evals.rubrica_humana --db copia.db --novela 1 --comparar

La plantilla trae los seis criterios con lo que mide cada uno; se rellenan `nota` (1 a 5),
`justificacion` y, si se quiere, `evidencia` (una cita de la novela). Importar la guarda en
`evaluacion_rubrica` con `origen = 'humano'`; comparar enseña la tabla del juez frente a la
persona y cuanto se parecen. Importar escribe en la base: hazlo sobre una copia, o con el
worker parado.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from compartido import db
from compartido.db import transaccion
from compartido.tipos import CRITERIOS_RUBRICA
from tareas.rubrica import servicio as s_rubrica

COLUMNAS = ("criterio", "que_mide", "nota", "justificacion", "evidencia")

#: Punto y coma y BOM: es lo que abre bien un Excel en castellano con doble clic.
SEPARADOR = ";"


class PlantillaInvalida(Exception):
    """La plantilla rellenada no trae una nota valida por criterio."""


def escribir_plantilla(ruta: Path) -> None:
    with ruta.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=SEPARADOR)
        w.writerow(COLUMNAS)
        for c in CRITERIOS_RUBRICA:
            w.writerow([c, s_rubrica.DESCRIPCIONES[c], "", "", ""])


def leer_plantilla(ruta: Path) -> list[dict[str, str | int]]:
    """Las seis notas de una plantilla rellenada, o `PlantillaInvalida` con lo que falta."""
    bruto = ruta.read_bytes()
    try:
        texto = bruto.decode("utf-8-sig")
    except UnicodeDecodeError:
        texto = bruto.decode("cp1252")  # Excel en Windows guarda asi el «CSV (delimitado)»
    cabecera = texto.splitlines()[0] if texto else ""
    separador = ";" if cabecera.count(";") > cabecera.count(",") else ","
    filas = {str(r.get("criterio") or "").strip(): r
             for r in csv.DictReader(texto.splitlines(), delimiter=separador)}
    notas: list[dict[str, str | int]] = []
    errores: list[str] = []
    for c in CRITERIOS_RUBRICA:
        fila = filas.get(c)
        bruto = str((fila or {}).get("nota") or "").strip()
        if not bruto.isdigit() or not 1 <= int(bruto) <= 5:
            errores.append(f"{c}: la nota tiene que ser un numero de 1 a 5 (hay «{bruto}»)")
            continue
        assert fila is not None
        notas.append({"criterio": c, "nota": int(bruto),
                      "justificacion": str(fila.get("justificacion") or "").strip(),
                      "evidencia": str(fila.get("evidencia") or "").strip()})
    if errores:
        raise PlantillaInvalida("\n".join(errores))
    return notas


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Revision humana con la rubrica del juez.")
    p.add_argument("--db", type=Path, required=True)
    p.add_argument("--novela", type=int, required=True)
    que = p.add_mutually_exclusive_group(required=True)
    que.add_argument("--plantilla", type=Path, help="escribe la plantilla vacia en este CSV")
    que.add_argument("--importar", type=Path, help="guarda las notas de este CSV rellenado")
    que.add_argument("--comparar", action="store_true", help="juez frente a revision humana")
    args = p.parse_args(argv)

    if args.plantilla:
        escribir_plantilla(args.plantilla)
        print(f"Plantilla en {args.plantilla}: rellena nota, justificacion y evidencia.")
        return 0
    con = db.conectar(args.db, solo_lectura=args.comparar)
    try:
        if not s_rubrica.existe_la_tabla(con):
            print("La base no tiene la rubrica (migracion 015): abrela antes con el worker.")
            return 1
        if con.execute("SELECT 1 FROM novela WHERE id = ?", (args.novela,)).fetchone() is None:
            print(f"No hay ninguna novela {args.novela} en esa base.")
            return 1
        if args.comparar:
            print(s_rubrica.comparar(con, args.novela))
            return 0
        try:
            notas = leer_plantilla(args.importar)
        except PlantillaInvalida as exc:
            print(f"La plantilla no vale:\n{exc}")
            return 1
        with transaccion(con):
            s_rubrica.registrar(con, args.novela, list(notas), origen="humano")
        print(f"Guardadas {len(notas)} notas de la revision humana de la novela {args.novela}.")
        print(s_rubrica.comparar(con, args.novela))
        return 0
    finally:
        con.close()


if __name__ == "__main__":
    sys.exit(main())
