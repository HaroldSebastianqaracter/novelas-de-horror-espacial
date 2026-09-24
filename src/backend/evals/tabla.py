"""La tabla de evals: que validadores pasan y cuales fallan con cada brief (specs/spec3.md, 3.10,
RF3-EVL-01 a 03).

    python -m evals.tabla ../../ejemplos/brief-ejemplo.json ../../ejemplos/evals/*.json \\
        --puerto falso --dir evals_out --salida evals_out/tabla.md

Cada brief corre de principio a fin por el mismo camino que una novela de verdad (el texto
libre por el entrevistador, `crear_novela` y `arrancar` en el worker) sobre una base propia en
`--dir`. Una parada no se resuelve: es un resultado, y la tabla dice que validador la provoco.
Con `--puerto terminal` cuesta dinero (Claude Code real).
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import sqlite3
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from pydantic import ValidationError

import config
import entrevista
import worker
from compartido import db
from compartido.brief import analizar
from compartido.db import transaccion
from compartido.grafo.escritura import normalizar
from compartido.puerto import construir as construir_puerto
from compartido.tipos import como_dict, como_lista
from orquestador import cola


@dataclass(frozen=True)
class Validador:
    clave: str
    nombre: str
    tipo: str        # programatico, semantico o formal (enunciado, seccion 5)
    donde: str       # en que punto del harness corre


#: Los validadores de la tabla, en el orden en que corren (RF3-EVL-02).
VALIDADORES: tuple[Validador, ...] = (
    Validador("brief_schema", "Schema del brief", "programático", "configuración"),
    Validador("brief_completo", "Datos que faltan", "programático", "configuración"),
    Validador("brief_contradicciones", "Contradicciones del brief", "programático",
              "configuración"),
    Validador("inyeccion", "Inyección en el texto libre", "programático", "configuración"),
    Validador("puerta_1", "Estructura (puerta 1)", "programático", "planificación"),
    Validador("puerta_2", "Escaleta (puerta 2)", "programático", "planificación"),
    Validador("puerta_3", "Continuidad en SQL (puerta 3)", "programático",
              "capítulo (validación)"),
    Validador("guardrail", "Palabras vetadas", "programático", "capítulo (política)"),
    Validador("nombres", "Personalización: nombres, allegados, elementos y etiquetas",
              "programático", "capítulo (puerta 4)"),
    Validador("longitud", "Longitud del capítulo", "programático", "capítulo (puerta 4)"),
    Validador("puerta_4_mecanica", "Mecánica de prosa (puerta 4)", "programático",
              "capítulo (puerta 4)"),
    Validador("juez", "LLM-as-judge de oficio", "semántico", "capítulo (rol editor)"),
    Validador("puerta_5", "Puerta global (puerta 5)", "programático", "antes de publicar"),
    Validador("lean", "Cronología en Lean 4", "formal", "antes de publicar"),
    Validador("canario", "Canario de la inyección en la prosa", "programático", "evals"),
)

_NOMBRES = frozenset({"nombre_mal_escrito", "allegado_ausente", "etiqueta_en_la_prosa",
                      "elemento_sin_integrar"})
#: Avisos de la puerta 4 que hablan del juez, no de la prosa.
_DEL_JUEZ = frozenset({"juicio_no_invocado", "juicio_dividido", "juicio_ausente"})


def validador_de(puerta: int, comprobacion: str) -> str:
    """A que fila de la tabla va una comprobacion registrada por una puerta."""
    if puerta == 4:
        if comprobacion.startswith("juicio") or comprobacion in _DEL_JUEZ:
            return "juez"
        if comprobacion == "termino_vetado":
            return "guardrail"
        if comprobacion in _NOMBRES:
            return "nombres"
        if comprobacion.startswith("longitud"):
            return "longitud"
        return "puerta_4_mecanica"
    return f"puerta_{puerta}"


@dataclass
class Resultado:
    """Lo que salio de un brief: una celda por validador y el detalle de lo que salto."""

    nombre: str
    proposito: str
    celdas: dict[str, str] = field(default_factory=dict[str, str])
    detalle: Counter[str] = field(default_factory=Counter[str])
    estado: str = "sin ejecutar"
    capitulos: str = "0"
    paradas: list[str] = field(default_factory=list[str])
    coste_usd: float = 0.0
    llamadas: int = 0


def _celda(evaluaciones: int, fallos: int, avisos: int) -> str:
    if not evaluaciones:
        return "sin ejecutar"
    base = "pasa" if not fallos else f"falla {fallos}/{evaluaciones}"
    return base + (f" · {avisos} avisos" if avisos else "")


def evaluar_brief(fichero: Path, directorio: Path, cfg_base: config.Config, *,
                  capitulos: int | None = None) -> Resultado:
    """Corre un brief entero sobre una base nueva y devuelve su columna de la tabla."""
    datos = como_dict(json.loads(fichero.read_text(encoding="utf-8")))
    meta = como_dict(datos.get("eval"))
    r = Resultado(nombre=str(meta.get("nombre") or fichero.stem),
                  proposito=str(meta.get("proposito") or ""))
    for v in VALIDADORES:
        r.celdas[v.clave] = "sin ejecutar"
    r.celdas["lean"] = "no integrado"

    try:
        brief = entrevista.leer_brief(fichero)
    except ValidationError as exc:
        r.celdas["brief_schema"] = f"falla ({exc.error_count()} errores)"
        r.estado = "brief rechazado"
        return r
    r.celdas["brief_schema"] = "pasa"
    if capitulos is not None:
        brief = brief.model_copy(update={"capitulos": capitulos})
    analisis = analizar(brief.con_codigos())
    r.celdas["brief_completo"] = ("pasa" if not analisis.faltantes
                                  else f"falla ({len(analisis.faltantes)})")
    r.celdas["brief_contradicciones"] = (
        "pasa" if not analisis.contradicciones
        else "detecta " + ", ".join(c.codigo for c in analisis.contradicciones)
    )

    ruta = directorio / f"{r.nombre}.db"
    if ruta.exists():
        raise FileExistsError(f"{ruta} ya existe: cada eval empieza sobre una base nueva.")
    cfg = replace(cfg_base, db_path=ruta)
    con = db.preparar(ruta)
    try:
        transcripcion: dict[str, Any] = {"origen": "eval", "fichero": fichero.name}
        texto = brief.texto_libre
        if texto.strip():
            llamadas: list[dict[str, Any]] = []
            brief, alertas, aplicado = entrevista.procesar_texto_libre(
                construir_puerto(cfg, None), brief.model_copy(update={"texto_libre": ""}),
                texto, llamadas,
            )
            transcripcion.update(texto_libre=aplicado, alertas=alertas, llamadas=llamadas)
            r.celdas["inyeccion"] = (f"detecta {len(alertas)}" if alertas
                                     else "no detecta")
        else:
            r.celdas["inyeccion"] = "no aplica"
        if analisis.faltantes:
            r.estado = "brief incompleto"
            return r

        w = worker.Worker(cfg, con=con)
        with transaccion(con):
            cola.encolar(con, "crear_novela", None, brief=brief.model_dump(mode="json"),
                         entrevista=transcripcion)
        _atender(w, con)
        fila = con.execute("SELECT MAX(id) FROM novela").fetchone()
        if fila[0] is None:
            r.estado = "no se creó la novela"
            return r
        novela_id = int(fila[0])
        with transaccion(con):
            cola.encolar(con, "arrancar", novela_id)
        _atender(w, con)
        _recoger(con, novela_id, r, canario=str(meta.get("canario") or ""))
    finally:
        con.close()
    return r


def _atender(w: worker.Worker, con: sqlite3.Connection) -> None:
    intencion = cola.tomar(con)
    if intencion is not None:
        w.atender(intencion)


def _recoger(con: sqlite3.Connection, novela_id: int, r: Resultado, *, canario: str) -> None:
    evaluaciones: Counter[str] = Counter()
    fallos: Counter[str] = Counter()
    avisos: Counter[str] = Counter()
    for puerta, detalle in con.execute(
        "SELECT puerta, detalle FROM resultado_puerta WHERE novela_id = ? ORDER BY id",
        (novela_id,),
    ):
        conflictos = [como_dict(c) for c in como_lista(
            como_dict(json.loads(detalle or "{}")).get("conflictos"))]
        filas = {validador_de(int(puerta), "")} if int(puerta) != 4 else {
            "juez", "guardrail", "nombres", "longitud", "puerta_4_mecanica"}
        for f in filas:
            evaluaciones[f] += 1
        fallan: set[str] = set()
        for c in conflictos:
            comprobacion = str(c.get("comprobacion"))
            fila = validador_de(int(puerta), comprobacion)
            if c.get("aviso"):
                avisos[fila] += 1
                r.detalle[f"{comprobacion} (aviso)"] += 1
            else:
                fallan.add(fila)
                r.detalle[comprobacion] += 1
        for f in fallan:
            fallos[f] += 1
    for clave in evaluaciones:
        r.celdas[clave] = _celda(evaluaciones[clave], fallos[clave], avisos[clave])

    estado = con.execute("SELECT estado FROM ejecucion WHERE novela_id = ?",
                         (novela_id,)).fetchone()
    r.estado = str(estado[0]) if estado else "sin ejecución"
    hechos = con.execute(
        "SELECT COUNT(*) FROM capitulo WHERE novela_id = ? AND estado = 'completado'",
        (novela_id,)).fetchone()[0]
    total = con.execute("SELECT COUNT(*) FROM capitulo WHERE novela_id = ?",
                        (novela_id,)).fetchone()[0]
    r.capitulos = f"{hechos}/{total}"
    r.paradas = [f"{t} (cap. {c})" if c else str(t) for t, c in con.execute(
        "SELECT p.tipo, p.capitulo FROM parada p JOIN ejecucion e ON e.id = p.ejecucion_id "
        "WHERE e.novela_id = ? ORDER BY p.id", (novela_id,))]
    for (meta,) in con.execute("SELECT metadatos FROM llamada_modelo WHERE novela_id = ?",
                               (novela_id,)):
        r.llamadas += 1
        with contextlib.suppress(ValueError, TypeError):
            r.coste_usd += float(como_dict(json.loads(meta or "{}")).get("total_cost_usd")
                                 or 0)

    if canario:
        textos = [str(t) for (t,) in con.execute(
            "SELECT et.texto FROM escena_texto et JOIN escena e ON e.id = et.escena_id "
            "WHERE e.novela_id = ?", (novela_id,))]
        veces = normalizar(" ".join(textos)).count(normalizar(canario))
        # Sin prosa no hay nada que mirar: `sin ejecutar`, no `pasa` (validador de 73d4723).
        r.celdas["canario"] = ("sin ejecutar" if not textos
                               else "pasa" if not veces else f"falla ({veces})")
    else:
        r.celdas["canario"] = "no aplica"


def tabla_markdown(resultados: list[Resultado]) -> str:
    """Las dos tablas: una fila por validador y una columna por brief, y lo que salto."""
    cab = "| Validador | Tipo | Dónde | " + " | ".join(r.nombre for r in resultados) + " |"
    sep = "| --- | --- | --- | " + " | ".join("---" for _ in resultados) + " |"
    lineas = ["## Validadores por brief", "", cab, sep]
    for v in VALIDADORES:
        lineas.append(f"| {v.nombre} | {v.tipo} | {v.donde} | "
                      + " | ".join(r.celdas.get(v.clave, "") for r in resultados) + " |")
    finales: list[tuple[str, Callable[[Resultado], str]]] = [
        ("Estado final", lambda r: r.estado),
        ("Capítulos completados", lambda r: r.capitulos),
        ("Paradas", lambda r: ", ".join(r.paradas) or "ninguna"),
        ("Llamadas al modelo", lambda r: str(r.llamadas)),
        ("Coste (USD)", lambda r: f"{r.coste_usd:.2f}"),
    ]
    for etiqueta, valor in finales:
        lineas.append(f"| **{etiqueta}** | | | " + " | ".join(valor(r) for r in resultados)
                      + " |")
    lineas += ["", "## Qué saltó en cada brief", ""]
    for r in resultados:
        lineas.append(f"### {r.nombre}")
        if r.proposito:
            lineas.append(f"\n{r.proposito}\n")
        if r.detalle:
            lineas += [f"- `{k}`: {n}" for k, n in sorted(r.detalle.items())]
        else:
            lineas.append("- Nada.")
        lineas.append("")
    return "\n".join(lineas)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("briefs", nargs="+", type=Path)
    parser.add_argument("--puerto", choices=("falso", "terminal"), default="falso")
    parser.add_argument("--dir", type=Path, required=True,
                        help="carpeta nueva para las bases de cada brief")
    parser.add_argument("--capitulos", type=int, default=None,
                        help="recorta cada brief a N capitulos (una pasada barata)")
    parser.add_argument("--salida", type=Path, default=None, help="fichero .md de la tabla")
    args = parser.parse_args()

    args.dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("NOVELAS_DB_PATH", str(args.dir / "sin_uso.db"))
    cfg = replace(config.cargar(), puerto=args.puerto)
    resultados = [evaluar_brief(b, args.dir, cfg, capitulos=args.capitulos)
                  for b in args.briefs]
    texto = tabla_markdown(resultados)
    if args.salida:
        args.salida.write_text(texto + "\n", encoding="utf-8")
        args.salida.with_suffix(".json").write_text(json.dumps(
            [{**r.__dict__, "detalle": dict(r.detalle)} for r in resultados],
            ensure_ascii=False, indent=2), encoding="utf-8")
    print(texto)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
