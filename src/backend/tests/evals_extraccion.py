"""Puntuador determinista de la cobertura del extractor (spec2, fase 10; fila 38 de spec1).

Compara una salida del extractor con un capitulo anotado a mano y da el recall por tipo de
registro: cuantos de los registros que la prosa afirma aparecen en la salida. Sin juez: un
registro esperado casa con uno extraido si coinciden la escena, las referencias (por
contencion sobre texto normalizado, para no castigar «el capitan Oyelaran» frente a
«Oyelaran») y, si las lleva, cada grupo de claves, del que basta una alternativa en el texto
del registro (atributo, valor, cita o descripcion). El nombre exacto del atributo es libre:
lo que se mide es si el hecho se capturo, no como se llamo.

Cada registro extraido casa con un solo esperado, para que un hecho no cuente dos veces.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from compartido.grafo import normalizar

DATOS = Path(__file__).parent / "datos"

#: Campo del registro esperado -> campo de la salida del extractor.
_CAMPOS = {
    "sujeto": "sujeto_ref", "personaje": "personaje_ref", "objeto": "objeto_ref",
    "ubicacion": "ubicacion_ref", "condicion": "condicion", "nombre": "nombre",
}
_TEXTO = ("atributo", "valor", "cita", "descripcion")


@dataclass(frozen=True)
class Recall:
    acertados: int
    esperados: int

    @property
    def valor(self) -> float:
        return self.acertados / self.esperados if self.esperados else 1.0


def cargar(nombre: str = "extraccion_capitulo_1.json") -> dict[str, Any]:
    return json.loads((DATOS / nombre).read_text(encoding="utf-8"))


def _casa(esperado: dict[str, Any], extraido: dict[str, Any]) -> bool:
    if extraido.get("escena_orden") != esperado["escena_orden"]:
        return False
    for campo, destino in _CAMPOS.items():
        if campo in esperado and normalizar(esperado[campo]) not in normalizar(
            str(extraido.get(destino) or "")
        ):
            return False
    texto = normalizar(" ".join(str(extraido.get(c) or "") for c in _TEXTO))
    return all(any(normalizar(alt) in texto for alt in grupo)
               for grupo in esperado.get("claves", []))


def puntuar(salida: dict[str, Any], esperado: dict[str, list[dict[str, Any]]]) -> dict[str, Recall]:
    """Recall por tipo de registro, y el global bajo la clave `total`."""
    por_tipo: dict[str, Recall] = {}
    for tipo, registros in esperado.items():
        libres = list(salida.get(tipo) or [])
        acertados = 0
        for reg in registros:
            for i, extraido in enumerate(libres):
                if _casa(reg, extraido):
                    acertados += 1
                    del libres[i]
                    break
        por_tipo[tipo] = Recall(acertados, len(registros))
    por_tipo["total"] = Recall(
        sum(r.acertados for r in por_tipo.values()), sum(r.esperados for r in por_tipo.values())
    )
    return por_tipo


def informe(recall: dict[str, Recall]) -> str:
    return "\n".join(
        f"{tipo:<26} {r.acertados:>2}/{r.esperados:<2} {r.valor:.2f}" for tipo, r in recall.items()
    )
