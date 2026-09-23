"""Exportacion a Langfuse (specs/spec3.md, 3.4: RF3-OBS-03 a RF3-OBS-10).

La base es la unica fuente. Cada llamada a un agente ya esta en `llamada_modelo` con su
entrada, su salida, sus tokens y el coste que declaro Claude Code; cada puerta, en
`resultado_puerta`. Este modulo los convierte en eventos de la API de ingestion de Langfuse y
los envia. El primer harness exportaba desde ficheros de registro y fallo de tres formas: no
veia el coste de quien orquestaba, un modelo sin precio salia gratis y los identificadores
chocaban entre novelas. Aqui el coste viene del puerto, llamada a llamada, y los
identificadores son UUID deterministas de la novela y de la fila de origen: reenviar actualiza,
no duplica.

Nada de esto puede parar el pipeline: `exportar_a_langfuse` del pipeline se traga cualquier
fallo y lo deja en la traza como `langfuse_fallo`.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol, cast
from urllib.parse import quote

import httpx

from compartido.brief import Brief
from compartido.db import transaccion
from compartido.grafo import lectura
from compartido.tipos import como_dict, como_lista
from config import Config

#: Espacio de nombres de los UUID deterministas. Cambiarlo duplicaria todo lo ya enviado.
ESPACIO = uuid.UUID("5e1b7c3a-8f2d-4b6e-9a41-0c7d2f9e6b13")

TIEMPO_MAXIMO_S = 10.0
#: Langfuse admite lotes de unos 3,5 MB; se deja margen.
LOTE_MAXIMO_BYTES = 3_000_000

#: El rol de cada agente en el vocabulario del enunciado (plan de entrega, «Ya cubierto»).
ROL_DEL_AGENTE: dict[str, str] = {
    "arquitecto": "planner", "mundo": "planner", "elenco": "planner", "estructura": "planner",
    "escaleta": "planner", "redaccion": "writer", "oficio": "editor", "continuidad": "editor",
    "extraccion": "extractor", "entrevistador": "entrevistador",
}


class ErrorLangfuse(Exception):
    """Langfuse no acepto el envio, o parte de el."""


def id_estable(*partes: object) -> str:
    """UUID v5 de las partes: el mismo origen da siempre el mismo identificador."""
    return str(uuid.uuid5(ESPACIO, "/".join(str(p) for p in partes)))


def clave_de_novela(con: sqlite3.Connection, novela_id: int) -> str:
    """Identidad de la novela entre bases: su id y el momento en que se creo.

    El id solo no basta: `novela.db`, `novela_real.db` y cada base temporal tienen su novela
    1, y con el id solo se pisarian en Langfuse. Es la colision del primer harness (commit
    `b87775d`). La fecha de creacion no cambia nunca y distingue dos novelas 1 cualesquiera.
    """
    fila = con.execute("SELECT creado_en FROM novela WHERE id = ?", (novela_id,)).fetchone()
    creado = str(fila[0]) if fila is not None else ""
    return f"{novela_id}-" + hashlib.sha256(f"{novela_id}|{creado}".encode()).hexdigest()[:10]


def sesion_de(clave: str) -> str:
    return f"storymaker-novela-{clave}"


def _iso(momento: object) -> str:
    """Las fechas de SQLite (`datetime('now')`, UTC) en ISO 8601 con zona."""
    texto = str(momento or "").strip()
    if not texto:
        return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    return texto.replace(" ", "T") + ("" if texto.endswith("Z") else "Z")


# --- Seudonimizacion (RF3-OBS-07) ---------------------------------------------------------------


#: Apostrofos rectos y tipograficos, y las letras modificadoras que Unicode recomienda como
#: apostrofo («Oʼ», U+02BC): todos pliegan a «'», que no es letra.
_APOSTROFOS = frozenset({"'", "’", "‘", "`", "´", "ʼ", "ʹ", "ʻ", "ʽ", "′", "＇"})
#: Letras sin descomposicion Unicode que se leen como otra: «Łukasz» y «Lukasz» son el mismo
#: nombre para quien lo lee.
_ESPECIALES: dict[str, str] = {
    "ł": "l", "ø": "o", "đ": "d", "ħ": "h", "ı": "i", "ŀ": "l", "æ": "ae", "œ": "oe",
    "þ": "th", "ð": "d",
}
#: Palabras de un nombre o de una firma que sueltas no identifican a nadie: las particulas de
#: un nombre compuesto («Maria de los Angeles» no convierte en etiqueta cada «los» del texto) y
#: lo que acompana a un nombre en `quien_regala` («Andres, tu hermano»).
_NO_IDENTIFICAN = frozenset({
    "de", "del", "la", "las", "los", "el", "y", "da", "das", "do", "dos", "di", "van", "von",
    "der", "den", "le", "les", "tus", "mis", "sus", "con", "para", "por", "que", "una", "uno",
    "unos", "unas", "todos", "todas", "tu", "mi", "su", "hermano", "hermana", "hermanos",
    "hermanas", "padre", "madre", "padres", "abuelo", "abuela", "abuelos", "tio", "tia",
    "tios", "primo", "prima", "primos", "hijo", "hija", "hijos", "amigo", "amiga", "amigos",
    "amigas", "novio", "novia", "esposo", "esposa", "marido", "mujer", "familia", "querido",
    "querida", "queridos",
})
#: Letras de un nombre del brief, con los apostrofos de dentro («o'hara») o sin ellos.
_TOKEN_CON_APOSTROFO = re.compile(r"[^\W\d_]+(?:'[^\W\d_]+)*")
_TOKEN = re.compile(r"[^\W\d_]+")


def _descartable(c: str) -> bool:
    """Lo que no se ve: formato (bidi, anchos cero, guion blando) y marcas, tambien las que
    `combining()` no detecta (el CGJ, los selectores de variante)."""
    return unicodedata.category(c) in {"Mn", "Me", "Cf"}


def _plegar_caracter(c: str) -> str:
    """Un caracter sin marcas y en minusculas; vacio si no se ve."""
    if c in _APOSTROFOS:
        return "'"
    # NFKD antes de bajar a minusculas: «𝐌» o «ℳ» no tienen minuscula hasta ser «M».
    base = unicodedata.normalize("NFKD", unicodedata.normalize("NFKD", c).casefold())
    return "".join(
        "'" if x in _APOSTROFOS else _ESPECIALES.get(x, x) for x in base if not _descartable(x)
    )


def _plegar(texto: str) -> tuple[str, list[int], set[int]]:
    """El texto plegado; para cada caracter plegado, su posicion en el original; y donde habia
    un caracter de formato quitado, que puede separar dos palabras («Marta​Ibanez»).

    Plegar el texto entero, y no solo el nombre, es lo que hace que cualquier marca casen en
    los dos lados: «João» en el brief y «Joao» o «João» en la prosa, «Dvořák», «Ştefan».
    """
    plegado: list[str] = []
    posiciones: list[int] = []
    suaves: set[int] = set()
    formato_antes = False
    for i, c in enumerate(texto):
        trozo = _plegar_caracter(c)
        if not trozo:
            formato_antes = formato_antes or unicodedata.category(c) == "Cf"
            continue
        if formato_antes:
            suaves.add(len(plegado))
            formato_antes = False
        for x in trozo:
            plegado.append(x)
            posiciones.append(i)
    return "".join(plegado), posiciones, suaves


class Seudonimizador:
    """Sustituye los nombres del encargo por etiquetas antes de que salgan de la maquina.

    El destinatario, quien regala y cada allegado, completos y por partes de tres letras o mas
    que identifiquen a alguien (ni particulas ni «tu hermano»). El nombre del brief se trocea
    por cualquier caracter que no sea letra. Se compara sobre el texto plegado (sin marcas, sin
    lo que no se ve, sin distinguir mayusculas) y como palabra completa: una letra pegada la
    hace otra palabra, salvo que medie un caracter de formato o un cambio de minuscula a
    mayuscula («regaloParaMarta»); un digito o un guion bajo no la hacen otra palabra. Tambien
    en las claves de los diccionarios (`nivel_confianza` va por personaje). El mapa no se envia
    nunca.
    """

    def __init__(self, brief: Brief | None) -> None:
        self._formas: list[tuple[str, str]] = []
        if brief is None:
            return
        grupos: list[tuple[str, str]] = []
        if brief.destinatario.nombre:
            grupos.append(("[DESTINATARIO]", brief.destinatario.nombre))
        if brief.quien_regala:
            grupos.append(("[QUIEN_REGALA]", brief.quien_regala))
        grupos.extend(
            (f"[ALLEGADO_{i}]", a.nombre) for i, a in enumerate(brief.allegados, start=1)
        )
        # El primero que reclama una forma se la queda: el destinatario manda sobre un
        # allegado que comparta apellido.
        asignadas: dict[str, str] = {}
        for etiqueta, nombre in grupos:
            plegado = _plegar(nombre)[0]
            completo = " ".join(plegado.split())
            # «O'Hara» entero antes que «Hara»: si no, la prosa deja «O'[X]».
            partes = [
                p for p in (*_TOKEN_CON_APOSTROFO.findall(plegado), *_TOKEN.findall(plegado))
                if len(p) >= 3 and p not in _NO_IDENTIFICAN
            ]
            for forma in (completo, *partes):
                if forma:
                    asignadas.setdefault(forma, etiqueta)
        # Las formas largas antes que sus partes: «Marta Ibanez» entera, no «[X] Ibanez».
        self._formas = sorted(asignadas.items(), key=lambda par: len(par[0]), reverse=True)

    def texto(self, texto: str) -> str:
        if not self._formas or not texto:
            return texto
        plegado, posiciones, suaves = _plegar(texto)

        def frontera(k: int) -> bool:
            if k in (0, len(plegado)) or k in suaves:
                return True
            if not (plegado[k - 1].isalpha() and plegado[k].isalpha()):
                return True
            antes, despues = posiciones[k - 1], posiciones[k]
            return antes != despues and texto[antes].islower() and texto[despues].isupper()

        # Varios espacios seguidos del texto casan con uno del nombre.
        tramos: list[tuple[int, int, str]] = []
        for forma, etiqueta in self._formas:
            patron = r"\s+".join(re.escape(p) for p in forma.split(" "))
            tramos.extend(
                (m.start(), m.end(), etiqueta)
                for m in re.finditer(patron, plegado)
                if frontera(m.start()) and frontera(m.end())
            )
        if not tramos:
            return texto
        # En coordenadas del texto original, ganando el mas largo (las formas ya van de mas
        # larga a mas corta). Un tramo contenido en otro ya elegido sobra; dos que se solapan
        # solo en parte (un caracter que pliega a varios, «℀») se funden: descartar uno dejaria
        # a la vista el trozo que no cubre el otro.
        elegidos: list[tuple[int, int, str]] = []
        for ini, fin, etiqueta in tramos:
            desde = posiciones[ini]
            hasta = posiciones[fin - 1] + 1
            # Las marcas sueltas que siguen al ultimo caracter (texto en NFD) son del nombre.
            while hasta < len(texto) and _plegar_caracter(texto[hasta]) == "":
                hasta += 1
            if any(d <= desde and hasta <= h for d, h, _ in elegidos):
                continue
            solapados = [t for t in elegidos if t[0] < hasta and desde < t[1]]
            for t in solapados:
                elegidos.remove(t)
            partes = sorted([*solapados, (desde, hasta, etiqueta)])
            elegidos.append((
                min(t[0] for t in partes), max(t[1] for t in partes),
                "".join(dict.fromkeys(t[2] for t in partes)),
            ))
        salida = texto
        for desde, hasta, etiqueta in sorted(elegidos, reverse=True):
            salida = salida[:desde] + etiqueta + salida[hasta:]
        return unicodedata.normalize("NFC", salida)

    def valor(self, valor: Any) -> Any:
        if isinstance(valor, str):
            return self.texto(valor)
        if isinstance(valor, dict):
            # Dos claves que seudonimizan a la misma etiqueta no se pisan.
            salida: dict[str, Any] = {}
            for k, v in como_dict(cast(object, valor)).items():
                clave = base = self.texto(str(k))
                n = 2
                while clave in salida:
                    clave = f"{base} #{n}"
                    n += 1
                salida[clave] = self.valor(v)
            return salida
        if isinstance(valor, list):
            return [self.valor(v) for v in como_lista(cast(object, valor))]
        return valor


# --- Cliente ------------------------------------------------------------------------------------


class Cliente(Protocol):
    def enviar(self, eventos: list[dict[str, Any]]) -> None: ...
    def version_de_prompt(self, nombre: str, etiqueta: str) -> int | None: ...
    def crear_prompt(self, nombre: str, texto: str, etiqueta: str) -> int: ...
    def comprobar(self) -> None: ...


def _trozos(eventos: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Lotes por debajo del tamano maximo; un evento enorme viaja solo."""
    salida: list[list[dict[str, Any]]] = []
    actual: list[dict[str, Any]] = []
    tamano = 0
    for evento in eventos:
        peso = len(json.dumps(evento, ensure_ascii=False, default=str).encode("utf-8"))
        if actual and tamano + peso > LOTE_MAXIMO_BYTES:
            salida.append(actual)
            actual, tamano = [], 0
        actual.append(evento)
        tamano += peso
    if actual:
        salida.append(actual)
    return salida


