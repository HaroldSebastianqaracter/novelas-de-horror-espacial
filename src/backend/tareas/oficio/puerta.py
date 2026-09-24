"""Puerta 4: la parte mecanica y la combinacion con el juicio (RF-PIPE-13, RF2-PIPE-13).

Busquedas dirigidas sobre listas cerradas: lo que se puede comprobar contando, antes de
gastar una llamada de juicio. Corre primero porque es gratis.

Fallan los tics prohibidos, un termino vetado (spec3, RF3-GRD-03) y, desde spec3 RF3-VAL-01 y
RF3-VAL-03, un nombre del canon mal escrito y un allegado del encargo que la escaleta planifico
en el capitulo y la prosa no nombra: son errores que el lector ve, y el capitulo vuelve al
redactor. El resto son avisos que
van al informe y al juez: que haya tres palabras filtro no significa que la voz falle, y
convertirlo en fallo automatico produciria prosa timida en vez de prosa buena. La longitud real
fuera del rango tambien es un aviso (RF3-VAL-02).
"""

from __future__ import annotations

import re
import sqlite3
import unicodedata

from compartido import politica
from compartido.grafo import lectura
from compartido.puerta_base import Conflicto, ResultadoPuerta
from compartido.texto import (
    INICIO_DE_FRASE,
    MINIMO_NOMBRE,
    PALABRA_DE_NOMBRE,
    nombra,
)
from config import CRITERIOS_OFICIO, PALABRAS_FILTRO

from .esquemas import SalidaOficio, VeredictoCriterio

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


# --- spec3 RF3-GRD-03: los terminos vetados ------------------------------------------------------

_MAXIMO_EN_LA_DESCRIPCION = 10


def _terminos_vetados(
    con: sqlite3.Connection, novela_id: int, capitulo: int, texto: str
) -> Conflicto | None:
    aplicadas = politica.reglas(con, novela_id)
    hallazgos = politica.buscar(texto, aplicadas)
    if not hallazgos:
        return None
    lista = "; ".join(
        f"«{h.forma}» (termino «{h.regla.termino}») en «…{h.fragmento}…»"
        for h in hallazgos[:_MAXIMO_EN_LA_DESCRIPCION]
    )
    resto = len(hallazgos) - _MAXIMO_EN_LA_DESCRIPCION
    return Conflicto(
        comprobacion="termino_vetado", capitulo=capitulo,
        descripcion=(
            f"Terminos vetados en la prosa: {lista}" + (f"; y {resto} mas" if resto > 0 else "")
            + ". Reescribe esos pasajes sin esas palabras ni lo que nombran."
        ),
        datos={
            "politica": politica.huella(aplicadas),
            "hallazgos": [
                {"termino": h.regla.termino, "origen": h.regla.origen, "forma": h.forma,
                 "fragmento": h.fragmento, "inicio": h.inicio, "fin": h.fin}
                for h in hallazgos
            ],
        },
    )


# --- spec3 RF3-VAL-01: los nombres del canon, escritos exactamente ------------------------------

# Las piezas para buscar nombres (la palabra, el inicio de frase, las particulas) viven en
# compartido.texto desde el cambio del lector (spec3, RF3-CAM-05), que busca igual que aqui.


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
            for parte in PALABRA_DE_NOMBRE.findall(str(nombre)):
                if len(parte) >= MINIMO_NOMBRE and parte[0].isupper():
                    salida.setdefault(_plano(parte), set()).add(parte)
    return salida


