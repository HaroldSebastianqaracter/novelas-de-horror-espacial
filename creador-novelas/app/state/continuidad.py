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


def filtrar_para_capitulo(log: LogContinuidad, entrada: EntradaOutline) -> list[HechoContinuidad]:
    """RF-05.1: selección de lectura, no escribe.

    Entran los hechos vigentes cuyo sujeto es un personaje o la locación del capítulo; entran siempre los de
    categoria = "mundo" y los de sujeto_validado = False. El filtro puede incluir de más, nunca de menos.
    """
    personajes = set(entrada.personajes)
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