class ClienteHTTP:
    """La API publica de Langfuse con httpx: ingestion por lotes y gestion de prompts.

    Se descarto el SDK oficial: con la API y unos identificadores propios basta, no anade
    dependencias al backend y deja probar el cliente con un transporte simulado.
    """

    def __init__(
        self, host: str, publica: str, secreta: str, *,
        tiempo_s: float = TIEMPO_MAXIMO_S, transporte: httpx.BaseTransport | None = None,
    ) -> None:
        # El limite es por operacion (conectar, leer...), no por envio: con Langfuse caido, cada
        # envio espera como mucho unos segundos por lote antes de rendirse.
        self._http = httpx.Client(
            base_url=host.rstrip("/"), auth=(publica, secreta),
            timeout=httpx.Timeout(tiempo_s, connect=min(tiempo_s, 5.0)), transport=transporte,
        )

    @staticmethod
    def _revisar(respuesta: httpx.Response, que: str) -> None:
        if respuesta.status_code >= 400:
            raise ErrorLangfuse(f"{que}: HTTP {respuesta.status_code} {respuesta.text[:300]}")

    def enviar(self, eventos: list[dict[str, Any]]) -> None:
        for lote in _trozos(eventos):
            respuesta = self._http.post("/api/public/ingestion", json={"batch": lote})
            self._revisar(respuesta, "ingestion")
            try:
                errores = como_lista(como_dict(respuesta.json()).get("errors"))
            except ValueError:
                errores = []
            if errores:
                # Un lote a medias no se marca: se reenvia entero y los ids evitan duplicados.
                raise ErrorLangfuse(
                    f"Langfuse rechazo {len(errores)} de {len(lote)} eventos: "
                    + json.dumps(errores[:3], ensure_ascii=False)[:500]
                )

    def version_de_prompt(self, nombre: str, etiqueta: str) -> int | None:
        respuesta = self._http.get(
            f"/api/public/v2/prompts/{quote(nombre, safe='')}", params={"label": etiqueta}
        )
        if respuesta.status_code == 404:
            return None
        self._revisar(respuesta, "prompt")
        return int(como_dict(respuesta.json())["version"])

    def crear_prompt(self, nombre: str, texto: str, etiqueta: str) -> int:
        respuesta = self._http.post("/api/public/v2/prompts", json={
            "name": nombre, "prompt": texto, "type": "text", "labels": [etiqueta],
            "config": {"huella": etiqueta},
        })
        self._revisar(respuesta, "crear prompt")
        return int(como_dict(respuesta.json())["version"])

    def comprobar(self) -> None:
        self._revisar(self._http.get("/api/public/projects"), "comprobar claves")

    def cerrar(self) -> None:
        self._http.close()


