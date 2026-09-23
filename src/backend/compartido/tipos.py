"""Tipos compartidos por las tareas: listas cerradas de la ontologia y del pipeline.

Vive en compartido/ porque lo usan varias tareas y una tarea no importa de otra (RF-COD-03).
Son la traduccion de las listas cerradas de docs/definitions.md y docs/domain-knowledge.md.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Literal, cast

# --- Ontologia ---------------------------------------------------------------------------

RolNarrativo = Literal[
    "protagonista", "oponente", "aliado", "falso_aliado", "mentor", "heraldo",
    "guardian_del_umbral", "espejo",
]
TipoArco = Literal["positivo", "plano", "negativo"]
SubtipoArco = Literal["desilusion", "caida", "corrupcion"]
Dureza = Literal["duro", "blando"]
TipoHilo = Literal["principal", "subtrama"]
EstadoHilo = Literal["abierto", "complicando", "latente", "resuelto", "abierto_deliberado"]
EstadoSiembra = Literal["sembrada", "regada", "pagada", "abandonada"]
NivelRevelacion = Literal["rastro", "efecto", "vislumbre", "encuentro", "confrontacion"]
Postura = Literal["sabe", "cree", "sospecha", "ignora", "cree_version_falsa"]
#: La muerte como dato cerrado, y no como busqueda en el texto libre de la salud (RF2-PIPE-12).
CondicionPersonaje = Literal["vivo", "herido", "incapacitado", "muerto", "desaparecido"]
Via = Literal["presencio", "se_lo_contaron", "dedujo", "le_mintieron"]
CategoriaHecho = Literal[
    "nombre", "fisico", "fecha", "distancia", "regla", "relacion", "ubicacion", "otro",
]
SujetoTipo = Literal[
    "personaje", "lugar", "objeto", "amenaza", "sistema_tecnologico", "faccion", "mundo",
    "novela", "otro",
]
TipoPuntoDeGiro = Literal[
    "gancho", "incidente_incitador", "primer_umbral", "punto_de_pellizco", "punto_medio",
    "segundo_pellizco", "todo_esta_perdido", "entrada_tercer_acto", "crisis", "climax",
    "resolucion",
]
Pov = Literal["primera", "tercera_limitada", "omnisciente", "objetiva"]
TiempoVerbal = Literal["pasado", "presente"]
TipoFinal = Literal[
    "cerrado", "tragico", "agridulce", "con_giro", "ambiguo", "circular", "ironico",
    "cierre_parcial", "abierto", "victoria_pirrica",
]
Subgenero = Literal[
    "terror_corporal", "infeccion", "horror_cosmico", "slasher_espacial", "ia_hostil",
    "supervivencia",
]

# --- Pipeline ----------------------------------------------------------------------------

EstadoEjecucion = Literal[
    "configurada", "planificando", "escaletando", "generando", "parada", "detenida",
    "completada", "completada_con_avisos", "error",
]
TipoParada = Literal["estructura", "escaleta", "continuidad", "oficio", "presupuesto"]
TipoIntencion = Literal["crear_novela", "arrancar", "parar", "relanzar", "resolver_parada"]
EstadoIntencion = Literal["pendiente", "en_curso", "hecha", "rechazada", "interrumpida"]
Veredicto = Literal["pasa", "falla", "aviso"]

AGENTES: tuple[str, ...] = (
    "arquitecto", "mundo", "elenco", "estructura", "escaleta", "redaccion", "extraccion",
    "continuidad", "oficio",
    # El entrevistador no corre en el pipeline: lo invoca entrevista.py antes de crear la
    # novela (specs/spec3.md, RF3-ENT-01). Es un agente con su skill igual que los demas.
    "entrevistador",
)

TIPOS_EVENTO: tuple[str, ...] = (
    "intencion_recibida", "fase_cambiada", "agente_iniciado", "agente_terminado",
    "puerta_evaluada", "capitulo_completado", "parada", "parada_resuelta", "detenida",
    "revertido", "rehecho", "completada", "error", "worker_recuperado", "paquete_recortado",
    "extraccion_descartes", "indice_fallo",
)


def como_dict(valor: object) -> dict[str, Any]:
    """Un objeto JSON ya cargado, o {} si no lo es. El tipo lo fija quien lo lee."""
    return cast(dict[str, Any], valor) if isinstance(valor, dict) else {}


def como_lista(valor: object) -> list[Any]:
    """Una lista JSON ya cargada, o [] si no lo es."""
    return cast(list[Any], valor) if isinstance(valor, list) else []


def nombres_repetidos(nombres: Iterable[str]) -> list[str]:
    """Los nombres que coinciden con otro una vez normalizados (RF2-PER-11).

    Lo usan los esquemas de mundo, elenco y estructura para que el agente corrija en su
    reintento dos entidades que solo difieren en tildes o mayusculas, en vez de que la
    escritura falle contra el indice unico.
    """
    from compartido.grafo.escritura import normalizar

    vistos: dict[str, str] = {}
    repetidos: list[str] = []
    for nombre in nombres:
        clave = normalizar(nombre)
        if clave in vistos:
            repetidos.append(f"'{vistos[clave]}' y '{nombre}'")
        else:
            vistos[clave] = nombre
    return repetidos
