"""Puerta 4: la parte mecanica y la combinacion con el juicio (RF-PIPE-13, RF2-PIPE-13).

Busquedas dirigidas sobre listas cerradas: lo que se puede comprobar contando, antes de
gastar una llamada de juicio. Corre primero porque es gratis.

Fallan los tics prohibidos y, desde spec3 RF3-VAL-01 y RF3-VAL-03, un nombre del canon mal
escrito y un allegado del encargo que la escaleta planifico en el capitulo y la prosa no nombra:
los tres son errores que el lector ve, y el capitulo vuelve al redactor. El resto son avisos que
van al informe y al juez: que haya tres palabras filtro no significa que la voz falle, y
convertirlo en fallo automatico produciria prosa timida en vez de prosa buena. La longitud real
fuera del rango tambien es un aviso (RF3-VAL-02).
"""

from __future__ import annotations

import re
import sqlite3
import unicodedata

from compartido.grafo import lectura
from compartido.puerta_base import Conflicto, ResultadoPuerta
from compartido.texto import contiene_termino
from config import PALABRAS_FILTRO

from .esquemas import SalidaOficio

# «dijo secamente», «respondio friamente»: el adverbio que sostiene un verbo debil.
_ADVERBIO_ATRIBUCION = re.compile(
    r"\b(dijo|respondio|respondió|pregunto|preguntó|exclamo|exclamó|murmuro|murmuró|"
    r"susurro|susurró|anadio|añadió)\s+\w+mente\b",
    re.IGNORECASE,
)

# Verbos de habla expresivos: si hacen falta, la replica no es lo bastante dura por si sola.
_VERBOS_EXPRESIVOS = (
    "espeto", "espetó", "bramo", "bramó", "vocifero", "vociferó", "siseo", "siseó",
    "gruno", "gruñó", "chillo", "chilló", "ladro", "ladró", "escupio", "escupió",
)


def _sin_tildes(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    ).lower()


def _contar(texto_normalizado: str, expresion: str) -> int:
    return len(re.findall(rf"\b{re.escape(_sin_tildes(expresion))}\b", texto_normalizado))


# --- spec3 RF3-VAL-01: los nombres del canon, escritos exactamente ------------------------------

_PALABRA_CON_POSICION = re.compile(r"[^\W\d_]+")
#: Lo que abre una frase: ahi va mayuscula cualquier palabra, y «Mas» (apellido) y «Más» (al
#: empezar) solo se distinguen por la tilde.
_INICIO_DE_FRASE = re.compile(r"(?:^|[.!?¿¡:;«\"—\n])[\s«\"—]*$")
_MINIMO_NOMBRE = 3
_MINIMO_NOMBRE_AL_INICIO = 6


def _plano(palabra: str) -> str:
    """Sin ninguna marca, tampoco la de la ene, y sin mayusculas: la clave del parecido."""
    return "".join(
        c for c in unicodedata.normalize("NFD", palabra) if unicodedata.category(c) != "Mn"
    ).casefold()


def _partes_de_los_nombres(con: sqlite3.Connection, novela_id: int) -> dict[str, set[str]]:
    """Cada palabra con mayuscula de un nombre del canon, agrupada por su clave plana."""
    salida: dict[str, set[str]] = {}
    for tabla in ("personaje", "lugar", "objeto", "faccion"):
        for (nombre,) in con.execute(f"SELECT nombre FROM {tabla} WHERE novela_id = ?",
                                     (novela_id,)):
            for parte in _PALABRA_CON_POSICION.findall(str(nombre)):
                if len(parte) >= _MINIMO_NOMBRE and parte[0].isupper():
                    salida.setdefault(_plano(parte), set()).add(parte)
    return salida


