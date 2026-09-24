"""Validador formal de la cronologia en Lean 4 (specs/spec-lean.md).

`generar` saca de la story bible un fichero `.lean` con solo datos: eventos con dia,
presencias, nacimientos, muertes y edades declaradas (RF-LEAN-02). Los invariantes y los lemas
viven en `formal/lean/Storymaker/Cronologia.lean`; el fichero generado los afirma con `decide`
y solo compila si la novela los cumple (RF-LEAN-03).

`verificar` lo compila con `lake env lean` y devuelve un `ResultadoPuerta`: cada testigo que
Lean imprime es un conflicto con el evento y el personaje que rompen el invariante
(RF-LEAN-05).
"""

from __future__ import annotations

import re
import shutil
import sqlite3
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import config
from compartido.puerta_base import Conflicto, ResultadoPuerta

#: Numero con el que la verificacion formal queda en `resultado_puerta` (RF-LEAN-06).
PUERTA = 6

#: Limite de la compilacion, en segundos (RF-LEAN-05).
TIEMPO_LIMITE = 300

INVARIANTES = (
    ("nadie_antes_de_nacer", "NadieAntesDeNacer"),
    ("nadie_tras_morir", "NadieTrasMorir"),
    ("edad_coherente", "EdadCoherente"),
    ("el_tiempo_no_retrocede", "ElTiempoNoRetrocede"),
)

# Una edad en cifras y, como mucho, «años» detras: «6 meses» o «34 y medio» no se leen.
#: Sin Lean no se publica (spec-lean, RF-LEAN-05): el informe dice como instalarlo.
INSTALAR = (
    "Lean no esta instalado: la cronologia no se ha comprobado y la version no se publica. "
    "Instala elan a nivel de usuario (https://github.com/leanprover/elan), compila una vez "
    "con `lake build` en formal/lean y relanza."
)

_EDAD = re.compile(r"^\s*(\d{1,4})\s*(?:a[ñn]os?)?\s*\.?\s*$", re.IGNORECASE)


def directorio_lean() -> Path:
    """El proyecto Lake del repositorio (RF-LEAN-01)."""
    return config.raiz_repo() / "formal" / "lean"


# --- Datos -----------------------------------------------------------------------------------


@dataclass(frozen=True)
class Evento:
    id: int
    dia: int
    orden: int | None
    capitulo: int
    previo: bool
    linea: bool
    analepsis: bool
    presente: int
    descripcion: str


@dataclass
class Cronologia:
    """Lo que el generador exporta, antes de escribirlo en Lean."""

    novela_id: int
    titulo: str
    eventos: list[Evento] = field(default_factory=list[Evento])
    #: (evento, personaje, dia)
    presencias: list[tuple[int, int, int]] = field(default_factory=list[tuple[int, int, int]])
    #: personaje -> dia de nacimiento
    nacimientos: dict[int, int] = field(default_factory=dict[int, int])
    #: personaje -> dia de la muerte
    muertes: dict[int, int] = field(default_factory=dict[int, int])
    #: (hecho, personaje, dia, edad)
    edades: list[tuple[int, int, int, int]] = field(
        default_factory=list[tuple[int, int, int, int]])
    nombres: dict[int, str] = field(default_factory=dict[int, str])
    eventos_sin_dia: int = 0
    muertes_sin_dia: int = 0
    edades_sin_dia: int = 0
    #: hecho de edad -> capitulo de su escena, para el feedback del editor
    capitulo_de_hecho: dict[int, int] = field(default_factory=dict[int, int])


# La vista `presencia` (spec2, RF2-PIPE-31) sin el estado `muerto`: registrar que alguien sigue
# muerto no es estar en la escena (spec-lean, RF-LEAN-02). Las demas fuentes son las de la
# vista; tests/test_formal_lean.py comprueba que sin estados `muerto` coinciden.
_SQL_PRESENCIA = """
SELECT escena_id, personaje_id FROM escena_personaje
UNION SELECT id, pov_id FROM escena WHERE pov_id IS NOT NULL
UNION SELECT escena_id, personaje_id FROM presencia_escena
UNION SELECT escena_id, personaje_id FROM uso_conocimiento
UNION SELECT escena_id, personaje_id FROM estado_personaje
      WHERE condicion IS NULL OR condicion <> 'muerto'
"""


