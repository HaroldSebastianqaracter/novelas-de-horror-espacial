"""Model checking de la maquina de estados y de `avanzar` (spec2, fase 2: RF2-PIPE-00).

Explora por anchura todos los estados alcanzables desde `configurada`. En cada estado aplica
cada suceso que el worker sabe atender (las cinco intenciones, sus variantes de
`resolver_parada`, la recuperacion tras una caida y la propia caida) con cada combinacion de
resultados de las puertas, y comprueba los invariantes sobre el resultado:

  I1. `generar_capitulo` nunca se llama sin las puertas 1 y 2 vigentes.
  I2. La puerta 5 nunca se evalua sin las puertas 1 y 2 vigentes.
  I3. Una novela completada tiene capitulos, todos completados, y las puertas 1 y 2 vigentes.
  I4. En `parada` hay exactamente una parada abierta, y es la que dice la ejecucion.
  I5. Una intencion rechazada no cambia nada.
  I6. Fuera de una ejecucion activa, el grafo esta integro.

Las puertas y el capitulo son falsos a proposito: lo que se comprueba es el ORDEN que impone el
orquestador, no lo que juzgan las puertas. Los estados se comparan por su abstraccion (estado,
tipo de parada, que fases estan hechas y que puertas vigentes), asi que el espacio es pequeno y
se recorre entero.
"""

from __future__ import annotations

import sqlite3
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pytest

import worker
from compartido import db
from compartido.db import transaccion
from compartido.puerta_base import Conflicto, ResultadoPuerta
from orquestador import cola, fallo, pipeline, vigencia
from tests.entorno import cfg_de, crear_novela, nueva_bd

NOVELA = 1
PROFUNDIDAD = 4


class Caida(BaseException):
    """El proceso muere a mitad de algo: ningun except del pipeline la captura."""


@dataclass(frozen=True)
class Resultados:
    """Lo que devuelven las puertas y el capitulo en una transicion."""

    puerta_1: bool = True
    puerta_2: bool = True
    capitulo: str = "cierra"  # cierra | continuidad | oficio | presupuesto | excepcion
    cae_en: str | None = None  # planificacion | puerta_1 | escaleta | puerta_2 | capitulo
    puerta_5_limpia: bool = False


COMBINACIONES = (
    Resultados(),
    Resultados(puerta_1=False),
    Resultados(puerta_2=False),
    Resultados(capitulo="continuidad"),
    Resultados(capitulo="oficio"),
    Resultados(capitulo="presupuesto"),
    Resultados(capitulo="excepcion"),
    Resultados(puerta_5_limpia=True),
)
#: Donde puede morir el proceso. Entre escribir una fase y evaluar su puerta es donde el
#: `avanzar` de spec1 se saltaba la puerta (hallazgo 1).
CAIDAS = tuple(
    Resultados(cae_en=donde)
    for donde in ("planificacion", "puerta_1", "escaleta", "puerta_2", "capitulo")
)

#: Sucesos que ponen a correr el pipeline: se prueban con todas las combinaciones.
SUCESOS_QUE_CORREN = (
    "arrancar", "relanzar_1", "relanzar_2", "rehacer", "aceptar_retcon", "resolver_relanzar",
)
#: Sucesos que no llegan a ninguna puerta.
SUCESOS_QUIETOS = ("parar", "recuperar")


def _foto(con: sqlite3.Connection) -> bytes:
    """La base entera como bytes, sin la marca de WAL: una base en memoria no puede usar WAL."""
    datos = bytearray(con.serialize())
    datos[18] = datos[19] = 1
    return bytes(datos)


