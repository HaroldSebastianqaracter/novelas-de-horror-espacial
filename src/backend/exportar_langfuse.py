"""Exporta novelas enteras a Langfuse desde la base (specs/spec3.md, RF3-OBS-09).

    python exportar_langfuse.py --comprobar       # prueba las claves y el host
    python exportar_langfuse.py --novela 1        # una novela
    python exportar_langfuse.py --todas           # todas las de la base

Abre la base en SOLO LECTURA y no marca nada: los identificadores son deterministas, asi que
repetirlo no duplica en Langfuse. Sirve para novelas escritas antes del bloque 4 o con el
worker sin claves. Las claves se leen de `src/backend/.env` (RF3-OBS-02).
"""

from __future__ import annotations

import argparse
import sys

import config
from compartido import db
from orquestador.observabilidad import ClienteHTTP, ErrorLangfuse, Exportador


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Exporta novelas enteras a Langfuse desde la base.")
    que = p.add_mutually_exclusive_group(required=True)
    que.add_argument("--novela", type=int, help="id de la novela a exportar")
    que.add_argument("--todas", action="store_true", help="todas las novelas de la base")
    que.add_argument("--comprobar", action="store_true", help="solo prueba claves y host")
    args = p.parse_args(argv)

    cfg = config.cargar()
    if not cfg.langfuse_activo:
        print("Faltan LANGFUSE_PUBLIC_KEY y LANGFUSE_SECRET_KEY en src/backend/.env.")
        return 2
    cliente = ClienteHTTP(
        cfg.langfuse_host, str(cfg.langfuse_public_key), str(cfg.langfuse_secret_key)
    )
    try:
        if args.comprobar:
            cliente.comprobar()
            print(f"Claves validas en {cfg.langfuse_host}.")
            return 0
        con = db.conectar(cfg.db_path, solo_lectura=True)
        ids = (
            [int(f[0]) for f in con.execute("SELECT id FROM novela ORDER BY id")]
            if args.todas else [args.novela]
        )
        exportador = Exportador(cliente, marcar=False)
        for novela_id in ids:
            informe = exportador.exportar(con, novela_id)
            print(f"Novela {novela_id}: {informe.eventos} eventos de {informe.filas} filas.")
        return 0
    except ErrorLangfuse as exc:
        print(f"Langfuse rechazo el envio: {exc}")
        return 1
    finally:
        cliente.cerrar()


if __name__ == "__main__":
    sys.exit(main())
