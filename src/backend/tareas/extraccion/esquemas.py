"""Entrada y salida del extractor (RF-PIPE-10, RF-PIPE-11).

El extractor es la pieza fragil del diseno: es el unico punto por el que el texto alimenta
el grafo. Dos decisiones del esquema salen de ahi:

  * El Hecho es un TRIPLE (sujeto, atributo, valor), no un enunciado libre. Con enunciados
    libres, "contradiccion" no es una consulta sino una opinion, y la puerta 3 dejaria de
    ser determinista.
  * `usos_de_conocimiento` es distinto de `conocimiento`: uno es lo que un personaje USA en
    la escena, el otro lo que ADQUIERE. Detectar que alguien actua sobre algo que todavia no
    ha recibido exige las dos listas.

Los `*_ref` son nombres de entidades que venian en el paquete. El extractor no inventa ids;
lo que no reconozca va a `entidades_no_reconocidas`, que es un dato para la puerta 3, no un
error de validacion.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field, model_validator

from compartido.tipos import (
    CategoriaHecho,
    CondicionPersonaje,
    EstadoHilo,
    EstadoSiembra,
    NivelRevelacion,
    Postura,
    SujetoTipo,
)


class HechoExtraido(BaseModel):
    escena_orden: int = Field(ge=1)
    sujeto_tipo: SujetoTipo
    sujeto_ref: str = Field(min_length=1, description="Nombre de la entidad del paquete")
    atributo: str = Field(min_length=2, description="Reutiliza los atributos que ya existen")
    valor: str = Field(min_length=1)
    conducta: bool = Field(
        default=False,
        description=(
            "true si el atributo es un habito, un ritual o una manera de hacer del sujeto "
            "(algo que hace siempre), no un rasgo (RF2-PIPE-29)"
        ),
    )
    categoria: CategoriaHecho = "otro"
    cita: str = Field(default="", description="Fragmento literal de la prosa que lo fija")
    supersede_a: str = Field(
        default="",
        description="Atributo del hecho anterior que este sustituye, si lo sustituye "
                    "legitimamente (una herida que cicatriza no contradice la herida)",
    )


class ConocimientoExtraido(BaseModel):
    escena_orden: int = Field(ge=1)
    personaje_ref: str = Field(min_length=1)
    sujeto_ref: str = Field(min_length=1)
    atributo: str = Field(min_length=2)
    postura: Postura
    via: str = Field(pattern="^(presencio|se_lo_contaron|dedujo|le_mintieron)$")


class UsoConocimiento(BaseModel):
    escena_orden: int = Field(ge=1)
    personaje_ref: str = Field(min_length=1)
    sujeto_ref: str = Field(min_length=1)
    atributo: str = Field(min_length=2)


class EstadoPersonajeExtraido(BaseModel):
    escena_orden: int = Field(ge=1)
    personaje_ref: str = Field(min_length=1)
    condicion: CondicionPersonaje = Field(
        description="Dato cerrado: vivo, herido, incapacitado, muerto o desaparecido. La puerta "
                    "de continuidad lo consulta para saber si alguien puede reaparecer"
    )
    salud_fisica: str = ""
    estado_psicologico: str = ""
    nivel_confianza: dict[str, str] = Field(default_factory=dict[str, str])


class EstadoObjetoExtraido(BaseModel):
    escena_orden: int = Field(ge=1)
    objeto_ref: str = Field(min_length=1)
    poseedor_ref: str = ""
    ubicacion_ref: str = Field(min_length=1)


class EventoExtraido(BaseModel):
    escena_orden: int | None = None
    fecha_interna: str = Field(min_length=1)
    orden_interno: int | None = Field(
        default=None,
        description="Posicion del suceso en la cronologia interna, creciente. OBLIGATORIO si "
                    "el evento esta dramatizado: continua la escala desde el ultimo valor que "
                    "trae el paquete. Es lo que hace exacta la comprobacion temporal",
    )
    dia: int | None = Field(
        default=None,
        description="Dias desde el comienzo de la historia (dia 0), negativos antes. "
                    "OBLIGATORIO si el evento esta dramatizado, como orden_interno, y creciente "
                    "con el: un suceso posterior no puede caer en un dia anterior (RF3-BIB-08)",
    )
    descripcion: str = Field(min_length=5)
    tipo: str = ""
    dramatizado: bool = True

    @model_validator(mode="after")
    def _dramatizado_con_orden(self) -> EventoExtraido:
        # Sin orden no hay ni ubicuidad ni retroceso temporal que comprobar, y autoasignarlo
        # hacia crecer siempre la cronologia (RF2-PIPE-10). Sin dia, Lean no puede contar
        # edades (RF3-BIB-08), y tampoco se inventa aqui.
        if self.dramatizado and self.orden_interno is None:
            raise ValueError(
                f"El evento dramatizado «{self.descripcion[:60]}» no trae orden_interno."
            )
        if self.dramatizado and self.dia is None:
            raise ValueError(
                f"El evento dramatizado «{self.descripcion[:60]}» no trae dia."
            )
        return self


class SiembraExtraida(BaseModel):
    escena_orden: int = Field(ge=1)
    siembra_ref: str = Field(
        default="", description="Elemento de una siembra ya viva; vacio si es nueva"
    )
    elemento: str = Field(default="", description="Solo si la siembra es nueva")
    nuevo_estado: EstadoSiembra

    @model_validator(mode="after")
    def _ref_o_elemento(self) -> SiembraExtraida:
        if not self.siembra_ref and not self.elemento:
            raise ValueError("Una siembra necesita o su referencia o su elemento.")
        return self


class HiloExtraido(BaseModel):
    """Un hilo que el capitulo abre, complica, deja latente o resuelve (RF2-PIPE-18)."""

    escena_orden: int = Field(ge=1)
    hilo: int = Field(ge=1, description="Numero del hilo en la lista de HILOS VIVOS del paquete")
    nuevo_estado: EstadoHilo


class EntidadNoReconocida(BaseModel):
    escena_orden: int = Field(ge=1)
    nombre: str = Field(min_length=1)
    contexto: str = ""


#: Limites de los resumenes (spec1, salida del extractor; RF2-PIPE-20).
PALABRAS_RESUMEN = 200
PALABRAS_RESUMEN_BREVE = 40


class SalidaExtraccion(BaseModel):
    """Termina cuando todo lo que el texto afirma esta registrado."""

    hechos: list[HechoExtraido] = Field(default_factory=list[HechoExtraido])
    conocimiento: list[ConocimientoExtraido] = Field(default_factory=list[ConocimientoExtraido])
    usos_de_conocimiento: list[UsoConocimiento] = Field(default_factory=list[UsoConocimiento])
    estados_personaje: list[EstadoPersonajeExtraido] = Field(
        default_factory=list[EstadoPersonajeExtraido]
    )
    estados_objeto: list[EstadoObjetoExtraido] = Field(default_factory=list[EstadoObjetoExtraido])
    eventos: list[EventoExtraido] = Field(default_factory=list[EventoExtraido])
    siembras: list[SiembraExtraida] = Field(default_factory=list[SiembraExtraida])
    hilos: list[HiloExtraido] = Field(default_factory=list[HiloExtraido])
    amenaza_revelacion: NivelRevelacion | None = None
    entidades_no_reconocidas: list[EntidadNoReconocida] = Field(
        default_factory=list[EntidadNoReconocida]
    )
    resumen: str = Field(
        min_length=20, description=f"Sinopsis del capitulo, hasta {PALABRAS_RESUMEN} palabras"
    )
    resumen_breve: str = Field(
        min_length=10, description=f"Una frase, hasta {PALABRAS_RESUMEN_BREVE} palabras"
    )

    @model_validator(mode="after")
    def _resumenes_dentro_de_limite(self) -> SalidaExtraccion:
        # El estado rodante se compone con estos dos resumenes (RF-CTX-04): si crecen, el
        # presupuesto del bloque elastico deja de cuadrar. Pero pasarse no invalida la salida:
        # se recorta (RF2-PIPE-20). Un modelo no cuenta palabras, y rechazar tiraba una
        # extraccion entera por cinco palabras de mas.
        self.resumen = recortar(self.resumen, PALABRAS_RESUMEN)
        self.resumen_breve = recortar(self.resumen_breve, PALABRAS_RESUMEN_BREVE)
        return self


def recortar(texto: str, limite: int) -> str:
    """`texto` hasta `limite` palabras: por la ultima frase completa que quepa, o por la palabra."""
    palabras = texto.split()
    if len(palabras) <= limite:
        return texto
    corte = " ".join(palabras[:limite])
    frases = [m.end() for m in re.finditer(r"[.!?…][»\"')]*(?=\s|$)", corte)]
    return corte[: frases[-1]] if frases else corte
