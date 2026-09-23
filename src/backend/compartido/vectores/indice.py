"""Indice vectorial sobre texto de escena y hechos (RF2-CTX-07 a RF2-CTX-10, RF-PER-10).

La linea que no se cruza: el indice sirve para RECUPERAR, nunca para VERIFICAR. Decidir si
hay una contradiccion de continuidad es una consulta sobre hecho y estado_conocimiento, con
respuesta exacta. La similitud semantica da respuestas aproximadas, y una puerta que a veces
falla no es una puerta.

De ahi que todo aqui sea prescindible: si sqlite-vec no carga o el modelo no esta, el bloque
recuperado queda vacio y el pipeline sigue igual. Pero prescindible no es silencioso: todo
fallo se lanza como `IndiceNoDisponible` y el orquestador lo lleva a la traza (RF2-CTX-09).
"""

from __future__ import annotations

import sqlite3
import struct
from dataclasses import dataclass
from typing import Any

from ..db import transaccion
from .embebido import Embedder, construir


def _a_blob(vector: list[float]) -> bytes:
    return struct.pack(f"{len(vector)}f", *vector)


class IndiceNoDisponible(Exception):
    """El indice no puede usarse: la extension no carga, el modelo no carga o fallo algo."""


@dataclass(frozen=True)
class Fragmento:
    """Un trozo de prosa ya escrita que el redactor deberia tener delante."""

    escena_id: int
    capitulo: int
    orden: int
    lugar: str
    texto: str
    distancia: float


def _tablas_existen(con: sqlite3.Connection) -> bool:
    return con.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'vec_escena'"
    ).fetchone() is not None


def purgar_descartes(con: sqlite3.Connection) -> str | None:
    """Saca del indice todo lo que ya no es vigente (RF2-FALLO-04b). Devuelve el error o None.

    La llama cualquier reversion del grafo, dentro de su transaccion: las versiones de texto
    descartadas y los hechos borrados o revocados no pueden seguir recuperandose. Si las
    tablas vec0 existen pero la extension no esta cargada en esta conexion, no puede borrar y
    lo devuelve para que quede en la traza.
    """
    if not _tablas_existen(con):
        return None
    try:
        con.execute(
            "DELETE FROM vec_escena WHERE escena_texto_id NOT IN "
            "(SELECT id FROM escena_texto WHERE estado = 'vigente')"
        )
        con.execute(
            "DELETE FROM vec_hecho WHERE hecho_id NOT IN (SELECT id FROM hecho_vigente)"
        )
    except sqlite3.OperationalError as exc:
        return str(exc)
    return None