def extraer(con: sqlite3.Connection, novela_id: int) -> Cronologia:
    """Lee de la story bible lo que Lean comprueba (RF-LEAN-02)."""
    fila = con.execute("SELECT titulo FROM novela WHERE id = ?", (novela_id,)).fetchone()
    crono = Cronologia(novela_id=novela_id, titulo=str(fila[0]) if fila else "")
    crono.nombres = {
        int(f[0]): str(f[1])
        for f in con.execute("SELECT id, nombre FROM personaje WHERE novela_id = ?", (novela_id,))
    }

    filas = con.execute(
        """
        SELECT c.evento_id, c.dia, c.orden_interno, c.dramatizado, c.escena_id,
               c.capitulo_numero, c.descripcion, e.analepsis, eo.ordinal
        FROM cronologia c
        LEFT JOIN escena e          ON e.id = c.escena_id
        LEFT JOIN escena_ordinal eo ON eo.escena_id = c.escena_id
        WHERE c.novela_id = ?
        ORDER BY c.evento_id
        """,
        (novela_id,),
    ).fetchall()
    con_dia = [f for f in filas if f[1] is not None]
    crono.eventos_sin_dia = len(filas) - len(con_dia)

    def dramatizado(f: sqlite3.Row) -> bool:
        return f[4] is not None and bool(f[3])

    def es_linea(f: sqlite3.Row) -> bool:
        return dramatizado(f) and not bool(f[7])

    def es_previo(f: sqlite3.Row) -> bool:
        # Como los inserta el constructor de mundo: sin escena, sin dramatizar y con orden
        # negativo. Un evento que el extractor refiere sin escena no es un antecedente.
        return f[4] is None and not bool(f[3]) and f[2] is not None and int(f[2]) < 0

    # El presente de cada escena: el mayor dia de la linea principal en las anteriores.
    linea = sorted((int(f[8]), int(f[1])) for f in con_dia if es_linea(f))

    def presente(ordinal: int | None) -> int:
        if ordinal is None:
            return 0
        return max((d for o, d in linea if o < ordinal), default=0)

    for f in con_dia:
        crono.eventos.append(Evento(
            id=int(f[0]), dia=int(f[1]),
            orden=int(f[2]) if f[2] is not None else None,
            capitulo=int(f[5]) if f[5] is not None else 0,
            previo=es_previo(f), linea=es_linea(f),
            analepsis=dramatizado(f) and bool(f[7]),
            presente=presente(int(f[8]) if f[8] is not None else None),
            descripcion=str(f[6]),
        ))
    crono.eventos.sort(key=lambda e: (e.dia, e.orden if e.orden is not None else 0, e.id))

    # El dia de una escena, y quien esta en cada suceso, salen de lo que la escena dramatiza:
    # un evento referido (un recuerdo contado, algo que paso lejos) no pone a nadie en el.
    dia_de_escena: dict[int, int] = {}
    for f in con_dia:
        if dramatizado(f):
            dia_de_escena[int(f[4])] = max(dia_de_escena.get(int(f[4]), int(f[1])), int(f[1]))

    presentes: dict[int, set[int]] = {}
    for escena_id, personaje_id in con.execute(_SQL_PRESENCIA):
        presentes.setdefault(int(escena_id), set()).add(int(personaje_id))
    for f in con_dia:
        if not dramatizado(f):
            continue
        for p in sorted(presentes.get(int(f[4]), set())):
            if p in crono.nombres:
                crono.presencias.append((int(f[0]), p, int(f[1])))
    crono.presencias.sort()

    crono.nacimientos = {
        int(f[0]): int(f[1]) for f in con.execute(
            "SELECT personaje_id, nacimiento_dia FROM personaje_nacimiento WHERE novela_id = ?",
            (novela_id,))
    }

    _extraer_muertes(con, novela_id, crono, dia_de_escena)
    _extraer_edades(con, novela_id, crono, dia_de_escena)
    return crono