def _nombres_mal_escritos(
    con: sqlite3.Connection, novela_id: int, capitulo: int, texto: str
) -> list[Conflicto]:
    """Una palabra con mayuscula que es un nombre del canon salvo por las tildes o la ene.

    «Sebastian» por «Sebastián», «Nunez» por «Núñez». Solo se miran las palabras con mayuscula;
    las mayusculas no cuentan («NÚÑEZ» gritado esta bien escrito). A mitad de frase, una palabra
    con mayuscula es un nombre propio, y el capitulo vuelve al redactor (`nombre_mal_escrito`).
    Al empezar frase o dialogo puede ser una palabra corriente («Cortes profundos», «Más tarde»),
    y corregirla le pediria al redactor una falta: ahi es un aviso (`nombre_por_revisar`) para
    el juez y el autor (validador de 469d64d). Salvo el nombre del destinatario y de sus
    allegados, el error mas visible de un regalo: si la palabra no sale nunca en minuscula en el
    capitulo, no es una palabra corriente, y tambien devuelve el capitulo (validador de
    bfb95a3). Una forma que ya devuelve el capitulo cuenta todas sus apariciones.
    """
    partes = _partes_de_los_nombres(con, novela_id)
    if not partes:
        return []
    del_regalo = _partes_del_regalo(con, novela_id)
    en_minuscula = {_plano(p) for p in PALABRA_DE_NOMBRE.findall(texto) if p[0].islower()}
    seguros: dict[tuple[str, str], int] = {}
    dudosos: dict[tuple[str, str], int] = {}
    for m in PALABRA_DE_NOMBRE.finditer(texto):
        palabra = m.group(0)
        if not palabra[0].isupper() or len(palabra) < MINIMO_NOMBRE:
            continue
        buenas = partes.get(_plano(palabra))
        if not buenas or palabra.casefold() in {b.casefold() for b in buenas}:
            continue
        al_empezar = bool(INICIO_DE_FRASE.search(texto, 0, m.start()))
        corriente = _plano(palabra) not in del_regalo or _plano(palabra) in en_minuscula
        donde = dudosos if al_empezar and corriente else seguros
        clave = (palabra, " o ".join(f"«{b}»" for b in sorted(buenas)))
        donde[clave] = donde.get(clave, 0) + 1
    for clave in [c for c in dudosos if c in seguros]:
        seguros[clave] += dudosos.pop(clave)
    salida: list[Conflicto] = []
    if seguros:
        salida.append(Conflicto(
            comprobacion="nombre_mal_escrito", capitulo=capitulo,
            descripcion="Nombres del canon mal escritos: " + _lista_de_nombres(seguros) + ".",
            datos={"errores": _datos_de_nombres(seguros)},
        ))
    if dudosos:
        salida.append(Conflicto(
            comprobacion="nombre_por_revisar", aviso=True, capitulo=capitulo,
            descripcion=(
                "Al empezar frase, palabras que son un nombre del canon salvo por las tildes (o "
                "una palabra corriente): " + _lista_de_nombres(dudosos) + "."
            ),
            datos={"errores": _datos_de_nombres(dudosos)},
        ))
    return salida


def _partes_del_regalo(con: sqlite3.Connection, novela_id: int) -> set[str]:
    """Las palabras del nombre del destinatario y de sus allegados, en clave plana."""
    brief = lectura.brief(con, novela_id)
    if brief is None:
        return set()
    nombres = [n for n in (brief.destinatario.nombre, *(a.nombre for a in brief.allegados))
               if n]
    return {_plano(p) for n in nombres for p in PALABRA_DE_NOMBRE.findall(n)
            if len(p) >= MINIMO_NOMBRE}


def _veces(n: int) -> str:
    return "1 vez" if n == 1 else f"{n} veces"


def _lista_de_nombres(errores: dict[tuple[str, str], int]) -> str:
    return "; ".join(f"«{mal}» ({_veces(n)}) se escribe {bien}"
                     for (mal, bien), n in sorted(errores.items()))


