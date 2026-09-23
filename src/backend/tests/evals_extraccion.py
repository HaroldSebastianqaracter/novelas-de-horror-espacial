"""Puntuador determinista de la cobertura del extractor (spec2, fase 10; fila 38 de spec1).

Compara una salida del extractor con un capitulo anotado a mano y da el recall por tipo de
registro: cuantos de los registros que la prosa afirma aparecen en la salida. Sin juez: un
registro esperado casa con uno extraido si coinciden la escena, las referencias (por
contencion sobre texto normalizado, para no castigar «el capitan Oyelaran» frente a
«Oyelaran») y, si las lleva, cada grupo de claves, del que basta una alternativa en el texto
del registro (atributo, valor, cita o descripcion). El nombre exacto del atributo es libre:
lo que se mide es si el hecho se capturo, no como se llamo.

Cada registro extraido casa con un solo esperado, para que un hecho no cuente dos veces.

Los capitulos de la pasada real traen ademas los valores vigentes antes del capitulo, y con
ellos se cuentan las contradicciones falsas: hechos que repiten un sujeto y atributo ya
registrados con otro valor y sin declarar la sustitucion. Son lo que la puerta 3 tomaria por
contradiccion, y la causa de casi todas las paradas en falso de aquella pasada.
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
        if campo not in esperado:
            continue
        clave, dado = normalizar(esperado[campo]), normalizar(str(extraido.get(destino) or ""))
        # Un nombre no reconocido casa por contencion («el capitan Oyelaran»). Una referencia al
        # canon, por prefijo: «Anillo de habitacion» abrevia «Anillo de habitacion, sectores 1 a
        # 8», pero «Sala de lechos» no es «Lecho 2 de la sala de lechos».
        if not (clave in dado if campo == "nombre" else dado.startswith(clave)):
            return False
    texto = normalizar(" ".join(str(extraido.get(c) or "") for c in _TEXTO))
    return all(any(normalizar(alt) in texto for alt in grupo)
               for grupo in esperado.get("claves", []))


def puntuar(salida: dict[str, Any], esperado: dict[str, list[dict[str, Any]]]) -> dict[str, Recall]:
    """Recall por tipo de registro, y el global bajo la clave `total`."""
    por_tipo: dict[str, Recall] = {}
    for tipo, registros in esperado.items():
        por_tipo[tipo] = Recall(_emparejar(registros, list(salida.get(tipo) or [])),
                                len(registros))
    por_tipo["total"] = Recall(
        sum(r.acertados for r in por_tipo.values()), sum(r.esperados for r in por_tipo.values())
    )
    return por_tipo


def _emparejar(esperados: list[dict[str, Any]], extraidos: list[dict[str, Any]]) -> int:
    """El maximo de esperados que casan, cada extraido con uno solo (caminos de aumento).

    Con un emparejamiento voraz, un extraido que casa con dos esperados podia gastarse en el
    primero y dejar sin pareja al segundo aunque hubiera otro extraido para el.
    """
    candidatos = [[j for j, x in enumerate(extraidos) if _casa(e, x)] for e in esperados]
    pareja: dict[int, int] = {}

    def aumentar(i: int, vistos: set[int]) -> bool:
        for j in candidatos[i]:
            if j in vistos:
                continue
            vistos.add(j)
            if j not in pareja or aumentar(pareja[j], vistos):
                pareja[j] = i
                return True
        return False

    return sum(aumentar(i, set()) for i in range(len(esperados)))


def informe(recall: dict[str, Recall]) -> str:
    return "\n".join(
        f"{tipo:<26} {r.acertados:>2}/{r.esperados:<2} {r.valor:.2f}" for tipo, r in recall.items()
    )


def falsas_contradicciones(
    salida: dict[str, Any], vigentes: list[dict[str, str]]
) -> list[dict[str, Any]]:
    """Hechos que chocan con un valor vigente sin declarar `supersede_a`.

    Cuenta lo que la puerta 3 veria como contradiccion. Que sea FALSA lo dice el dataset: en
    los capitulos anotados, la prosa no cambia ninguno de esos datos, solo los vuelve a decir.
    """
    valor = {(normalizar(v["sujeto"]), normalizar(v["atributo"])): normalizar(v["valor"])
             for v in vigentes}
    choques: list[dict[str, Any]] = []
    for h in salida.get("hechos") or []:
        clave = (normalizar(str(h.get("sujeto_ref", ""))), normalizar(str(h.get("atributo", ""))))
        if clave in valor and not h.get("supersede_a") and (
            normalizar(str(h.get("valor", ""))) != valor[clave]
        ):
            choques.append(h)
    return choques