def _extraer_muertes(
    con: sqlite3.Connection, novela_id: int, crono: Cronologia, dia_de_escena: dict[int, int],
) -> None:
    """La muerte cuenta si es la ultima condicion registrada; su escena es la primera de esa
    racha de `muerto` (spec-lean, RF-LEAN-02)."""
    condiciones: dict[int, list[tuple[str, int]]] = {}
    for personaje_id, escena_id, condicion in con.execute(
        """
        SELECT ep.personaje_id, ep.escena_id, ep.condicion
        FROM estado_personaje ep
        JOIN escena_ordinal eo ON eo.escena_id = ep.escena_id
        WHERE ep.novela_id = ? AND ep.condicion IS NOT NULL
        ORDER BY eo.ordinal, ep.id
        """,
        (novela_id,),
    ):
        condiciones.setdefault(int(personaje_id), []).append((str(condicion), int(escena_id)))
    for personaje_id, lista in condiciones.items():
        if lista[-1][0] != "muerto":
            continue
        k = len(lista) - 1
        while k > 0 and lista[k - 1][0] == "muerto":
            k -= 1
        escena = lista[k][1]
        if escena in dia_de_escena:
            crono.muertes[personaje_id] = dia_de_escena[escena]
        else:
            crono.muertes_sin_dia += 1


def _extraer_edades(
    con: sqlite3.Connection, novela_id: int, crono: Cronologia, dia_de_escena: dict[int, int],
) -> None:
    """Hechos `edad` de un personaje cuyo valor empieza por cifras (RF-LEAN-02)."""
    for hecho_id, personaje_id, escena_id, valor, capitulo in con.execute(
        """
        SELECT h.id, h.sujeto_id, h.escena_id, h.valor, eo.capitulo_numero
        FROM hecho_vigente h
        JOIN escena_ordinal eo ON eo.escena_id = h.escena_id
        WHERE h.novela_id = ? AND h.sujeto_tipo = 'personaje' AND h.sujeto_id IS NOT NULL
          AND h.atributo_clave = 'edad'
        ORDER BY h.id
        """,
        (novela_id,),
    ):
        m = _EDAD.match(str(valor))
        if not m:
            continue
        if int(escena_id) not in dia_de_escena:
            crono.edades_sin_dia += 1
            continue
        crono.edades.append(
            (int(hecho_id), int(personaje_id), dia_de_escena[int(escena_id)], int(m.group(1))))
        crono.capitulo_de_hecho[int(hecho_id)] = int(capitulo)


# --- Fichero de Lean ---------------------------------------------------------------------------


def _comentario(texto: str) -> str:
    """Una linea de comentario de Lean que no puede cerrarse ni romper el fichero."""
    return " ".join(texto.replace("-/", "- /").split())[:90]


def _bool(v: bool) -> str:
    return "true" if v else "false"


def _evento(e: Evento) -> str:
    campos = [f"id := {e.id}", f"dia := {e.dia}"]
    if e.orden is not None:
        campos += [f"orden := {e.orden}", "conOrden := true"]
    if e.capitulo:
        campos.append(f"capitulo := {e.capitulo}")
    for nombre, valor in (("previo", e.previo), ("linea", e.linea), ("analepsis", e.analepsis)):
        if valor:
            campos.append(f"{nombre} := {_bool(valor)}")
    if e.presente:
        campos.append(f"presente := {e.presente}")
    return "{ " + ", ".join(campos) + " }"


