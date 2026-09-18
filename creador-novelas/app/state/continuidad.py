"""Log de continuidad: append-only y filtrado por relevancia (RF-05.1, RF-06.3, RF-07.6, INV-03, §12.3).

Este módulo expone `agregar()` y `marcar_superado()`; no existe `eliminar()` ni `modificar()` (§10).
Todas las funciones devuelven un log nuevo: nunca mutan el recibido.
"""

from __future__ import annotations

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
    return seleccion


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
import re  # noqa: E402  (queda junto a lo que usa, que es lo único que lo necesita)

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
