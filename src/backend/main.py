"""La API: el borde HTTP entre el backend y el frontend.

Tres reglas que este fichero materializa:

* **Solo lee.** La unica escritura es insertar una fila en `intencion`. Y no es disciplina:
  la conexion de lectura se abre en modo `ro` y el motor rechaza cualquier otra cosa.
* **No ejecuta el pipeline.** No importa el orquestador ni el puerto. Escribe una intencion y
  el worker la recoge.
* **El `GET` es la verdad; el SSE es comodidad.** Ninguna decision del cliente puede depender
  de haber recibido un evento: si el stream se cae, se reconsulta y se recupera.

Los endpoints son funciones sincronas a proposito. FastAPI las ejecuta en su pool de hilos,
asi que ninguna consulta al grafo bloquea el bucle de eventos. El unico `async` es el stream,
y lo unico que hace es dormir y consultar.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
from collections.abc import AsyncGenerator, AsyncIterator, Iterator
from contextlib import asynccontextmanager
from typing import Annotated, Any, Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field, ValidationError, model_validator

import config
from compartido import db
from compartido.brief import Analisis, Brief, BriefIncompleto, analizar
from compartido.grafo import lectura
from compartido.tipos import TipoIntencion

KEEPALIVE_SEGUNDOS = 15

log = logging.getLogger("api")


# --- Esquemas de la API (RF-API-01) ----------------------------------------------------------


class Error(BaseModel):
    codigo: str
    mensaje: str
    detalle: str | None = None


class CrearNovela(BaseModel):
    """Con `brief`, la novela es personalizada y sus restricciones salen de el (RF3-PER-01);
    el titulo lo propone el arquitecto. Sin brief, es el payload de spec1 y el titulo es
    obligatorio (RF3-PER-05)."""

    titulo: str = ""
    genero: str = "terror_espacial"
    semilla_premisa: str = ""
    restricciones: dict[str, str] = Field(default_factory=dict[str, str])
    brief: Brief | None = None
    entrevista: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _brief_completo_o_titulo(self) -> CrearNovela:
        if self.brief is None:
            if not self.titulo.strip():
                raise ValueError("Sin brief, el titulo es obligatorio.")
        else:
            # Un brief con faltantes o contradicciones no llega al worker (RF3-BRF-04).
            self.brief.validar_completo()
        return self


class PayloadRelanzar(BaseModel):
    desde_capitulo: int = Field(ge=1)


class PayloadResolverParada(BaseModel):
    parada_id: int = Field(ge=1)
    accion: Literal["relanzar", "aceptar_retcon", "dar_por_sabido", "rehacer"]
    desde_capitulo: int | None = Field(default=None, ge=1)


#: La API valida la FORMA de cada payload; el estado lo valida el worker (RF-API-04).
PAYLOADS: dict[str, type[BaseModel]] = {
    "crear_novela": CrearNovela,
    "relanzar": PayloadRelanzar,
    "resolver_parada": PayloadResolverParada,
}


class NuevaIntencion(BaseModel):
    tipo: TipoIntencion
    novela_id: int | None = None
    payload: dict[str, Any] = Field(default_factory=dict[str, Any])


class IntencionEncolada(BaseModel):
    id: int
    tipo: str
    estado: str


class EstadoIntencion(BaseModel):
    id: int
    tipo: str
    estado: str
    motivo: str | None = None
    resultado: dict[str, Any] | None = None
    creado_en: str


class NovelaResumen(BaseModel):
    id: int
    titulo: str
    genero: str
    subgenero_dominante: str | None = None
    estado: str | None = None
    capitulos_completados: int = 0
    creado_en: str


class Ejecucion(BaseModel):
    """La verdad sobre la generacion. El frontend pinta esto, no los eventos."""

    novela_id: int
    estado: str
    fase: str | None = None
    capitulo_actual: int | None = None
    intento_actual: int = 1
    capitulos_completados: int = 0
    total_capitulos: int = 0
    parada_abierta_id: int | None = None
    ultimo_error: str | None = None
    actualizado_en: str


class Parada(BaseModel):
    id: int
    tipo: str
    capitulo: int | None = None
    intento: int | None = None
    estado: str
    resolucion: str | None = None
    creado_en: str
    informe: dict[str, Any] | None = None


class Escena(BaseModel):
    orden: int
    pov: str
    lugar: str
    reparto: list[str]
    objetivo: str
    conflicto: str
    valor_inicial: str
    valor_final: str
    tension: int | None = None
    analepsis: bool = False


class Capitulo(BaseModel):
    numero: int
    objetivo: str | None = None
    estado: str
    resumen: str | None = None
    escenas: list[Escena] = Field(default_factory=list[Escena])


class CapituloTexto(BaseModel):
    numero: int
    version: int
    palabras: int
    texto: str


class Hecho(BaseModel):
    id: int
    sujeto_tipo: str
    sujeto_nombre: str | None = None
    atributo: str
    valor: str
    categoria: str
    capitulo_origen: int | None = None
    vigente: bool = True


class Pagina[T](BaseModel):
    total: int
    items: list[T]


# --- Canon y estructura (RF2-API-01: ninguna respuesta sin esquema) --------------------------


class NovelaCanon(BaseModel):
    id: int
    titulo: str
    genero: str
    subgenero_dominante: str | None = None
    premisa: str | None = None
    logline: str | None = None
    pregunta_dramatica: str | None = None
    tema_central: str | None = None
    tipo_final: str | None = None
    longitud_objetivo: int | None = None
    pov_por_defecto: str | None = None
    tiempo_verbal: str | None = None
    semilla_premisa: str | None = None
    creado_en: str


class EstiloNarrativo(BaseModel):
    registro: str
    ritmo_prosa: str
    densidad_sensorial: str
    distancia_psiquica: str
    tics_prohibidos: list[str] = Field(default_factory=list[str])
    convenciones_formato: str | None = None


class NovelaDetalle(BaseModel):
    novela: NovelaCanon
    restricciones: dict[str, str]
    estilo: EstiloNarrativo | None = None


class MundoCanon(BaseModel):
    entidad: Literal["mundo"] = "mundo"
    id: int
    nombre: str
    geografia: str | None = None
    historia: str | None = None
    culturas: str | None = None
    reglas_fisicas: str | None = None


class SistemaCanon(BaseModel):
    entidad: Literal["sistemas"] = "sistemas"
    id: int
    nombre: str
    capacidades: str
    costes: str
    limites: str
    acceso: str | None = None
    dureza: str


class LugarCanon(BaseModel):
    entidad: Literal["lugares"] = "lugares"
    id: int
    nombre: str
    tipo: str | None = None
    descripcion: str | None = None
    sistemas_criticos: list[int] = Field(default_factory=list[int])


class PersonajeCanon(BaseModel):
    entidad: Literal["personajes"] = "personajes"
    id: int
    nombre: str
    rol: str | None = None
    rol_narrativo: str
    deseo: str | None = None
    necesidad_interna: str | None = None
    fantasma: str | None = None
    herida: str | None = None
    mentira: str | None = None
    defecto: str | None = None
    tipo_arco: str | None = None
    subtipo_arco: str | None = None
    idiolecto: str | None = None
    secreto: str | None = None
    posicion_tematica: str | None = None
    faccion_id: int | None = None


class FaccionCanon(BaseModel):
    entidad: Literal["facciones"] = "facciones"
    id: int
    nombre: str
    proposito: str | None = None
    objetivos: str | None = None
    recursos: str | None = None


class ReglaAmenaza(BaseModel):
    capacidad: str = ""
    limite: str = ""
    activacion: str = ""


class AmenazaCanon(BaseModel):
    entidad: Literal["amenaza"] = "amenaza"
    id: int
    naturaleza: str
    reglas: list[ReglaAmenaza] = Field(default_factory=list[ReglaAmenaza])
    origen: str | None = None
    tema_id: int | None = None


class ObjetoCanon(BaseModel):
    entidad: Literal["objetos"] = "objetos"
    id: int
    nombre: str
    funcion_narrativa: str | None = None


class TemaCanon(BaseModel):
    entidad: Literal["temas"] = "temas"
    id: int
    pregunta_central: str
    verdad_tematica: str


class MotivoCanon(BaseModel):
    entidad: Literal["motivos"] = "motivos"
    id: int
    tema_id: int | None = None
    simbolo: str
    significado_inicial: str | None = None
    significado_final: str | None = None


class EventoCanon(BaseModel):
    entidad: Literal["eventos"] = "eventos"
    id: int
    escena_id: int | None = None
    fecha_interna: str
    orden_interno: int | None = None
    descripcion: str
    tipo: str | None = None
    dramatizado: bool


#: Una fila de canon: la entidad del camino dice cual de los modelos es (union discriminada).
EntidadCanon = Annotated[
    MundoCanon | SistemaCanon | LugarCanon | PersonajeCanon | FaccionCanon | AmenazaCanon
    | ObjetoCanon | TemaCanon | MotivoCanon | EventoCanon,
    Field(discriminator="entidad"),
]


class Acto(BaseModel):
    numero: int
    funcion_narrativa: str | None = None


class Hilo(BaseModel):
    hilo_id: int
    tipo: str
    conflicto_central: str
    estado: str


class SiembraVista(BaseModel):
    siembra_id: int
    elemento: str
    hilo_id: int | None = None
    capitulo_pago_previsto: int | None = None
    estado: str


class PuntoDeGiro(BaseModel):
    id: int
    hilo_id: int
    tipo: str
    posicion: float


class Estructura(BaseModel):
    actos: list[Acto]
    capitulos: list[Capitulo]
    hilos: list[Hilo]
    siembras: list[SiembraVista]
    puntos_de_giro: list[PuntoDeGiro]


class VersionEscena(BaseModel):
    escena: int
    version: int
    estado: str
    origen: str
    intento: int | None = None
    palabras: int
    creado_en: str
    llamada_modelo_id: int | None = None


class ConocimientoVista(BaseModel):
    personaje: str
    sujeto_nombre: str | None = None
    atributo: str
    valor: str
    postura: str
    via: str
    capitulo: int


class Llamada(BaseModel):
    id: int
    agente: str
    capitulo: int | None = None
    intento: int | None = None
    tokens_entrada: int | None = None
    tokens_salida: int | None = None
    duracion_ms: int | None = None
    exit_code: int | None = None
    estado: str
    creado_en: str
    # Solo con ?completo=1: son decenas de miles de tokens por fila.
    sistema: str | None = None
    entrada: str | None = None
    salida_cruda: str | None = None
    tokens_entrada_por_bloque: dict[str, int] | None = None
    metadatos: dict[str, Any] | None = None


# --- Aplicacion ------------------------------------------------------------------------------


def _cargar_config() -> config.Config:
    return config.cargar()


@asynccontextmanager
async def ciclo(app: FastAPI) -> AsyncGenerator[None]:
    """Al arrancar, crea el esquema si no existe. NO lanza el worker: son dos comandos.

    Crear el esquema es la unica escritura que se le permite a la API fuera de las
    intenciones, y es segura entre procesos (RF2-PROC-03). Migrar no: eso es del worker, que
    lo hace con su cerrojo tomado.

    Si alguien ya dejo una configuracion en `app.state.cfg` —los tests— se respeta. Leer el
    entorno por encima de lo que el llamante puso obligaria a montar variables globales solo
    para poder probar la API.
    """
    cfg: config.Config = getattr(app.state, "cfg", None) or _cargar_config()
    con = db.conectar(cfg.db_path)
    db.crear_esquema(con)
    actual, objetivo = db.version_actual(con), db.version_objetivo()
    con.close()
    if actual < objetivo:
        log.warning(
            "La base esta en la version %s del esquema y el codigo espera la %s. Arranca el "
            "worker para que la migre; hasta entonces algunas lecturas fallaran.",
            actual, objetivo,
        )
    app.state.cfg = cfg
    yield


app = FastAPI(
    title="Novela de terror espacial",
    version="0.1.0",
    summary="Borde HTTP del backend. Solo lee; actuar es encolar una intencion.",
    lifespan=ciclo,
)


def leer(request: Request) -> Iterator[sqlite3.Connection]:
    """Conexion de SOLO LECTURA. El motor rechaza cualquier escritura por aqui."""
    con = db.conectar(request.app.state.cfg.db_path, solo_lectura=True)
    try:
        yield con
    finally:
        con.close()


def escribir_intencion(request: Request) -> Iterator[sqlite3.Connection]:
    """La unica excepcion a la regla de solo lectura (RF-API-02)."""
    con = db.conectar(request.app.state.cfg.db_path)
    try:
        yield con
    finally:
        con.close()


Con = Annotated[sqlite3.Connection, Depends(leer)]
ConEscritura = Annotated[sqlite3.Connection, Depends(escribir_intencion)]


def _novela_o_404(con: sqlite3.Connection, novela_id: int) -> dict[str, Any]:
    n = lectura.novela(con, novela_id)
    if n is None:
        raise HTTPException(status_code=404, detail=f"No existe la novela {novela_id}")
    return n


def _json(valor: Any) -> Any:
    if isinstance(valor, str):
        try:
            return json.loads(valor)
        except json.JSONDecodeError:
            return None
    return valor


# --- Intenciones: la unica via para actuar ------------------------------------------------------


@app.post("/intenciones", status_code=202, response_model=IntencionEncolada)
def crear_intencion(cuerpo: NuevaIntencion, con: ConEscritura) -> IntencionEncolada:
    """Encola una intencion. El worker la recoge; la API no ejecuta nada.

    La API valida la FORMA; el estado lo valida el worker, que es quien lo conoce.
    """
    if cuerpo.tipo != "crear_novela":
        if cuerpo.novela_id is None:
            raise HTTPException(status_code=422, detail="Falta novela_id")
        if lectura.novela(con, cuerpo.novela_id) is None:
            raise HTTPException(status_code=404, detail=f"No existe la novela {cuerpo.novela_id}")

    if cuerpo.tipo == "crear_novela" and cuerpo.payload.get("brief") is not None:
        # RF3-PER-05: un brief bien formado pero incompleto o contradictorio devuelve 422 con
        # las dos listas en `detalle`, para que el cliente sepa que preguntar. Uno mal formado
        # cae en la validacion general de abajo.
        try:
            analisis = analizar(Brief.model_validate(cuerpo.payload["brief"]))
        except ValidationError:
            analisis = None
        if analisis is not None and not analisis.completo:
            raise BriefNoValido(analisis)

    modelo = PAYLOADS.get(cuerpo.tipo)
    if modelo is not None:
        try:
            modelo.model_validate(cuerpo.payload)
        except ValidationError as exc:
            # Un payload mal formado es 422, nunca un 500 (RF2-API-04).
            detalle = "; ".join(
                f"{'.'.join(str(x) for x in e['loc']) or 'payload'}: {e['msg']}"
                for e in exc.errors()
            )
            raise HTTPException(status_code=422, detail=detalle) from exc

    cur = con.execute(
        "INSERT INTO intencion (tipo, novela_id, payload) VALUES (?,?,?)",
        (cuerpo.tipo, cuerpo.novela_id, json.dumps(cuerpo.payload, ensure_ascii=False)),
    )
    con.commit()
    return IntencionEncolada(id=int(cur.lastrowid or 0), tipo=cuerpo.tipo, estado="pendiente")


@app.get("/intenciones/{intencion_id}", response_model=EstadoIntencion)
def ver_intencion(intencion_id: int, con: Con) -> EstadoIntencion:
    fila = con.execute("SELECT * FROM intencion WHERE id = ?", (intencion_id,)).fetchone()
    if fila is None:
        raise HTTPException(status_code=404, detail=f"No existe la intencion {intencion_id}")
    return EstadoIntencion(
        id=int(fila["id"]), tipo=str(fila["tipo"]), estado=str(fila["estado"]),
        motivo=fila["motivo"], resultado=_json(fila["resultado"]),
        creado_en=str(fila["creado_en"]),
    )


# --- Novelas -------------------------------------------------------------------------------------


@app.get("/novelas", response_model=list[NovelaResumen])
def listar_novelas(con: Con) -> list[NovelaResumen]:
    return [
        NovelaResumen(
            id=int(f["id"]), titulo=str(f["titulo"]), genero=str(f["genero"]),
            subgenero_dominante=f["subgenero_dominante"], estado=f["estado"],
            capitulos_completados=int(f["capitulos_completados"] or 0),
            creado_en=str(f["creado_en"]),
        )
        for f in con.execute(
            """
            SELECT n.*, e.estado, e.capitulos_completados
            FROM novela n LEFT JOIN ejecucion e ON e.novela_id = n.id
            ORDER BY n.id DESC
            """
        )
    ]


@app.get("/novelas/{novela_id}", response_model=NovelaDetalle)
def ver_novela(novela_id: int, con: Con) -> NovelaDetalle:
    n = _novela_o_404(con, novela_id)
    estilo = lectura.estilo(con, novela_id)
    return NovelaDetalle(
        novela=NovelaCanon.model_validate(n),
        restricciones=lectura.restricciones(con, novela_id),
        estilo=EstiloNarrativo.model_validate(estilo) if estilo else None,
    )


@app.get("/novelas/{novela_id}/ejecucion", response_model=Ejecucion)
def ver_ejecucion(novela_id: int, con: Con) -> Ejecucion:
    """El estado completo. Esta es la verdad; el stream solo avisa de que cambio."""
    _novela_o_404(con, novela_id)
    e = lectura.ejecucion(con, novela_id)
    if e is None:
        raise HTTPException(status_code=404, detail="La novela no tiene ejecucion")
    return Ejecucion(
        novela_id=novela_id, estado=str(e["estado"]), fase=e["fase"],
        capitulo_actual=e["capitulo_actual"], intento_actual=int(e["intento_actual"] or 1),
        capitulos_completados=int(e["capitulos_completados"] or 0),
        total_capitulos=lectura.total_capitulos(con, novela_id),
        parada_abierta_id=e["parada_abierta_id"], ultimo_error=e["ultimo_error"],
        actualizado_en=str(e["actualizado_en"]),
    )


# --- Canon y estructura ---------------------------------------------------------------------------

_ENTIDADES = {
    "mundo": "mundo", "sistemas": "sistema_tecnologico", "lugares": "lugar",
    "personajes": "personaje", "facciones": "faccion", "amenaza": "amenaza",
    "objetos": "objeto", "temas": "tema", "motivos": "motivo", "eventos": "evento",
}


_MODELOS_CANON: dict[str, type[BaseModel]] = {
    "mundo": MundoCanon, "sistemas": SistemaCanon, "lugares": LugarCanon,
    "personajes": PersonajeCanon, "facciones": FaccionCanon, "amenaza": AmenazaCanon,
    "objetos": ObjetoCanon, "temas": TemaCanon, "motivos": MotivoCanon, "eventos": EventoCanon,
}
_COLUMNAS_JSON = ("sistemas_criticos", "reglas")


@app.get("/novelas/{novela_id}/canon/{entidad}", response_model=list[EntidadCanon])
def ver_canon(novela_id: int, entidad: str, con: Con) -> list[BaseModel]:
    _novela_o_404(con, novela_id)
    tabla = _ENTIDADES.get(entidad)
    if tabla is None:
        raise HTTPException(
            status_code=404,
            detail=f"Entidad desconocida. Validas: {', '.join(sorted(_ENTIDADES))}",
        )
    modelo = _MODELOS_CANON[entidad]
    filas: list[BaseModel] = []
    for f in con.execute(f"SELECT * FROM {tabla} WHERE novela_id = ? ORDER BY id", (novela_id,)):
        datos: dict[str, Any] = {**dict(f), "entidad": entidad}
        for columna in _COLUMNAS_JSON:
            if columna in datos:
                datos[columna] = _json(datos[columna]) or []
        filas.append(modelo.model_validate(datos))
    return filas


@app.get("/novelas/{novela_id}/estructura", response_model=Estructura)
def ver_estructura(novela_id: int, con: Con) -> Estructura:
    _novela_o_404(con, novela_id)
    actos = [
        Acto.model_validate(dict(f)) for f in con.execute(
            "SELECT numero, funcion_narrativa FROM acto WHERE novela_id = ? ORDER BY numero",
            (novela_id,),
        )
    ]
    capitulos: list[Capitulo] = []
    for f in con.execute(
        "SELECT numero, objetivo, estado, resumen FROM capitulo WHERE novela_id = ? "
        "ORDER BY numero", (novela_id,)
    ):
        escenas = [
            Escena(
                orden=int(e["orden"]), pov=str(e["pov_nombre"]), lugar=str(e["lugar_nombre"]),
                reparto=list(e["reparto"]), objetivo=str(e["objetivo"]),
                conflicto=str(e["conflicto"]), valor_inicial=str(e["valor_inicial"]),
                valor_final=str(e["valor_final"]), tension=e["tension"],
                analepsis=bool(e["analepsis"]),
            )
            for e in lectura.escenas_del_capitulo(con, novela_id, int(f["numero"]))
        ]
        capitulos.append(Capitulo(
            numero=int(f["numero"]), objetivo=f["objetivo"], estado=str(f["estado"]),
            resumen=f["resumen"], escenas=escenas,
        ))
    return Estructura(
        actos=actos,
        capitulos=capitulos,
        hilos=[Hilo.model_validate(h) for h in lectura.hilos(con, novela_id)],
        siembras=[
            SiembraVista.model_validate(dict(f)) for f in con.execute(
                "SELECT * FROM siembra_vigente WHERE novela_id = ?", (novela_id,)
            )
        ],
        puntos_de_giro=[
            PuntoDeGiro.model_validate(dict(f)) for f in con.execute(
                "SELECT g.* FROM punto_de_giro g JOIN hilo h ON h.id = g.hilo_id "
                "WHERE h.novela_id = ? ORDER BY g.posicion", (novela_id,)
            )
        ],
    )


# --- Manuscrito -----------------------------------------------------------------------------------


@app.get("/novelas/{novela_id}/capitulos/{numero}", response_model=CapituloTexto)
def ver_capitulo(
    novela_id: int, numero: int, con: Con, version: int | None = None
) -> CapituloTexto:
    _novela_o_404(con, novela_id)
    if version is None:
        fila = con.execute(
            """
            SELECT cc.* FROM capitulo_compilado cc JOIN capitulo c ON c.id = cc.capitulo_id
            WHERE cc.novela_id = ? AND c.numero = ? AND cc.estado = 'vigente'
            ORDER BY cc.version DESC LIMIT 1
            """,
            (novela_id, numero),
        ).fetchone()
    else:
        fila = con.execute(
            """
            SELECT cc.* FROM capitulo_compilado cc JOIN capitulo c ON c.id = cc.capitulo_id
            WHERE cc.novela_id = ? AND c.numero = ? AND cc.version = ?
            """,
            (novela_id, numero, version),
        ).fetchone()
    if fila is None:
        raise HTTPException(status_code=404, detail=f"El capitulo {numero} no esta escrito")
    return CapituloTexto(
        numero=numero, version=int(fila["version"]), palabras=int(fila["palabras"]),
        texto=str(fila["texto"]),
    )


@app.get("/novelas/{novela_id}/capitulos/{numero}/versiones", response_model=list[VersionEscena])
def ver_versiones(novela_id: int, numero: int, con: Con) -> list[VersionEscena]:
    _novela_o_404(con, novela_id)
    return [
        VersionEscena.model_validate(dict(f)) for f in con.execute(
            """
            SELECT e.orden AS escena, et.version, et.estado, et.origen, et.intento,
                   et.palabras, et.creado_en, et.llamada_modelo_id
            FROM escena_texto et
            JOIN escena e   ON e.id = et.escena_id
            JOIN capitulo c ON c.id = e.capitulo_id
            WHERE et.novela_id = ? AND c.numero = ?
            ORDER BY e.orden, et.version
            """,
            (novela_id, numero),
        )
    ]


# --- Estado ---------------------------------------------------------------------------------------


@app.get("/novelas/{novela_id}/hechos", response_model=Pagina[Hecho])
def ver_hechos(
    novela_id: int,
    con: Con,
    sujeto: str | None = None,
    categoria: str | None = None,
    capitulo: int | None = None,
    limite: Annotated[int, Query(ge=1, le=500)] = 100,
    desde: Annotated[int, Query(ge=0)] = 0,
) -> Pagina[Hecho]:
    _novela_o_404(con, novela_id)
    condiciones = ["h.novela_id = ?"]
    params: list[Any] = [novela_id]
    if sujeto:
        condiciones.append("LOWER(h.sujeto_nombre) LIKE LOWER(?)")
        params.append(f"%{sujeto}%")
    if categoria:
        condiciones.append("h.categoria = ?")
        params.append(categoria)
    if capitulo is not None:
        condiciones.append("c.numero = ?")
        params.append(capitulo)
    donde = " AND ".join(condiciones)

    total = int(con.execute(
        f"SELECT COUNT(*) FROM hecho h JOIN escena e ON e.id = h.escena_id "
        f"JOIN capitulo c ON c.id = e.capitulo_id WHERE {donde}", params
    ).fetchone()[0])
    filas = con.execute(
        f"""
        SELECT h.id, h.sujeto_tipo, h.sujeto_nombre, h.atributo, h.valor, h.categoria,
               NOT EXISTS (SELECT 1 FROM hecho_revocacion r WHERE r.hecho_id = h.id)
                   AS vigente,
               c.numero AS capitulo_origen
        FROM hecho h JOIN escena e ON e.id = h.escena_id
        JOIN capitulo c ON c.id = e.capitulo_id
        WHERE {donde} ORDER BY h.id LIMIT ? OFFSET ?
        """,
        [*params, limite, desde],
    ).fetchall()
    return Pagina(total=total, items=[
        Hecho(
            id=int(f["id"]), sujeto_tipo=str(f["sujeto_tipo"]), sujeto_nombre=f["sujeto_nombre"],
            atributo=str(f["atributo"]), valor=str(f["valor"]), categoria=str(f["categoria"]),
            capitulo_origen=f["capitulo_origen"], vigente=bool(f["vigente"]),
        ) for f in filas
    ])


@app.get("/novelas/{novela_id}/conocimiento", response_model=list[ConocimientoVista])
def ver_conocimiento(
    novela_id: int, con: Con, personaje: str | None = None,
    limite: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[ConocimientoVista]:
    _novela_o_404(con, novela_id)
    sql = """
        SELECT p.nombre AS personaje, h.sujeto_nombre, h.atributo, h.valor, ec.postura, ec.via,
               c.numero AS capitulo
        FROM estado_conocimiento ec
        JOIN personaje p ON p.id = ec.personaje_id
        JOIN hecho h     ON h.id = ec.hecho_id
        JOIN escena e    ON e.id = ec.escena_id
        JOIN capitulo c  ON c.id = e.capitulo_id
        WHERE ec.novela_id = ?
    """
    params: list[Any] = [novela_id]
    if personaje:
        sql += " AND LOWER(p.nombre) LIKE LOWER(?)"
        params.append(f"%{personaje}%")
    sql += " ORDER BY p.nombre, c.numero LIMIT ?"
    params.append(limite)
    return [ConocimientoVista.model_validate(dict(f)) for f in con.execute(sql, params)]


# --- Paradas --------------------------------------------------------------------------------------


@app.get("/novelas/{novela_id}/paradas", response_model=list[Parada])
def listar_paradas(novela_id: int, con: Con) -> list[Parada]:
    _novela_o_404(con, novela_id)
    return [
        Parada(
            id=int(f["id"]), tipo=str(f["tipo"]), capitulo=f["capitulo"], intento=f["intento"],
            estado=str(f["estado"]), resolucion=f["resolucion"], creado_en=str(f["creado_en"]),
        )
        for f in con.execute(
            "SELECT p.* FROM parada p JOIN ejecucion e ON e.id = p.ejecucion_id "
            "WHERE e.novela_id = ? ORDER BY p.id DESC",
            (novela_id,),
        )
    ]


@app.get("/novelas/{novela_id}/paradas/{parada_id}", response_model=Parada)
def ver_parada(novela_id: int, parada_id: int, con: Con) -> Parada:
    _novela_o_404(con, novela_id)
    f = con.execute(
        "SELECT p.* FROM parada p JOIN ejecucion e ON e.id = p.ejecucion_id "
        "WHERE e.novela_id = ? AND p.id = ?",
        (novela_id, parada_id),
    ).fetchone()
    if f is None:
        raise HTTPException(status_code=404, detail=f"No existe la parada {parada_id}")
    return Parada(
        id=int(f["id"]), tipo=str(f["tipo"]), capitulo=f["capitulo"], intento=f["intento"],
        estado=str(f["estado"]), resolucion=f["resolucion"], creado_en=str(f["creado_en"]),
        informe=_json(f["informe"]),
    )


# --- Traza ----------------------------------------------------------------------------------------


@app.get(
    "/novelas/{novela_id}/traza/llamadas", response_model=list[Llamada],
    response_model_exclude_unset=True,
)
def ver_llamadas(
    novela_id: int, con: Con, completo: bool = False,
    limite: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[Llamada]:
    """Por defecto sin el prompt: son decenas de miles de tokens por fila."""
    columnas = (
        "id, agente, capitulo, intento, tokens_entrada, tokens_salida, duracion_ms, "
        "exit_code, estado, creado_en"
    )
    if completo:
        columnas += ", sistema, entrada, salida_cruda, tokens_entrada_por_bloque, metadatos"
    llamadas: list[Llamada] = []
    for f in con.execute(
        f"SELECT {columnas} FROM llamada_modelo WHERE novela_id = ? ORDER BY id DESC LIMIT ?",
        (novela_id, limite),
    ):
        datos: dict[str, Any] = dict(f)
        for columna in ("tokens_entrada_por_bloque", "metadatos"):
            if columna in datos:
                datos[columna] = _json(datos[columna])
        llamadas.append(Llamada.model_validate(datos))
    return llamadas


class RespuestaSSE(StreamingResponse):
    """El stream de eventos: `text/event-stream`, no JSON, tambien en el contrato OpenAPI."""

    media_type = "text/event-stream"


@app.get(
    "/novelas/{novela_id}/eventos", response_class=RespuestaSSE,
    responses={200: {"description": "Un evento de traza por linea `data:`, con su `id:`."}},
)
async def stream_eventos(novela_id: int, request: Request) -> StreamingResponse:
    """SSE. Un evento avisa de que algo cambio; el cliente reconsulta.

    Si el cliente trae `Last-Event-ID`, se retoma justo despues. La reconexion es un caso de
    primera clase: esto va a estar abierto horas.
    """
    cabecera = request.headers.get("last-event-id") or request.query_params.get("last_event_id")
    try:
        ultimo = int(cabecera) if cabecera else 0
    except ValueError:
        ultimo = 0
    ruta = request.app.state.cfg.db_path

    async def generar() -> AsyncIterator[str]:
        desde = ultimo
        silencio = 0.0
        while True:
            if await request.is_disconnected():
                break
            con = db.conectar(ruta, solo_lectura=True)
            try:
                filas = con.execute(
                    "SELECT id, tipo, payload, creado_en FROM traza_evento "
                    "WHERE novela_id = ? AND id > ? ORDER BY id LIMIT 200",
                    (novela_id, desde),
                ).fetchall()
            finally:
                con.close()

            for f in filas:
                desde = int(f["id"])
                datos = json.dumps(
                    {"tipo": f["tipo"], "creado_en": f["creado_en"],
                     "payload": _json(f["payload"])},
                    ensure_ascii=False,
                )
                yield f"id: {desde}\nevent: {f['tipo']}\ndata: {datos}\n\n"
                silencio = 0.0

            await asyncio.sleep(1.0)
            silencio += 1.0
            if silencio >= KEEPALIVE_SEGUNDOS:
                silencio = 0.0
                yield ": keepalive\n\n"

    return RespuestaSSE(
        generar(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# --- Errores --------------------------------------------------------------------------------------


class BriefNoValido(Exception):
    """Un brief bien formado al que le falta algo o que se contradice (RF3-PER-05)."""

    def __init__(self, analisis: Analisis) -> None:
        super().__init__(str(BriefIncompleto(analisis)))
        self.analisis = analisis


@app.exception_handler(BriefNoValido)
async def error_brief(_: Request, exc: BriefNoValido) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=Error(
            codigo="brief_incompleto", mensaje=str(exc),
            detalle=json.dumps(exc.analisis.como_dict(), ensure_ascii=False),
        ).model_dump(),
    )


@app.exception_handler(HTTPException)
async def error_http(_: Request, exc: HTTPException) -> JSONResponse:
    codigos: dict[int, str] = {404: "no_encontrado", 422: "peticion_invalida"}
    return JSONResponse(
        status_code=exc.status_code,
        content=Error(
            codigo=codigos.get(exc.status_code, "error"), mensaje=str(exc.detail)
        ).model_dump(),
    )


@app.exception_handler(sqlite3.OperationalError)
async def error_sqlite(_: Request, exc: sqlite3.OperationalError) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content=Error(
            codigo="base_ocupada",
            mensaje="La base de datos no acepta la operacion ahora mismo.",
            detalle=str(exc),
        ).model_dump(),
    )


def main() -> int:
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
