"""Rompe StoryMaker.tla a proposito y comprueba que TLC lo detecta (RF-TLA-07).

Un invariante que nunca falla puede ser un invariante que no mira nada. Cada mutacion
introduce en una copia del modelo un fallo que el codigo real podria tener, y TLC tiene que
hacer saltar la propiedad que se espera, con el modelo reducido de CONFIG (2 capitulos), en al
menos uno de los dos modos:

- A: fallos acotados, todas las propiedades;
- T: las puertas y los agentes fallan sin limite, solo terminacion y seguridad.

Uso, desde la raiz del repo (necesita Java y tla2tools.jar; ver README):

    src\\backend\\.venv\\Scripts\\python.exe formal\\tla\\mutaciones.py JAVA TLA2TOOLS_JAR

Sale con 1 si alguna mutacion sobrevive o si el modelo sin mutar falla.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

AQUI = Path(__file__).resolve().parent

#: Las que TLC informa como "Temporal properties were violated", sin nombre. Para saber cual
#: salto, una mutacion que espera una de estas se comprueba con esa propiedad sola.
TEMPORALES = {"EjecucionTermina", "AcabaPublicada"}

#: (nombre, texto original, texto mutado, lo que tiene que saltar)
MUTACIONES: list[tuple[str, str, str, str]] = [
    (
        "la recuperacion no revierte el capitulo a medias",
        "THEN estado' = \"detenida\" /\\ cap' = RevertirDesde(MaxCompletado + 1)",
        'THEN estado\' = "detenida" /\\ UNCHANGED cap',
        "SinCapituloAMedias",
    ),
    (
        "el oficio reintenta sin limite",
        "IF intento < MaxIntentos",
        "IF TRUE",
        "ReintentosAcotados",
    ),
    (
        "el cambio del lector reintenta sin limite",
        "               /\\ IF lectorIntento < MaxIntentos",
        "               /\\ IF TRUE",
        "ReintentosAcotados",
    ),
    (
        "la escaleta se repite sin limite",
        "             ELSE /\\ escIntento' = 2 /\\ pc' = \"esc_agente\"",
        "             ELSE /\\ escIntento' = 1 /\\ pc' = \"esc_agente\"",
        "EjecucionTermina",
    ),
    (
        "un capitulo se cierra sin pasar la puerta 3",
        '       \\/ /\\ FallaPuerta /\\ AbrirParada("continuidad", cur) /\\ UNCHANGED cap',
        '       \\/ /\\ FallaPuerta /\\ cap\' = [cap EXCEPT ![cur] = "completado"]'
        ' /\\ pc\' = "caps" /\\ UNCHANGED <<estado, corriendo, invalida, paradaVars>>',
        "PublicacionConPuertas",
    ),
    (
        "un cambio fracasado se aplica igual",
        '                  ELSE /\\ cambio\' = "fallido" /\\ pc\' = "p5"',
        '                  ELSE /\\ cambio\' = "fallido" /\\ pc\' = "lector_aplicar"',
        "PublicacionConPuertas",
    ),
    (
        "el cambio reescribe un capitulo fuera del alcance",
        "          LET r == [i \\in Caps |-> IF i \\in cambiados THEN rev[i] + 1 ELSE rev[i]]",
        "          LET r == [i \\in Caps |-> IF i \\in cambiados \\/ i = 1 THEN rev[i] + 1"
        " ELSE rev[i]]",
        "SoloElAlcance",
    ),
    (
        "el cambio no revalida las puertas 1 y 2",
        '                  /\\ IF CambioRevalidaPuertas \\/ tipoCambio = "cambiar_hecho"',
        '                  /\\ IF tipoCambio = "cambiar_hecho"',
        "CompletadaConNovela",
    ),
    (
        "la parada de presupuesto del tramo 3 no revierte en su transaccion",
        "          /\\ IF PresupuestoRevierteEnLaParada",
        "          /\\ IF FALSE",
        "SinCapituloAMedias",
    ),
    (
        "la puerta 5 detiene en vez de completar",
        "          ELSE estado' = e2 /\\ PublicarCon(rev, aprobado)",
        '          ELSE estado\' = "detenida" /\\ UNCHANGED versiones',
        "AcabaPublicada",
    ),
    (
        "publicar sobrescribe la ultima version",
        "                 ELSE Append(versiones, Instantanea(r, a))",
        "                 ELSE IF Len(versiones) > 0"
        " THEN [versiones EXCEPT ![Len(versiones)] = Instantanea(r, a)]"
        " ELSE Append(versiones, Instantanea(r, a))",
        "VersionesInmutables",
    ),
    (
        "relanzar no comprueba las puertas 1 y 2",
        "    /\\ p1 /\\ p2\n    /\\ d \\in 1..(MaxCompletado + 1)",
        "    /\\ d \\in 1..(MaxCompletado + 1)",
        "SinTransicionInvalida",
    ),
    (
        "avanzar no mira la vigencia de la puerta 1",
        "    /\\ IF ~planificado \\/ ~p1\n       THEN EntrarFase",
        "    /\\ IF ~planificado\n       THEN EntrarFase",
        "SinTransicionInvalida",
    ),
]

CONFIG = """SPECIFICATION Spec
CONSTANTS
    N = 2
    MaxIntentos = 3
    MaxFallos = {fallos}
    MaxRegeneraciones = 1
    ConCambioDelLector = TRUE
    CambioRevalidaPuertas = TRUE
    FallosDePuertaAcotados = {acotados}
    MaxReinicios = {reinicios}
    PresupuestoRevierteEnLaParada = TRUE
    RecuperarRevierteEnParada = FALSE
