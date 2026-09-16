"""Fichas de personajes: aplicación de deltas y registro de sujetos (RF-04.1, RF-06.1, RF-06.2)."""

from __future__ import annotations

from app.schemas.mundo import Mundo
from app.schemas.outline import Outline
from app.schemas.personajes import FichaPersonajes, Personaje
from app.state.continuidad import SUJETO_MUNDO


def sujetos_conocidos(fichas: FichaPersonajes, mundo: Mundo | None) -> set[str]:
    """RF-06.1: claves de personajes.json + locaciones de mundo.json + el literal "mundo". Vocabulario, no memoria."""
    registro = set(fichas.root.keys())
    if mundo is not None:
        registro.update(mundo.locaciones.keys())
    registro.add(SUJETO_MUNDO)
    return registro


def claves_no_previstas(delta_personajes: dict[str, Personaje], registro: set[str]) -> list[str]:
    """EX-08: claves de delta.personajes ausentes del registro de sujetos."""
    return [clave for clave in delta_personajes if clave not in registro]


def aplicar_delta(fichas: FichaPersonajes, delta_personajes: dict[str, Personaje], n: int) -> FichaPersonajes:
    """RF-06.2: reemplaza los estados, une los secretos con los previos y fija ultima_aparicion = N.

    Las claves deben existir en las fichas (EX-08 se decide antes, con `claves_no_previstas`).
    """
    nuevas = dict(fichas.root)
    for clave, cambio in delta_personajes.items():
        previa = nuevas.get(clave)
        secretos_previos = list(previa.secretos_que_conoce) if previa else []
        secretos = secretos_previos + [s for s in cambio.secretos_que_conoce if s not in secretos_previos]
        nuevas[clave] = Personaje(
            estado_fisico=cambio.estado_fisico,
            estado_psicologico=cambio.estado_psicologico,
            secretos_que_conoce=secretos,
            ultima_aparicion=n,
        )
    return FichaPersonajes(nuevas)


def sin_ficha(fichas: FichaPersonajes, outline: Outline) -> list[str]:
    """RF-04.1: personajes del outline que no tienen ficha."""
    return [p for p in outline.personajes_mencionados() if p not in fichas.root]


def fichas_presentes(fichas: FichaPersonajes, nombres: list[str]) -> dict[str, Personaje]:
    return {nombre: fichas.root[nombre] for nombre in nombres if nombre in fichas.root}