def _abrir(datos: bytes) -> sqlite3.Connection:
    con = sqlite3.connect(":memory:", isolation_level=None)
    con.deserialize(datos)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def _abstraccion(con: sqlite3.Connection) -> tuple[Any, ...]:
    e = con.execute("SELECT estado FROM ejecucion WHERE novela_id = ?", (NOVELA,)).fetchone()
    abiertas = fallo.paradas_abiertas(con, NOVELA)
    total = int(con.execute("SELECT COUNT(*) FROM capitulo").fetchone()[0])
    hechos = int(con.execute(
        "SELECT COUNT(*) FROM capitulo WHERE estado = 'completado'"
    ).fetchone()[0])
    return (
        str(e["estado"]),
        tuple(sorted(str(p["tipo"]) for p in abiertas)),
        not pipeline._fase_pendiente_de_planificacion(
            pipeline.Contexto(con=con, puerto=None, cfg=None, novela_id=NOVELA)  # type: ignore[arg-type]
        ),
        vigencia.puerta_vigente(con, NOVELA, 1),
        total > 0,
        vigencia.puerta_vigente(con, NOVELA, 2),
        hechos,
    )


class Explorador:
    def __init__(self, monkeypatch: pytest.MonkeyPatch, profundidad: int = PROFUNDIDAD) -> None:
        self.mp = monkeypatch
        self.profundidad = profundidad
        self.violaciones: list[str] = []
        self.transiciones = 0
        self._real_p1 = pipeline.p_estructura.evaluar
        self._real_p2 = pipeline.p_escaleta.evaluar
        self._real_p5 = pipeline.evaluar_puerta_global
        _, ruta = nueva_bd()
        self.cfg = cfg_de(ruta)
        self._traza: str = ""

    # -- el mundo falso ------------------------------------------------------------------------

    def _preparar(self, w: worker.Worker, r: Resultados) -> None:
        falla = lambda n: (  # noqa: E731
            lambda *_: ResultadoPuerta(puerta=n, conflictos=[Conflicto("forzado", "falla")])
        )
        self.mp.setattr(pipeline.p_estructura, "evaluar", self._real_p1 if r.puerta_1 else falla(1))
        self.mp.setattr(pipeline.p_escaleta, "evaluar", self._real_p2 if r.puerta_2 else falla(2))

        def puerta_5(con: sqlite3.Connection, novela_id: int) -> ResultadoPuerta:
            self._exigir_puertas(con, novela_id, "puerta 5")
            if r.puerta_5_limpia:
                return ResultadoPuerta(puerta=5)
            return self._real_p5(con, novela_id)

        self.mp.setattr(pipeline, "evaluar_puerta_global", puerta_5)
        self.mp.setattr(pipeline, "generar_capitulo", self._capitulo_falso(r))

        def cae(*_: object) -> dict[str, Any]:
            raise Caida()

        if r.cae_en == "planificacion":
            w.puerto.registrar("elenco", cae)  # type: ignore[attr-defined]
        elif r.cae_en == "escaleta":
            w.puerto.registrar("escaleta", cae)  # type: ignore[attr-defined]
        elif r.cae_en == "puerta_1":
            self.mp.setattr(pipeline.p_estructura, "evaluar", cae)
        elif r.cae_en == "puerta_2":
            self.mp.setattr(pipeline.p_escaleta, "evaluar", cae)

    def _exigir_puertas(self, con: sqlite3.Connection, novela_id: int, que: str) -> None:
        for p in (1, 2):
            if not vigencia.puerta_vigente(con, novela_id, p):
                self.violaciones.append(f"{que} sin la puerta {p} vigente: {self._traza}")

    def _capitulo_falso(self, r: Resultados) -> Callable[[pipeline.Contexto, int], None]:
        def generar(ctx: pipeline.Contexto, numero: int) -> None:
            self._exigir_puertas(ctx.con, ctx.novela_id, f"generar_capitulo({numero})")
            if r.cae_en == "capitulo" and numero == 2:
                raise Caida()
            if r.capitulo == "excepcion" and numero == 2:
                raise RuntimeError("fallo no controlado en el capitulo")
            if numero == 2 and r.capitulo != "cierra":
                informe: dict[str, Any] = {"motivo": "forzado"}
                if r.capitulo == "continuidad":
                    informe["conflictos"] = [{"datos": {"hecho_previo_id": 1}}]
                pipeline._abrir_parada(ctx, r.capitulo, informe, capitulo=numero)
            with transaccion(ctx.con):
                pipeline._cerrar_capitulo(ctx, numero)

        return generar

    # -- una transicion ------------------------------------------------------------------------

    def aplicar(self, datos: bytes, suceso: str, r: Resultados) -> bytes | None:
        con = _abrir(datos)
        w = worker.Worker(self.cfg, con=con)
        self._preparar(w, r)
        antes = _abstraccion(con)
        intencion = self._intencion(con, suceso)
        try:
            if suceso == "recuperar":
                w.recuperar()
            elif suceso == "parar":
                w._parar(intencion)
            elif suceso == "arrancar":
                w._arrancar(intencion)
            elif suceso.startswith("relanzar_"):
                w._relanzar(intencion)
            else:
                w._resolver_parada(intencion)
        except Caida:
            pass
        finally:
            self.mp.undo()
        self.transiciones += 1
        self._comprobar(con, antes, intencion)
        return _foto(con)

    def _intencion(self, con: sqlite3.Connection, suceso: str) -> cola.Intencion:
        payload: dict[str, Any] = {}
        tipo = suceso
        if suceso.startswith("relanzar_"):
            tipo, payload = "relanzar", {"desde_capitulo": int(suceso[-1])}
        elif suceso in ("rehacer", "aceptar_retcon", "resolver_relanzar"):
            abiertas = fallo.paradas_abiertas(con, NOVELA)
            tipo = "resolver_parada"
            payload = {
                "parada_id": int(abiertas[0]["id"]) if abiertas else 999,
                "accion": "relanzar" if suceso == "resolver_relanzar" else suceso,
            }
        elif suceso == "recuperar":
            tipo = "parar"  # no se usa: recuperar no consume intencion
        iid = cola.encolar(con, tipo, NOVELA, **payload)
        con.execute("UPDATE intencion SET estado = 'en_curso' WHERE id = ?", (iid,))
        return cola.Intencion(id=iid, tipo=tipo, novela_id=NOVELA, payload=payload)

    def _comprobar(
        self, con: sqlite3.Connection, antes: tuple[Any, ...], intencion: cola.Intencion
    ) -> None:
        despues = _abstraccion(con)
        estado = despues[0]
        if estado.startswith("completada"):
            total = int(con.execute("SELECT COUNT(*) FROM capitulo").fetchone()[0])
            if total == 0 or despues[6] != total or not (despues[3] and despues[5]):
                self.violaciones.append(f"I3 completada sin manuscrito: {despues} {self._traza}")
        abiertas = fallo.paradas_abiertas(con, NOVELA)
        if estado == "parada":
            e = con.execute("SELECT parada_abierta_id FROM ejecucion").fetchone()
            if len(abiertas) != 1 or e["parada_abierta_id"] != abiertas[0]["id"]:
                self.violaciones.append(f"I4 parada incoherente: {despues} {self._traza}")
        elif abiertas:
            self.violaciones.append(f"I4 parada abierta en {estado}: {self._traza}")
        fila = con.execute(
            "SELECT estado FROM intencion WHERE id = ?", (intencion.id,)
        ).fetchone()
        if fila["estado"] == "rechazada" and despues != antes:
            self.violaciones.append(
                f"I5 rechazo que cambia algo: {antes} -> {despues} {self._traza}"
            )
        if estado not in db.ESTADOS_ACTIVOS:
            rotas = [v.regla for v in db.verificar_integridad(con)]
            if rotas:
                self.violaciones.append(f"I6 integridad {rotas}: {self._traza}")

    # -- recorrido -----------------------------------------------------------------------------

    def explorar(self, inicial: bytes) -> set[tuple[Any, ...]]:
        vistos = {_abstraccion(_abrir(inicial))}
        cola_bfs: deque[tuple[bytes, int, str]] = deque([(inicial, 0, "configurada")])
        while cola_bfs:
            datos, nivel, camino = cola_bfs.popleft()
            if nivel >= self.profundidad:
                continue
            pasos = [(s, r) for s in SUCESOS_QUE_CORREN for r in COMBINACIONES]
            pasos += [(s, Resultados()) for s in SUCESOS_QUIETOS]
            pasos += [("arrancar", r) for r in CAIDAS]
            for suceso, r in pasos:
                self._traza = f"{camino} -> {suceso} {r}"
                nuevo = self.aplicar(datos, suceso, r)
                if nuevo is None:
                    continue
                clave = _abstraccion(_abrir(nuevo))
                if clave not in vistos:
                    vistos.add(clave)
                    cola_bfs.append((nuevo, nivel + 1, f"{camino} -> {suceso}"))
        return vistos


