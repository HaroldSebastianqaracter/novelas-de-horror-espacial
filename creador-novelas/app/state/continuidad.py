"""Log de continuidad: append-only y filtrado por relevancia (RF-05.1, RF-06.3, RF-07.6, INV-03, §12.3).

Este módulo expone `agregar()` y `marcar_superado()`; no existe `eliminar()` ni `modificar()` (§10).
Todas las funciones devuelven un log nuevo: nunca mutan el recibido.
"""

from __future__ import annotations

from typing import Callable

from app.schemas.continuidad import HechoContinuidad, LogContinuidad
from app.schemas.outline import EntradaOutline

SUJETO_MUNDO = "mundo"


def validar_sujeto(hecho: HechoContinuidad, registro: set[str]) -> HechoContinuidad:
    """RF-06.1: un sujeto fuera del registro no rechaza el hecho; fija sujeto_validado = False."""
    validado = hecho.sujeto in registro or (hecho.categoria == "mundo" and hecho.sujeto == SUJETO_MUNDO)
    return hecho.model_copy(update={"sujeto_validado": validado})


def agregar(log: LogContinuidad, hechos: list[HechoContinuidad], cap_origen: int,
            registro: set[str]) -> LogContinuidad:
    """RF-06.3: agrega hechos con cap_origen = N y sujeto validado contra el registro. Solo crece."""
    nuevos = [
        validar_sujeto(h.model_copy(update={"cap_origen": cap_origen, "superado_por": None}), registro)
        for h in hechos
    ]
    return LogContinuidad(list(log.root) + nuevos)


def marcar_superado(log: LogContinuidad, caps: list[int]) -> LogContinuidad:
    """RF-07.6: los hechos con cap_origen en `caps` quedan superados por la reextracción de ese capítulo. Nada se borra."""
    objetivo = set(caps)
    resultado = []
    for h in log.root:
        if h.cap_origen in objetivo and h.superado_por is None:
            resultado.append(h.model_copy(update={"superado_por": h.cap_origen}))
        else:
            resultado.append(h)
    return LogContinuidad(resultado)


def filtrar_para_capitulo(log: LogContinuidad, entrada: EntradaOutline,
                          personajes: set[str] | None = None) -> list[HechoContinuidad]:
    """RF-05.1: selección de lectura, no escribe.

    Entran los hechos vigentes cuyo sujeto es un personaje o la locación del capítulo; entran siempre los de
    categoria = "mundo" y los de sujeto_validado = False. El filtro puede incluir de más, nunca de menos.

    `personajes` permite ampliar el conjunto por defecto (los de la entrada de escaleta). El escritor pasa
    aquí todos los personajes permitidos (X-02.1): un personaje al que la regla 2 le deja escribir tiene que
    llegar con sus hechos vigentes, o el escritor escribe a ciegas sobre él.
    """
    personajes = set(entrada.personajes) if personajes is None else set(personajes)
    seleccion = []
    for h in log.root:
        if h.superado_por is not None:
            continue
        if h.categoria == "mundo" or not h.sujeto_validado:
            seleccion.append(h)
        elif h.sujeto in personajes or h.sujeto == entrada.locacion:
            seleccion.append(h)
        # X-05: el salto de vecindad. Un hecho cuyo sujeto no está en escena pero que toca a alguien
        # que sí lo está entra igual: es exactamente el que hoy se pierde y sobre el que el escritor
        # --que no puede leer capítulos anteriores-- acaba escribiendo a ciegas.
        elif set(h.relacionados) & personajes:
            seleccion.append(h)
    return seleccion


# X-05: pesos de la puntuación. Salen de para qué sirve cada hecho en el prompt, no de un ajuste
# fino: quien está en escena manda sobre quien la toca de refilón, y lo reciente sobre lo viejo.
PESO_SUJETO_EN_ESCENA = 3
PESO_LOCACION = 2
PESO_RELACIONADO = 1
PESO_CATEGORIA = {"personaje": 2, "locacion": 1, "mundo": 0}


def puntuar(h: HechoContinuidad, entrada: EntradaOutline, personajes: set[str], n: int) -> int:
    """Cuánto pide este hecho su sitio en el prompt del capítulo `n`.

    No sirve para descartar por debajo de un umbral: solo para ordenar la cola cuando el presupuesto
    aprieta. Con sitio de sobra entra todo, igual que hasta ahora.
    """
    puntos = PESO_CATEGORIA.get(h.categoria, 0)
    if h.sujeto in personajes:
        puntos += PESO_SUJETO_EN_ESCENA
    if h.sujeto == entrada.locacion:
        puntos += PESO_LOCACION
    if set(h.relacionados) & personajes:
        puntos += PESO_RELACIONADO
    # Recencia: lo de hace dos capítulos pesa más que lo de hace doce, pero nunca al punto de que un
    # hecho antiguo de un personaje en escena pierda contra uno reciente de alguien que no está.
    antiguedad = max(0, n - (h.cap_origen or 0))
    return puntos * 10 - antiguedad


