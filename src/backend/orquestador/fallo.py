"""Politica de fallo: paradas, reversion y resolucion (RF-FALLO-01, RF2-FALLO-03).

Dos ideas sostienen este modulo.

**La friccion es informacion.** Una parada no es un fallo del sistema, es el sistema haciendo
su trabajo. Nunca se acumula deuda narrativa silenciosa: ante un conflicto de continuidad se
detiene la generacion y se espera a un humano.

**El estado es la unidad de reanudacion, no el texto.** Relanzar desde el capitulo N es
restaurar el grafo a como estaba al terminar N-1. Eso es posible porque todo el estado es
append-only y lleva su escena de origen: revertir es borrar por escena, no deshacer pasos.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from compartido.db import TABLAS_DE_ESTADO
from compartido.grafo import emitir_evento, insertar
from compartido.tipos import como_dict, como_lista
from compartido.vectores import purgar_descartes

from . import estados


def abrir_parada(
    con: sqlite3.Connection,
    novela_id: int,
    tipo: str,
    informe: dict[str, Any],
    *,
    capitulo: int | None = None,
    intento: int | None = None,
) -> int:
    """Crea la parada y la deja abierta. El informe se lee sin abrir la base de datos."""
    ejecucion = con.execute(
        "SELECT id FROM ejecucion WHERE novela_id = ?", (novela_id,)
    ).fetchone()
    parada_id = insertar(
        con, "parada", ejecucion_id=int(ejecucion["id"]), tipo=tipo, capitulo=capitulo,
        intento=intento, informe=json.dumps(informe, ensure_ascii=False, default=str),
        estado="abierta",
    )
    emitir_evento(
        con, novela_id, "parada", parada_id=parada_id, tipo=tipo, capitulo=capitulo,
        intento=intento,
    )
    return parada_id


def cerrar_parada(
    con: sqlite3.Connection, novela_id: int, parada_id: int, resolucion: str
) -> None:
    con.execute(
        "UPDATE parada SET estado = 'resuelta', resolucion = ?, resuelto_en = datetime('now') "
        "WHERE id = ?",
        (resolucion, parada_id),
    )
    emitir_evento(con, novela_id, "parada_resuelta", parada_id=parada_id, resolucion=resolucion)


def paradas_abiertas(con: sqlite3.Connection, novela_id: int) -> list[dict[str, Any]]:
    return [
        dict(f) for f in con.execute(
            """
            SELECT p.* FROM parada p
            JOIN ejecucion e ON e.id = p.ejecucion_id
            WHERE e.novela_id = ? AND p.estado = 'abierta' ORDER BY p.id
            """,
            (novela_id,),
        )
    ]


def hechos_a_revocar(con: sqlite3.Connection, parada_id: int) -> set[int]:
    """Los hechos establecidos con los que chocan los conflictos de una parada.

    Si no hay ninguno, `aceptar_retcon` no tiene nada que revocar y el mismo conflicto se
    repetiria al regenerar: por eso el worker la rechaza (RF2-FALLO-03).
    """
    fila = con.execute("SELECT informe FROM parada WHERE id = ?", (parada_id,)).fetchone()
    if fila is None:
        return set()
    try:
        informe = como_dict(json.loads(fila["informe"] or "{}"))
    except json.JSONDecodeError:
        return set()
    ids: set[int] = set()
    for conflicto in como_lista(informe.get("conflictos")):
        previo = como_dict(como_dict(conflicto).get("datos")).get("hecho_previo_id")
        if previo:
            ids.add(int(previo))
    return ids


def aceptar_retcon(con: sqlite3.Connection, novela_id: int, parada_id: int) -> int:
    """Revoca a mano los hechos que el conflicto senala, con rastro (RF-FALLO-03).

    La regla dice que un hecho establecido no se borra por una pasada de prosa. Aqui no lo
    borra una pasada: lo retira una persona, a conciencia, y queda registrado quien y por que.
    El capitulo se regenera entero; la prosa rechazada no se reutiliza.
    """
    ids = hechos_a_revocar(con, parada_id)
    if not ids:
        return 0
    capitulo = con.execute("SELECT capitulo FROM parada WHERE id = ?", (parada_id,)).fetchone()

    # Revocar es INSERTAR, nunca un UPDATE sobre el hecho (RF2-PER-06): el hecho sigue ahi,
    # con su escena y su cita, y la revocacion dice quien lo retiro, cuando y por que.
    for hecho_id in sorted(ids):
        con.execute(
            "INSERT OR IGNORE INTO hecho_revocacion (novela_id, hecho_id, parada_id, capitulo, "
            "motivo) SELECT novela_id, id, ?, ?, 'retcon' FROM hecho WHERE id = ?",
            (parada_id, int(capitulo["capitulo"]), hecho_id),
        )

    linea = con.execute(
        "SELECT id FROM linea_de_tiempo WHERE novela_id = ?", (novela_id,)
    ).fetchone()
    if linea is not None:
        insertar(
            con, "evento", novela_id=novela_id, linea_de_tiempo_id=int(linea["id"]),
            fecha_interna="(retcon)", descripcion=(
                f"El autor revoco {len(ids)} hecho(s) al resolver la parada {parada_id}."
            ),
            tipo="retcon", dramatizado=False,
        )
    return len(ids)


def revertir_grafo(
    con: sqlite3.Connection, novela_id: int, desde_capitulo: int, *, motivo: str = "relanzar"
) -> dict[str, int]:
    """Deja el grafo como estaba al terminar el capitulo N-1 (RF-FALLO-04, RF2-PIPE-08).

    Solo toca el grafo: estado, texto y el estado de los capitulos. No mueve la ejecucion ni
    cierra paradas, que es lo que distingue esta operacion de `relanzar`. La usan el reintento
    de oficio, la salida anomala del bucle de capitulo y la recuperacion del worker caido.

    No toca el canon ni la escaleta: relanzar regenera prosa, no plan.
    """
    borrado: dict[str, int] = {}

    escenas = [
        int(f["id"]) for f in con.execute(
            """
            SELECT e.id FROM escena e JOIN capitulo c ON c.id = e.capitulo_id
            WHERE e.novela_id = ? AND c.numero >= ?
            """,
            (novela_id, desde_capitulo),
        )
    ]

    if escenas:
        huecos = ",".join("?" * len(escenas))
        # El conocimiento cuelga de hechos que estan a punto de desaparecer, asi que va antes.
        for tabla in ("estado_conocimiento", "uso_conocimiento"):
            cur = con.execute(
                f"DELETE FROM {tabla} WHERE escena_id IN ({huecos}) OR hecho_id IN "
                f"(SELECT id FROM hecho WHERE escena_id IN ({huecos}))",
                [*escenas, *escenas],
            )
            borrado[tabla] = cur.rowcount
        for tabla in TABLAS_DE_ESTADO:
            if tabla in ("estado_conocimiento", "uso_conocimiento"):
                continue
            cur = con.execute(f"DELETE FROM {tabla} WHERE escena_id IN ({huecos})", escenas)
            borrado[tabla] = cur.rowcount
        cur = con.execute(
            f"DELETE FROM evento WHERE escena_id IN ({huecos})", escenas
        )
        borrado["evento"] = cur.rowcount

        # Las siembras que planifico el estructurador se conservan; las que nacieron de la
        # extraccion de estos capitulos, no.
        cur = con.execute(
            f"DELETE FROM siembra WHERE novela_id = ? AND origen = 'extraccion' "
            f"AND sembrada_en_escena_id IN ({huecos})",
            [novela_id, *escenas],
        )
        borrado["siembra"] = cur.rowcount
        con.execute(
            f"UPDATE siembra SET sembrada_en_escena_id = NULL WHERE sembrada_en_escena_id IN "
            f"({huecos})",
            escenas,
        )

        # El texto no se borra: se descarta. Es historia legible en /versiones.
        cur = con.execute(
            f"UPDATE escena_texto SET estado = 'descartada' WHERE escena_id IN ({huecos}) "
            f"AND estado = 'vigente'",
            escenas,
        )
        borrado["escena_texto_descartada"] = cur.rowcount

    con.execute(
        """
        UPDATE capitulo_compilado SET estado = 'descartada'
         WHERE capitulo_id IN (SELECT id FROM capitulo WHERE novela_id = ? AND numero >= ?)
           AND estado = 'vigente'
        """,
        (novela_id, desde_capitulo),
    )
    con.execute(
        "UPDATE capitulo SET estado = 'planificado', resumen = NULL, resumen_breve = NULL "
        "WHERE novela_id = ? AND numero >= ?",
        (novela_id, desde_capitulo),
    )
    # Las revocaciones decididas despues de N se deshacen con el resto. La del retcon que se
    # acepta en N se conserva: es el punto de partida de la regeneracion de N (RF2-PER-06).
    cur = con.execute(
        "DELETE FROM hecho_revocacion WHERE novela_id = ? AND capitulo > ?",
        (novela_id, desde_capitulo),
    )
    borrado["hecho_revocacion"] = cur.rowcount
    # Lo que acaba de dejar de ser vigente sale tambien del indice, en esta misma transaccion
    # (RF2-FALLO-04b). Si no se puede, queda en la traza.
    error = purgar_descartes(con)
    if error:
        emitir_evento(con, novela_id, "indice_fallo", operacion="purgar", error=error)
    emitir_evento(
        con, novela_id, "revertido", desde_capitulo=desde_capitulo, motivo=motivo,
        borrado=borrado,
    )
    return borrado


def estado_y_parada(con: sqlite3.Connection, novela_id: int) -> tuple[str, str | None]:
    """Estado de la ejecucion y, si esta en parada, el tipo de la parada abierta."""
    estado = str(con.execute(
        "SELECT estado FROM ejecucion WHERE novela_id = ?", (novela_id,)
    ).fetchone()["estado"])
    abiertas = paradas_abiertas(con, novela_id)
    return estado, (str(abiertas[-1]["tipo"]) if abiertas else None)


def relanzar(
    con: sqlite3.Connection, novela_id: int, desde_capitulo: int, *, suceso: str = "relanzar"
) -> dict[str, int]:
    """Revierte el grafo y deja la ejecucion lista para regenerar desde N (RF-FALLO-04).

    Es lo que hacen `relanzar` y `resolver_parada` con `relanzar` o `aceptar_retcon`: ademas
    de `revertir_grafo`, cierra las paradas abiertas y mueve el estado. La transicion se
    valida ANTES de tocar nada: sobre una parada de estructura, por ejemplo, lanza
    `TransicionInvalida` y el grafo queda intacto (RF2-FALLO-03). Corre dentro de la
    transaccion del llamante.
    """
    estado_actual, tipo = estado_y_parada(con, novela_id)
    destino = estados.siguiente(estado_actual, suceso, tipo_parada=tipo)

    borrado = revertir_grafo(con, novela_id, desde_capitulo, motivo=suceso)

    resolucion = "aceptar_retcon" if suceso == "aceptar_retcon" else "relanzado"
    for parada in paradas_abiertas(con, novela_id):
        cerrar_parada(con, novela_id, int(parada["id"]), resolucion)

    # Revertir el grafo y dejar el estado diciendo «completada» seria mentir: el manuscrito
    # que justificaba ese estado acaba de descartarse. La ejecucion vuelve a generando, que es
    # justo lo que significa `relanzar`.
    con.execute(
        """
        UPDATE ejecucion SET estado = ?, fase = 'paquete', capitulo_actual = ?,
               intento_actual = 1, capitulos_completados = ?, parada_abierta_id = NULL,
               ultimo_error = NULL, actualizado_en = datetime('now')
         WHERE novela_id = ?
        """,
        (destino, desde_capitulo, desde_capitulo - 1, novela_id),
    )
    return borrado


# --- Rehacer una fase de planificacion (RF2-FALLO-03) ---------------------------------------


def borrar_escaleta(con: sqlite3.Connection, novela_id: int) -> None:
    """Capitulos y secuencias; escenas, beats, secuelas y reparto caen en cascada."""
    con.execute("DELETE FROM capitulo WHERE novela_id = ?", (novela_id,))
    con.execute("DELETE FROM secuencia WHERE novela_id = ?", (novela_id,))


def _rehacer(con: sqlite3.Connection, novela_id: int, parada_id: int) -> str:
    estado_actual, tipo = estado_y_parada(con, novela_id)
    destino = estados.siguiente(estado_actual, "rehacer", tipo_parada=tipo)
    cerrar_parada(con, novela_id, parada_id, "rehacer")
    con.execute(
        """
        UPDATE ejecucion SET estado = ?, fase = NULL, capitulo_actual = NULL,
               intento_actual = 1, parada_abierta_id = NULL, ultimo_error = NULL,
               actualizado_en = datetime('now')
         WHERE novela_id = ?
        """,
        (destino, novela_id),
    )
    emitir_evento(con, novela_id, "rehecho", parada_id=parada_id, tipo=tipo, destino=destino)
    return destino


def rehacer_estructura(con: sqlite3.Connection, novela_id: int, parada_id: int) -> str:
    """Borra lo que rechazo la puerta 1 y deja la ejecucion en `planificando`.

    El estructurador vuelve a correr con el informe de la puerta 1 en su paquete; mundo,
    elenco y premisa se conservan. Corre dentro de la transaccion del llamante.
    """
    _, tipo = estado_y_parada(con, novela_id)
    if tipo != "estructura":
        estados.siguiente("parada", "rehacer", tipo_parada=tipo)  # lanza con el motivo
    # La escaleta cuelga de los actos: si la hubiera, caeria con ellos.
    borrar_escaleta(con, novela_id)
    con.execute("DELETE FROM acto WHERE novela_id = ?", (novela_id,))
    con.execute("DELETE FROM hilo WHERE novela_id = ?", (novela_id,))
    con.execute(
        "DELETE FROM siembra WHERE novela_id = ? AND origen = 'estructura'", (novela_id,)
    )
    con.execute("DELETE FROM objeto WHERE novela_id = ?", (novela_id,))
    return _rehacer(con, novela_id, parada_id)


def rehacer_escaleta(con: sqlite3.Connection, novela_id: int, parada_id: int) -> str:
    """Borra la escaleta rechazada, si queda algo, y deja la ejecucion en `escaletando`."""
    _, tipo = estado_y_parada(con, novela_id)
    if tipo != "escaleta":
        estados.siguiente("parada", "rehacer", tipo_parada=tipo)
    borrar_escaleta(con, novela_id)
    return _rehacer(con, novela_id, parada_id)
