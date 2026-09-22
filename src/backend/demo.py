"""Lanzador de prueba: crea una novela, la arranca y muestra como va.

No sustituye al worker ni a la API: encola intenciones igual que haria el frontend, y luego
va leyendo el estado. Sirve para ver el pipeline correr sin montar nada mas.

    python demo.py --puerto falso      # sin Claude Code y sin gastar nada
    python demo.py --puerto terminal   # con Claude Code de verdad (cuesta dinero)
    python demo.py --ver               # solo mirar como va lo que ya hay
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import config
from compartido import db
from compartido.db import transaccion
from compartido.grafo import lectura
from orquestador import cola, fallo

SEMILLA = (
    "Una cuadrilla de mantenimiento llega a una estacion de reabastecimiento que lleva ocho "
    "meses sin responder."
)
RESTRICCIONES = {
    "longitud_objetivo_palabras": "9000",
    "longitud_capitulo_palabras": "1500-3500",
    "publico": "adulto",
    "politica_contenido": "violencia explicita permitida, sin contenido sexual",
    "pov_por_defecto": "tercera_limitada",
    "tiempo_verbal": "pasado",
}


def crear(ruta: Path, titulo: str) -> int:
    con = db.preparar(ruta)
    try:
        with transaccion(con):
            intencion_id = cola.encolar(
                con, "crear_novela", None,
                titulo=titulo, genero="terror_espacial", semilla_premisa=SEMILLA,
                restricciones=RESTRICCIONES,
            )
        print(f"Intencion {intencion_id}: crear_novela. Esperando al worker...")

        for _ in range(120):
            fila = con.execute(
                "SELECT estado, resultado, motivo FROM intencion WHERE id = ?", (intencion_id,)
            ).fetchone()
            if fila["estado"] == "hecha":
                novela_id = int(json.loads(fila["resultado"])["novela_id"])
                print(f"Novela {novela_id} creada.")
                return novela_id
            if fila["estado"] == "rechazada":
                print(f"Rechazada: {fila['motivo']}", file=sys.stderr)
                return 0
            time.sleep(1)
        print("El worker no responde. Arrancalo en otra ventana.", file=sys.stderr)
        return 0
    finally:
        con.close()


def arrancar(ruta: Path, novela_id: int) -> None:
    con = db.preparar(ruta)
    try:
        with transaccion(con):
            cola.encolar(con, "arrancar", novela_id)
        print(f"Novela {novela_id}: arrancar encolado.")
    finally:
        con.close()


def parar(ruta: Path, novela_id: int) -> None:
    con = db.preparar(ruta)
    try:
        with transaccion(con):
            cola.encolar(con, "parar", novela_id)
        print(f"Novela {novela_id}: parar encolado.")
    finally:
        con.close()


def mirar(ruta: Path, novela_id: int | None, segundos: int) -> None:
    """Muestra el estado cada pocos segundos, como haria el panel del frontend."""
    if not ruta.exists():
        print(f"No existe {ruta}. Crea una novela primero.", file=sys.stderr)
        return
    con = db.conectar(ruta, solo_lectura=True)
    try:
        if novela_id is None:
            fila = con.execute("SELECT id FROM novela ORDER BY id DESC LIMIT 1").fetchone()
            if fila is None:
                print("No hay ninguna novela todavia.")
                return
            novela_id = int(fila["id"])

        ultimo = ""
        limite = time.monotonic() + segundos
        while time.monotonic() < limite:
            e = lectura.ejecucion(con, novela_id) or {}
            total = lectura.total_capitulos(con, novela_id)
            linea = (
                f"[{e.get('estado', '?'):>22}] fase={str(e.get('fase') or '-'):<12} "
                f"cap {e.get('capitulo_actual') or '-'}/{total or '-'} "
                f"intento {e.get('intento_actual')} "
                f"completados {e.get('capitulos_completados')}"
            )
            if linea != ultimo:
                print(linea, flush=True)
                ultimo = linea

            if e.get("estado") == "parada":
                for p in fallo.paradas_abiertas(con, novela_id):
                    print(f"\n  PARADA {p['tipo']} en el capitulo {p['capitulo']}:")
                    informe = json.loads(p["informe"] or "{}")
                    for c in informe.get("conflictos", [])[:8]:
                        print(f"    - {c.get('descripcion', '')[:140]}")
                    if informe.get("motivo"):
                        print(f"    {str(informe['motivo'])[:200]}")
                    print(
                        f"\n  Para seguir:  python demo.py --relanzar {p['capitulo']} "
                        f"--novela {novela_id}"
                    )
                break
            if e.get("estado") in ("completada", "completada_con_avisos", "error", "detenida"):
                break
            time.sleep(2)

        resumen(con, novela_id)
    finally:
        con.close()


def resumen(con, novela_id: int) -> None:
    capitulos = con.execute(
        "SELECT numero, estado, resumen_breve FROM capitulo WHERE novela_id = ? ORDER BY numero",
        (novela_id,),
    ).fetchall()
    if not capitulos:
        return
    print("\nCapitulos:")
    for c in capitulos:
        marca = "escrito" if c["estado"] == "completado" else "pendiente"
        print(f"  {c['numero']:>3}. [{marca:^9}] {(c['resumen_breve'] or '')[:90]}")

    coste = con.execute(
        "SELECT COUNT(*) n, COALESCE(SUM(tokens_salida),0) tok FROM llamada_modelo "
        "WHERE novela_id = ?", (novela_id,)
    ).fetchone()
    print(f"\nLlamadas al agente: {coste['n']} | tokens de salida: {coste['tok']}")
    print(f"Lee un capitulo:  python demo.py --leer 1 --novela {novela_id}")


def leer(ruta: Path, novela_id: int | None, numero: int) -> None:
    con = db.conectar(ruta, solo_lectura=True)
    try:
        if novela_id is None:
            fila = con.execute("SELECT id FROM novela ORDER BY id DESC LIMIT 1").fetchone()
            novela_id = int(fila["id"]) if fila else 0
        texto = lectura.texto_capitulo(con, novela_id, numero)
        print(texto or f"El capitulo {numero} no esta escrito todavia.")
    finally:
        con.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--novela", type=int, default=None, help="id; por defecto, la ultima")
    parser.add_argument("--titulo", default="Cerro Quince")
    parser.add_argument("--ver", action="store_true", help="solo mirar, sin crear nada")
    parser.add_argument("--parar", action="store_true")
    parser.add_argument("--relanzar", type=int, default=None, metavar="N")
    parser.add_argument("--leer", type=int, default=None, metavar="N")
    parser.add_argument("--segundos", type=int, default=3600, help="cuanto tiempo mirar")
    args = parser.parse_args()

    try:
        cfg = config.cargar()
    except config.ConfiguracionInvalida as exc:
        print(f"{exc}\n\nEn cmd:  set NOVELAS_DB_PATH=novela.db", file=sys.stderr)
        return 2

    ruta = cfg.db_path
    print(f"Base de datos: {ruta}   Puerto: {cfg.puerto}\n")

    if args.leer is not None:
        leer(ruta, args.novela, args.leer)
        return 0
    if args.parar:
        parar(ruta, args.novela or 0)
        return 0
    if args.relanzar is not None:
        con = db.preparar(ruta)
        with transaccion(con):
            cola.encolar(con, "relanzar", args.novela, desde_capitulo=args.relanzar)
        con.close()
        print(f"Relanzar desde el capitulo {args.relanzar} encolado.")
        return 0

    if not args.ver:
        novela_id = crear(ruta, args.titulo)
        if not novela_id:
            return 1
        arrancar(ruta, novela_id)
        args.novela = novela_id

    mirar(ruta, args.novela, args.segundos)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
