"""Comprueba la cronologia de una novela con Lean, desde la base (specs/spec-lean.md, RF-LEAN-05).

    python verificar_lean.py --novela 1                  # la base de NOVELAS_DB_PATH
    python verificar_lean.py --novela 1 --db copia.db    # otra base
    python verificar_lean.py --novela 1 --generar        # solo imprime el fichero .lean

Abre la base en SOLO LECTURA: se puede lanzar con el worker en marcha, y sobre una copia hecha
con la API de backup de una base que no se debe tocar.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import config
from compartido import db
from orquestador import lean


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Comprueba la cronologia de una novela con Lean.")
    p.add_argument("--novela", type=int, required=True, help="id de la novela")
    p.add_argument("--db", type=Path, help="ruta de la base; por defecto, la de la config")
    p.add_argument("--generar", action="store_true", help="solo imprime el fichero .lean")
    args = p.parse_args(argv)

    ruta = args.db or config.cargar().db_path
    con = db.conectar(ruta, solo_lectura=True)
    try:
        if args.generar:
            # En bytes: la consola de Windows no es UTF-8 y el fichero lleva texto de la prosa.
            sys.stdout.buffer.write(lean.generar(con, args.novela).encode("utf-8"))
            sys.stdout.flush()
            return 0
        resultado = lean.verificar(con, args.novela)
    finally:
        con.close()
    print(f"Novela {args.novela}: {resultado.veredicto}")
    for c in resultado.conflictos:
        print(f"  {c}")
    return 0 if resultado.pasa else 1


if __name__ == "__main__":
    sys.exit(main())
