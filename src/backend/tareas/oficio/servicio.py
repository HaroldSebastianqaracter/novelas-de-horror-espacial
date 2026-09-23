"""El paquete del revisor de oficio: la parte de juicio de la puerta 4."""

from __future__ import annotations

import sqlite3

from compartido.contexto import Elemento, Paquete, Presupuesto, ajustar
from compartido.grafo import lectura
from compartido.puerta_base import ResultadoPuerta
from compartido.texto import tiene_cifra

AGENTE = "oficio"


def paquete(
    con: sqlite3.Connection,
    novela_id: int,
    capitulo: int,
    texto: str,
    mecanica: ResultadoPuerta | None = None,
    *,
    presupuesto: Presupuesto,
) -> Paquete:
    e = lectura.estilo(con, novela_id) or {}
    escenas = lectura.escenas_del_capitulo(con, novela_id, capitulo)
    canon = lectura.canon_del_capitulo(con, novela_id, capitulo)

    p = Paquete(agente=AGENTE, capitulo=capitulo)

    instrucciones = [
        f"Juzga el capitulo {capitulo}. Ya ha pasado la continuidad de hechos, conocimiento "
        "y presencias: de la continuidad solo te toca comprobar las cuentas "
        "(`cuentas_cuadran`), con los hechos con cifras que van al final.",
        "",
        "ESTILO NARRATIVO DE LA OBRA (contra el que se mide la voz):",
        f"- Registro: {e.get('registro', '')}",
        f"- Ritmo de prosa: {e.get('ritmo_prosa', '')}",
        f"- Densidad sensorial: {e.get('densidad_sensorial', '')}",
        f"- Distancia psiquica por defecto: {e.get('distancia_psiquica', '')}",
    ]
    tics = lectura.tics_prohibidos(con, novela_id)
    if tics:
        instrucciones.append("- Tics prohibidos: " + "; ".join(tics))
    p.anadir("instrucciones", "\n".join(instrucciones), "TU ENCARGO Y EL ESTILO")

    # La voz del POV es obligatoria; la del resto del reparto se recorta por apariciones.
    voces = [
        Elemento(
            f"- **{per['nombre']}**: {per['idiolecto']}",
            obligatorio=int(per.get("escenas_pov") or 0) > 0,
        )
        for per in canon["personajes"] if per.get("idiolecto")
    ]
    if voces:
        p.anadir_elementos(
            "canon",
            [Elemento("Al tapar las acotaciones se tiene que seguir sabiendo quien habla:",
                      True), *voces],
            "VOZ DE CADA PERSONAJE",
        )

    plan = [
        f"- Escena {x['orden']} ({x['pov_nombre']}, {x['lugar_nombre']}): "
        f"objetivo «{x['objetivo']}», conflicto «{x['conflicto']}», "
        f"valor {x['valor_inicial']} -> {x['valor_final']}, tension {x['tension']}/10"
        for x in escenas
    ]
    p.anadir(
        "escaleta",
        "Lo que cada escena tenia que conseguir:\n" + "\n".join(plan),
        f"ESCALETA DEL CAPITULO {capitulo}",
    )
    p.anadir("prosa", texto, f"PROSA DEL CAPITULO {capitulo}")

    # Las cuentas se comprueban contra el canon (spec3, RF3-PAS-12). Opcionales: sin ellos el
    # juez aun ve si la prosa cuadra consigo misma.
    cifras = [h for h in lectura.hechos_hasta(con, novela_id, capitulo)
              if tiene_cifra(h["valor"])]
    if cifras:
        p.anadir_elementos(
            "hechos",
            [Elemento("Canon cerrado: toda cifra de la prosa que se derive de estos hechos "
                      "tiene que cuadrar con ellos.", True),
             *(Elemento(f"- {h['sujeto_nombre']} · {h['atributo']}: {h['valor']} "
                        f"(cap. {h['capitulo_origen']})", False) for h in cifras)],
            "HECHOS ESTABLECIDOS CON CIFRAS",
        )

    if mecanica is not None and mecanica.conflictos:
        p.anadir(
            "criterios_incumplidos",
            "Son insumo, no veredicto: mira cada caso en su sitio y decide.\n"
            + "\n".join(f"- {c}" for c in mecanica.conflictos),
            "AVISOS DE LA PASADA MECANICA",
        )

    return ajustar(p, presupuesto)