# --- Exportador ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class Informe:
    eventos: int
    filas: int


def _evento(tipo: str, cuerpo: dict[str, Any]) -> dict[str, Any]:
    # El sobre lleva un id nuevo cada vez: Langfuse puede descartar un evento con un id de sobre
    # ya visto, y un reenvio con el cuerpo cambiado tiene que actualizar. Lo que no duplica es
    # el id del cuerpo, que es determinista.
    return {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "type": tipo,
        "body": {k: v for k, v in cuerpo.items() if v is not None},
    }


def _salida_estructurada(cruda: object) -> Any:
    """Lo que contesto el agente: `structured_output` del sobre de Claude Code, o el texto."""
    if not cruda:
        return None
    try:
        sobre = json.loads(str(cruda))
    except json.JSONDecodeError:
        return str(cruda)
    sobre = como_dict(sobre)
    if "structured_output" in sobre:
        return sobre["structured_output"]
    return sobre.get("result", sobre)


def _unidad_de_llamada(capitulo: object) -> str:
    return "planificacion" if capitulo is None else f"capitulo-{capitulo}"


def _unidad_de_puerta(puerta: int, capitulo: object) -> str:
    if puerta in (1, 2) or capitulo is None:
        return "cierre" if puerta == 5 else "planificacion"
    return f"capitulo-{capitulo}"