def _nombres_mal_escritos(
    con: sqlite3.Connection, novela_id: int, capitulo: int, texto: str
) -> Conflicto | None:
    """Una palabra con mayuscula que es un nombre del canon salvo por las tildes o la ene.

    «Sebastian» por «Sebastián», «Nunez» por «Núñez». Solo se miran las palabras con mayuscula,
    y al empezar frase solo las de seis letras o mas: ahi «Más» y el apellido «Mas» no se
    distinguen. Las mayusculas no cuentan: «NÚÑEZ» gritado esta bien escrito.
    """
    partes = _partes_de_los_nombres(con, novela_id)
    if not partes:
        return None
    errores: dict[tuple[str, str], int] = {}
    for m in _PALABRA_CON_POSICION.finditer(texto):
        palabra = m.group(0)
        if not palabra[0].isupper() or len(palabra) < _MINIMO_NOMBRE:
            continue
        buenas = partes.get(_plano(palabra))
        if not buenas or palabra.casefold() in {b.casefold() for b in buenas}:
            continue
        if (_INICIO_DE_FRASE.search(texto, 0, m.start())
                and len(palabra) < _MINIMO_NOMBRE_AL_INICIO):
            continue
        clave = (palabra, sorted(buenas)[0])
        errores[clave] = errores.get(clave, 0) + 1
    if not errores:
        return None
    lista = "; ".join(f"«{mal}» ({n} vez/veces) se escribe «{bien}»"
                      for (mal, bien), n in sorted(errores.items()))
    return Conflicto(
        comprobacion="nombre_mal_escrito", capitulo=capitulo,
        descripcion=f"Nombres del canon mal escritos: {lista}.",
        datos={"errores": [{"escrito": mal, "canon": bien, "veces": n}
                           for (mal, bien), n in sorted(errores.items())]},
    )


# --- spec3 RF3-VAL-02: la longitud real ---------------------------------------------------------


def _longitud_real(
    con: sqlite3.Connection, novela_id: int, capitulo: int, texto: str
) -> Conflicto | None:
    fila = con.execute(
        "SELECT valor FROM restriccion WHERE novela_id = ? AND tipo = 'longitud_capitulo_palabras'",
        (novela_id,),
    ).fetchone()
    rango = str(fila[0]) if fila else ""
    if "-" not in rango:
        return None
    minimo, maximo = (int(x) for x in rango.split("-", 1))
    palabras = len(texto.split())
    if minimo <= palabras <= maximo:
        return None
    return Conflicto(
        comprobacion="longitud_real", aviso=True, capitulo=capitulo,
        descripcion=f"El capitulo tiene {palabras} palabras, fuera del rango {minimo}-{maximo}.",
        datos={"palabras": palabras, "minimo": minimo, "maximo": maximo},
    )


# --- spec3 RF3-VAL-03: los allegados planificados, en la prosa ----------------------------------


def _allegados_ausentes(
    con: sqlite3.Connection, novela_id: int, capitulo: int, texto: str
) -> list[Conflicto]:
    """Un allegado del encargo que la escaleta puso en este capitulo y la prosa no nombra.

    Basta con una palabra de su nombre de tres letras o mas: el redactor lo llama por el nombre
    de pila. Los rasgos y los recuerdos no se pueden buscar por palabras; son del juez.
    """
    brief = lectura.brief(con, novela_id)
    if brief is None:
        return []
    nombres = {a.codigo: a.nombre for a in brief.con_codigos().allegados}
    planificados = [
        (str(f["codigo"]), int(f["orden"])) for f in con.execute(
            """
            SELECT ep.codigo, MIN(e.orden) AS orden FROM escena_elemento ee
            JOIN elemento_personal ep ON ep.id = ee.elemento_id
            JOIN escena e   ON e.id = ee.escena_id
            JOIN capitulo c ON c.id = e.capitulo_id
            WHERE ep.novela_id = ? AND c.numero = ? AND ep.tipo = 'allegado'
            GROUP BY ep.codigo ORDER BY ep.codigo
            """,
            (novela_id, capitulo),
        )
    ]
    salida: list[Conflicto] = []
    for codigo, orden in planificados:
        nombre = nombres.get(codigo)
        if nombre is None:
            continue
        partes = [p for p in _PALABRA_CON_POSICION.findall(nombre) if len(p) >= _MINIMO_NOMBRE]
        if any(contiene_termino(texto, p) for p in partes or [nombre]):
            continue
        salida.append(Conflicto(
            comprobacion="allegado_ausente", capitulo=capitulo,
            descripcion=(
                f"La escaleta pone a «{nombre}» ({codigo}) en la escena {orden} y la prosa del "
                "capitulo no lo nombra. Es un elemento del regalo: integralo en esa escena."
            ),
            datos={"codigo": codigo, "nombre": nombre, "escena": orden},
        ))
    return salida


