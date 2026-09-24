"""Comparacion de terminos en texto libre (RF3-BRF-03).

La usan el analisis del brief, para saber si un termino vetado aparece en un elemento
personal, y la usara el guardrail de palabras prohibidas del bloque 5. Por eso vive aqui y
no en ninguno de los dos: tienen que normalizar exactamente igual, o lo que uno deja pasar el
otro lo bloquea.

La normalizacion es la de los nombres del grafo (`normalizar`: sin mayusculas ni acentos,
con la ene) mas un plural simple. El castellano forma el plural con -s tras vocal («nave»,
«naves») y con -es tras consonante («motor», «motores»), y desde el plural no se sabe cual de
las dos quitar. Por eso cada palabra lleva sus formas singulares posibles, y dos palabras son
el mismo termino si comparten alguna.
"""

from __future__ import annotations

import re

from compartido.grafo.escritura import normalizar

# Letras y cifras: «41» tambien es una palabra, y una cita con la edad tiene que casar.
_PALABRA = re.compile(r"[^\W_]+", re.UNICODE)
_MINIMO = 2

#: Las palabras de una cifra escrita en letra, normalizadas. Las usan el extractor, para no
#: cortar una cifra al comparar trozos (spec3, RF3-PAS-01), y el juez de oficio, para saber
#: que hechos llevan una cuenta (RF3-PAS-12).
NUMERALES = frozenset({
    "cero", "un", "uno", "una", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho",
    "nueve", "diez", "once", "doce", "trece", "catorce", "quince", "dieciseis", "diecisiete",
    "dieciocho", "diecinueve", "veinte", "veintiun", "veintiuno", "veintidos", "veintitres",
    "veinticuatro", "veinticinco", "veintiseis", "veintisiete", "veintiocho", "veintinueve",
    "treinta", "cuarenta", "cincuenta", "sesenta", "setenta", "ochenta", "noventa", "cien",
    "ciento", "doscientos", "trescientos", "cuatrocientos", "quinientos", "seiscientos",
    "setecientos", "ochocientos", "novecientos", "mil", "millon", "millones", "medio",
})
#: Tambien son articulos o adjetivos: «una mancha» no es una cuenta, pero «una hora» si.
_NUMERALES_AMBIGUOS = frozenset({"un", "uno", "una", "medio", "media"})
#: Cantidades que no son numerales: «una docena», «la mitad», «miles». No entran «par» ni
#: «cuarto», que casi siempre son otra cosa («a la par», el cuarto de maquinas).
_CANTIDADES = frozenset({
    "docena", "docenas", "decena", "decenas", "veintena", "centenar", "centenares", "cientos",
    "miles", "millar", "millares", "mitad", "tercio", "tercios",
})
#: Tras un numeral ambiguo, la unidad dice que es una cantidad: «un minuto», «una persona».
_UNIDADES = frozenset({
    "segundo", "minuto", "hora", "dia", "noche", "semana", "mes", "año", "turno", "metro",
    "kilometro", "litro", "kilo", "grado", "persona", "racion", "dosis", "tanque", "bombona",
})


#: Las palabras que dicen que una cifra cuenta personas (spec3, RF3-PAS-16), enteras y casi
#: siempre en plural: una raiz como «persona» casaba con «personalidad», «herid» con «herida en
#: el casco» y «bordo» con «presion a bordo» (validador de f752f39).
_PALABRA_DE_PERSONAS = re.compile(
    r"personas?|personal|gente|tripulacion|tripulantes?|dotacion|cuadrillas?|evacuad[oa]s"
    r"|supervivientes?|muert[oa]s|bajas|herid[oa]s|colonos|habitantes|pasajer[oa]s|miembros"
    r"|hombres|mujeres|niñ[oa]s|respirando|viv[oa]s|dormid[oa]s|desaparecid[oa]s|cadaveres"
    r"|cuerpos|infectad[oa]s|tecnicos|mineros|ocupantes|soldados|durmientes|trabajadores"
    r"|operarios|cientificos|ingenieros|guardias|rehenes|quedan"
)


def cuenta_personas(texto: str) -> bool:
    """Si el texto da una cifra de personas: una cantidad y una palabra de gente.

    Sirve para el censo del redactor (RF3-PAS-16): «personas a bordo: siete», «bajas del turno:
    dos», «once respirando». Mejor de mas que de menos: una linea que sobra en el censo cuesta
    unos tokens; una que falta deja al redactor sumando de memoria.
    """
    if not tiene_cifra(texto):
        return False
    return any(_PALABRA_DE_PERSONAS.fullmatch(p) for p in _PALABRA.findall(normalizar(texto)))


#: Una etiqueta que la prosa no deberia llevar nunca (spec3, RF3-SEU-04): una del encargo sin
#: restaurar, u otra que el modelo invente («[NOMBRE_ANONIMIZADO]», «[DESTINATARIO_APODO]»).
ETIQUETA_SIN_NOMBRE = re.compile(r"\[[A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ0-9_]{2,}\]")