def _inicio_de_unidad(con: sqlite3.Connection, novela_id: int, unidad: str) -> object:
    """El primer momento de la unidad en la base: la fecha de su traza, estable entre envios."""
    if unidad == "entrevista":
        sql, params = "SELECT MIN(creado_en) FROM entrevista WHERE novela_id = ?", (novela_id,)
    elif unidad == "cierre":
        sql = "SELECT MIN(creado_en) FROM resultado_puerta WHERE novela_id = ? AND puerta = 5"
        params = (novela_id,)
    elif unidad == "planificacion":
        sql = ("SELECT MIN(creado_en) FROM llamada_modelo WHERE novela_id = ? "
               "AND capitulo IS NULL")
        params = (novela_id,)
    else:
        sql = "SELECT MIN(creado_en) FROM llamada_modelo WHERE novela_id = ? AND capitulo = ?"
        params = (novela_id, int(unidad.removeprefix("capitulo-")))
    fila = con.execute(sql, params).fetchone()
    return fila[0] if fila is not None else None


_TODAS = "SELECT * FROM {tabla} t WHERE t.novela_id = :novela {extra} ORDER BY t.id"
#: Lo que el worker no ha enviado todavia. El comando no lo usa: abre en solo lectura bases que
#: pueden ser anteriores a la migracion 008 y no tener `langfuse_envio`.
_PENDIENTES = """
SELECT * FROM {tabla} t
WHERE t.novela_id = :novela {extra}
  AND NOT EXISTS (SELECT 1 FROM langfuse_envio e WHERE e.tabla = '{tabla}' AND e.fila_id = t.id)
ORDER BY t.id
"""