def recortar_a_presupuesto(hechos: list[HechoContinuidad], entrada: EntradaOutline, personajes: set[str],
                           n: int, *, tope_tokens: int,
                           coste: Callable[[HechoContinuidad], int]) -> list[HechoContinuidad]:
    """X-05: si los hechos no caben, se quedan los que más falta hacen. Pero se leen en orden.

    Dos reglas que no se negocian:

    - Los de `cap_origen = 0` entran siempre. Son el canon del preludio, las reglas del mundo que la
      novela no puede contradecir; recortarlas provoca justo la contradicción que esto evita.
    - La salida va ordenada por `cap_origen`, no por puntuación. El escritor tiene que leer una
      cronología; un ranking le cuenta la historia desordenada, y eso es peor que darle menos hechos.
    """
    canon = [h for h in hechos if (h.cap_origen or 0) == 0]
    resto = [h for h in hechos if (h.cap_origen or 0) != 0]
    gastado = sum(coste(h) for h in canon)
    elegidos = list(canon)
    if gastado < tope_tokens:
        for h in sorted(resto, key=lambda x: puntuar(x, entrada, personajes, n), reverse=True):
            c = coste(h)
            if gastado + c > tope_tokens:
                continue  # sigue mirando: detrás puede venir uno más corto que sí cabe
            elegidos.append(h)
            gastado += c
    return sorted(elegidos, key=lambda h: (h.cap_origen or 0))


def es_superconjunto(anterior: LogContinuidad, nuevo: LogContinuidad) -> tuple[bool, str]:
    """INV-03 / H-03: todo hecho previo sigue presente, idéntico, a lo sumo con `superado_por` nuevo."""
    if len(nuevo.root) < len(anterior.root):
        return False, f"el log pasó de {len(anterior.root)} a {len(nuevo.root)} hechos"
    for i, (a, b) in enumerate(zip(anterior.root, nuevo.root)):
        base_a = a.model_dump(exclude={"superado_por"})
        base_b = b.model_dump(exclude={"superado_por"})
        if base_a != base_b:
            return False, f"el hecho #{i} (cap_origen {a.cap_origen}) cambió o desapareció: {a.hecho!r}"
        if a.superado_por is not None and b.superado_por != a.superado_por:
            return False, f"el hecho #{i} perdió su marca superado_por={a.superado_por}"
    return True, ""


def por_capitulo(log: LogContinuidad, cap_origen: int) -> list[HechoContinuidad]:
    return [h for h in log.root if h.cap_origen == cap_origen]


# ---------- hechos que la propia novela tiene que desmentir (§17.3) ----------
#
# Tres novelas de la corrida de velocidad murieron por lo mismo. La fase 4 anotaba como hecho
# permanente del mundo justo aquello que la trama existe para revelar como falso --«no hay ningún
# pasillo de servicio entre la bodega y la sala de máquinas», «el pasajero nunca pregunta nada»--,
# y el capítulo del giro lo desmentía, porque el susto ES que aparezca el pasillo. QA lo marcaba
# como contradicción, con toda la razón, y la novela paraba a mitad.
#
# El error de fondo es meter dos afirmaciones en una. «Los planos no recogen ningún pasillo» es
# cierto para siempre y no le cierra la puerta a nada. «No hay ningún pasillo» es una afirmación
# sobre la realidad que el capítulo 2 tiene que negar para que haya novela. Un hecho inicial puede
# decir lo que un registro recoge, lo que alguien sabe o lo que se ha medido; no lo que el mundo es
# para siempre.
import re  # noqa: E402
import unicodedata  # noqa: E402  (queda junto a lo que usa, que es lo único que lo necesita)

_ABSOLUTOS = (
    (re.compile(r"\bno\s+(hay|existe[n]?|queda[n]?|tiene[n]?)\s+(ning[úu]n|ninguna|nada)\b", re.I),
     "niega la existencia de algo"),
    (re.compile(r"\bnunca\b|\bjam[áa]s\b", re.I), "declara que algo no pasa nunca"),
    (re.compile(r"\ben\s+ning[úu]n\s+(momento|caso)\b", re.I), "declara una excepción imposible"),
    (re.compile(r"\bnadie\s+(puede|podr[íi]a|consigue|logra|ha\s+conseguido|ha\s+logrado)\b", re.I),
     "declara que nadie puede algo"),
)

