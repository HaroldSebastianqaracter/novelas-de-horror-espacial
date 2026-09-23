"""PuertoFalso: la misma interfaz, con respuestas grabadas (RF-PUERTO-07).

Es lo que permite correr el pipeline entero de principio a fin sin Claude Code instalado y
sin gastar dinero. Los tests del orquestador y las demos lo usan con NOVELAS_PUERTO=falso.

Busca la respuesta de un agente, por orden:
  1. `<dir>/<agente>/<capitulo>-<intento>.json`
  2. `<dir>/<agente>/<capitulo>.json`
  3. `<dir>/<agente>.json`
Y si no hay fixtures, usa un generador registrado en memoria.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ..tipos import como_dict
from .base import AgenteInterrumpido, ResultadoAgente, SalidaInvalida

Generador = Callable[[str, str], dict[str, Any]]


class PuertoFalso:
    """Puerto de pruebas. Registra lo que recibe para poder afirmarlo en los tests."""

    def __init__(
        self,
        *,
        fixtures_dir: Path | None = None,
        generadores: dict[str, Generador] | None = None,
        con: sqlite3.Connection | None = None,
        retraso_s: float = 0.0,
    ) -> None:
        self.fixtures_dir = Path(fixtures_dir) if fixtures_dir else None
        self.generadores: dict[str, Generador] = dict(generadores or {})
        self.con = con
        self.retraso_s = retraso_s
        self.invocaciones: list[dict[str, Any]] = []
        self._interrumpido = threading.Event()
        self._cerrado = threading.Event()

    def registrar(self, agente: str, generador: Generador) -> None:
        self.generadores[agente] = generador

    def _buscar_fixture(
        self, agente: str, capitulo: int | None, intento: int | None
    ) -> dict[str, Any] | None:
        if self.fixtures_dir is None:
            return None
        candidatos: list[Path] = []
        if capitulo is not None and intento is not None:
            candidatos.append(self.fixtures_dir / agente / f"{capitulo}-{intento}.json")
        if capitulo is not None:
            candidatos.append(self.fixtures_dir / agente / f"{capitulo}.json")
        candidatos.append(self.fixtures_dir / f"{agente}.json")
        for ruta in candidatos:
            if ruta.is_file():
                cargado = como_dict(json.loads(ruta.read_text(encoding="utf-8")))
                if cargado:
                    return cargado
        return None

    def invocar(
        self,
        agente: str,
        entrada: str,
        esquema_salida: dict[str, Any],
        *,
        timeout_s: int | None = None,
        novela_id: int | None = None,
        capitulo: int | None = None,
        intento: int | None = None,
        tokens_por_bloque: dict[str, int] | None = None,
    ) -> ResultadoAgente:
        if self._cerrado.is_set():
            raise AgenteInterrumpido("El puerto se cerro por una senal de terminar.")
        self._interrumpido.clear()
        self.invocaciones.append(
            {
                "agente": agente,
                "entrada": entrada,
                "esquema": esquema_salida,
                "novela_id": novela_id,
                "capitulo": capitulo,
                "intento": intento,
                "tokens_por_bloque": dict(tokens_por_bloque or {}),
            }
        )

        if self.retraso_s:
            # Sirve para probar `parar` en mitad de una llamada (RF-WK-03).
            esperado = self._interrumpido.wait(self.retraso_s)
            if esperado:
                raise AgenteInterrumpido("Invocacion falsa cortada por parar.")

        salida = self._buscar_fixture(agente, capitulo, intento)
        if salida is None:
            generador = self.generadores.get(agente)
            if generador is None:
                raise SalidaInvalida(
                    f"PuertoFalso no tiene respuesta para el agente '{agente}'. "
                    "Anade un fixture o registra un generador."
                )
            salida = generador(entrada, agente)

        cruda = json.dumps({"result": json.dumps(salida), "structured_output": salida,
                            "is_error": False}, ensure_ascii=False)
        llamada_id = self._trazar(
            agente, entrada, esquema_salida, cruda, novela_id, capitulo, intento,
            tokens_por_bloque,
        )
        return ResultadoAgente(
            agente=agente,
            salida=salida,
            salida_cruda=cruda,
            duracion_ms=1,
            exit_code=0,
            tokens_entrada=len(entrada) // 4,
            tokens_salida=len(cruda) // 4,
            llamada_id=llamada_id,
            metadatos={"puerto": "falso"},
        )

    def _trazar(
        self,
        agente: str,
        entrada: str,
        esquema: dict[str, Any],
        cruda: str,
        novela_id: int | None,
        capitulo: int | None,
        intento: int | None,
        tokens_por_bloque: dict[str, int] | None,
    ) -> int | None:
        """Registra la llamada igual que el puerto real.

        Sin esto el puerto falso seria un sustituto infiel: el pipeline correria pero sin
        traza, y RNF-01 —toda llamada se reconstruye desde `llamada_modelo`— no se podria
        comprobar sin gastar dinero.
        """
        if self.con is None:
            return None
        from ..db import transaccion

        with transaccion(self.con):
            cur = self.con.execute(
                """
                INSERT INTO llamada_modelo
                    (novela_id, agente, capitulo, intento, sistema, entrada, esquema,
                     salida_cruda, tokens_entrada_por_bloque, tokens_entrada, tokens_salida,
                     duracion_ms, exit_code, estado, metadatos, terminado_en)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,0,'ok',?, datetime('now'))
                """,
                (
                    novela_id, agente, capitulo, intento,
                    f"(puerto falso: skill de '{agente}')", entrada,
                    json.dumps(esquema, ensure_ascii=False), cruda,
                    json.dumps(tokens_por_bloque or {}, ensure_ascii=False),
                    len(entrada) // 4, len(cruda) // 4, 1,
                    json.dumps({"puerto": "falso"}, ensure_ascii=False),
                ),
            )
            return int(cur.lastrowid or 0)

    def interrumpir(self, *, definitivo: bool = False) -> None:
        self._interrumpido.set()
        if definitivo:
            self._cerrado.set()
