"""Modelos de embeddings locales, intercambiables (RF-CTX-10).

Claude Code escribe y juzga, pero no produce embeddings: el indice necesita un modelo aparte.
Se elige local y en CPU para no introducir la clave de proveedor que la eleccion de Claude
Code precisamente evita.

UNA ADVERTENCIA QUE DECIDE LA ELECCION: la novela es en castellano. Los modelos pequenos mas
citados —`BAAI/bge-small-en-v1.5`, `all-MiniLM-L6-v2`, `minishlab/potion-base-8M`— son de
INGLES; sobre texto espanol degradan bastante. Por eso los valores por defecto de aqui son
las variantes multilingues de esas mismas familias.

Tres backends, de mas ligero a mas capaz:

| Backend     | Modelo por defecto                   | Peso    |
|-------------|--------------------------------------|---------|
| `model2vec` | `minishlab/potion-multilingual-128M` | ~120 MB |
| `fastembed` | `intfloat/multilingual-e5-small`     | ~470 MB |
| `hash`      | -                                    | 0       |

`model2vec` da embeddings estaticos: rapidisimos en CPU, pero sin contexto. `fastembed` va
por ONNX, entiende el contexto y recupera mejor a cambio de peso. `hash` es deterministico y
sin dependencias: existe solo para los tests.

Cambiar de modelo obliga a reconstruir el indice entero, y eso es barato porque el indice es
derivado: se borra y se reconstruye desde el texto y los hechos sin perder nada.
"""

from __future__ import annotations

import hashlib
import math
import struct
from typing import Literal, Protocol, runtime_checkable

# Los modelos de la familia e5 se entrenan con prefijos y los esperan: 'query:' para lo que
# se busca y 'passage:' para lo indexado. Sin ellos la recuperacion empeora de forma
# apreciable, y es un fallo silencioso: el indice sigue devolviendo resultados, solo que
# peores. Por eso el tipo de texto es parte de la interfaz y no una decision del llamante.
Tipo = Literal["pasaje", "consulta"]

PREFIJOS_E5: dict[str, str] = {"pasaje": "passage: ", "consulta": "query: "}

MODELO_POR_DEFECTO: dict[str, str] = {
    "model2vec": "minishlab/potion-multilingual-128M",
    "fastembed": "intfloat/multilingual-e5-small",
    "hash": "hash-384",
}


class EmbeddingNoDisponible(Exception):
    """No hay backend de embeddings instalado o el modelo no carga."""


@runtime_checkable
class Embedder(Protocol):
    nombre: str
    dimension: int

    def codificar(self, textos: list[str], *, tipo: Tipo = "pasaje") -> list[list[float]]: ...


def _normalizar(v: list[float]) -> list[float]:
    norma = math.sqrt(sum(x * x for x in v))
    return v if norma == 0 else [x / norma for x in v]


class EmbedderHash:
    """Embedding deterministico por hash. No entiende nada; sirve para los tests.

    Existe para que la suite pueda ejercitar el camino del indice sin descargar un modelo
    de cientos de megas, no para recuperar nada util.
    """

    def __init__(self, dimension: int = 384) -> None:
        self.nombre = f"hash-{dimension}"
        self.dimension = dimension

    def codificar(self, textos: list[str], *, tipo: Tipo = "pasaje") -> list[list[float]]:
        del tipo  # el hash no distingue consulta de pasaje
        salida: list[list[float]] = []
        for texto in textos:
            vector = [0.0] * self.dimension
            for palabra in texto.lower().split():
                digest = hashlib.blake2b(palabra.encode("utf-8"), digest_size=8).digest()
                indice = struct.unpack("<Q", digest)[0] % self.dimension
                vector[indice] += 1.0
            salida.append(_normalizar(vector))
        return salida


class EmbedderModel2Vec:
    """Embeddings estaticos. Muy rapidos en CPU y sin ONNX de por medio."""

    def __init__(self, modelo: str | None = None) -> None:
        try:
            from model2vec import StaticModel  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover
            raise EmbeddingNoDisponible("model2vec no esta instalado.") from exc
        self.nombre = modelo or MODELO_POR_DEFECTO["model2vec"]
        self._modelo = StaticModel.from_pretrained(self.nombre)
        self.dimension = int(self._modelo.dim)

    def codificar(self, textos: list[str], *, tipo: Tipo = "pasaje") -> list[list[float]]:
        del tipo  # los embeddings estaticos no usan prefijos
        return [_normalizar([float(x) for x in v]) for v in self._modelo.encode(textos)]


class EmbedderFastEmbed:
    """ONNX en CPU, con contexto. Mejor recuperacion a cambio de mas peso."""

    def __init__(self, modelo: str | None = None) -> None:
        try:
            from fastembed import TextEmbedding  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover
            raise EmbeddingNoDisponible("fastembed no esta instalado.") from exc
        self.nombre = modelo or MODELO_POR_DEFECTO["fastembed"]
        self._modelo = TextEmbedding(model_name=self.nombre)
        self.usa_prefijos = "e5" in self.nombre.lower()
        self.dimension = len(next(iter(self._modelo.embed(["dimension"]))))

    def codificar(self, textos: list[str], *, tipo: Tipo = "pasaje") -> list[list[float]]:
        if self.usa_prefijos:
            textos = [PREFIJOS_E5[tipo] + t for t in textos]
        return [_normalizar([float(x) for x in v]) for v in self._modelo.embed(textos)]


def _backend_de(modelo: str) -> str:
    if modelo in ("hash", "hash-384"):
        return "hash"
    if modelo == "model2vec" or "potion" in modelo or "model2vec" in modelo:
        return "model2vec"
    return "fastembed"


def construir(modelo: str, *, permitir_hash: bool = False) -> Embedder:
    """Devuelve el embedder que pide la configuracion, cayendo con elegancia.

    `modelo` es un nombre de modelo o uno de los alias 'model2vec', 'fastembed', 'hash'.

    Si el backend pedido no arranca, se prueba el otro CON SU PROPIO MODELO por defecto: un
    nombre de modelo no es intercambiable entre backends, y pasarle a model2vec el nombre de
    un modelo de fastembed solo produce un segundo fallo.

    El hash solo se usa si se pide expresamente (RF2-CTX-10): un indice por hash recupera
    por coincidencia de palabras, y caer a el en silencio mezclaba en la misma tabla vectores
    de dos espacios distintos. Si ningun modelo carga, se lanza `EmbeddingNoDisponible` y el
    indice queda sin usar, con el motivo en la traza. Cual se uso de verdad queda en
    `indice_estado`.
    """
    pedido = _backend_de(modelo)
    if pedido == "hash":
        return EmbedderHash()

    clases: dict[str, type[EmbedderModel2Vec] | type[EmbedderFastEmbed]] = {
        "model2vec": EmbedderModel2Vec,
        "fastembed": EmbedderFastEmbed,
    }
    # Primero el pedido con el nombre dado; despues el otro con el suyo.
    orden: list[tuple[str, str | None]] = [
        (pedido, None if modelo == pedido else modelo),
        *[(b, None) for b in clases if b != pedido],
    ]

    ultimo: Exception | None = None
    for backend, nombre in orden:
        try:
            return clases[backend](nombre)
        except Exception as exc:  # se prueba el siguiente backend
            ultimo = exc

    if permitir_hash:
        return EmbedderHash()
    raise EmbeddingNoDisponible(f"Ningun backend de embeddings disponible: {ultimo}")