def evaluar(
    con: sqlite3.Connection, novela_id: int, capitulo: int, texto: str
) -> ResultadoPuerta:
    conflictos: list[Conflicto] = []
    plano = _sin_tildes(texto)
    palabras = max(1, len(texto.split()))

    for tic in lectura.tics_prohibidos(con, novela_id):
        veces = _contar(plano, tic)
        if veces:
            conflictos.append(Conflicto(
                comprobacion="tic_prohibido", capitulo=capitulo,
                descripcion=(
                    f"«{tic}» aparece {veces} vez(ces). Esta en los tics prohibidos del estilo "
                    "narrativo de la obra."
                ),
                datos={"tic": tic, "veces": veces},
            ))

    filtro = {p: _contar(plano, p) for p in PALABRAS_FILTRO}
    total_filtro = sum(filtro.values())
    if total_filtro:
        por_mil = round(total_filtro * 1000 / palabras, 1)
        conflictos.append(Conflicto(
            comprobacion="palabras_filtro", aviso=True, capitulo=capitulo,
            descripcion=(
                f"{total_filtro} palabras filtro ({por_mil} por cada mil). En punto de vista "
                "limitado son tautologicas y alejan al lector un centimetro cada vez."
            ),
            datos={"total": total_filtro, "por_mil": por_mil,
                   "detalle": {k: v for k, v in filtro.items() if v}},
        ))

    adverbios = _ADVERBIO_ATRIBUCION.findall(texto)
    if adverbios:
        conflictos.append(Conflicto(
            comprobacion="adverbio_de_atribucion", aviso=True, capitulo=capitulo,
            descripcion=(
                f"{len(adverbios)} atribucion(es) sostenidas por un adverbio en -mente. Si hace "
                "falta el adverbio, la replica no dice lo que deberia."
            ),
            datos={"casos": len(adverbios)},
        ))

    expresivos = {v: _contar(plano, v) for v in _VERBOS_EXPRESIVOS}
    total_expresivos = sum(expresivos.values())
    if total_expresivos:
        conflictos.append(Conflicto(
            comprobacion="verbo_de_habla_expresivo", aviso=True, capitulo=capitulo,
            descripcion=(
                f"{total_expresivos} verbo(s) de habla expresivos. «Dijo» es invisible y casi "
                "siempre el correcto."
            ),
            datos={k: v for k, v in expresivos.items() if v},
        ))

    for extra in (
        _nombres_mal_escritos(con, novela_id, capitulo, texto),
        _longitud_real(con, novela_id, capitulo, texto),
    ):
        if extra is not None:
            conflictos.append(extra)
    conflictos.extend(_allegados_ausentes(con, novela_id, capitulo, texto))

    return ResultadoPuerta(puerta=4, conflictos=conflictos)


def combinar(mecanica: ResultadoPuerta, juicio: SalidaOficio | None) -> ResultadoPuerta:
    """La puerta 4 entera en un solo resultado: mecanica y juicio (RF2-PIPE-13).

    Cada criterio que el juez da por `falla` es un conflicto, con su evidencia y su
    sugerencia. Si la mecanica falla, el juez no se invoca y el resultado lo dice: registrar
    solo la mecanica hacia que la traza dijera `pasa` con el juez en contra.
    """
    conflictos = list(mecanica.conflictos)
    if juicio is None:
        if mecanica.pasa:
            conflictos.append(Conflicto(
                comprobacion="juicio_ausente",
                descripcion="La mecanica paso pero no hay veredicto del juez de oficio.",
            ))
        else:
            conflictos.append(Conflicto(
                comprobacion="juicio_no_invocado", aviso=True,
                descripcion="La mecanica fallo: el juez de oficio no se invoco.",
            ))
    else:
        conflictos.extend(
            Conflicto(
                comprobacion=f"juicio:{v.criterio}",
                descripcion=f"Principio {v.principio}. {v.sugerencia}".strip(),
                datos={"criterio": v.criterio, "principio": v.principio,
                       "evidencia": v.evidencia, "sugerencia": v.sugerencia},
            )
            for v in juicio.incumplidos
        )
    return ResultadoPuerta(puerta=4, conflictos=conflictos)
