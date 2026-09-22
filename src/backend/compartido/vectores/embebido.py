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
from typing import Protocol, runtime_checkable

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

    def codificar(self, textos: list[str]) -> list[list[float]]: ...


def _normalizar(v: list[float]) -> list[float]:
    norma = math.sqrt(sum(x * x for x in v))
    return v if norma == 0 else [x / norma for x in v]


class EmbedderHash:
    """Embedding deterministico por hash. No entiende nada; sirve para los tests.

    Existe para que la suite pueda ejercitar el camino del indice sin descargar un modelo
    de cientos de megas, no para recuperar nada util.
    """

    def __init__(self, dimension: int = 384) -> None:
        self.nombre = "hash-384"
        self.dimension = dimension

    def codificar(self, textos: list[str]) -> list[list[float]]:
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

    def codificar(self, textos: list[str]) -> list[list[float]]:
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
        self.dimension = len(next(iter(self._modelo.embed(["dimension"]))))

    def codificar(self, textos: list[str]) -> list[list[float]]:
        return [_normalizar([float(x) for x in v]) for v in self._modelo.embed(textos)]


def construir(modelo: str, *, permitir_hash: bool = True) -> Embedder:
    """Devuelve el embedder que pide la configuracion, cayendo con elegancia.

    `modelo` puede ser un nombre de modelo o uno de los alias 'model2vec', 'fastembed', 'hash'.
    Si el backend pedido no esta instalado y `permitir_hash`, cae al deterministico: el
    indice es derivado y ninguna decision del pipeline depende de el (RF-CTX-09).
    """
    if modelo in ("hash", "hash-384"):
        return EmbedderHash()

    intentos: list[type[EmbedderModel2Vec] | type[EmbedderFastEmbed]]
    nombre: str | None = modelo

    if modelo == "model2vec":
        intentos, nombre = [EmbedderModel2Vec], None
    elif modelo == "fastembed":
        intentos, nombre = [EmbedderFastEmbed], None
    elif "potion" in modelo or "model2vec" in modelo:
        intentos = [EmbedderModel2Vec]
    else:
        intentos = [EmbedderFastEmbed, EmbedderModel2Vec]

    ultimo: Exception | None = None
    for clase in intentos:
        try:
            return clase(nombre)
        except Exception as exc:  # noqa: BLE001 - se prueba el siguiente backend
            ultimo = exc

    if permitir_hash:
        return EmbedderHash()
    raise EmbeddingNoDisponible(f"Ningun backend de embeddings disponible: {ultimo}")