def escribir(crono: Cronologia, *, espacio: str = "Novela") -> str:
    """El texto del fichero `.lean`, determinista para una misma cronologia (RF-LEAN-02)."""
    n = crono.nombres
    lineas = [
        "/-",
        f"Novela {crono.novela_id}: generado por src/backend/orquestador/lean.py.",
        "No editar a mano: se regenera desde la story bible (specs/spec-lean.md).",
        "",
        f"Eventos con dia: {len(crono.eventos)}. Sin dia, no comprobados: "
        f"{crono.eventos_sin_dia}.",
        f"Muertes en una escena sin dia, no comprobadas: {crono.muertes_sin_dia}.",
        f"Edades declaradas en una escena sin dia, no comprobadas: {crono.edades_sin_dia}.",
        "-/",
        "import Storymaker.Cronologia",
        "",
        "open Storymaker",
        "",
        f"namespace {espacio}",
        "",
        "def datos : Datos where",
    ]

    def lista(nombre: str, filas: list[tuple[str, str]]) -> None:
        if not filas:
            lineas.append(f"  {nombre} := []")
            return
        lineas.append(f"  {nombre} := [")
        for k, (valor, nota) in enumerate(filas):
            coma = "," if k < len(filas) - 1 else ""
            lineas.append(f"    {valor}{coma}  -- {_comentario(nota)}")
        lineas.append("  ]")

    lista("eventos", [(_evento(e), e.descripcion) for e in crono.eventos])
    lista("presencias", [
        (f"{{ evento := {ev}, personaje := {p}, dia := {d} }}", n.get(p, "?"))
        for ev, p, d in crono.presencias
    ])
    lista("nacimientos", [
        (f"{{ personaje := {p}, dia := {d} }}", n.get(p, "?"))
        for p, d in sorted(crono.nacimientos.items())
    ])
    lista("muertes", [
        (f"{{ personaje := {p}, dia := {d} }}", n.get(p, "?"))
        for p, d in sorted(crono.muertes.items())
    ])
    lista("edades", [
        (f"{{ hecho := {h}, personaje := {p}, dia := {d}, edad := {e} }}", n.get(p, "?"))
        for h, p, d, e in crono.edades
    ])
    lineas += ["", "#eval informe datos", ""]
    for nombre, prop in INVARIANTES:
        lineas.append(f"theorem {nombre} : {prop} datos := by decide +kernel")
    lineas += ["", f"end {espacio}", ""]
    return "\n".join(lineas)


def generar(con: sqlite3.Connection, novela_id: int, *, espacio: str = "Novela") -> str:
    """El fichero `.lean` de una novela (RF-LEAN-02)."""
    return escribir(extraer(con, novela_id), espacio=espacio)


# --- Ejecucion -------------------------------------------------------------------------------


def lake_disponible() -> str | None:
    """La ruta de `lake`, en el PATH o en la instalacion de usuario de elan."""
    encontrado = shutil.which("lake")
    if encontrado:
        return encontrado
    for nombre in ("lake.exe", "lake"):
        candidato = Path.home() / ".elan" / "bin" / nombre
        if candidato.exists():
            return str(candidato)
    return None


_TESTIGO = re.compile(r"^TESTIGO (\w+) (.*)$")


def leer_testigos(salida: str) -> list[tuple[str, dict[str, int]]]:
    """Los testigos que imprime `informe` en `Storymaker/Cronologia.lean`."""
    testigos: list[tuple[str, dict[str, int]]] = []
    for linea in salida.splitlines():
        m = _TESTIGO.match(linea.strip())
        if not m:
            continue
        valores: dict[str, int] = {}
        for par in m.group(2).split():
            clave, _, valor = par.partition("=")
            try:
                valores[clave] = int(valor)
            except ValueError:
                continue
        testigos.append((m.group(1), valores))
    return testigos