def _datos_de_nombres(errores: dict[tuple[str, str], int]) -> list[dict[str, object]]:
    return [{"escrito": mal, "canon": bien, "veces": n}
            for (mal, bien), n in sorted(errores.items())]


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

    Basta con una palabra de su nombre (`_nombra`): el redactor lo llama por el nombre de pila.
    Los rasgos y los recuerdos no se pueden buscar por palabras; son del juez.
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
        if nombre is None or nombra(texto, nombre):
            continue
        salida.append(Conflicto(
            comprobacion="allegado_ausente", capitulo=capitulo,
            descripcion=(
                f"La escaleta pone a «{nombre}» ({codigo}) en la escena {orden} y la prosa del "
                f"capitulo no escribe su nombre. Es un elemento del regalo: en esa escena, "
                f"escribe «{nombre}» al menos una vez, con mayuscula. Llamarlo por su parentesco "
                "o su papel («tu hermano», «la perra») no cuenta, aunque este en la escena "
                "(RF3-PAS-13)."
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
        _terminos_vetados(con, novela_id, capitulo, texto),
        _longitud_real(con, novela_id, capitulo, texto),
    ):
        if extra is not None:
            conflictos.append(extra)
    conflictos.extend(_nombres_mal_escritos(con, novela_id, capitulo, texto))
    conflictos.extend(_allegados_ausentes(con, novela_id, capitulo, texto))

    return ResultadoPuerta(puerta=4, conflictos=conflictos)


def _voto(juicio: SalidaOficio, criterio: str) -> VeredictoCriterio | None:
    """El voto de una muestra en un criterio: uno solo aunque lo repita, y en contra si alguno de
    sus veredictos falla (validador de 5da56ac: contar veredictos dejaba que una muestra con un
    criterio repetido pesara varias veces)."""
    del_criterio = [v for v in juicio.veredictos if v.criterio == criterio]
    return next((v for v in del_criterio if v.veredicto == "falla"),
                del_criterio[0] if del_criterio else None)


def discrepan(juicios: list[SalidaOficio]) -> bool:
    """Si alguna muestra vota otra cosa que las demas en algun criterio (RF3-JUE-02)."""
    return any(
        len({v.veredicto for j in juicios if (v := _voto(j, c)) is not None}) > 1
        for c in CRITERIOS_OFICIO
    )


def votar(juicios: list[SalidaOficio]) -> tuple[SalidaOficio, dict[str, tuple[int, int]]]:
    """Un veredicto por criterio por mayoria de las muestras, y los votos (en contra, muestras).

    Cada muestra es un voto. Con empate falla: un `falla` cuesta una reescritura, dejar pasar un
    error cuesta la novela. El veredicto que se devuelve es el de la primera muestra que
    coincide con la mayoria, para que el redactor reciba una evidencia y una sugerencia reales.
    """
    elegidos: list[VeredictoCriterio] = []
    votos: dict[str, tuple[int, int]] = {}
    for c in CRITERIOS_OFICIO:
        del_criterio = [v for j in juicios if (v := _voto(j, c)) is not None]
        if not del_criterio:
            raise ValueError(f"Ninguna muestra del juez trae el criterio '{c}'.")
        fallan = sum(v.veredicto == "falla" for v in del_criterio)
        votos[c] = (fallan, len(del_criterio))
        gana = "falla" if fallan * 2 >= len(del_criterio) else "pasa"
        elegidos.append(next(v for v in del_criterio if v.veredicto == gana))
    return SalidaOficio(veredictos=elegidos), votos


def combinar(
    mecanica: ResultadoPuerta, juicio: SalidaOficio | None,
    votos: dict[str, tuple[int, int]] | None = None,
) -> ResultadoPuerta:
    """La puerta 4 entera en un solo resultado: mecanica y juicio (RF2-PIPE-13).

    Cada criterio que el juez da por `falla` es un conflicto, con su evidencia y su
    sugerencia. La generacion invoca al juez siempre (spec3, RF3-PAS-14); la correccion del
    lector no lo invoca si su mecanica falla, y el resultado lo dice: registrar solo la
    mecanica hacia que la traza dijera `pasa` con el juez en contra.
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
        votos = votos or {}
        conflictos.extend(
            Conflicto(
                comprobacion=f"juicio:{v.criterio}",
                descripcion=f"Principio {v.principio}. {v.sugerencia}".strip(),
                datos={"criterio": v.criterio, "principio": v.principio,
                       "evidencia": v.evidencia, "sugerencia": v.sugerencia,
                       **({"votos": list(votos[v.criterio])} if v.criterio in votos else {})},
            )
            for v in juicio.incumplidos
        )
        # Lo que el juez no tiene claro, a la vista aunque pase (RF3-JUE-02).
        divididos = {c: (f, t) for c, (f, t) in votos.items() if 0 < f < t}
        if divididos:
            conflictos.append(Conflicto(
                comprobacion="juicio_dividido", aviso=True,
                descripcion="El juez no fue unanime: " + "; ".join(
                    f"{c}, {f} de {t} muestras en contra" for c, (f, t) in divididos.items()
                ) + ".",
                datos={"votos": {c: list(ft) for c, ft in divididos.items()}},
            ))
    return ResultadoPuerta(puerta=4, conflictos=conflictos)