# Lo mismo dicho sobre un registro, un plano o una medición no compromete a nada: ahí la negación es
# del documento, no del mundo, y revelar que el documento estaba incompleto es el giro, no una
# contradicción.
_SOBRE_UN_REGISTRO = re.compile(
    r"\b(plano|planos|registro|registros|manifiesto|inventario|carta|cartas|expediente|informe|"
    r"informes|parte|partes|papel|papeles|archivo|archivos|barrido|barridos|documentaci[óo]n|"
    r"sondeo|mapa|mapas|bit[áa]cora|historial|ficha|fichas)\b", re.I)

# `nunca` sobre el pasado --«nunca lo ha contado a bordo»-- es un secreto, no una ley: que salga a la
# luz en el capítulo 3 es la novela funcionando. `nunca` en presente --«nunca pregunta nada»-- sí es
# una ley, y esa es la que el giro tiene que romper.
_NUNCA_DEL_PASADO = re.compile(r"\b(nunca|jam[áa]s)\b[^.;:]{0,40}?\b(ha|han|hab[íi]a|hab[íi]an|"
                               r"hubo|fue|fueron|estuvo|estuvieron|lleg[óo]|volvi[óo])\b", re.I)

# Cada oración se juzga sola. El hecho que mató a la cuarta novela decía las dos cosas en una línea:
# «no hay ningún pasillo de servicio: los planos de a bordo no registran ninguno». Mirando la frase
# entera, la palabra «planos» la daba por buena; mirando oración por oración, la primera mitad niega
# la existencia sin apoyarse en ningún documento, que es justo lo que el capítulo 2 desmintió.
_CORTE = re.compile(r"[.;:]|\s+--\s+|\s+—\s+")


def absolutos_que_la_trama_desmentira(log: LogContinuidad) -> list[tuple[str, str]]:
    """Hechos iniciales escritos como ley del mundo en vez de como lo que dice un registro.

    Devuelve `(hecho, motivo)` por cada uno. Solo mira los de `cap_origen = 0`: los que llegan por
    extracción describen lo que un capítulo estableció, y ahí la permanencia ya la juzga QA.
    """
    encontrados = []
    for h in log.root:
        if h.cap_origen != 0:
            continue
        for oracion in _CORTE.split(h.hecho):
            if _SOBRE_UN_REGISTRO.search(oracion) or _NUNCA_DEL_PASADO.search(oracion):
                continue
            motivo = next((m for patron, m in _ABSOLUTOS if patron.search(oracion)), None)
            if motivo:
                encontrados.append((h.hecho, motivo))
                break
    return encontrados


# ---------- personajes puestos en dos sitios a la vez ----------
#
# El escritor no puede preguntar ni leer capítulos anteriores, así que todo hueco de la escaleta lo
# rellena él a ciegas. En «abordaje» el hecho decía que Oyarzo tenía la guardia del puente y el
# capítulo 1 la mataba en el pasillo del nivel dos: las dos cosas pueden ser ciertas --baja y ya
# está--, pero alguien tiene que narrar la bajada, y en 400 palabras no cupo. El escritor escribió
# «bajaron los cinco» y tres párrafos después «Oyarzo venía del puente», y QA paró la novela.
#
# No se trata de prohibir que un personaje se mueva, sino de que el salto no quede implícito. Hay
# dos arreglos y los dos valen: narrar el paso («baja al nivel dos al oír la alarma») o evitarlo
# (que la escena ocurra donde ya estaba).

def _plano(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode("ascii").lower()


def _terminos_de_locacion(nombre: str) -> list[str]:
    """Las locaciones se llaman «Vereda Sur - puente», pero los hechos dicen «la guardia del puente».

    Así que se busca por el nombre entero y también por su cola distintiva, la parte que va después
    del último guion, que es como la nombra la prosa.
    """
    entero = _plano(nombre).strip()
    cola = entero.rsplit(" - ", 1)[-1].strip()
    return [t for t in dict.fromkeys([entero, cola]) if len(t) >= 4]


def personajes_en_dos_sitios(log: LogContinuidad, outline, locaciones: list[str]) -> list[tuple[str, str, str, int]]:
    """Hechos iniciales que sitúan a un personaje lejos del capítulo en el que aparece.

    Devuelve `(sujeto, locación del hecho, locación del capítulo, número de capítulo)`.
    """
    encontrados = []
    for h in log.root:
        if h.cap_origen != 0 or h.categoria != "personaje":
            continue
        texto = _plano(h.hecho)
        entrada = next((e for e in outline.root if h.sujeto in e.personajes), None)
        if entrada is None:
            continue
        propia = _terminos_de_locacion(entrada.locacion)
        for nombre in locaciones:
            if nombre == entrada.locacion:
                continue
            if any(t in texto for t in _terminos_de_locacion(nombre)) and not any(t in texto for t in propia):
                encontrados.append((h.sujeto, nombre, entrada.locacion, entrada.num))
                break
    return encontrados