class Exportador:
    """Lo nuevo de una novela, en eventos de Langfuse. `marcar` lo usa solo el worker."""

    def __init__(self, cliente: Cliente, *, marcar: bool = True) -> None:
        self.cliente = cliente
        self.marcar = marcar
        self._prompts: dict[tuple[str, str], int] = {}

    def _pendientes(self, con: sqlite3.Connection, tabla: str, novela_id: int,
                    extra: str = "") -> list[sqlite3.Row]:
        sql = _PENDIENTES if self.marcar else _TODAS
        return con.execute(sql.format(tabla=tabla, extra=extra), {"novela": novela_id}).fetchall()

    def _version_de_prompt(self, agente: str, sistema: str) -> tuple[str, int] | None:
        """RF3-OBS-06: la skill como prompt versionado por la huella de su texto."""
        if not sistema:
            return None
        nombre = f"storymaker-{agente}"
        etiqueta = "sha-" + hashlib.sha256(sistema.encode("utf-8")).hexdigest()[:12]
        clave = (nombre, etiqueta)
        if clave not in self._prompts:
            version = self.cliente.version_de_prompt(nombre, etiqueta)
            if version is None:
                version = self.cliente.crear_prompt(nombre, sistema, etiqueta)
            self._prompts[clave] = version
        return nombre, self._prompts[clave]

    def exportar(self, con: sqlite3.Connection, novela_id: int) -> Informe:
        seud = Seudonimizador(lectura.brief(con, novela_id))
        clave = clave_de_novela(con, novela_id)
        eventos: list[dict[str, Any]] = []
        filas: list[tuple[str, int]] = []
        trazas: dict[str, str] = {}

        def traza(unidad: str) -> str:
            tid = id_estable(clave, "unidad", unidad)
            if unidad not in trazas:
                trazas[unidad] = tid
                eventos.append(_evento("trace-create", {
                    "id": tid, "name": unidad, "sessionId": sesion_de(clave),
                    # De la base y no del lote: reenviar la traza no le cambia la fecha.
                    "timestamp": _iso(_inicio_de_unidad(con, novela_id, unidad)),
                    "metadata": {"novela_id": novela_id, "unidad": unidad},
                    "tags": ["storymaker"],
                }))
            return tid

        terminadas = self._pendientes(
            con, "llamada_modelo", novela_id, "AND t.estado <> 'en_curso'"
        )
        for f in terminadas:
            generacion = self._generacion(f, clave, seud, traza)
            eventos.append(_evento("generation-create", generacion))
            filas.append(("llamada_modelo", int(f["id"])))

        for f in self._pendientes(con, "resultado_puerta", novela_id):
            eventos.extend(self._puerta(f, clave, seud, traza))
            filas.append(("resultado_puerta", int(f["id"])))

        for f in self._pendientes(con, "entrevista", novela_id):
            eventos.extend(self._entrevista(f, clave, traza))
            filas.append(("entrevista", int(f["id"])))

        if not eventos:
            return Informe(0, 0)
        self.cliente.enviar(eventos)
        if self.marcar:
            with transaccion(con):
                con.executemany(
                    "INSERT OR IGNORE INTO langfuse_envio (tabla, fila_id, novela_id) "
                    "VALUES (?, ?, ?)",
                    [(tabla, fila, novela_id) for tabla, fila in filas],
                )
        return Informe(len(eventos), len(filas))

    def _generacion(self, f: sqlite3.Row, clave: str, seud: Seudonimizador,
                    traza: Any) -> dict[str, Any]:
        try:
            meta = como_dict(json.loads(f["metadatos"] or "{}"))
        except json.JSONDecodeError:
            meta = {}
        agente = str(f["agente"])
        # El puerto falso no gasta: su coste es cero, no desconocido.
        coste = 0.0 if meta.get("puerto") == "falso" else meta.get("total_cost_usd")
        uso = como_dict(meta.get("usage"))
        modelos = list(como_dict(meta.get("modelUsage")))
        estado = str(f["estado"])
        coste_desconocido = estado == "ok" and coste is None
        nivel = "DEFAULT" if estado == "ok" else "ERROR"
        if coste_desconocido:
            nivel = "WARNING"  # parecer gratis es peor que no contarlo (RF3-OBS-03)
        detalle_uso = {
            "input": f["tokens_entrada"] or uso.get("input_tokens"),
            "output": f["tokens_salida"] or uso.get("output_tokens"),
            "cache_read_input_tokens": uso.get("cache_read_input_tokens"),
            "cache_creation_input_tokens": uso.get("cache_creation_input_tokens"),
        }
        prompt = self._version_de_prompt(agente, str(f["sistema"] or ""))
        return {
            "id": id_estable(clave,"llamada_modelo", f["id"]),
            "traceId": traza(_unidad_de_llamada(f["capitulo"])),
            "name": agente,
            "startTime": _iso(f["creado_en"]),
            "endTime": _iso(f["terminado_en"] or f["creado_en"]),
            "model": modelos[0] if modelos else None,
            "input": seud.texto(str(f["entrada"] or "")),
            "output": seud.valor(_salida_estructurada(f["salida_cruda"])),
            "usageDetails": {k: int(v) for k, v in detalle_uso.items() if v is not None},
            "costDetails": {"total": float(coste)} if coste is not None else None,
            "level": nivel,
            "statusMessage": None if estado == "ok" else estado,
            "promptName": prompt[0] if prompt else None,
            "promptVersion": prompt[1] if prompt else None,
            "metadata": {
                "agente": agente, "rol": ROL_DEL_AGENTE.get(agente, agente),
                "capitulo": f["capitulo"], "intento": f["intento"], "estado": estado,
                "num_turns": meta.get("num_turns"), "duracion_ms": f["duracion_ms"],
                "llamada_id": f["id"], "coste_desconocido": coste_desconocido or None,
            },
        }

    def _puerta(self, f: sqlite3.Row, clave: str, seud: Seudonimizador,
                traza: Any) -> list[dict[str, Any]]:
        try:
            detalle = como_dict(json.loads(f["detalle"] or "{}"))
        except json.JSONDecodeError:
            detalle = {}
        conflictos = [como_dict(c) for c in como_lista(detalle.get("conflictos"))]
        bloqueantes = [c for c in conflictos if not c.get("aviso")]
        avisos = [c for c in conflictos if c.get("aviso")]
        puerta = int(f["puerta"])
        veredicto = str(f["veredicto"])
        tid = traza(_unidad_de_puerta(puerta, f["capitulo"]))
        span_id = id_estable(clave,"resultado_puerta", f["id"])
        salida = [_evento("span-create", {
            "id": span_id, "traceId": tid, "name": f"puerta-{puerta}",
            "startTime": _iso(f["creado_en"]), "endTime": _iso(f["creado_en"]),
            "level": "ERROR" if veredicto == "falla" else ("WARNING" if avisos else "DEFAULT"),
            "metadata": seud.valor({
                "veredicto": veredicto, "capitulo": f["capitulo"], "intento": f["intento"],
                "conflictos": [
                    {"comprobacion": c.get("comprobacion"), "aviso": bool(c.get("aviso")),
                     "descripcion": c.get("descripcion")}
                    for c in conflictos
                ],
            }),
        })]

        def score(nombre: str, valor: float, tipo: str, comentario: str | None = None) -> None:
            salida.append(_evento("score-create", {
                "id": id_estable(clave,"resultado_puerta", f["id"], nombre),
                "traceId": tid, "observationId": span_id, "name": nombre,
                "value": valor, "dataType": tipo,
                "comment": seud.texto(comentario) if comentario else None,
            }))

        score(f"puerta_{puerta}", 0.0 if veredicto == "falla" else 1.0, "BOOLEAN")
        score(f"puerta_{puerta}_bloqueantes", float(len(bloqueantes)), "NUMERIC")
        score(f"puerta_{puerta}_avisos", float(len(avisos)), "NUMERIC")
        vistas: set[str] = set()
        for c in conflictos:
            nombre = str(c.get("comprobacion") or "")
            if nombre and nombre not in vistas:
                vistas.add(nombre)
                score(nombre, 0.0, "BOOLEAN", str(c.get("descripcion") or ""))
        return salida

    def _entrevista(self, f: sqlite3.Row, clave: str, traza: Any) -> list[dict[str, Any]]:
        """Las llamadas de la entrevista solo guardan metricas: van sin texto (RF3-OBS-04)."""
        try:
            transcripcion = como_dict(json.loads(f["transcripcion"] or "{}"))
        except json.JSONDecodeError:
            transcripcion = {}
        tid = traza("entrevista")
        salida: list[dict[str, Any]] = []
        for i, llamada in enumerate(map(como_dict, como_lista(transcripcion.get("llamadas")))):
            coste = llamada.get("coste_usd")
            uso = {"input": llamada.get("tokens_entrada"), "output": llamada.get("tokens_salida")}
            salida.append(_evento("generation-create", {
                "id": id_estable(clave,"entrevista", f["id"], i),
                "traceId": tid, "name": "entrevistador",
                "startTime": _iso(f["creado_en"]), "endTime": _iso(f["creado_en"]),
                "usageDetails": {k: int(v) for k, v in uso.items() if v is not None},
                "costDetails": {"total": float(coste)} if coste is not None else None,
                "metadata": {"agente": "entrevistador", "rol": "entrevistador", "turno": i,
                             "duracion_ms": llamada.get("duracion_ms")},
            }))
        return salida


def exportador_desde(cfg: Config) -> Exportador | None:
    """El exportador del worker, o None si no hay claves (RF3-OBS-01) o si el puerto es el falso.

    Una demo o un test con el puerto falso no gasta nada y no tiene nada que medir: con las
    claves en `.env`, sus trazas solo ensuciarian el proyecto del autor.
    """
    if not cfg.langfuse_activo or cfg.puerto == "falso":
        return None
    return Exportador(ClienteHTTP(
        cfg.langfuse_host, str(cfg.langfuse_public_key), str(cfg.langfuse_secret_key),
    ))
