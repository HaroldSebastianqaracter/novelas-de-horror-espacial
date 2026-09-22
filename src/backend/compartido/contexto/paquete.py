"""Ensamblado del paquete de contexto y reparto del presupuesto (RF-CTX-01 a RF-CTX-03).

Aqui vive la consecuencia practica del principio 7: **el contexto se selecciona, nunca se
vuelca**. Cada bloque entra porque el orquestador decidio que esta unidad lo necesita, y el
tamano total se comprueba antes de llamar a nadie.

La regla que no se cruza: **superar el presupuesto es un fallo del orquestador, no del
modelo**. Si un paquete no cabe despues de recortar lo elastico, la respuesta correcta es
parar, no truncar el canon. Un canon truncado produce prosa que contradice lo que no llego a
leerse, y eso no se detecta hasta mucho despues.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from config import BLOQUES_FIJOS, ORDEN_DE_RECORTE, PRESUPUESTO_BLOQUES

from .tokens import estimar, recortar_a


class PresupuestoExcedido(Exception):
    """El paquete no cabe ni despues de recortar todo lo recortable (RF-CTX-03)."""

    def __init__(self, mensaje: str, *, detalle: dict[str, int], total: int, techo: int) -> None:
        super().__init__(mensaje)
        self.detalle = detalle
        self.total = total
        self.techo = techo

    def informe(self) -> dict[str, object]:
        return {
            "motivo": str(self),
            "total_tokens": self.total,
            "techo_tokens": self.techo,
            "bloques": self.detalle,
        }


@dataclass
class Bloque:
    """Un trozo con nombre del paquete, con su politica de recorte."""

    nombre: str
    texto: str
    titulo: str = ""

    @property
    def tokens(self) -> int:
        return estimar(self.texto)

    @property
    def fijo(self) -> bool:
        return self.nombre in BLOQUES_FIJOS

    def render(self) -> str:
        if not self.texto.strip():
            return ""
        cabecera = self.titulo or self.nombre.replace("_", " ").upper()
        return f"## {cabecera}\n\n{self.texto.strip()}"


@dataclass
class Paquete:
    """El contexto de una llamada, con la cuenta de lo que ocupa cada parte."""

    agente: str
    bloques: list[Bloque] = field(default_factory=list)
    capitulo: int | None = None
    recortes: dict[str, int] = field(default_factory=dict)

    def anadir(self, nombre: str, texto: str, titulo: str = "") -> None:
        if texto and texto.strip():
            self.bloques.append(Bloque(nombre=nombre, texto=texto, titulo=titulo))

    @property
    def tokens_por_bloque(self) -> dict[str, int]:
        return {b.nombre: b.tokens for b in self.bloques}

    @property
    def total(self) -> int:
        return sum(b.tokens for b in self.bloques)

    def render(self) -> str:
        return "\n\n".join(p for p in (b.render() for b in self.bloques) if p)


def ajustar(paquete: Paquete, techo: int | None = None) -> Paquete:
    """Recorta lo recortable hasta que el paquete quepa, o falla.

    El orden lo fija `config.ORDEN_DE_RECORTE`: primero el texto del capitulo anterior, que
    se sustituye por su resumen; luego lo recuperado; luego el estado rodante; y solo al
    final el canon y los hechos, que se recortan por relevancia porque su fuente ya viene
    ordenada.

    Lo declarado fijo no se toca nunca: las instrucciones y el estilo garantizan la
    consistencia de voz, la escaleta es la tarea, y las siembras son baratas y su olvido
    caro.
    """
    limite = techo if techo is not None else sum(PRESUPUESTO_BLOQUES.values())

    # Primero, cada bloque a su propio presupuesto.
    for b in paquete.bloques:
        tope = PRESUPUESTO_BLOQUES.get(b.nombre)
        if tope is None or b.fijo or b.tokens <= tope:
            continue
        antes = b.tokens
        b.texto = recortar_a(b.texto, tope)
        paquete.recortes[b.nombre] = antes - b.tokens

    # Despues, si el conjunto sigue sin caber, se va vaciando en orden.
    for nombre in ORDEN_DE_RECORTE:
        if paquete.total <= limite:
            break
        for b in paquete.bloques:
            if b.nombre != nombre or b.fijo:
                continue
            sobra = paquete.total - limite
            objetivo = max(0, b.tokens - sobra)
            antes = b.tokens
            b.texto = recortar_a(b.texto, objetivo) if objetivo else ""
            paquete.recortes[nombre] = paquete.recortes.get(nombre, 0) + (antes - b.tokens)

    if paquete.total > limite:
        raise PresupuestoExcedido(
            f"El paquete de '{paquete.agente}' ocupa {paquete.total} tokens y el techo es "
            f"{limite}. No se trunca el canon: hay que partir la unidad o recomprimir.",
            detalle=paquete.tokens_por_bloque, total=paquete.total, techo=limite,
        )

    paquete.bloques = [b for b in paquete.bloques if b.texto.strip()]
    return paquete