def tiene_cifra(texto: str) -> bool:
    """Si el texto da una cantidad (spec3, RF3-PAS-12).

    Un digito en cualquier parte de la palabra («31h», «T-40h»), un numeral en letra, una
    cantidad como «docena» o «mitad», o un numeral ambiguo («un», «una») seguido de una unidad.
    """
    palabras = _PALABRA.findall(normalizar(texto))
    for i, p in enumerate(palabras):
        if any(c.isdigit() for c in p) or p in _CANTIDADES:
            return True
        if p in NUMERALES and p not in _NUMERALES_AMBIGUOS:
            return True
        siguiente = palabras[i + 1] if i + 1 < len(palabras) else ""
        if p in _NUMERALES_AMBIGUOS and formas(siguiente) & _UNIDADES:
            return True
        # «un cuarto de hora»: el cuarto de maquinas no es una cantidad.
        if p == "cuarto" and palabras[i + 1:i + 2] == ["de"] and \
                formas(palabras[i + 2] if i + 2 < len(palabras) else "") & _UNIDADES:
            return True
    return False


def formas(palabra: str) -> frozenset[str]:
    """La palabra y sus singulares simples posibles, sin bajar de dos letras («las», «la»)."""
    salida = {palabra}
    if palabra.endswith("s") and len(palabra) - 1 >= _MINIMO:
        salida.add(palabra[:-1])
    if palabra.endswith("es") and len(palabra) - 2 >= _MINIMO:
        salida.add(palabra[:-2])
    return frozenset(salida)


def palabras(texto: str) -> list[frozenset[str]]:
    """Las palabras del texto, normalizadas, cada una con sus formas, en orden."""
    return [formas(p) for p in _PALABRA.findall(normalizar(texto))]


def contiene_termino(texto: str, termino: str) -> bool:
    """Si el termino aparece en el texto como palabra o secuencia de palabras completas.

    «Laura» no aparece en «Laurana»; «la nave» aparece en «Las naves ardian».
    """
    return aparece_en(palabras(texto), termino)


def veces_termino(texto: str, termino: str) -> int:
    """Cuantas veces aparece el termino como palabras completas (spec3, RF3-CAM-09)."""
    presentes, buscadas = palabras(texto), palabras(termino)
    n = len(buscadas)
    if not n:
        return 0
    return sum(
        all(presentes[i + k] & buscadas[k] for k in range(n))
        for i in range(len(presentes) - n + 1)
    )


def aparece_en(presentes: list[frozenset[str]], termino: str) -> bool:
    """`contiene_termino` sobre un texto ya partido con `palabras`.

    Para buscar muchos terminos en la misma prosa sin normalizarla cada vez (RF3-BIB-01).
    """
    buscadas = palabras(termino)
    if not buscadas:
        return False
    n = len(buscadas)
    return any(
        all(presentes[i + k] & buscadas[k] for k in range(n))
        for i in range(len(presentes) - n + 1)
    )


# --- Nombres propios en la prosa (spec3, RF3-VAL-01, RF3-VAL-03 y RF3-CAM-05) -----------------

#: Una palabra de un nombre: solo letras.
PALABRA_DE_NOMBRE = re.compile(r"[^\W\d_]+")
#: Lo que abre una frase o un dialogo: ahi va mayuscula cualquier palabra, y «Cortes» (heridas)
#: y el apellido «Cortés» solo se distinguen por la tilde. Tras «:» y «;» va minuscula, asi que
#: una mayuscula ahi es un nombre propio; salvo tras dos puntos que abren una cita o un dialogo
#: («Le dijo: —Tomas el primer turno»), que llevan mayuscula (validador de a5d0355).
INICIO_DE_FRASE = re.compile(
    r"(?:^|[.!?¿¡…\n]|:\s*[«\"“‘'\-–—])[\s«»\"“”‘’'\-–—*(\[]*$")
MINIMO_NOMBRE = 3
#: Partes de un nombre que no lo identifican: «Pedro del Río» no se nombra con «del».
PARTICULAS_DE_NOMBRE = frozenset({"de", "del", "la", "las", "los", "el", "y", "e", "san", "santa"})


def partes_de_nombre(nombre: str) -> list[str]:
    """Las palabras que identifican un nombre: de tres letras o mas y sin particulas."""
    return [
        p for p in PALABRA_DE_NOMBRE.findall(nombre)
        if len(p) >= MINIMO_NOMBRE and normalizar(p) not in PARTICULAS_DE_NOMBRE
    ]


def nombra(texto: str, nombre: str) -> bool:
    """Si la prosa nombra a alguien: una palabra de su nombre, sin contar las particulas, escrita
    con mayuscula. «La luz parpadeo» no nombra a Luz, ni «el tunel del sector» a Pedro del Rio.
    Las tildes no cuentan: un «Tomas» mal escrito tambien nombra a Tomás."""
    buscadas = {normalizar(p) for p in partes_de_nombre(nombre)} or {normalizar(nombre)}
    return any(
        m.group(0)[0].isupper() and normalizar(m.group(0)) in buscadas
        for m in PALABRA_DE_NOMBRE.finditer(texto)
    )
