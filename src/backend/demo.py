"""Lanzador de prueba: crea una novela, la arranca y muestra como va.

No sustituye al worker ni a la API: encola intenciones igual que haria el frontend, y luego
va leyendo el estado. Sirve para ver el pipeline correr sin montar nada mas.

    python demo.py            # crear una novela, arrancarla y ver como avanza
    python demo.py --brief ../../ejemplos/brief-ejemplo.json  # una novela personalizada
    python demo.py --arrancar # arrancar la que ya existe, sin crear otra
    python demo.py --ver      # solo mirar
    python demo.py --cambio "Que se llame «Kira»" --entidad personajes:4  # cambio del lector
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

import config
from compartido import db
from compartido.brief import Brief, analizar
from compartido.cambio import PeticionCambio
from compartido.db import transaccion
from compartido.grafo import lectura
from compartido.tipos import como_dict
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


def _abrir(ruta: Path) -> sqlite3.Connection:
    """Como la API: crea el esquema si hace falta, pero no migra; eso es del worker."""
    con = db.conectar(ruta)
    db.crear_esquema(con)
    return con


def leer_brief(fichero: Path) -> Brief:
    """Admite la intencion entera (como ejemplos/brief-ejemplo.json), su payload o el brief."""
    datos = como_dict(json.loads(fichero.read_text(encoding="utf-8")))
    if "payload" in datos:
        datos = como_dict(datos["payload"])
    if "brief" in datos:
        datos = como_dict(datos["brief"])
    return Brief.model_validate(datos)


def crear(ruta: Path, titulo: str, brief: Brief | None = None) -> int:
    if brief is not None:
        analisis = analizar(brief)
        if not analisis.completo:
            print("El brief no esta completo:", file=sys.stderr)
            for f in analisis.faltantes:
                print(f"  - falta {f}", file=sys.stderr)
            for c in analisis.contradicciones:
                print(f"  - {c.mensaje}", file=sys.stderr)
            return 0
    con = _abrir(ruta)
    try:
        with transaccion(con):
            if brief is not None:
                intencion_id = cola.encolar(
                    con, "crear_novela", None, brief=brief.model_dump(mode="json"),
                )
            else:
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
    con = _abrir(ruta)
    try:
        with transaccion(con):
            cola.encolar(con, "arrancar", novela_id)
        print(f"Novela {novela_id}: arrancar encolado.")
    finally:
        con.close()


def pedir_cambio(
    ruta: Path, novela_id: int, peticion: str, *, entidad: str | None = None,
    hecho: int | None = None, cita_capitulo: int | None = None, cita: str | None = None,
) -> bool:
    """Encola un cambio del lector sobre la ultima version (spec3, RF3-CAM-15).

    Es la variante por linea de comandos del cambio que la web pide desde la pagina.
    """
    if entidad:
        tipo, _, id_ = entidad.partition(":")
        objetivo: dict[str, object] = {"tipo": "entidad", "entidad": tipo, "id": int(id_ or 0)}
    elif hecho is not None:
        objetivo = {"tipo": "hecho", "hecho_id": hecho}
    else:
        objetivo = {"tipo": "fragmento"}
    con = _abrir(ruta)
    try:
        ultima = con.execute(
            "SELECT MAX(numero) FROM novela_version WHERE novela_id = ?", (novela_id,)
        ).fetchone()[0]
        payload: dict[str, object] = {
            "version_base": int(ultima or 0), "objetivo": objetivo, "peticion": peticion,
        }
        if cita_capitulo is not None:
            payload["cita"] = {"capitulo": cita_capitulo, "texto": cita or ""}
        try:
            PeticionCambio.model_validate(payload)
        except ValueError as exc:
            print(f"El cambio no tiene la forma que se espera:\n{exc}", file=sys.stderr)
            return False
        with transaccion(con):
            cola.encolar(con, "cambio_lector", novela_id, **payload)
        print(f"Novela {novela_id}: cambio encolado sobre la version {payload['version_base']}.")
        return True
    finally:
        con.close()


def parar(ruta: Path, novela_id: int) -> None:
    con = _abrir(ruta)
    try:
        with transaccion(con):
            cola.encolar(con, "parar", novela_id)
        print(f"Novela {novela_id}: parar encolado.")
    finally:
        con.close()


def _ultima(ruta: Path) -> int:
    """La novela mas reciente. Casi siempre es con la que se quiere trabajar."""
    if not ruta.exists():
        return 0
    con = db.conectar(ruta, solo_lectura=True)
    try:
        fila = con.execute("SELECT id FROM novela ORDER BY id DESC LIMIT 1").fetchone()
        return int(fila["id"]) if fila else 0
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
            novela_id = _ultima(ruta)
            if not novela_id:
                print("No hay ninguna novela todavia.")
                return

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
                        f"--novela {novela_id}\n  O, si alguien se entero fuera de escena:"
                        f"  python demo.py --dar-por-sabido --novela {novela_id}"
                    )
                break
            if e.get("estado") in ("completada", "completada_con_avisos", "error", "detenida"):
                break
            time.sleep(2)

        resumen(con, novela_id)
    finally:
        con.close()


def resumen(con: sqlite3.Connection, novela_id: int) -> None:
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
            novela_id = _ultima(ruta)
        texto = lectura.texto_capitulo(con, novela_id, numero)
        print(texto or f"El capitulo {numero} no esta escrito todavia.")
    finally:
        con.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--novela", type=int, default=None, help="id; por defecto, la ultima")
    parser.add_argument("--titulo", default="Cerro Quince")
    parser.add_argument("--ver", action="store_true", help="solo mirar, sin crear nada")
    parser.add_argument(
        "--arrancar", action="store_true",
        help="arrancar una novela que ya existe, sin crear otra",
    )
    parser.add_argument("--parar", action="store_true")
    parser.add_argument("--relanzar", type=int, default=None, metavar="N")
    parser.add_argument(
        "--dar-por-sabido", action="store_true",
        help="resolver la parada de continuidad dando por sabido lo que el personaje uso",
    )
    parser.add_argument("--leer", type=int, default=None, metavar="N")
    parser.add_argument("--cambio", default=None, metavar="PETICION",
                        help="pedir un cambio del lector sobre la ultima version (RF3-CAM-15)")
    parser.add_argument("--entidad", default=None, metavar="TIPO:ID",
                        help="con --cambio: personajes:N, lugares:N u objetos:N")
    parser.add_argument("--hecho", type=int, default=None, metavar="ID",
                        help="con --cambio: el hecho que cambia")
    parser.add_argument("--cita-capitulo", type=int, default=None, metavar="N",
                        help="con --cambio: el capitulo del fragmento seleccionado")
    parser.add_argument("--cita", default=None, metavar="TEXTO",
                        help="con --cambio: el fragmento seleccionado")
    parser.add_argument("--segundos", type=int, default=3600, help="cuanto tiempo mirar")
    parser.add_argument(
        "--brief", type=Path, default=None, metavar="FICHERO",
        help="crear una novela personalizada desde un brief (RF3-PER-06)",
    )
    args = parser.parse_args()

    try:
        cfg = config.cargar()
    except config.ConfiguracionInvalida as exc:
        print(f"{exc}\n\nEn cmd:  set NOVELAS_DB_PATH=novela.db", file=sys.stderr)
        return 2

    ruta = cfg.db_path
    print(f"Base de datos: {ruta}   Puerto: {cfg.puerto}\n")

    if args.arrancar:
        novela_id = args.novela or _ultima(ruta)
        if not novela_id:
            print("No hay ninguna novela que arrancar.", file=sys.stderr)
            return 1
        arrancar(ruta, novela_id)
        mirar(ruta, novela_id, args.segundos)
        return 0
    if args.leer is not None:
        leer(ruta, args.novela, args.leer)
        return 0
    if args.cambio is not None:
        novela_id = args.novela or _ultima(ruta)
        if not novela_id or not pedir_cambio(
            ruta, novela_id, args.cambio, entidad=args.entidad, hecho=args.hecho,
            cita_capitulo=args.cita_capitulo, cita=args.cita,
        ):
            return 1
        mirar(ruta, novela_id, args.segundos)
        return 0
    if args.parar:
        parar(ruta, args.novela or _ultima(ruta))
        return 0
    if args.dar_por_sabido:
        con = _abrir(ruta)
        novela_id = args.novela or _ultima(ruta)
        paradas = fallo.paradas_abiertas(con, novela_id) if novela_id else []
        if not paradas:
            print("No hay ninguna parada abierta.", file=sys.stderr)
            return 1
        with transaccion(con):
            cola.encolar(con, "resolver_parada", novela_id, parada_id=int(paradas[0]["id"]),
                         accion="dar_por_sabido")
        con.close()
        print(f"Dar por sabido encolado para la parada {paradas[0]['id']}.")
        return 0
    if args.relanzar is not None:
        con = _abrir(ruta)
        with transaccion(con):
            cola.encolar(con, "relanzar", args.novela, desde_capitulo=args.relanzar)
        con.close()
        print(f"Relanzar desde el capitulo {args.relanzar} encolado.")
        return 0

    if not args.ver:
        brief = leer_brief(args.brief) if args.brief is not None else None
        novela_id = crear(ruta, args.titulo, brief)
        if not novela_id:
            return 1
        arrancar(ruta, novela_id)
        args.novela = novela_id

    mirar(ruta, args.novela, args.segundos)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
