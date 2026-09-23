"""La entrevista: el CLI que recoge el brief de una novela personalizada (specs/spec3.md, 3.2).

    python entrevista.py                          # entrevista conversacional
    python entrevista.py --texto-libre carta.txt  # empezando por un texto que pega el comprador
    python entrevista.py --brief brief.json       # valida un brief ya escrito, sin agente

Que falta y que se contradice lo calcula el codigo (`compartido.brief.analizar`); el agente
entrevistador solo entiende las respuestas y formula las preguntas. Cuando el brief esta
completo y el comprador lo confirma, se encola `crear_novela` con el brief y la transcripcion.

La entrevista no escribe en la base salvo esa intencion, igual que la API (RF3-ENT-06): llama
al puerto sin conexion, y su traza viaja en la transcripcion.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import config
from compartido import db
from compartido.brief import Brief, analizar
from compartido.db import transaccion
from compartido.puerto import PuertoAgente
from compartido.puerto import construir as construir_puerto
from compartido.tipos import como_dict
from orquestador import cola
from tareas.entrevistador import servicio
from tareas.entrevistador.esquemas import SalidaEntrevistador

MAX_TURNOS = 25
AFIRMATIVAS = frozenset({"s", "si", "sí", "vale", "ok", "confirmo", "adelante"})

Leer = Callable[[str], str]
Escribir = Callable[[str], None]


@dataclass
class ResultadoEntrevista:
    brief: Brief
    completo: bool
    confirmado: bool
    transcripcion: dict[str, Any] = field(default_factory=dict[str, Any])


def _invocar(
    puerto: PuertoAgente, entrada: str, llamadas: list[dict[str, Any]]
) -> SalidaEntrevistador:
    resultado = puerto.invocar(
        servicio.AGENTE, entrada, SalidaEntrevistador.model_json_schema(),
    )
    llamadas.append({
        "tokens_entrada": resultado.tokens_entrada, "tokens_salida": resultado.tokens_salida,
        "coste_usd": resultado.coste_usd, "duracion_ms": resultado.duracion_ms,
    })
    return SalidaEntrevistador.model_validate(resultado.salida)


def _resumen(brief: Brief) -> str:
    d = brief.destinatario
    lineas = [
        f"Para: {d.nombre} ({d.edad} años, {d.pronombres})",
        f"Ocasion: {brief.ocasion}. Regala: {brief.quien_regala}",
        f"Intensidad: {brief.intensidad}. Tono: {brief.tono}. "
        f"Subgenero: {brief.subgenero or 'lo elige el arquitecto'}. Capitulos: {brief.capitulos}",
        "Rasgos: " + "; ".join(e.texto for e in d.rasgos),
        "Recuerdos: " + "; ".join(e.texto for e in brief.recuerdos),
    ]
    if brief.allegados:
        lineas.append(
            "Allegados: " + "; ".join(f"{a.nombre} ({a.relacion})" for a in brief.allegados)
        )
    if brief.vetados:
        lineas.append("Vetados: " + ", ".join(brief.vetados))
    return "\n".join(lineas)


def entrevistar(
    puerto: PuertoAgente,
    leer: Leer,
    escribir: Escribir,
    *,
    brief: Brief | None = None,
    texto_libre: str = "",
    max_turnos: int = MAX_TURNOS,
) -> ResultadoEntrevista:
    """El bucle de RF3-ENT-02. `leer` y `escribir` son la consola, o un guion en los tests."""
    brief = brief or Brief()
    turnos: list[dict[str, Any]] = []
    llamadas: list[dict[str, Any]] = []
    transcripcion: dict[str, Any] = {"turnos": turnos, "llamadas": llamadas, "alertas": []}

    if texto_libre.strip():
        alertas = servicio.alertas_de_inyeccion(texto_libre)
        salida = _invocar(puerto, servicio.paquete_texto_libre(brief, texto_libre), llamadas)
        aplicado = servicio.aplicar(
            brief, salida, texto_libre, permitidos=servicio.CAMPOS_TEXTO_LIBRE,
            origen="texto_libre",
        )
        brief = aplicado.brief.model_copy(update={"texto_libre": texto_libre})
        transcripcion["texto_libre"] = {
            "aplicadas": aplicado.aplicadas, "descartadas": aplicado.descartadas,
        }
        transcripcion["alertas"] = alertas
        if alertas:
            escribir(
                "Aviso: el texto pegado contiene frases con forma de instruccion "
                f"({', '.join(alertas)}). Se ha tratado como una anecdota, sin obedecerlas."
            )

    respuesta, campo_preguntado = "", ""
    for _ in range(max_turnos):
        analisis = analizar(brief)
        if analisis.completo:
            escribir("\nAsi queda el encargo:\n" + _resumen(brief))
            confirmacion = leer("¿Lo confirmas? (s/n) ").strip().lower()
            turnos.append({"pregunta": "confirmacion", "respuesta": confirmacion})
            if confirmacion in AFIRMATIVAS:
                return ResultadoEntrevista(brief, True, True, transcripcion)
            respuesta = leer("¿Que quieres cambiar? ")
            campo_preguntado = "correccion"
            turnos.append({"pregunta": "¿Que quieres cambiar?", "campo": campo_preguntado,
                           "respuesta": respuesta})
        paquete = servicio.paquete_turno(brief, analisis, turnos, respuesta, campo_preguntado)
        salida = _invocar(puerto, paquete, llamadas)
        aplicado = servicio.aplicar(brief, salida, respuesta)
        brief = aplicado.brief
        if turnos and respuesta:
            turnos[-1].update(aplicadas=aplicado.aplicadas, descartadas=aplicado.descartadas)

        pendientes = analizar(brief).pendientes()
        if not pendientes:
            continue
        pregunta = salida.pregunta.strip() or f"Necesito un dato mas: {pendientes[0]}."
        campo_preguntado = servicio.campo_de(pendientes[0])
        respuesta = leer(pregunta + "\n> ")
        turnos.append({"pregunta": pregunta, "campo": campo_preguntado, "respuesta": respuesta})

    if analizar(brief).completo:
        # El ultimo turno completo el encargo: falta solo que el comprador lo confirme.
        escribir("\nAsi queda el encargo:\n" + _resumen(brief))
        confirmacion = leer("¿Lo confirmas? (s/n) ").strip().lower()
        turnos.append({"pregunta": "confirmacion", "respuesta": confirmacion})
        if confirmacion in AFIRMATIVAS:
            return ResultadoEntrevista(brief, True, True, transcripcion)
        escribir(f"No se ha confirmado y ya van {max_turnos} turnos: no se crea ninguna novela.")
        return ResultadoEntrevista(brief, True, False, transcripcion)

    escribir(
        f"La entrevista ha llegado a {max_turnos} turnos sin completar el encargo. No se crea "
        "ninguna novela; falta: " + ", ".join(analizar(brief).pendientes())
    )
    return ResultadoEntrevista(brief, False, False, transcripcion)


def encolar(ruta: Path, brief: Brief, transcripcion: dict[str, Any]) -> int:
    """La unica escritura de la entrevista: la intencion, como haria la API."""
    con = db.conectar(ruta)
    try:
        db.crear_esquema(con)
        with transaccion(con):
            return cola.encolar(
                con, "crear_novela", None,
                brief=brief.model_dump(mode="json"), entrevista=transcripcion,
            )
    finally:
        con.close()


def _leer_brief(fichero: Path) -> Brief:
    datos = como_dict(json.loads(fichero.read_text(encoding="utf-8")))
    if "payload" in datos:
        datos = como_dict(datos["payload"])
    if "brief" in datos:
        datos = como_dict(datos["brief"])
    return Brief.model_validate(datos)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--brief", type=Path, default=None, help="validar un brief ya escrito")
    parser.add_argument(
        "--texto-libre", type=Path, default=None, help="texto que pega el comprador"
    )
    parser.add_argument("--no-encolar", action="store_true", help="solo mostrar el brief")
    parser.add_argument("--max-turnos", type=int, default=MAX_TURNOS)
    args = parser.parse_args()

    try:
        cfg = config.cargar()
    except config.ConfiguracionInvalida as exc:
        print(f"{exc}\n\nEn cmd:  set NOVELAS_DB_PATH=novela.db", file=sys.stderr)
        return 2

    if args.brief is not None:
        # RF3-ENT-04: sin agente. Solo validar y, si es valido, encolar.
        brief = _leer_brief(args.brief).con_codigos()
        analisis = analizar(brief)
        if not analisis.completo:
            print(json.dumps(analisis.como_dict(), ensure_ascii=False, indent=2))
            return 1
        transcripcion: dict[str, Any] = {"origen": "brief", "fichero": str(args.brief)}
    else:
        texto = args.texto_libre.read_text(encoding="utf-8") if args.texto_libre else ""
        resultado = entrevistar(
            construir_puerto(cfg, None), input, print, texto_libre=texto,
            max_turnos=args.max_turnos,
        )
        if not resultado.confirmado:
            return 1
        brief, transcripcion = resultado.brief, resultado.transcripcion

    if args.no_encolar:
        print(brief.model_dump_json(indent=2))
        return 0
    intencion_id = encolar(cfg.db_path, brief, transcripcion)
    print(f"Intencion {intencion_id}: crear_novela encolada. El worker la recoge.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
