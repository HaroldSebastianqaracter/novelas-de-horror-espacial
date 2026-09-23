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

from pydantic import BaseModel, Field, model_validator

from compartido.tipos import (
    CategoriaHecho,
    CondicionPersonaje,
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
    nivel_confianza: dict[str, str] = Field(default_factory=dict)


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
    descripcion: str = Field(min_length=5)
    tipo: str = ""
    dramatizado: bool = True

    @model_validator(mode="after")
    def _dramatizado_con_orden(self) -> EventoExtraido:
        # Sin orden no hay ni ubicuidad ni retroceso temporal que comprobar, y autoasignarlo
        # hacia crecer siempre la cronologia (RF2-PIPE-10).
        if self.dramatizado and self.orden_interno is None:
            raise ValueError(
                f"El evento dramatizado «{self.descripcion[:60]}» no trae orden_interno."
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


class EntidadNoReconocida(BaseModel):
    escena_orden: int = Field(ge=1)
    nombre: str = Field(min_length=1)
    contexto: str = ""


class SalidaExtraccion(BaseModel):
    """Termina cuando todo lo que el texto afirma esta registrado."""

    hechos: list[HechoExtraido] = Field(default_factory=list)
    conocimiento: list[ConocimientoExtraido] = Field(default_factory=list)
    usos_de_conocimiento: list[UsoConocimiento] = Field(default_factory=list)
    estados_personaje: list[EstadoPersonajeExtraido] = Field(default_factory=list)
    estados_objeto: list[EstadoObjetoExtraido] = Field(default_factory=list)
    eventos: list[EventoExtraido] = Field(default_factory=list)
    siembras: list[SiembraExtraida] = Field(default_factory=list)
    amenaza_revelacion: NivelRevelacion | None = None
    entidades_no_reconocidas: list[EntidadNoReconocida] = Field(default_factory=list)
    resumen: str = Field(min_length=20, description="Sinopsis del capitulo, hasta 200 palabras")
    resumen_breve: str = Field(min_length=10, description="Una frase, hasta 40 palabras")

    @model_validator(mode="after")
    def _resumenes_dentro_de_limite(self) -> SalidaExtraccion:
        # El estado rodante se compone con estos dos resumenes (RF-CTX-04): si crecen, el
        # presupuesto del bloque elastico deja de cuadrar.
        if len(self.resumen.split()) > 200:
            raise ValueError("El resumen supera las 200 palabras.")
        if len(self.resumen_breve.split()) > 40:
            raise ValueError("El resumen breve supera las 40 palabras.")
        return self
