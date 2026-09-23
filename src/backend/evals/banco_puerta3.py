"""Banco de contraejemplos de la puerta 3 (specs/spec3.md, 3.10: RF3-BAN-01 a RF3-BAN-05).

La puerta 3 se ha afinado parada a parada quitando falsos positivos, y cada arreglo afloja algo.
Los falsos negativos no paran nada, asi que nadie los ve: en la primera novela real, «siete de
fuera» con una cuadrilla de seis paso las cinco puertas. El banco mete a proposito errores
conocidos en una novela aprobada y cuenta cuantos detecta cada comprobacion, y tambien cuantos
casos limpios paran sin motivo (la idea es la de FlawedFictions y ConStory-Bench).

Cada caso cambia el grafo de la novela aprobada como lo habria dejado el extractor ante una
prosa con ese error, o lo deja sin tocar si el extractor no lo habria registrado. El cambio puede
caer en un capitulo anterior (una muerte, una presencia), pero la contradiccion aflora siempre en
el ultimo, que es el que la puerta evalua. Mide la puerta, no
el extractor: el extractor tiene su propia eval (spec3-verification, fila 34).
"""

from __future__ import annotations

import sqlite3
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import config
from compartido import db
from compartido.grafo import insertar, insertar_hecho, normalizar
from compartido.puerto import PuertoFalso
from compartido.puerto import demo as agentes_falsos
from orquestador import pipeline
from tareas.continuidad import puerta

#: El capitulo sobre el que se mete cada error: el ultimo de la novela de demo.
CAPITULO = 3

Verdad = Literal["contradiccion", "limpio"]


@dataclass(frozen=True)
class Base:
    """La novela de demo completa, en disco, y los ids que usan las mutaciones."""

    ruta: Path
    novela_id: int
    escenas: dict[tuple[int, int], int]
    personajes: dict[str, int]
    lugares: dict[str, int]
    objetos: dict[str, int]
    hechos: dict[tuple[str, str], int]
    linea_id: int


@dataclass(frozen=True)
class Esperado:
    """Lo que la puerta hace HOY con el caso: bloqueantes y avisos que tienen que salir."""

    bloqueantes: frozenset[str] = frozenset()
    avisos: frozenset[str] = frozenset()


#: Una mutacion cambia la copia de la base y puede devolver prosa para las busquedas dirigidas
#: (escena -> texto); sin prosa, la puerta corre sin ellas.
Mutacion = Callable[[sqlite3.Connection, Base], dict[int, str] | None]


@dataclass(frozen=True)
class Caso:
    id: str
    subtipo: str
    verdad: Verdad
    descripcion: str
    mutar: Mutacion
    esperado: Esperado
    #: Por que hoy no se detecta, con su fila del plan de verificacion. Solo si la verdad es una
    #: contradiccion y el esperado no trae ningun bloqueante.
    punto_ciego: str = ""


@dataclass
class Resultado:
    caso: Caso
    bloqueantes: set[str]
    avisos: set[str]

    @property
    def conforme(self) -> bool:
        """Si la puerta hace lo que el banco dice que hace hoy (RF3-BAN-04)."""
        e = self.caso.esperado
        return self.bloqueantes == set(e.bloqueantes) and set(e.avisos) <= self.avisos

    @property
    def detectado(self) -> bool:
        return bool(self.bloqueantes)


