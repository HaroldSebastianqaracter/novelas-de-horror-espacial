"""El cambio del lector como dato (specs/spec3.md, 3.8).

Lo comparten el interprete, que lo produce; el revisor, que lo aplica a la prosa; y el
orquestador, que lo aplica al canon. Aqui no se escribe nada en la base: solo la forma del
cambio y las operaciones de texto que los tres tienen que hacer exactamente igual.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from compartido.grafo.escritura import normalizar
from compartido.texto import PALABRA_DE_NOMBRE, partes_de_nombre

TipoCambio = Literal["renombrar", "cambiar_hecho"]

#: La entidad como la nombra la API (el payload del lector) y como la nombra el grafo.
TABLAS_DE_ENTIDAD: dict[str, str] = {
    "personajes": "personaje", "lugares": "lugar", "objetos": "objeto",
}

#: Las categorias de hecho cuyo valor es un literal que la prosa repite (RF3-BIB-01).
_CATEGORIAS_LITERALES = frozenset({"nombre", "fecha", "distancia"})
_LETRAS_MINIMAS = 3


@dataclass(frozen=True)
class Cambio:
    """Un cambio del canon: renombrar una entidad o cambiar el valor de un hecho."""

    tipo: TipoCambio
    antes: str
    despues: str
    tabla: str | None = None          # renombrar: personaje, lugar u objeto
    entidad_id: int | None = None
    hecho_id: int | None = None       # cambiar_hecho
    sujeto: str | None = None
    atributo: str | None = None
    categoria: str | None = None
    #: Renombrar: los nombres de OTRAS entidades que comparten una palabra con el viejo («Pedro
    #: Reyes» al renombrar a «Reyes»). No se tocan ni cuentan como nombre viejo que queda.
    protegidos: tuple[str, ...] = ()

    def como_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def desde_dict(cls, datos: dict[str, Any]) -> Cambio:
        campos: dict[str, Any] = {k: datos.get(k) for k in cls.__dataclass_fields__}
        campos["protegidos"] = tuple(campos.get("protegidos") or ())
        return cls(**campos)

    @property
    def literal(self) -> bool:
        """Si lo viejo es un literal que se puede buscar en la prosa (RF3-CAM-09).

        Un nombre siempre. Un hecho, con las categorias y las cifras de RF3-BIB-01: «castano
        corto» o «alta» aparecen en cualquier descripcion y no se pueden contar.
        """
        if self.tipo == "renombrar":
            return True
        cifras = any(c.isdigit() for c in self.antes)
        buscable = len(normalizar(self.antes)) >= _LETRAS_MINIMAS or cifras
        return buscable and (self.categoria in _CATEGORIAS_LITERALES or cifras)

    def _compartidas(self) -> set[str]:
        """Las palabras del nombre viejo que tambien salen en el nombre de otra entidad."""
        return {normalizar(p) for n in self.protegidos for p in partes_de_nombre(n)}

    def mapa(self) -> dict[str, str]:
        """Que se sustituye por que al renombrar (`mapa_de_nombres`), sin lo que es de otros.

        Una palabra del nombre viejo que tambien nombra a otra entidad no se sustituye suelta:
        renombrar «Nina Reyes» a «Nina Soto» cuando existe «Reyes» cambia «Nina Reyes» y deja
        «Reyes», que es el otro (validador de 58e70f0). El nombre entero se sustituye siempre.
        """
        compartidas = self._compartidas()
        return {
            k: v for k, v in mapa_de_nombres(self.antes, self.despues).items()
            if k == self.antes or normalizar(k) not in compartidas
        }

    def partes_viejas(self) -> list[str]:
        """Lo del nombre viejo que no puede quedar en la prosa (`partes_viejas`), sin lo de otros.

        Si todas sus palabras las comparte con otra entidad, queda el nombre entero, que se
        busca como frase: «Nina Reyes» cuenta, «Reyes» a secas no.
        """
        compartidas = self._compartidas()
        partes = [p for p in partes_viejas(self.antes, self.despues)
                  if p == self.antes or normalizar(p) not in compartidas]
        return partes or ([self.antes] if normalizar(self.antes) != normalizar(self.despues)
                          else [])

    def describir(self) -> str:
        if self.tipo == "renombrar":
            return f"«{self.antes}» ({self.tabla}) pasa a llamarse «{self.despues}»."
        return (
            f"El hecho «{self.sujeto} · {self.atributo}» pasa de «{self.antes}» a "
            f"«{self.despues}»."
        )


# --- Renombrar: el mapa de palabras y la sustitucion ---------------------------------------


def mapa_de_nombres(viejo: str, nuevo: str) -> dict[str, str]:
    """Que se sustituye por que al renombrar, de lo mas largo a lo mas corto.

    El nombre entero por el entero. Si los dos tienen varias palabras, la primera por la
    primera y la ultima por la ultima cuando cambian: «Tomás Ruiz» a «Tomás Vidal» sustituye
    «Ruiz» por «Vidal» y deja «Tomás». Con una sola palabra en el viejo, solo el nombre entero.
    """
    mapa = {viejo: nuevo}
    pv, pn = partes_de_nombre(viejo), partes_de_nombre(nuevo)
    if len(pv) >= 2 and len(pn) >= 2:
        for a, b in ((pv[0], pn[0]), (pv[-1], pn[-1])):
            if normalizar(a) != normalizar(b):
                mapa.setdefault(a, b)
    return dict(sorted(mapa.items(), key=lambda kv: -len(kv[0])))


def _palabras(claves: tuple[str, ...] | list[str]) -> re.Pattern[str]:
    ordenadas = sorted(claves, key=len, reverse=True)
    return re.compile(
        r"(?<![^\W\d_])(" + "|".join(re.escape(k) for k in ordenadas) + r")(?![^\W\d_])"
    )


def tapar(texto: str, protegidos: tuple[str, ...], dejar: tuple[str, ...] = ()) -> str:
    """El texto con cada nombre protegido tapado por un relleno de su misma longitud.

    Conserva las posiciones, para que el inicio de frase se siga midiendo igual. Lo de `dejar`
    compite con los protegidos, el mas largo primero, y no se tapa: con «Reyes» protegido y
    «Nina Reyes» en `dejar`, «Nina Reyes» queda entero y «Reyes» a secas se tapa.
    """
    if not protegidos:
        return texto
    visibles = set(dejar)
    return _palabras([*protegidos, *dejar]).sub(
        lambda m: m.group(1) if m.group(1) in visibles else "_" * len(m.group(1)), texto
    )


def sustituir_nombres(texto: str, mapa: dict[str, str], protegidos: tuple[str, ...] = ()) -> str:
    """Cada clave del mapa, como palabra completa y escrita igual, por su valor.

    Palabra completa y con su mayuscula: «Luna» no toca «la luna» ni «Lunares». Todo en una
    pasada, para que una sustitucion no se sustituya otra vez («Ana Luna» a «Luna Ana»). Los
    nombres protegidos, de otras entidades, se saltan enteros: renombrar a «Reyes» no toca a
    «Pedro Reyes» (validador de 2fa0ee6). Lo que sustituye es lo del mapa y nada mas, asi que un
    protegido que tambien sea clave del mapa se sustituye: por eso el mapa sale de
    `Cambio.mapa`, que ya quita las palabras de otros (validador de 58e70f0).
    """
    if not mapa:
        return texto
    claves = [*protegidos, *mapa]
    return _palabras(claves).sub(lambda m: mapa.get(m.group(1), m.group(1)), texto)


def veces_protegidos(texto: str, protegidos: tuple[str, ...], viejo: str) -> dict[str, int]:
    """Cuantas veces sale cada nombre protegido, fuera del nombre viejo entero.

    El mas largo gana: con «Reyes» protegido, el «Reyes» de «Nina Reyes» (el viejo) no cuenta.
    """
    if not protegidos:
        return {}
    veces = dict.fromkeys(protegidos, 0)
    for m in _palabras([*protegidos, viejo]).finditer(texto):
        if m.group(1) in veces and m.group(1) != viejo:
            veces[m.group(1)] += 1
    return veces


def partes_viejas(viejo: str, nuevo: str) -> list[str]:
    """Las palabras del nombre viejo que el nuevo no tiene: las que no pueden quedar."""
    nuevas = {normalizar(p) for p in partes_de_nombre(nuevo)}
    partes = [p for p in partes_de_nombre(viejo) if normalizar(p) not in nuevas]
    return partes or ([viejo] if normalizar(viejo) != normalizar(nuevo) else [])


def menciones_de(texto: str, nombre: str) -> list[int]:
    """Donde empieza el nombre en el texto, con mayuscula y sin mirar tildes.

    Un nombre de varias palabras se busca como frase: sus palabras seguidas, separadas solo por
    espacios («Nina Reyes», no «Nina, Reyes» ni «Nina y Reyes»).
    """
    claves = [normalizar(p) for p in PALABRA_DE_NOMBRE.findall(nombre)]
    if not claves:
        return []
    palabras = list(PALABRA_DE_NOMBRE.finditer(texto))
    salida: list[int] = []
    for i in range(len(palabras) - len(claves) + 1):
        tramo = palabras[i:i + len(claves)]
        if (
            tramo[0].group(0)[0].isupper()
            and all(normalizar(m.group(0)) == c for m, c in zip(tramo, claves, strict=True))
            and all(not texto[a.end():b.start()].strip()
                    for a, b in zip(tramo, tramo[1:], strict=False))
        ):
            salida.append(tramo[0].start())
    return salida


# --- La peticion, como llega de la API (RF3-CAM-01) ------------------------------------------


class ObjetivoEntidad(BaseModel):
    tipo: Literal["entidad"]
    entidad: Literal["personajes", "lugares", "objetos"]
    id: int = Field(ge=1)


class ObjetivoHecho(BaseModel):
    tipo: Literal["hecho"]
    hecho_id: int = Field(ge=1)


class ObjetivoFragmento(BaseModel):
    tipo: Literal["fragmento"]


class CitaLector(BaseModel):
    capitulo: int = Field(ge=1)
    texto: str = Field(min_length=1, max_length=500)


class PeticionCambio(BaseModel):
    """El payload de `cambio_lector`. La API lo valida en forma y el worker lo relee con esto."""

    version_base: int = Field(ge=1)
    objetivo: ObjetivoEntidad | ObjetivoHecho | ObjetivoFragmento = Field(discriminator="tipo")
    peticion: str = Field(min_length=3, max_length=300)
    cita: CitaLector | None = None

    @model_validator(mode="after")
    def _fragmento_con_cita(self) -> PeticionCambio:
        if self.objetivo.tipo == "fragmento" and self.cita is None:
            raise ValueError("Un cambio sobre un fragmento necesita la cita.")
        return self
