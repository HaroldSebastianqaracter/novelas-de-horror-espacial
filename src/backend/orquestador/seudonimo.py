"""Los nombres del encargo no salen de la maquina (specs/spec3.md, RF3-SEU-01 a 05).

Antes de cada llamada a un agente del pipeline, los nombres del brief (destinatario, quien
regala y allegados), enteros y por partes, se cambian por etiquetas reversibles; al volver la
respuesta, las etiquetas se cambian por los nombres, escritos como en el brief. Asi el modelo
trabaja con `[DESTINATARIO_NOMBRE]` y el grafo, las puertas y la lectura siguen viendo el nombre
real. La busqueda es la del seudonimizador de Langfuse (plegado, fronteras, mayusculas), que ya
paso seis revisiones; lo que cambia es que aqui cada forma tiene su propia etiqueta, para poder
deshacerla.
"""

from __future__ import annotations

import re
from typing import Any, cast

from compartido.brief import Brief
from compartido.tipos import como_dict, como_lista

from .observabilidad import Seudonimizador, partes_del_nombre, plegar


class Mascara:
    """El cambio de nombres por etiquetas y su vuelta, para un brief."""

    def __init__(self, brief: Brief | None) -> None:
        self._originales: dict[str, str] = {}
        self._roles: list[str] = []
        formas: dict[str, tuple[str, bool]] = {}
        if brief is not None:
            for base, nombre, firma, rol in _grupos(brief):
                self._anadir(formas, base, nombre, firma=firma, rol=rol)
        # Las formas largas antes que sus partes: «Marta Ibanez» entera, no «[X] Ibanez».
        self._busqueda = Seudonimizador.desde_formas(sorted(
            ((f, e, libre) for f, (e, libre) in formas.items()),
            key=lambda t: len(t[0]), reverse=True,
        ))
        self._vuelta = re.compile(
            r"\[(" + "|".join(re.escape(e[1:-1]) for e in self._originales) + r")\]",
            re.IGNORECASE,
        ) if self._originales else None

    def _anadir(self, formas: dict[str, tuple[str, bool]], base: str, nombre: str, *,
                firma: bool, rol: str) -> None:
        plegado, posiciones, _ = plegar(nombre)
        completo = " ".join(plegado.split())
        palabras = completo.split(" ")
        partes = partes_del_nombre(nombre, firma=firma)
        candidatas = dict(partes)
        if completo and completo not in candidatas:
            candidatas[completo] = True
        extra = 2
        propias = 0
        for forma, libre in sorted(candidatas.items(), key=lambda kv: plegado.find(kv[0])):
            if forma in formas:
                continue  # el primero que la reclama se la queda (el destinatario manda)
            if forma == completo:
                etiqueta = f"[{base}]"
            elif len(palabras) > 1 and forma == palabras[0]:
                etiqueta = f"[{base}_NOMBRE]"
            elif len(palabras) > 1 and forma == palabras[-1]:
                etiqueta = f"[{base}_APELLIDO]"
            else:
                etiqueta = f"[{base}_{extra}]"
                extra += 1
            original = _original(nombre, plegado, posiciones, forma)
            if original is None:
                continue
            formas[forma] = (etiqueta, libre)
            self._originales[etiqueta] = original
            propias += 1
        if propias:
            self._roles.append(rol)
        elif completo in formas:
            # La misma persona que otra del encargo (quien regala suele ser un allegado): la
            # leyenda lo dice, en vez de dar una etiqueta que no existe.
            self._roles.append(f"{rol.split(':', 1)[1].strip().rstrip('.').capitalize()}: es "
                               f"{formas[completo][0]}.")

    @property
    def vacia(self) -> bool:
        return not self._originales

    def ocultar(self, texto: str) -> str:
        """El texto con cada nombre del encargo cambiado por su etiqueta."""
        return self._busqueda.texto(texto)

    def restaurar(self, valor: Any) -> Any:
        """La respuesta del agente con cada etiqueta del encargo cambiada por el nombre.

        Recorre textos, listas y diccionarios, tambien sus claves. Una etiqueta que no es del
        encargo se queda como esta: la ve la puerta 4 (`etiqueta_en_la_prosa`).
        """
        if self._vuelta is None:
            return valor
        if isinstance(valor, str):
            return self._vuelta.sub(
                lambda m: self._originales.get(f"[{m.group(1).upper()}]", m.group(0)), valor
            )
        if isinstance(valor, dict):
            return {self.restaurar(str(k)): self.restaurar(v)
                    for k, v in como_dict(cast(object, valor)).items()}
        if isinstance(valor, list):
            return [self.restaurar(v) for v in como_lista(cast(object, valor))]
        return valor

    def leyenda(self) -> str:
        """Lo que el agente tiene que saber de las etiquetas, sin ningun nombre."""
        if self.vacia:
            return ""
        etiquetas = ", ".join(self._originales)
        return (
            "## NOMBRES DEL ENCARGO\n\n"
            "Los nombres reales del encargo no se envian: van como etiquetas entre corchetes, y "
            "el sistema pone los nombres al guardar. Escribe la etiqueta tal cual, con sus "
            "corchetes, cada vez que iria ese nombre, y nunca inventes otro nombre ni otra "
            "etiqueta para esas personas. `_NOMBRE` es el nombre de pila (el que se usa casi "
            "siempre en la prosa), `_APELLIDO` el apellido, y la etiqueta sin sufijo el nombre "
            "completo.\n\n" + "\n".join(f"- {r}" for r in self._roles)
            + f"\n\nEtiquetas validas: {etiquetas}."
        )


def _grupos(brief: Brief) -> list[tuple[str, str, bool, str]]:
    """(etiqueta base, nombre, es firma, papel sin nombres) de cada persona del encargo."""
    grupos: list[tuple[str, str, bool, str]] = []
    d = brief.destinatario
    if d.nombre:
        pron = {"el": "el", "ella": "ella", "neutro": "neutro"}.get(d.pronombres or "", "")
        grupos.append(("DESTINATARIO", d.nombre, False,
                       "[DESTINATARIO]: quien recibe el regalo y protagoniza la novela"
                       + (f" (pronombres: {pron})" if pron else "") + "."))
    for i, a in enumerate(brief.allegados, start=1):
        grupos.append((f"ALLEGADO_{i}", a.nombre, False,
                       f"[ALLEGADO_{i}]: allegado del destinatario ({a.relacion})."))
    # Despues de los allegados: quien regala suele ser uno de ellos, y entonces lleva su etiqueta.
    if brief.quien_regala:
        grupos.append(("QUIEN_REGALA", brief.quien_regala, True,
                       "[QUIEN_REGALA]: quien hace el regalo y firma la dedicatoria."))
    return grupos


def _original(nombre: str, plegado: str, posiciones: list[int], forma: str) -> str | None:
    """La forma, escrita como en el brief (con sus tildes y mayusculas)."""
    patron = r"\s+".join(re.escape(p) for p in forma.split(" "))
    m = re.search(patron, plegado)
    if m is None or m.end() == 0:
        return None
    return nombre[posiciones[m.start()]:posiciones[m.end() - 1] + 1]