def _conflicto(crono: Cronologia, comprobacion: str, v: dict[str, int]) -> Conflicto:
    eventos = {e.id: e for e in crono.eventos}
    nombre = crono.nombres.get(v.get("personaje", 0), "?")
    ev = eventos.get(v.get("evento", 0))
    otro = eventos.get(v.get("otro", 0))
    capitulo = (ev.capitulo if ev and ev.capitulo
                else crono.capitulo_de_hecho.get(v.get("hecho", 0)))
    dia, limite = v.get("dia", 0), v.get("limite", 0)
    que = f"«{ev.descripcion[:80]}» (evento {ev.id})" if ev else ""
    if comprobacion == "lean_nadie_antes_de_nacer":
        texto = f"{nombre} esta en {que} el dia {dia}, pero nace el dia {limite}."
    elif comprobacion == "lean_nadie_tras_morir":
        texto = f"{nombre} esta en {que} el dia {dia}, pero murio el dia {limite}."
    elif comprobacion == "lean_edad_coherente":
        texto = (f"La prosa da a {nombre} {dia} años (hecho {v.get('hecho', 0)}), pero por su "
                 f"nacimiento ese dia tiene {limite}.")
    elif otro is not None:
        texto = (f"{que} va antes o a la vez en el orden interno que «{otro.descripcion[:80]}» "
                 f"(evento {otro.id}), pero cae el dia {dia} y el otro el dia {limite}.")
    elif ev is not None and ev.previo:
        texto = f"El antecedente {que} cae el dia {dia}, despues del comienzo de la historia."
    elif ev is not None and ev.analepsis:
        texto = (f"La analepsis {que} cae el dia {dia}, despues del presente de la historia "
                 f"en ese punto (dia {limite}).")
    else:
        texto = f"{que} cae el dia {dia}, antes del comienzo de la historia."
    return Conflicto(comprobacion=comprobacion, descripcion=texto, capitulo=capitulo,
                     datos=dict(v))


def verificar(
    con: sqlite3.Connection,
    novela_id: int,
    *,
    directorio: Path | None = None,
    lake: str | None = None,
    tiempo_limite: int = TIEMPO_LIMITE,
) -> ResultadoPuerta:
    """Genera el fichero de la novela y lo compila con Lean (RF-LEAN-05)."""
    directorio = directorio or directorio_lean()
    lake = lake or lake_disponible()
    if lake is None:
        return ResultadoPuerta(puerta=PUERTA, conflictos=[Conflicto(
            comprobacion="lean_no_disponible", descripcion=INSTALAR)])

    crono = extraer(con, novela_id)
    carpeta = directorio / "Generado"
    carpeta.mkdir(exist_ok=True)
    fichero = carpeta / f"Novela{novela_id}_{uuid.uuid4().hex[:8]}.lean"
    fichero.write_text(escribir(crono), encoding="utf-8", newline="\n")
    # Un solo limite para las dos llamadas: compilar la biblioteca (casi nada si ya lo esta)
    # y comprobar el fichero de la novela.
    fin = time.monotonic() + tiempo_limite
    try:
        subprocess.run(
            [lake, "build", "Storymaker.Cronologia"], cwd=directorio, capture_output=True,
            text=True, encoding="utf-8", errors="replace", timeout=tiempo_limite, check=True,
        )
        proceso = subprocess.run(
            [lake, "env", "lean", str(fichero.relative_to(directorio))], cwd=directorio,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=max(1.0, fin - time.monotonic()),
        )
    except subprocess.TimeoutExpired:
        return ResultadoPuerta(puerta=PUERTA, conflictos=[Conflicto(
            comprobacion="lean_no_disponible",
            descripcion=f"Lean no termino en {tiempo_limite} s: la cronologia no se ha "
                        "comprobado y la version no se publica. Relanza para reintentarlo.")])
    except subprocess.CalledProcessError as e:
        return ResultadoPuerta(puerta=PUERTA, conflictos=[Conflicto(
            comprobacion="lean_error",
            descripcion="La biblioteca Storymaker no compila: "
                        + ((e.stdout or "") + (e.stderr or ""))[-800:])])
    finally:
        fichero.unlink(missing_ok=True)

    salida = (proceso.stdout or "") + (proceso.stderr or "")
    conflictos = [_conflicto(crono, c, v) for c, v in leer_testigos(salida)]
    if proceso.returncode != 0 and not conflictos:
        conflictos.append(Conflicto(
            comprobacion="lean_error",
            descripcion="El fichero generado no compila en Lean: " + salida[-800:]))
    return ResultadoPuerta(puerta=PUERTA, conflictos=conflictos)