def test_ningun_camino_genera_un_capitulo_sin_las_puertas_1_y_2(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    con, _ = nueva_bd()
    assert crear_novela(con) == NOVELA
    inicial = _foto(con)

    explorador = Explorador(monkeypatch)
    vistos = explorador.explorar(inicial)

    assert not explorador.violaciones, "\n".join(explorador.violaciones[:15])
    estados = {v[0] for v in vistos}
    # El recorrido tiene que haber llegado a todos los estados de la maquina: si no, el
    # invariante se habria comprobado sobre un espacio mas pequeno del que dice.
    assert estados == {
        "configurada", "planificando", "escaletando", "generando", "parada", "detenida",
        "completada", "completada_con_avisos", "error",
    }, estados
    tipos = {t for v in vistos for t in v[1]}
    assert tipos == {"estructura", "escaleta", "continuidad", "oficio", "presupuesto"}, tipos
    assert explorador.transiciones > 100


def test_el_recorrido_detecta_un_avanzar_que_se_salta_la_puerta_1(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mutacion del propio model checking: con el `avanzar` de spec1, que no miraba si la
    puerta 1 estaba vigente, el recorrido tiene que encontrar la violacion."""

    class VigenciaCiega:
        huella = staticmethod(vigencia.huella)
        informe_de_rechazo = staticmethod(vigencia.informe_de_rechazo)

        @staticmethod
        def puerta_vigente(*_: object) -> bool:
            return True

    con, _ = nueva_bd()
    crear_novela(con)
    explorador = Explorador(monkeypatch, profundidad=3)
    real = pipeline.vigencia
    original = explorador._preparar

    def preparar_con_mutante(w: worker.Worker, r: Resultados) -> None:
        original(w, r)
        monkeypatch.setattr(pipeline, "vigencia", VigenciaCiega)

    explorador._preparar = preparar_con_mutante  # type: ignore[method-assign]
    explorador.explorar(_foto(con))
    assert pipeline.vigencia is real
    assert any("generar_capitulo" in v and "puerta 1" in v for v in explorador.violaciones)


def test_el_informe_de_rechazo_sobrevive_a_un_reinicio() -> None:
    """El escaletador que rehace recibe el informe aunque el worker se haya reiniciado."""
    con, ruta = nueva_bd()
    novela_id = crear_novela(con)
    ctx = pipeline.Contexto(con=con, puerto=worker.construir_puerto(cfg_de(ruta), con),
                            cfg=cfg_de(ruta), novela_id=novela_id)
    pipeline.planificar(ctx)
    ResultadoPuerta(puerta=2, conflictos=[Conflicto("escena_sin_conflicto", "sin conflicto")]
                    ).registrar(con, novela_id)
    otra = db.conectar(ruta)
    assert vigencia.informe_de_rechazo(otra, novela_id, 2) == [
        "[escena_sin_conflicto] sin conflicto"
    ]
