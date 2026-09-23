"""El brief de una novela personalizada (specs/spec3.md, 3.2).

Vive en compartido/ porque lo usan tres procesos: la API lo valida al encolar, el worker lo
guarda y deriva de el las restricciones, y el entrevistador lo va rellenando.

La pieza que importa es `analizar`: decide QUE falta y QUE se contradice sin preguntar a
ningun modelo (RF3-BRF-03). El agente entrevistador solo entiende respuestas y formula
preguntas; si decidiera el tambien que falta, un brief incompleto podria darse por bueno
porque el agente lo dijo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from compartido.texto import contiene_termino
from compartido.tipos import Subgenero

Intensidad = Literal["atmosferico", "tension", "intenso"]
Pronombres = Literal["el", "ella", "neutro"]
Ocasion = Literal["cumpleanos", "aniversario", "boda", "jubilacion", "navidad", "otra"]
Tono = Literal["sobrio", "emotivo", "humor_negro", "aventura"]
Origen = Literal["entrevista", "texto_libre"]
TipoElemento = Literal["rasgo", "recuerdo", "allegado"]


# --- Intensidad (RF3-BRF-02): la unica fuente de la tabla ---------------------------------


@dataclass(frozen=True)
class NivelIntensidad:
    edad_minima: int
    publico: str
    admite: str
    no_admite: str


INTENSIDADES: dict[str, NivelIntensidad] = {
    "atmosferico": NivelIntensidad(
        edad_minima=10,
        publico="juvenil, desde 10 años",
        admite="inquietud, amenaza sugerida, peligro que se resuelve, perdidas sin descripcion",
        no_admite="muertes en escena, sangre, heridas descritas, crueldad",
    ),
    "tension": NivelIntensidad(
        edad_minima=14,
        publico="adolescente, desde 14 años",
        admite="peligro real, muertes fuera de plano, heridas sin detalle anatomico",
        no_admite="violencia grafica, tortura, terror corporal explicito",
    ),
    "intenso": NivelIntensidad(
        edad_minima=18,
        publico="adulto",
        admite="violencia explicita al servicio de la historia",
        no_admite="contenido sexual",
    ),
}

EDAD_MINIMA_DEL_PRODUCTO = min(n.edad_minima for n in INTENSIDADES.values())

#: Subgeneros que viven del cuerpo o de las bajas y no caben en el nivel atmosferico.
SUBGENEROS_QUE_EXIGEN_INTENSIDAD = frozenset({"terror_corporal", "slasher_espacial"})


def describir_intensidad(nivel: str) -> str:
    """El texto que reciben el arquitecto y el redactor sobre lo que admite un nivel."""
    n = INTENSIDADES[nivel]
    return (
        f"Intensidad {nivel} (publico {n.publico}). Admite: {n.admite}. "
        f"No admite: {n.no_admite}. Nunca contenido sexual."
    )


# --- Modelo (RF3-BRF-01) ---------------------------------------------------------------------


class ElementoPersonal(BaseModel):
    """Un rasgo o un recuerdo del destinatario, con un codigo estable dentro del brief."""

    codigo: str = ""
    texto: str = Field(min_length=1, max_length=500)
    obligatorio: bool = True
    origen: Origen = "entrevista"
    cita: str = ""


class Allegado(BaseModel):
    """Una persona o mascota cercana al destinatario que entra en la novela."""

    codigo: str = ""
    nombre: str = Field(min_length=1, max_length=60)
    relacion: str = Field(min_length=1, max_length=60)
    rasgos: list[str] = Field(default_factory=list[str], max_length=5)
    obligatorio: bool = True
    origen: Origen = "entrevista"
    cita: str = ""


class Destinatario(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=60)
    edad: int | None = Field(default=None, ge=1, le=110)
    pronombres: Pronombres | None = None
    rasgos: list[ElementoPersonal] = Field(default_factory=list[ElementoPersonal], max_length=8)

    @field_validator("nombre")
    @classmethod
    def _sin_espacios_de_sobra(cls, v: str | None) -> str | None:
        return " ".join(v.split()) if v is not None else None


class Brief(BaseModel):
    """El encargo. Los campos obligatorios admiten None mientras la entrevista lo rellena;
    que un brief este completo lo decide `analizar`, no el tipo."""

    destinatario: Destinatario = Field(default_factory=Destinatario)
    recuerdos: list[ElementoPersonal] = Field(
        default_factory=list[ElementoPersonal], max_length=10
    )
    allegados: list[Allegado] = Field(default_factory=list[Allegado], max_length=6)
    ocasion: Ocasion | None = None
    ocasion_detalle: str = Field(default="", max_length=120)
    quien_regala: str | None = Field(default=None, min_length=1, max_length=80)
    mensaje_dedicatoria: str = Field(default="", max_length=300)
    intensidad: Intensidad | None = None
    tono: Tono | None = None
    subgenero: Subgenero | None = None
    capitulos: int = Field(default=10, ge=1, le=10)
    vetados: list[str] = Field(default_factory=list[str], max_length=30)
    texto_libre: str = Field(default="", max_length=4000)

    def con_codigos(self) -> Brief:
        """Una copia con codigo en cada elemento que no lo tenga: RAS1, REC1, ALL1…"""
        copia = self.model_copy(deep=True)
        for prefijo, lista in (
            ("RAS", copia.destinatario.rasgos), ("REC", copia.recuerdos), ("ALL", copia.allegados),
        ):
            usados = {e.codigo for e in lista if e.codigo}
            n = 1
            for e in lista:
                if e.codigo:
                    continue
                while f"{prefijo}{n}" in usados:
                    n += 1
                e.codigo = f"{prefijo}{n}"
                usados.add(e.codigo)
        return copia

    def validar_completo(self) -> None:
        """RF3-BRF-04: lanza BriefIncompleto si falta algo o algo se contradice."""
        analisis = analizar(self)
        if not analisis.completo:
            raise BriefIncompleto(analisis)


# --- Analisis (RF3-BRF-03) --------------------------------------------------------------------


@dataclass(frozen=True)
class Contradiccion:
    codigo: str
    campos: tuple[str, ...]
    mensaje: str


@dataclass(frozen=True)
class Analisis:
    faltantes: list[str] = field(default_factory=list[str])
    contradicciones: list[Contradiccion] = field(default_factory=list[Contradiccion])

    @property
    def completo(self) -> bool:
        return not self.faltantes and not self.contradicciones

    def pendientes(self) -> list[str]:
        """Lo que la entrevista tiene que resolver, en orden: primero lo contradictorio."""
        return [f"contradiccion:{c.codigo}" for c in self.contradicciones] + [
            f"falta:{f}" for f in self.faltantes
        ]

    def como_dict(self) -> dict[str, object]:
        return {
            "faltantes": self.faltantes,
            "contradicciones": [
                {"codigo": c.codigo, "campos": list(c.campos), "mensaje": c.mensaje}
                for c in self.contradicciones
            ],
        }


class BriefIncompleto(ValueError):
    def __init__(self, analisis: Analisis) -> None:
        partes = [f"falta {f}" for f in analisis.faltantes] + [
            c.mensaje for c in analisis.contradicciones
        ]
        super().__init__("El brief no esta completo: " + "; ".join(partes))
        self.analisis = analisis


def _faltantes(b: Brief) -> list[str]:
    d = b.destinatario
    comprobaciones: list[tuple[str, bool]] = [
        ("destinatario.nombre", d.nombre is None),
        ("destinatario.edad", d.edad is None),
        ("destinatario.pronombres", d.pronombres is None),
        ("destinatario.rasgos", not d.rasgos),
        ("recuerdos", not b.recuerdos),
        ("ocasion", b.ocasion is None),
        ("quien_regala", b.quien_regala is None),
        ("intensidad", b.intensidad is None),
        ("tono", b.tono is None),
    ]
    return [campo for campo, falta in comprobaciones if falta]


def _textos_obligatorios(b: Brief) -> list[tuple[str, str]]:
    """(donde, texto) de todo lo obligatorio que va a aparecer en la novela."""
    salida: list[tuple[str, str]] = []
    for e in b.destinatario.rasgos:
        if e.obligatorio:
            salida.append((f"rasgo {e.codigo or e.texto[:20]}", e.texto))
    for e in b.recuerdos:
        if e.obligatorio:
            salida.append((f"recuerdo {e.codigo or e.texto[:20]}", e.texto))
    for a in b.allegados:
        if a.obligatorio:
            texto = " ".join([a.nombre, a.relacion, *a.rasgos])
            salida.append((f"allegado {a.nombre}", texto))
    return salida


def _contradicciones(b: Brief) -> list[Contradiccion]:
    salida: list[Contradiccion] = []
    edad = b.destinatario.edad

    if edad is not None and edad < EDAD_MINIMA_DEL_PRODUCTO:
        salida.append(Contradiccion(
            "edad_bajo_intensidad", ("destinatario.edad", "intensidad"),
            f"Con {edad} años no hay ningun nivel de terror adecuado: el minimo del producto "
            f"es {EDAD_MINIMA_DEL_PRODUCTO}.",
        ))
    elif edad is not None and b.intensidad is not None:
        minima = INTENSIDADES[b.intensidad].edad_minima
        if edad < minima:
            salida.append(Contradiccion(
                "edad_bajo_intensidad", ("destinatario.edad", "intensidad"),
                f"La intensidad «{b.intensidad}» pide al menos {minima} años y el destinatario "
                f"tiene {edad}.",
            ))

    if b.subgenero in SUBGENEROS_QUE_EXIGEN_INTENSIDAD and b.intensidad == "atmosferico":
        salida.append(Contradiccion(
            "subgenero_exige_intensidad", ("subgenero", "intensidad"),
            f"El subgenero «{b.subgenero}» vive del cuerpo o de las bajas y no cabe en la "
            "intensidad «atmosferico».",
        ))

    for termino in b.vetados:
        for donde, texto in _textos_obligatorios(b):
            if contiene_termino(texto, termino):
                salida.append(Contradiccion(
                    "elemento_con_vetado", ("vetados", donde),
                    f"«{termino}» esta vetado y aparece en el {donde}, que es obligatorio.",
                ))
    return salida


def analizar(brief: Brief) -> Analisis:
    """Que falta y que se contradice. Determinista: no llama a ningun modelo."""
    return Analisis(faltantes=_faltantes(brief), contradicciones=_contradicciones(brief))


# --- Lo que el pipeline saca del brief (RF3-PER-01, RF3-PER-02) -----------------------------

PALABRAS_POR_CAPITULO_OBJETIVO = 1250
RANGO_CAPITULO = "1000-1500"


def restricciones_derivadas(brief: Brief) -> dict[str, str]:
    """Las restricciones de la novela salen del brief, no las escribe nadie a mano."""
    assert brief.intensidad is not None, "solo se derivan de un brief completo"
    nivel = INTENSIDADES[brief.intensidad]
    return {
        "longitud_objetivo_palabras": str(brief.capitulos * PALABRAS_POR_CAPITULO_OBJETIVO),
        "longitud_capitulo_palabras": RANGO_CAPITULO,
        "capitulos": str(brief.capitulos),
        "publico": nivel.publico,
        "politica_contenido": f"Admite: {nivel.admite}. No admite: {nivel.no_admite}.",
        "pov_por_defecto": "tercera_limitada",
        "tiempo_verbal": "pasado",
    }


def elementos(brief: Brief) -> list[tuple[str, TipoElemento, str, bool, str, str]]:
    """(codigo, tipo, texto, obligatorio, origen, cita) de cada elemento, con codigo."""
    b = brief.con_codigos()
    salida: list[tuple[str, TipoElemento, str, bool, str, str]] = []
    for e in b.destinatario.rasgos:
        salida.append((e.codigo, "rasgo", e.texto, e.obligatorio, e.origen, e.cita))
    for e in b.recuerdos:
        salida.append((e.codigo, "recuerdo", e.texto, e.obligatorio, e.origen, e.cita))
    for a in b.allegados:
        texto = f"{a.nombre} ({a.relacion})" + (f": {', '.join(a.rasgos)}" if a.rasgos else "")
        salida.append((a.codigo, "allegado", texto, a.obligatorio, a.origen, a.cita))
    return salida
