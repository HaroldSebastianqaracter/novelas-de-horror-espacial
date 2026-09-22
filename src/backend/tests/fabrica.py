"""Fabrica de grafos de prueba: una novela minima y correcta sobre la que mutar.

La usan los tests de la puerta 3. La idea es la de validators.md: introducir contradicciones
a proposito en un manuscrito correcto y comprobar que el validador las detecta. Es la unica
forma de saber si la verificacion determinista sirve de algo.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field


@dataclass
class Grafo:
    """Ids de lo insertado, para que los tests puedan mutar sin volver a consultar."""

    novela_id: int
    lugares: dict[str, int] = field(default_factory=dict)
    personajes: dict[str, int] = field(default_factory=dict)
    objetos: dict[str, int] = field(default_factory=dict)
    escenas: dict[tuple[int, int], int] = field(default_factory=dict)  # (capitulo, orden) -> id
    capitulos: dict[int, int] = field(default_factory=dict)
    hechos: dict[str, int] = field(default_factory=dict)
    linea_id: int = 0
    amenaza_id: int = 0


def _id(cur: sqlite3.Cursor) -> int:
    return int(cur.lastrowid or 0)


def novela_minima(con: sqlite3.Connection) -> Grafo:
    """Dos capitulos, dos escenas cada uno, sin ningun conflicto de continuidad."""
    nid = _id(con.execute(
        "INSERT INTO novela (titulo, subgenero_dominante, tipo_final, longitud_objetivo) "
        "VALUES ('El casco', 'horror_cosmico', 'victoria_pirrica', 80000)"
    ))
    g = Grafo(novela_id=nid)

    con.execute(
        "INSERT INTO estilo_narrativo (novela_id, registro, ritmo_prosa, densidad_sensorial,"
        " distancia_psiquica, tics_prohibidos) VALUES (?,?,?,?,?,?)",
        (nid, "sobrio", "medio", "alta", "cercana", '["de repente"]'),
    )
    mundo_id = _id(con.execute(
        "INSERT INTO mundo (novela_id, nombre, reglas_fisicas) VALUES (?,?,?)",
        (nid, "Estacion Tesalia", "Sin atmosfera fuera del casco."),
    ))
    g.linea_id = _id(con.execute(
        "INSERT INTO linea_de_tiempo (novela_id, origen, unidad) VALUES (?,?,?)",
        (nid, "dia 0", "dia"),
    ))
    tema_id = _id(con.execute(
        "INSERT INTO tema (novela_id, pregunta_central, verdad_tematica) VALUES (?,?,?)",
        (nid, "Que se debe a quien no volvera?", "El deber sobrevive a la esperanza."),
    ))
    g.amenaza_id = _id(con.execute(
        "INSERT INTO amenaza (novela_id, tema_id, naturaleza, reglas) VALUES (?,?,?,?)",
        (nid, tema_id, "Presencia que imita conducta", '[{"capacidad":"imita"}]'),
    ))

    for nombre in ("Puente", "Modulo de carga", "Esclusa"):
        g.lugares[nombre] = _id(con.execute(
            "INSERT INTO lugar (novela_id, mundo_id, nombre, descripcion) VALUES (?,?,?,?)",
            (nid, mundo_id, nombre, f"{nombre} de la estacion."),
        ))

    for nombre, rol in (("Kowalski", "protagonista"), ("Ibarra", "oponente"), ("Reyes", "aliado")):
        g.personajes[nombre] = _id(con.execute(
            "INSERT INTO personaje (novela_id, nombre, rol_narrativo, tipo_arco) VALUES (?,?,?,?)",
            (nid, nombre, rol, "positivo"),
        ))

    g.objetos["Baliza"] = _id(con.execute(
        "INSERT INTO objeto (novela_id, nombre, funcion_narrativa) VALUES (?,?,?)",
        (nid, "Baliza", "Prueba de que alguien estuvo antes"),
    ))

    acto_id = _id(con.execute(
        "INSERT INTO acto (novela_id, numero, funcion_narrativa) VALUES (?,1,'Planteamiento')",
        (nid,),
    ))

    orden_global = 0
    for numero in (1, 2):
        cap_id = _id(con.execute(
            "INSERT INTO capitulo (novela_id, acto_id, numero, objetivo, pov_id, estado) "
            "VALUES (?,?,?,?,?, 'planificado')",
            (nid, acto_id, numero, f"Objetivo del capitulo {numero}", g.personajes["Kowalski"]),
        ))
        g.capitulos[numero] = cap_id
        for orden in (1, 2):
            orden_global += 1
            lugar = "Puente" if orden == 1 else "Modulo de carga"
            esc_id = _id(con.execute(
                """
                INSERT INTO escena (novela_id, capitulo_id, pov_id, lugar_id, orden, objetivo,
                                    conflicto, resultado, valor_inicial, valor_final, tension)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """,
                (nid, cap_id, g.personajes["Kowalski"], g.lugares[lugar], orden,
                 "Llegar al modulo", "La escotilla no responde", "Entra con coste",
                 "seguro", "expuesto", 5),
            ))
            g.escenas[(numero, orden)] = esc_id
            for quien in ("Kowalski", "Ibarra"):
                con.execute(
                    "INSERT INTO escena_personaje (escena_id, personaje_id) VALUES (?,?)",
                    (esc_id, g.personajes[quien]),
                )
            con.execute(
                "INSERT INTO evento (novela_id, linea_de_tiempo_id, escena_id, fecha_interna,"
                " orden_interno, descripcion, dramatizado) VALUES (?,?,?,?,?,?,1)",
                (nid, g.linea_id, esc_id, f"dia {orden_global}", orden_global,
                 f"Sucesos de la escena {numero}.{orden}"),
            )

    # Un hecho establecido en el capitulo 1, con quien lo sabe y quien lo usa despues.
    esc11 = g.escenas[(1, 1)]
    esc21 = g.escenas[(2, 1)]
    g.hechos["ojos"] = _id(con.execute(
        """
        INSERT INTO hecho (novela_id, escena_id, sujeto_tipo, sujeto_id, sujeto_nombre,
                           atributo, valor, categoria, cita)
        VALUES (?,?,'personaje',?,?,'color de ojos','grises','fisico','tenia los ojos grises')
        """,
        (nid, esc11, g.personajes["Ibarra"], "Ibarra"),
    ))
    con.execute(
        "INSERT INTO estado_conocimiento (novela_id, personaje_id, hecho_id, escena_id, postura,"
        " via) VALUES (?,?,?,?, 'sabe','presencio')",
        (nid, g.personajes["Kowalski"], g.hechos["ojos"], esc11),
    )
    con.execute(
        "INSERT INTO uso_conocimiento (novela_id, personaje_id, hecho_id, escena_id) "
        "VALUES (?,?,?,?)",
        (nid, g.personajes["Kowalski"], g.hechos["ojos"], esc21),
    )

    # El objeto empieza en el modulo de carga y no se mueve.
    con.execute(
        "INSERT INTO estado_objeto (novela_id, objeto_id, escena_id, ubicacion_lugar_id) "
        "VALUES (?,?,?,?)",
        (nid, g.objetos["Baliza"], g.escenas[(1, 2)], g.lugares["Modulo de carga"]),
    )
    con.execute(
        "INSERT INTO escena_objeto (escena_id, objeto_id) VALUES (?,?)",
        (g.escenas[(1, 2)], g.objetos["Baliza"]),
    )
    con.execute(
        "INSERT INTO escena_objeto (escena_id, objeto_id) VALUES (?,?)",
        (g.escenas[(2, 2)], g.objetos["Baliza"]),
    )
    con.execute(
        "INSERT INTO estado_objeto (novela_id, objeto_id, escena_id, ubicacion_lugar_id) "
        "VALUES (?,?,?,?)",
        (nid, g.objetos["Baliza"], g.escenas[(2, 2)], g.lugares["Modulo de carga"]),
    )
    return g
