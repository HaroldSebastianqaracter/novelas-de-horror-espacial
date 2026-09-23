"""Tipos compartidos por las tareas: listas cerradas de la ontologia y del pipeline.

Vive en compartido/ porque lo usan varias tareas y una tarea no importa de otra (RF-COD-03).
Son la traduccion de las listas cerradas de docs/definitions.md y docs/domain-knowledge.md.
"""

from __future__ import annotations

from typing import Literal

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
)

TIPOS_EVENTO: tuple[str, ...] = (
    "intencion_recibida", "fase_cambiada", "agente_iniciado", "agente_terminado",
    "puerta_evaluada", "capitulo_completado", "parada", "parada_resuelta", "detenida",
    "revertido", "rehecho", "completada", "error", "worker_recuperado", "paquete_recortado",
)