INVARIANTS
    PublicacionConPuertas CompletadaConNovela SinCapituloAMedias AMediasSoloElActual
    ReintentosAcotados CapituloConPuertas SinTransicionInvalida ParadaCoherente
    SoloElAlcance CambioFallidoNoAplica
PROPERTIES
    VersionesInmutables ReanudarNoPierde CierreUnico EjecucionTermina {extra}
"""
MODOS = {
    "A": CONFIG.format(fallos=3, acotados="TRUE", reinicios=3, extra="AcabaPublicada"),
    "T": CONFIG.format(fallos=1, acotados="FALSE", reinicios=1, extra=""),
}


def tlc(java: str, jar: str, carpeta: Path, modo: str, solo: str | None = None) -> str:
    """La primera linea de veredicto de TLC para ese modo, o solo con la propiedad `solo`."""
    config = MODOS[modo]
    if solo is not None:
        config = config.split("INVARIANTS")[0] + f"PROPERTIES\n    {solo}\n"
    (carpeta / f"{modo}.cfg").write_text(config, encoding="utf-8")
    salida = subprocess.run(
        [
            java,
            "-cp",
            jar,
            "tlc2.TLC",
            "-workers",
            "auto",
            "-deadlock",
            "-config",
            f"{modo}.cfg",
            "StoryMaker.tla",
        ],
        cwd=carpeta,
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    for linea in salida.splitlines():
        if "is violated" in linea or "were violated" in linea or "No error" in linea:
            return linea.strip()
        if linea.startswith("Error:"):
            return linea.strip()
    return "sin veredicto"


def salta(veredicto: str, esperado: str) -> bool:
    """Si el veredicto de TLC es la violacion de la propiedad esperada, y no de otra."""
    if esperado in TEMPORALES:
        return "Temporal properties were violated" in veredicto
    return f" {esperado} is violated" in veredicto


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    java, jar = sys.argv[1], sys.argv[2]
    original = (AQUI / "StoryMaker.tla").read_text(encoding="utf-8")
    fallos = 0
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / "base"
        base.mkdir()
        (base / "StoryMaker.tla").write_text(original, encoding="utf-8")
        for modo in MODOS:
            veredicto = tlc(java, jar, base, modo)
            limpio = "No error" in veredicto
            fallos += not limpio
            print(f"{'ok ' if limpio else 'MAL'} sin mutar, modo {modo}: {veredicto}")
        for i, (nombre, viejo, nuevo, esperado) in enumerate(MUTACIONES):
            if original.count(viejo) != 1:
                print(f"MAL {nombre}: el texto a mutar aparece {original.count(viejo)} veces")
                fallos += 1
                continue
            carpeta = Path(tmp) / f"m{i}"
            carpeta.mkdir()
            (carpeta / "StoryMaker.tla").write_text(
                original.replace(viejo, nuevo), encoding="utf-8"
            )
            solo = esperado if esperado in TEMPORALES else None
            veredictos = {modo: tlc(java, jar, carpeta, modo, solo) for modo in MODOS}
            muerta = any(salta(v, esperado) for v in veredictos.values())
            fallos += not muerta
            detalle = "; ".join(f"{m}: {v}" for m, v in veredictos.items())
            print(f"{'ok ' if muerta else 'MAL'} {nombre} (se espera {esperado}). {detalle}")
    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(main())
