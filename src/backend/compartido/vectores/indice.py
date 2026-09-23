"""Indice vectorial sobre texto de escena y hechos (RF-CTX-07 a RF-CTX-10, RF-PER-10).

La linea que no se cruza: el indice sirve para RECUPERAR, nunca para VERIFICAR. Decidir si
hay una contradiccion de continuidad es una consulta sobre hecho y estado_conocimiento, con
respuesta exacta. La similitud semantica da respuestas aproximadas, y una puerta que a veces
falla no es una puerta.

De ahi que todo aqui sea opcional: si sqlite-vec no carga o el modelo no esta, el bloque
recuperado queda vacio y el pipeline sigue igual.
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


@dataclass(frozen=True)
class Fragmento:
    """Un trozo de prosa ya escrita que el redactor deberia tener delante."""

    escena_id: int
    capitulo: int
    orden: int
    lugar: str
    texto: str
    distancia: float


class Indice:
    """Envuelve las tablas vec0. Si no hay extension, todo es un no-op silencioso."""

    def __init__(
        self, con: sqlite3.Connection, *, modelo: str = "fastembed", activo: bool = True
    ) -> None:
        self.con = con
        self.disponible = False
        self.embedder: Embedder | None = None
        self._modelo = modelo
        self._intentado = False
        if not activo:
            self._registrar_estado()
            return
        # Solo se comprueba que la extension cargue, que es instantaneo. El MODELO se carga
        # la primera vez que hace falta: pesa cientos de megas y se descarga la primera vez,
        # y un worker no puede pasarse medio minuto bajandolo antes de aceptar una intencion
        # que quiza ni use el indice.
        self.disponible = self._cargar_extension()
        self._registrar_estado()

    def _asegurar_embedder(self) -> bool:
        """Carga el modelo y crea las tablas vec0 la primera vez que se usan de verdad."""
        if self.embedder is not None:
            return True
        if not self.disponible or self._intentado:
            return False
        self._intentado = True
        try:
            self.embedder = construir(self._modelo)
            self._crear_tablas(self.embedder.dimension)
        except Exception:  # noqa: BLE001 - el indice es prescindible por diseno
            self.embedder = None
            self.disponible = False
        self._registrar_estado()
        return self.embedder is not None

    # -- montaje ---------------------------------------------------------------------------

    def _cargar_extension(self) -> bool:
        try:
            import sqlite_vec  # type: ignore[import-not-found]

            self.con.enable_load_extension(True)
            sqlite_vec.load(self.con)
            self.con.enable_load_extension(False)
            return True
        except Exception:  # noqa: BLE001
            return False

    def _escribir(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        """Toda escritura del indice pasa por una transaccion inmediata, y por tanto por el
        fencing del worker (RF2-WK-08). Si ya hay una abierta, se escribe en ella."""
        if self.con.in_transaction:
            self.con.execute(sql, params)
        else:
            with transaccion(self.con):
                self.con.execute(sql, params)

    def _crear_tablas(self, dim: int) -> None:
        self._escribir(
            f"CREATE VIRTUAL TABLE IF NOT EXISTS vec_escena USING vec0("
            f"escena_texto_id INTEGER PRIMARY KEY, embedding float[{dim}])"
        )
        self._escribir(
            f"CREATE VIRTUAL TABLE IF NOT EXISTS vec_hecho USING vec0("
            f"hecho_id INTEGER PRIMARY KEY, embedding float[{dim}])"
        )

    def _registrar_estado(self) -> None:
        self._escribir(
            """
            INSERT INTO indice_estado (id, modelo, dimension, disponible, reconstruido_en)
            VALUES (1, ?, ?, ?, datetime('now'))
            ON CONFLICT(id) DO UPDATE SET modelo = excluded.modelo,
                dimension = excluded.dimension, disponible = excluded.disponible
            """,
            (
                getattr(self.embedder, "nombre", None),
                getattr(self.embedder, "dimension", None),
                1 if self.disponible else 0,
            ),
        )

    # -- indexado --------------------------------------------------------------------------

    def indexar_capitulo(self, novela_id: int, capitulo: int) -> int:
        """Vectoriza las escenas y los hechos del capitulo. Se llama TRAS confirmarlo."""
        if not self._asegurar_embedder() or self.embedder is None:
            return 0

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
        if filas:
            for fila, vector in zip(filas, self.embedder.codificar([f["texto"] for f in filas]),
                                    strict=True):
                self.con.execute(
                    "INSERT OR REPLACE INTO vec_escena (escena_texto_id, embedding) VALUES (?,?)",
                    (fila["id"], _a_blob(vector)),
                )
                n += 1
        if hechos:
            for fila, vector in zip(hechos, self.embedder.codificar([f["texto"] for f in hechos]),
                                    strict=True):
                self.con.execute(
                    "INSERT OR REPLACE INTO vec_hecho (hecho_id, embedding) VALUES (?,?)",
                    (fila["id"], _a_blob(vector)),
                )
                n += 1
        return n

    def purgar(self, novela_id: int, desde_capitulo: int) -> None:
        """Quita del indice lo que una reversion ha descartado (RF-CTX-10, RF-FALLO-04)."""
        if not self.disponible or self.embedder is None:
            return  # si nunca se cargo el modelo, no hay tablas que purgar
        self.con.execute(
            """
            DELETE FROM vec_escena WHERE escena_texto_id IN (
                SELECT et.id FROM escena_texto et
                JOIN escena e ON e.id = et.escena_id
                JOIN capitulo c ON c.id = e.capitulo_id
                WHERE et.novela_id = ? AND (c.numero >= ? OR et.estado = 'descartada'))
            """,
            (novela_id, desde_capitulo),
        )
        self.con.execute(
            "DELETE FROM vec_hecho WHERE hecho_id NOT IN (SELECT id FROM hecho_vigente)"
        )

    def reconstruir(self, novela_id: int) -> int:
        """Borra y rehace el indice entero. Necesario al cambiar de modelo."""
        if not self._asegurar_embedder():
            return 0
        self.con.execute("DELETE FROM vec_escena")
        self.con.execute("DELETE FROM vec_hecho")
        total = 0
        for f in self.con.execute(
            "SELECT numero FROM capitulo WHERE novela_id = ? AND estado = 'completado' "
            "ORDER BY numero", (novela_id,)
        ).fetchall():
            total += self.indexar_capitulo(novela_id, int(f["numero"]))
        self._registrar_estado()
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

        El filtro por lugar u objeto va ANTES que la similitud: el indice ordena candidatos
        que el filtro determinista ya admitio, nunca decide por su cuenta quien entra
        (RF-CTX-08).
        """
        if not consulta.strip() or not self._asegurar_embedder() or self.embedder is None:
            return []

        condiciones = ["et.novela_id = ?", "c.numero < ?", "et.estado = 'vigente'"]
        params: list[Any] = [novela_id, hasta_capitulo]
        if lugares or objetos:
            alternativas: list[str] = []
            if lugares:
                alternativas.append(
                    f"e.lugar_id IN ({','.join('?' * len(lugares))})"
                )
                params.extend(lugares)
            if objetos:
                alternativas.append(
                    "EXISTS (SELECT 1 FROM escena_objeto eo WHERE eo.escena_id = e.id "
                    f"AND eo.objeto_id IN ({','.join('?' * len(objetos))}))"
                )
                params.extend(objetos)
            condiciones.append("(" + " OR ".join(alternativas) + ")")

        candidatos = [dict(f) for f in self.con.execute(
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
        )]
        if not candidatos:
            return []

        permitidos = {c["texto_id"] for c in candidatos}
        vector = self.embedder.codificar([consulta], tipo="consulta")[0]
        cercanos = self.con.execute(
            """
            SELECT escena_texto_id, distance FROM vec_escena
            WHERE embedding MATCH ? AND k = ?
            ORDER BY distance
            """,
            (_a_blob(vector), max(limite * 5, 20)),
        ).fetchall()

        por_id = {c["texto_id"]: c for c in candidatos}
        salida: list[Fragmento] = []
        for fila in cercanos:
            tid = int(fila["escena_texto_id"])
            if tid not in permitidos:
                continue
            c = por_id[tid]
            salida.append(Fragmento(
                escena_id=int(c["escena_id"]), capitulo=int(c["capitulo"]),
                orden=int(c["orden"]), lugar=str(c["lugar"]), texto=str(c["texto"]),
                distancia=float(fila["distance"]),
            ))
            if len(salida) >= limite:
                break
        return salida