@dataclass
class Informe:
    resultados: list[Resultado] = field(default_factory=list[Resultado])

    def _de(self, verdad: Verdad) -> list[Resultado]:
        return [r for r in self.resultados if r.caso.verdad == verdad]

    @property
    def recall(self) -> float:
        """Contradicciones que paran la novela, de todas las del banco."""
        malas = self._de("contradiccion")
        return sum(r.detectado for r in malas) / len(malas) if malas else 1.0

    @property
    def falsos_positivos(self) -> float:
        """Casos limpios que paran la novela, de todos los limpios del banco."""
        limpios = self._de("limpio")
        return sum(r.detectado for r in limpios) / len(limpios) if limpios else 0.0

    def por_subtipo(self) -> dict[str, tuple[int, int]]:
        """(detectadas, total) de las contradicciones de cada subtipo."""
        salida: dict[str, tuple[int, int]] = {}
        for r in self._de("contradiccion"):
            d, t = salida.get(r.caso.subtipo, (0, 0))
            salida[r.caso.subtipo] = (d + r.detectado, t + 1)
        return salida

    @property
    def desviados(self) -> list[Resultado]:
        return [r for r in self.resultados if not r.conforme]

    def avisos(self) -> dict[str, int]:
        """En cuantos casos sale cada aviso: se cuentan aparte, porque no paran (RF3-BAN-03)."""
        salida: dict[str, int] = {}
        for r in self.resultados:
            for a in r.avisos:
                salida[a] = salida.get(a, 0) + 1
        return salida

    def tabla(self) -> str:
        filas = [
            "| Caso | Subtipo | Verdad | Esperado | Bloqueantes | Avisos | Conforme |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
        for r in self.resultados:
            e = r.caso.esperado
            esperado = ", ".join(sorted(e.bloqueantes)) or "—"
            filas.append(
                f"| {r.caso.id} | {r.caso.subtipo} | {r.caso.verdad} | {esperado} | "
                f"{', '.join(sorted(r.bloqueantes)) or '—'} | "
                f"{', '.join(sorted(r.avisos)) or '—'} | {'sí' if r.conforme else 'NO'} |"
            )
        filas.append("")
        filas.append(f"Recall sobre las contradicciones: {self.recall:.0%}")
        filas.append(f"Falsos positivos sobre los casos limpios: {self.falsos_positivos:.0%}")
        for subtipo, (d, t) in sorted(self.por_subtipo().items()):
            filas.append(f"- {subtipo}: {d} de {t}")
        filas.append(f"Avisos, en cuantos de los {len(self.resultados)} casos sale cada uno:")
        for aviso, n in sorted(self.avisos().items()):
            filas.append(f"- {aviso}: {n}")
        return "\n".join(filas)


# --- RF3-BAN-01: la base -------------------------------------------------------------------------


def _cfg(ruta: Path) -> config.Config:
    return config.Config(
        db_path=ruta, claude_bin="claude", skills_dir=config.raiz_repo() / ".claude" / "skills",
        poll_segundos=1, timeout_agente_segundos=60, presupuesto_tokens=100_000,
        puerto="falso", puerto_falso_dir=None, embedding_modelo="hash", vectores_activos=False,
    )


def construir_base(directorio: Path) -> Base:
    """La novela de demo entera con el puerto falso: tres capitulos aprobados, sin coste.

    Quien la pide pone la carpeta y la borra: la base vive lo que viva el banco.
    """
    ruta = directorio / "base.db"
    con = db.preparar(ruta)
    try:
        with db.transaccion(con):
            novela_id = insertar(con, "novela", titulo="Cerro Quince", genero="terror_espacial")
            insertar(con, "restriccion", novela_id=novela_id,
                     tipo="longitud_objetivo_palabras", valor="5400")
            insertar(con, "ejecucion", novela_id=novela_id, estado="configurada")
        puerto_falso = PuertoFalso(generadores=dict(agentes_falsos.TODOS), con=con)
        ctx = pipeline.Contexto(con=con, puerto=puerto_falso, cfg=_cfg(ruta), novela_id=novela_id)
        final = pipeline.avanzar(ctx)
        if final != "completada":
            raise RuntimeError(f"La novela de demo no se completo: {final}")

        def ids(sql: str) -> dict[str, int]:
            return {str(f[0]): int(f[1]) for f in con.execute(sql, (novela_id,))}

        escenas = {
            (int(f[0]), int(f[1])): int(f[2]) for f in con.execute(
                "SELECT c.numero, e.orden, e.id FROM escena e "
                "JOIN capitulo c ON c.id = e.capitulo_id WHERE e.novela_id = ?", (novela_id,))
        }
        hechos = {
            (str(f[0]), str(f[1])): int(f[2]) for f in con.execute(
                "SELECT sujeto_nombre, atributo, MIN(id) FROM hecho WHERE novela_id = ? "
                "GROUP BY sujeto_nombre, atributo", (novela_id,))
        }
        linea = con.execute(
            "SELECT id FROM linea_de_tiempo WHERE novela_id = ?", (novela_id,)
        ).fetchone()
        return Base(
            ruta=ruta, novela_id=novela_id, escenas=escenas,
            personajes=ids("SELECT nombre, id FROM personaje WHERE novela_id = ?"),
            lugares=ids("SELECT nombre, id FROM lugar WHERE novela_id = ?"),
            objetos=ids("SELECT nombre, id FROM objeto WHERE novela_id = ?"),
            hechos=hechos, linea_id=int(linea[0]),
        )
    finally:
        con.close()


def _copia(base: Base, destino: Path) -> sqlite3.Connection:
    """Una copia de la base para un caso: ningun caso ve lo que cambio otro."""
    origen = db.conectar(base.ruta, solo_lectura=True)
    copia = db.conectar(destino)
    try:
        origen.backup(copia)
    finally:
        origen.close()
    return copia


def _textos(con: sqlite3.Connection, novela_id: int, capitulo: int) -> dict[int, str]:
    return {
        int(f[0]): str(f[1]) for f in con.execute(
            "SELECT e.orden, t.texto FROM escena_texto t JOIN escena e ON e.id = t.escena_id "
            "JOIN capitulo c ON c.id = e.capitulo_id "
            "WHERE t.novela_id = ? AND c.numero = ? AND t.estado = 'vigente'",
            (novela_id, capitulo))
    }


def evaluar_caso(base: Base, caso: Caso) -> Resultado:
    # La copia se borra al acabar el caso; la conexion se cierra antes, porque en Windows un
    # fichero abierto no se borra.
    with tempfile.TemporaryDirectory(prefix="banco-caso-") as carpeta:
        con = _copia(base, Path(carpeta) / "caso.db")
        try:
            prosa = _textos(con, base.novela_id, CAPITULO)
            with db.transaccion(con):
                prosa.update(caso.mutar(con, base) or {})
                r = puerta.evaluar(con, base.novela_id, CAPITULO, textos=prosa)
        finally:
            con.close()
    return Resultado(
        caso=caso,
        bloqueantes={c.comprobacion for c in r.bloqueantes},
        avisos={c.comprobacion for c in r.avisos},
    )


def correr(base: Base | None = None, casos: list[Caso] | None = None) -> Informe:
    lista = casos if casos is not None else CASOS
    if base is not None:
        return Informe([evaluar_caso(base, c) for c in lista])
    with tempfile.TemporaryDirectory(prefix="banco-") as carpeta:
        nueva = construir_base(Path(carpeta))
        return Informe([evaluar_caso(nueva, c) for c in lista])


# --- RF3-BAN-02: las mutaciones ------------------------------------------------------------------
# Todas sobre el capitulo 3 de la demo: 3.1 en el modulo de carga y 3.2 en la esclusa, con Idris
# (POV) y Vaan en el reparto de las dos; Reyes no sale en ninguna escena y muere en la 3.2.


def _hecho(con: sqlite3.Connection, b: Base, escena: tuple[int, int], sujeto: str, atributo: str,
           valor: str, *, supersede_a: int | None = None) -> int:
    tipo = "lugar" if sujeto in b.lugares else "personaje"
    ids = b.lugares if tipo == "lugar" else b.personajes
    return insertar_hecho(
        con, novela_id=b.novela_id, escena_id=b.escenas[escena], sujeto_tipo=tipo,
        sujeto_id=ids[sujeto], sujeto_nombre=sujeto, atributo=atributo, valor=valor,
        categoria="fisico", cita=None, supersede_a=supersede_a,
    )


def _intruso(con: sqlite3.Connection, b: Base) -> int:
    """Un personaje sin faccion que ninguna escena pone en el reparto: nadie le cuenta nada."""
    return insertar(con, "personaje", novela_id=b.novela_id, nombre="Intruso",
                    nombre_clave=normalizar("Intruso"), rol_narrativo="aliado",
                    tipo_arco="plano")


def _usar(con: sqlite3.Connection, b: Base, personaje: int, hecho: int,
          escena: tuple[int, int]) -> None:
    insertar(con, "uso_conocimiento", novela_id=b.novela_id, personaje_id=personaje,
             hecho_id=hecho, escena_id=b.escenas[escena])


def _evento(con: sqlite3.Connection, b: Base, escena: tuple[int, int], orden: int,
            dia: int) -> None:
    insertar(con, "evento", novela_id=b.novela_id, linea_de_tiempo_id=b.linea_id,
             escena_id=b.escenas[escena], fecha_interna=f"dia {dia}", dia=dia,
             orden_interno=orden, descripcion="Suceso del banco", dramatizado=1)


def _hecho_contradictorio(con: sqlite3.Connection, b: Base) -> None:
    _hecho(con, b, (3, 1), "Idris", "color de pelo", "rubio largo")


def _constatar(con: sqlite3.Connection, b: Base, escena: tuple[int, int], *quienes: str) -> None:
    """Las presencias que registra el extractor de RF3-PAS-09 al leer la prosa."""
    for quien in quienes:
        con.execute("INSERT INTO presencia_escena (novela_id, escena_id, personaje_id) "
                    "VALUES (?,?,?)", (b.novela_id, b.escenas[escena], b.personajes[quien]))


def _muerto_que_vuelve(con: sqlite3.Connection, b: Base) -> None:
    # Sin presencias constatadas, como una base extraida antes de RF3-PAS-09: cuenta el reparto.
    insertar(con, "estado_personaje", novela_id=b.novela_id, personaje_id=b.personajes["Reyes"],
             escena_id=b.escenas[(2, 2)], condicion="muerto")
    con.execute("INSERT INTO escena_personaje (escena_id, personaje_id) VALUES (?,?)",
                (b.escenas[(3, 1)], b.personajes["Reyes"]))


def _muerto_que_la_prosa_trae(con: sqlite3.Connection, b: Base) -> None:
    _muerto_que_vuelve(con, b)
    _constatar(con, b, (3, 1), "Idris", "Vaan", "Reyes")
    _constatar(con, b, (3, 2), "Idris", "Vaan")


def _conocimiento_no_recibido(con: sqlite3.Connection, b: Base) -> None:
    _usar(con, b, _intruso(con, b), b.hechos[("Puente", "olor")], (3, 1))


def _presencia_inflada(con: sqlite3.Connection, b: Base) -> None:
    intruso = _intruso(con, b)
    # El extractor lo marca presente en la escena del hecho sin que estuviera.
    con.execute("INSERT INTO presencia_escena (novela_id, escena_id, personaje_id) "
                "VALUES (?,?,?)", (b.novela_id, b.escenas[(1, 1)], intruso))
    _usar(con, b, intruso, b.hechos[("Puente", "olor")], (3, 1))


def _presencia_real_fuera_del_reparto(con: sqlite3.Connection, b: Base) -> None:
    # Mismo grafo que el anterior, pero aqui la prosa si lo ponia alli: la puerta no los
    # distingue, y por eso la presencia autodeclarada es un punto ciego.
    _presencia_inflada(con, b)


def _objeto_sin_traslado(con: sqlite3.Connection, b: Base) -> None:
    # La baliza queda en la esclusa en la 2.2 y aparece en el modulo de carga en la 3.1.
    insertar(con, "estado_objeto", novela_id=b.novela_id, objeto_id=b.objetos["Baliza"],
             escena_id=b.escenas[(2, 2)], ubicacion_lugar_id=b.lugares["Esclusa"])
    con.execute("INSERT INTO escena_objeto (escena_id, objeto_id) VALUES (?,?)",
                (b.escenas[(3, 1)], b.objetos["Baliza"]))


def _objeto_con_su_poseedor(con: sqlite3.Connection, b: Base) -> None:
    # Igual, pero la lleva Idris, que esta en la 3.1: viaja con ella.
    insertar(con, "estado_objeto", novela_id=b.novela_id, objeto_id=b.objetos["Baliza"],
             escena_id=b.escenas[(2, 2)], ubicacion_lugar_id=b.lugares["Esclusa"],
             poseedor_id=b.personajes["Idris"])
    con.execute("INSERT INTO escena_objeto (escena_id, objeto_id) VALUES (?,?)",
                (b.escenas[(3, 1)], b.objetos["Baliza"]))


def _dos_lugares_a_la_vez(con: sqlite3.Connection, b: Base) -> None:
    # La 3.2 (esclusa) comparte orden interno con la 3.1 (modulo de carga), con Idris en las dos.
    _evento(con, b, (3, 2), 31, 3)


def _retroceso_temporal(con: sqlite3.Connection, b: Base) -> None:
    # Dia 2, como los ordenes 21 y 22: el unico error es el orden que retrocede.
    _evento(con, b, (3, 2), 15, 2)


def _dia_contra_orden(con: sqlite3.Connection, b: Base) -> None:
    _evento(con, b, (3, 2), 33, 1)


def _recuerdo_en_analepsis(con: sqlite3.Connection, b: Base) -> None:
    con.execute("UPDATE escena SET analepsis = 1 WHERE id = ?", (b.escenas[(3, 2)],))
    _evento(con, b, (3, 2), 5, -3)


def _cambio_sin_suceso(con: sqlite3.Connection, b: Base) -> None:
    # La estatura cambia con `supersede_a` y ningun suceso lo explica: la puerta confia en el
    # extractor.
    _hecho(con, b, (3, 1), "Idris", "estatura", "baja", supersede_a=b.hechos[("Idris", "estatura")])


def _cambio_con_suceso(con: sqlite3.Connection, b: Base) -> None:
    _evento(con, b, (3, 1), 31, 3)
    _hecho(con, b, (3, 1), "Idris", "color de pelo", "rapado",
           supersede_a=b.hechos[("Idris", "color de pelo")])


def _reafirmacion(con: sqlite3.Connection, b: Base) -> None:
    _hecho(con, b, (3, 1), "Idris", "voz", "ronca")


def _reformulacion(con: sqlite3.Connection, b: Base) -> None:
    _hecho(con, b, (3, 1), "Puente", "olor", "algo dulce y metal frio")


def _deduccion_falsa(con: sqlite3.Connection, b: Base) -> None:
    intruso = _intruso(con, b)
    insertar(con, "estado_conocimiento", novela_id=b.novela_id, personaje_id=intruso,
             hecho_id=b.hechos[("Puente", "olor")], escena_id=b.escenas[(3, 1)],
             postura="sabe", via="dedujo")
    _usar(con, b, intruso, b.hechos[("Puente", "olor")], (3, 1))


def _prosa_con_otra_distancia(con: sqlite3.Connection, b: Base, cifra: str) -> dict[int, str]:
    # La esclusa esta a «doce metros» del puente (hecho del capitulo 1). La prosa de la 3.2 da
    # otra cifra y el extractor no la registra. Como ya no dice «doce metros», tampoco registra
    # el uso de ese hecho, que es lo que la demo tenia en la 3.2.
    con.execute("DELETE FROM hecho_uso WHERE escena_id = ?", (b.escenas[(3, 2)],))
    return {2: f"Idris midio el pasillo con la linterna: la esclusa estaba a {cifra} metros del "
               "puente, no a los que recordaba. Vaan no dijo nada."}


def _cifra_solo_en_la_prosa(con: sqlite3.Connection, b: Base) -> dict[int, str]:
    return _prosa_con_otra_distancia(con, b, "20")


def _cifra_en_letra(con: sqlite3.Connection, b: Base) -> dict[int, str]:
    # En letra, que es como la escribe la prosa real: «los siete de fuera».
    return _prosa_con_otra_distancia(con, b, "veinte")


def _aritmetica_entre_hechos(con: sqlite3.Connection, b: Base) -> None:
    # «Once a bordo: cinco del turno y seis de cuadrilla», y despues «los siete de fuera»
    # (b1 de la pasada real). Son atributos distintos: nada los compara.
    _hecho(con, b, (1, 1), "Puente", "personas a bordo", "once: cinco del turno y seis fuera")
    _hecho(con, b, (3, 1), "Puente", "personas de fuera", "siete")


def _faccion_contra_la_prosa(con: sqlite3.Connection, b: Base) -> None:
    # El elenco pone a Vaan en una faccion y la prosa lo trata como de otra (b2 de la pasada
    # real): el hecho de pertenencia no se compara con `personaje.faccion_id`.
    otra = insertar(con, "faccion", novela_id=b.novela_id, nombre="Cuadrilla de fuera",
                    nombre_clave=normalizar("Cuadrilla de fuera"), proposito="Mantenimiento")
    nombre = con.execute("SELECT nombre FROM faccion WHERE id = ?", (otra,)).fetchone()[0]
    _hecho(con, b, (3, 1), "Vaan", "faccion", str(nombre))


def _reparto_desfasado(con: sqlite3.Connection, b: Base) -> None:
    # El muerto sigue en el reparto, pero la prosa no lo trae: la escaleta lo planifico antes de
    # su muerte y el redactor lo dejo fuera (en la 4.4 de la pasada real, tres del reparto ya se
    # habian ido). El extractor constata quien esta, y eso es lo que lee la puerta (RF3-PAS-11).
    _muerto_que_vuelve(con, b)
    _constatar(con, b, (3, 1), "Idris", "Vaan")
    _constatar(con, b, (3, 2), "Idris", "Vaan")


def _muerto_que_el_extractor_no_ve(con: sqlite3.Connection, b: Base) -> None:
    # Mismo grafo que L08, pero la prosa si lo traia y el extractor no lo registro.
    _reparto_desfasado(con, b)


def _sin_cambios(con: sqlite3.Connection, b: Base) -> None:
    return None


CASOS: list[Caso] = [
    Caso("C01", "factual", "contradiccion",
         "Un rasgo fisico del capitulo 1 cambia sin sustitucion",
         _hecho_contradictorio, Esperado(frozenset({"continuidad_factual"}))),
    Caso("C02", "personaje", "contradiccion",
         "Un personaje muerto en el capitulo 2 vuelve al reparto, sin presencias constatadas",
         _muerto_que_vuelve, Esperado(frozenset({"presencia_imposible"}))),
    Caso("C15", "personaje", "contradiccion",
         "Un personaje muerto en el capitulo 2 sale en la prosa y el extractor lo constata",
         _muerto_que_la_prosa_trae, Esperado(frozenset({"presencia_imposible"}))),
    Caso("C16", "personaje", "contradiccion",
         "Un personaje muerto sale en la prosa y el extractor no lo registra",
         _muerto_que_el_extractor_no_ve, Esperado(),
         punto_ciego="Con presencias constatadas, la muerte y la ubicuidad leen al extractor: "
                     "una presencia que se le escapa no para (RF3-PAS-11, fila 38f)"),
    Caso("C03", "conocimiento", "contradiccion",
         "Alguien actua sobre un hecho que nunca recibio",
         _conocimiento_no_recibido, Esperado(frozenset({"conocimiento_no_adquirido"}))),
    Caso("C04", "conocimiento", "contradiccion",
         "Lo mismo, pero el extractor lo marca presente donde se fijo el hecho",
         _presencia_inflada, Esperado(),
         punto_ciego="La presencia es autodeclarada: una marcada de mas habilita el uso "
                     "(fila 38d, RF2-PIPE-31)"),
    Caso("C05", "objeto", "contradiccion",
         "Un objeto aparece en otro lugar sin traslado ni poseedor",
         _objeto_sin_traslado, Esperado(frozenset({"objeto_sin_traslado"}))),
    Caso("C06", "espacio", "contradiccion",
         "Un personaje en dos lugares en el mismo momento de la cronologia",
         _dos_lugares_a_la_vez, Esperado(frozenset({"presencia_imposible"}))),
    Caso("C07", "tiempo", "contradiccion",
         "Una escena retrocede en el tiempo sin estar marcada como analepsis",
         _retroceso_temporal, Esperado(frozenset({"coherencia_temporal"}))),
    Caso("C08", "tiempo", "contradiccion",
         "Un suceso posterior cae en un dia anterior",
         _dia_contra_orden, Esperado(frozenset({"dia_contra_orden"}))),
    Caso("C09", "estado", "contradiccion",
         "Un rasgo fisico cambia con sustitucion y ningun suceso lo explica",
         _cambio_sin_suceso, Esperado(),
         punto_ciego="`supersede_a` se da por bueno: la puerta no pide un suceso que explique "
                     "el cambio (fila 50)"),
    Caso("C10", "factual", "contradiccion",
         "La prosa da otra cifra de un hecho y el extractor no la registra",
         _cifra_solo_en_la_prosa, Esperado(avisos=frozenset({"cifra_sin_hecho"})),
         punto_ciego="Una cifra que no llega a hecho no se compara con el canon; solo avisa "
                     "`cifra_sin_hecho`, y solo si la escena no tiene ningun hecho de fecha ni "
                     "de distancia (fila 50)"),
    Caso("C11", "conocimiento", "contradiccion",
         "El extractor toma por deduccion un hecho que el personaje no pudo deducir",
         _deduccion_falsa, Esperado(avisos=frozenset({"deduccion_por_verificar"})),
         punto_ciego="Una deduccion habilita el uso; solo avisa `deduccion_por_verificar` "
                     "(RF3-PAS-08, fila 38c)"),
    Caso("C12", "aritmetica", "contradiccion",
         "Dos cifras de atributos distintos que no cuadran entre si",
         _aritmetica_entre_hechos, Esperado(),
         punto_ciego="La puerta compara valores del mismo atributo; no suma ni resta entre "
                     "hechos (fila 50)"),
    Caso("C13", "pertenencia", "contradiccion",
         "La prosa pone a un personaje en otra faccion que el elenco",
         _faccion_contra_la_prosa, Esperado(),
         punto_ciego="Un hecho de pertenencia no se compara con la faccion del elenco, que es "
                     "la que usa el conocimiento por faccion (fila 50)"),
    Caso("C14", "factual", "contradiccion",
         "Lo mismo que C10, con la cifra en letra",
         _cifra_en_letra, Esperado(),
         punto_ciego="`cifra_sin_hecho` solo reconoce digitos: la cifra en letra, que es como "
                     "la escribe la prosa, ni avisa (fila 50)"),
    Caso("L01", "control", "limpio", "La novela aprobada, sin cambios", _sin_cambios, Esperado()),
    Caso("L02", "control", "limpio", "Un hecho repetido con el valor exacto",
         _reafirmacion, Esperado()),
    Caso("L03", "control", "limpio", "Un cambio con sustitucion y el suceso que lo explica",
         _cambio_con_suceso, Esperado()),
    Caso("L04", "control", "limpio", "Un recuerdo en una escena marcada como analepsis",
         _recuerdo_en_analepsis, Esperado()),
    Caso("L05", "control", "limpio", "Un objeto que viaja con su poseedor",
         _objeto_con_su_poseedor, Esperado()),
    Caso("L06", "control", "limpio",
         "Alguien que el redactor metio en la escena del hecho, bien registrado",
         _presencia_real_fuera_del_reparto, Esperado()),
    Caso("L08", "control", "limpio",
         "Un muerto sigue en el reparto planificado, pero la prosa no lo trae",
         _reparto_desfasado, Esperado()),
    Caso("L07", "control", "limpio", "El mismo hecho dicho con otras palabras",
         _reformulacion, Esperado(frozenset({"continuidad_factual"})),
         punto_ciego="Falso positivo conocido: una reformulacion parece otro valor "
                     "(RF2-PIPE-23, fila 50)"),
]