class Indice:
    """Envuelve las tablas vec0 y el modelo de embeddings."""

    def __init__(
        self,
        con: sqlite3.Connection,
        *,
        modelo: str = "fastembed",
        activo: bool = True,
        embedder: Embedder | None = None,
    ) -> None:
        self.con = con
        self.disponible = False
        self.embedder: Embedder | None = None
        #: Por que el indice no esta disponible, si es por un fallo y no por configuracion.
        self.fallo: str | None = None
        self._modelo = modelo
        self._inyectado = embedder
        self._intentado = False
        if not activo:
            self._registrar_disponible()
            return
        # Solo se comprueba que la extension cargue, que es instantaneo. El MODELO se carga
        # la primera vez que hace falta: pesa cientos de megas y se descarga la primera vez,
        # y un worker no puede pasarse medio minuto bajandolo antes de aceptar una intencion
        # que quiza ni use el indice.
        try:
            self._cargar_extension()
            self.disponible = True
        except Exception as exc:  # se guarda el motivo y se avisa al usarlo
            self.fallo = f"sqlite-vec no carga: {exc}"
        self._registrar_disponible()

    # -- montaje ---------------------------------------------------------------------------

    def _cargar_extension(self) -> None:
        import sqlite_vec  # type: ignore[import-not-found]

        self.con.enable_load_extension(True)
        try:
            sqlite_vec.load(self.con)
        finally:
            self.con.enable_load_extension(False)

    def _escribir(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        """Toda escritura del indice pasa por una transaccion inmediata, y por tanto por el
        fencing del worker (RF2-WK-08). Si ya hay una abierta, se escribe en ella."""
        if self.con.in_transaction:
            self.con.execute(sql, params)
        else:
            with transaccion(self.con):
                self.con.execute(sql, params)

    def _registrar_disponible(self) -> None:
        # Solo el indicador: el modelo y la dimension se escriben al CONSTRUIR las tablas, y
        # un proceso que arranca no puede borrar el registro de con que se construyeron.
        self._escribir(
            "INSERT INTO indice_estado (id, disponible) VALUES (1, ?) "
            "ON CONFLICT(id) DO UPDATE SET disponible = excluded.disponible",
            (1 if self.disponible else 0,),
        )

    def _asegurar_embedder(self) -> Embedder:
        """Carga el modelo y alinea las tablas con el la primera vez que se usan de verdad."""
        if self.embedder is not None:
            return self.embedder
        if not self.disponible or self._intentado:
            raise IndiceNoDisponible(self.fallo or "El indice esta desactivado.")
        self._intentado = True
        try:
            self.embedder = self._inyectado or construir(self._modelo)
            self._alinear_tablas(self.embedder)
        except Exception as exc:
            self.embedder = None
            self.disponible = False
            self.fallo = f"{type(exc).__name__}: {exc}"
            self._registrar_disponible()
            raise IndiceNoDisponible(self.fallo) from exc
        return self.embedder

    def _alinear_tablas(self, embedder: Embedder) -> None:
        """Si las tablas se construyeron con otro modelo o dimension, se rehacen (RF2-CTX-10).

        Mezclar vectores de dos modelos en una tabla no da error: da distancias sin sentido.
        Por eso el registro guarda con que modelo se construyo, y cualquier diferencia obliga
        a borrar y reindexar todo lo escrito antes de usar el indice.
        """
        estado = self.con.execute(
            "SELECT modelo, dimension FROM indice_estado WHERE id = 1"
        ).fetchone()
        existen = _tablas_existen(self.con)
        construido = (estado["modelo"], estado["dimension"]) if estado else (None, None)
        if existen and construido == (embedder.nombre, embedder.dimension):
            return
        self._escribir("DROP TABLE IF EXISTS vec_escena")
        self._escribir("DROP TABLE IF EXISTS vec_hecho")
        self._escribir(
            f"CREATE VIRTUAL TABLE vec_escena USING vec0("
            f"escena_texto_id INTEGER PRIMARY KEY, embedding float[{embedder.dimension}])"
        )
        self._escribir(
            f"CREATE VIRTUAL TABLE vec_hecho USING vec0("
            f"hecho_id INTEGER PRIMARY KEY, embedding float[{embedder.dimension}])"
        )
        self._escribir(
            "INSERT INTO indice_estado (id, modelo, dimension, disponible, reconstruido_en) "
            "VALUES (1, ?, ?, 1, datetime('now')) ON CONFLICT(id) DO UPDATE SET "
            "modelo = excluded.modelo, dimension = excluded.dimension, disponible = 1, "
            "reconstruido_en = excluded.reconstruido_en",
            (embedder.nombre, embedder.dimension),
        )
        for f in self.con.execute(
            "SELECT novela_id, numero FROM capitulo WHERE estado = 'completado' "
            "ORDER BY novela_id, numero"
        ).fetchall():
            self.indexar_capitulo(int(f["novela_id"]), int(f["numero"]))

    # -- indexado --------------------------------------------------------------------------

    def indexar_capitulo(self, novela_id: int, capitulo: int) -> int:
        """Vectoriza las escenas y los hechos del capitulo. Se llama TRAS confirmarlo."""
        embedder = self._asegurar_embedder()

        filas = [dict(f) for f in self.con.execute(
            """
            SELECT et.id, et.texto
            FROM escena_texto et
            JOIN escena e   ON e.id = et.escena_id
            JOIN capitulo c ON c.id = e.capitulo_id
            WHERE et.novela_id = ? AND c.numero = ? AND et.estado = 'vigente'
              AND et.id NOT IN (SELECT escena_texto_id FROM vec_escena)
            """,
            (novela_id, capitulo),
        )]
        hechos = [dict(f) for f in self.con.execute(
            """
            SELECT h.id, h.sujeto_nombre || ' ' || h.atributo || ': ' || h.valor AS texto
            FROM hecho_vigente h
            JOIN escena e   ON e.id = h.escena_id
            JOIN capitulo c ON c.id = e.capitulo_id
            WHERE h.novela_id = ? AND c.numero = ?
              AND h.id NOT IN (SELECT hecho_id FROM vec_hecho)
            """,
            (novela_id, capitulo),
        )]

        n = 0
        for tabla, columna, lote in (
            ("vec_escena", "escena_texto_id", filas), ("vec_hecho", "hecho_id", hechos),
        ):
            if not lote:
                continue
            vectores = embedder.codificar([f["texto"] for f in lote])
            for fila, vector in zip(lote, vectores, strict=True):
                self._escribir(
                    f"INSERT OR REPLACE INTO {tabla} ({columna}, embedding) VALUES (?,?)",
                    (fila["id"], _a_blob(vector)),
                )
                n += 1
        return n

    def purgar(self, novela_id: int, desde_capitulo: int) -> None:
        """Quita del indice lo que una reversion ha descartado (RF2-FALLO-04b)."""
        del novela_id, desde_capitulo  # la purga es por vigencia, no por capitulo
        error = purgar_descartes(self.con)
        if error:
            raise IndiceNoDisponible(error)

    def reconstruir(self, novela_id: int) -> int:
        """Borra y rehace el indice de una novela."""
        self._asegurar_embedder()
        self._escribir(
            "DELETE FROM vec_escena WHERE escena_texto_id IN "
            "(SELECT id FROM escena_texto WHERE novela_id = ?)", (novela_id,),
        )
        self._escribir(
            "DELETE FROM vec_hecho WHERE hecho_id IN (SELECT id FROM hecho WHERE novela_id = ?)",
            (novela_id,),
        )
        total = 0
        for f in self.con.execute(
            "SELECT numero FROM capitulo WHERE novela_id = ? AND estado = 'completado' "
            "ORDER BY numero", (novela_id,)
        ).fetchall():
            total += self.indexar_capitulo(novela_id, int(f["numero"]))
        return total

    # -- recuperacion ----------------------------------------------------------------------

    def recuperar(
        self,
        novela_id: int,
        consulta: str,
        *,
        hasta_capitulo: int,
        lugares: list[int] | None = None,
        objetos: list[int] | None = None,
        limite: int = 3,
    ) -> list[Fragmento]:
        """Prosa ya escrita afin a la consulta, de capitulos ANTERIORES.

        Primero el filtro determinista decide quien es candidato (capitulo anterior, texto
        vigente, mismo lugar u objeto); despues la distancia se calcula SOLO sobre esos
        candidatos (RF2-CTX-07). Un KNN sobre todo el indice filtrado despues dejaba fuera a
        los candidatos admitidos en cuanto la novela tenia bastantes escenas parecidas en
        otros sitios.
        """
        if not consulta.strip():
            return []
        embedder = self._asegurar_embedder()

        condiciones = ["et.novela_id = ?", "c.numero < ?", "et.estado = 'vigente'"]
        params: list[Any] = [novela_id, hasta_capitulo]
        if lugares or objetos:
            alternativas: list[str] = []
            if lugares:
                alternativas.append(f"e.lugar_id IN ({','.join('?' * len(lugares))})")
                params.extend(lugares)
            if objetos:
                alternativas.append(
                    "EXISTS (SELECT 1 FROM escena_objeto eo WHERE eo.escena_id = e.id "
                    f"AND eo.objeto_id IN ({','.join('?' * len(objetos))}))"
                )
                params.extend(objetos)
            condiciones.append("(" + " OR ".join(alternativas) + ")")

        candidatos = {
            int(f["texto_id"]): dict(f) for f in self.con.execute(
                f"""
                SELECT et.id AS texto_id, et.texto, e.id AS escena_id, e.orden,
                       c.numero AS capitulo, l.nombre AS lugar
                FROM escena_texto et
                JOIN escena e   ON e.id = et.escena_id
                JOIN capitulo c ON c.id = e.capitulo_id
                JOIN lugar l    ON l.id = e.lugar_id
                WHERE {' AND '.join(condiciones)}
                """,
                params,
            )
        }
        if not candidatos:
            return []

        vector = _a_blob(embedder.codificar([consulta], tipo="consulta")[0])
        ids = sorted(candidatos)
        cercanos = self.con.execute(
            f"""
            SELECT escena_texto_id, vec_distance_l2(embedding, ?) AS distancia
            FROM vec_escena
            WHERE escena_texto_id IN ({','.join('?' * len(ids))})
            ORDER BY distancia, escena_texto_id
            LIMIT ?
            """,
            [vector, *ids, limite],
        ).fetchall()

        return [
            Fragmento(
                escena_id=int(c["escena_id"]), capitulo=int(c["capitulo"]),
                orden=int(c["orden"]), lugar=str(c["lugar"]), texto=str(c["texto"]),
                distancia=float(fila["distancia"]),
            )
            for fila in cercanos
            for c in (candidatos[int(fila["escena_texto_id"])],)
        ]
