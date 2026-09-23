"""Ensamblado del paquete de contexto y reparto del presupuesto (RF2-CTX-01 a RF2-CTX-03).

Aqui vive la consecuencia practica del principio 7: **el contexto se selecciona, nunca se
vuelca**. Cada bloque entra porque el orquestador decidio que esta unidad lo necesita, y el
tamano total se comprueba antes de llamar a nadie.

Dos reglas que no se cruzan:

* **Superar el presupuesto es un fallo del orquestador, no del modelo.** Si lo obligatorio no
  cabe, la respuesta correcta es parar, no truncar el canon. Un canon truncado produce prosa
  que contradice lo que no llego a leerse, y eso no se detecta hasta mucho despues.
* **Ningun recorte es silencioso.** Un bloque es una lista de elementos, cada uno obligatorio
  u opcional; recortar es quitar opcionales desde el final, y cada elemento quitado queda
  apuntado en `recortes`, que el orquestador lleva a la traza. Un bloque que pierde todo lo
  que tenia no desaparece sin rastro.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from config import BLOQUES_FIJOS, ORDEN_DE_RECORTE

from .tokens import estimar


class PresupuestoExcedido(Exception):
    """Lo obligatorio no cabe ni despues de quitar todo lo opcional (RF2-CTX-03)."""

    def __init__(
        self,
        mensaje: str,
        *,
        detalle: dict[str, int],
        total: int,
        techo: int,
        recortes: dict[str, dict[str, int]] | None = None,
    ) -> None:
        super().__init__(mensaje)
        self.detalle = detalle
        self.total = total
        self.techo = techo
        self.recortes = recortes or {}

    def informe(self) -> dict[str, object]:
        return {
            "motivo": str(self),
            "total_tokens": self.total,
            "techo_tokens": self.techo,
            "bloques": self.detalle,
            "recortes": self.recortes,
        }


@dataclass(frozen=True)
class Presupuesto:
    """Cuanto puede ocupar cada bloque y el paquete entero. Llega desde `Config`."""

    bloques: Mapping[str, int]
    techo: int
    fijos: frozenset[str] = BLOQUES_FIJOS
    orden_de_recorte: tuple[str, ...] = ORDEN_DE_RECORTE


@dataclass(frozen=True)
class Elemento:
    """Una unidad que entra entera o no entra: un hecho, un personaje, un parrafo.

    `seccion` agrupa elementos bajo un encabezado al presentarlos. `posicion` es el orden de
    lectura; si no se da, es el de relevancia, que es el orden de la lista del bloque.
    """

    texto: str
    obligatorio: bool = False
    seccion: str = ""
    posicion: float | None = None


@dataclass
class Bloque:
    """Un trozo con nombre del paquete, como lista de elementos ordenada por relevancia.

    `alternativa`, si la hay, sustituye a los elementos opcionales la primera vez que el
    bloque tiene que recortarse: es como el capitulo anterior cae a su resumen antes de perder
    parrafos.
    """

    nombre: str
    elementos: list[Elemento]
    titulo: str = ""
    separador: str = "\n"
    alternativa: list[Elemento] | None = None

    @property
    def tokens(self) -> int:
        return estimar(self.render())

    def render(self) -> str:
        return _render(self.nombre, self.titulo, self.separador, self.elementos)


def _render(nombre: str, titulo: str, separador: str, elementos: list[Elemento]) -> str:
    visibles = [(i, e) for i, e in enumerate(elementos) if e.texto.strip()]
    if not visibles:
        return ""
    orden_seccion: dict[str, int] = {}
    for _, e in visibles:
        orden_seccion.setdefault(e.seccion, len(orden_seccion))
    visibles.sort(key=lambda p: (
        orden_seccion[p[1].seccion], p[1].posicion if p[1].posicion is not None else p[0]
    ))
    partes: list[str] = []
    seccion: str | None = None
    for _, e in visibles:
        if e.seccion != seccion:
            seccion = e.seccion
            if seccion:
                partes.append(seccion)
        partes.append(e.texto.strip())
    cabecera = titulo or nombre.replace("_", " ").upper()
    return f"## {cabecera}\n\n" + separador.join(partes)


@dataclass
class Paquete:
    """El contexto de una llamada, con la cuenta de lo que ocupa y de lo que se recorto."""

    agente: str
    bloques: list[Bloque] = field(default_factory=list)
    capitulo: int | None = None
    #: bloque -> {"elementos": quitados, "tokens": liberados, "sustituido": 0|1}
    recortes: dict[str, dict[str, int]] = field(default_factory=dict)

    def anadir(
        self, nombre: str, texto: str, titulo: str = "", *, obligatorio: bool | None = None
    ) -> None:
        """Un bloque de un solo elemento. Por defecto es obligatorio si el bloque es fijo."""
        if texto and texto.strip():
            self.bloques.append(Bloque(
                nombre=nombre, titulo=titulo,
                elementos=[Elemento(
                    texto, obligatorio=nombre in BLOQUES_FIJOS if obligatorio is None
                    else obligatorio,
                )],
            ))

    def anadir_elementos(
        self,
        nombre: str,
        elementos: Iterable[Elemento],
        titulo: str = "",
        *,
        separador: str = "\n",
        alternativa: Iterable[Elemento] | None = None,
    ) -> None:
        lista = [e for e in elementos if e.texto.strip()]
        if lista:
            self.bloques.append(Bloque(
                nombre=nombre, elementos=lista, titulo=titulo, separador=separador,
                alternativa=[e for e in alternativa if e.texto.strip()]
                if alternativa is not None else None,
            ))

    @property
    def tokens_por_bloque(self) -> dict[str, int]:
        return {b.nombre: b.tokens for b in self.bloques}

    @property
    def total(self) -> int:
        return sum(b.tokens for b in self.bloques)

    def render(self) -> str:
        return "\n\n".join(p for p in (b.render() for b in self.bloques) if p)

    def _apuntar(self, nombre: str, quitados: int, tokens: int, sustituido: bool) -> None:
        r = self.recortes.setdefault(nombre, {"elementos": 0, "tokens": 0, "sustituido": 0})
        r["elementos"] += quitados
        r["tokens"] += tokens
        r["sustituido"] = max(r["sustituido"], int(sustituido))


def _sin_los_ultimos_opcionales(elementos: list[Elemento], k: int) -> list[Elemento]:
    """Los elementos sin los `k` opcionales de menor relevancia (los del final)."""
    if k <= 0:
        return list(elementos)
    fuera: set[int] = set()
    for i in range(len(elementos) - 1, -1, -1):
        if len(fuera) == k:
            break
        if not elementos[i].obligatorio:
            fuera.add(i)
    return [e for i, e in enumerate(elementos) if i not in fuera]


def _recortar_bloque(paquete: Paquete, bloque: Bloque, objetivo: int) -> None:
    """Quita los opcionales justos, desde el final, para que el bloque quepa en `objetivo`.

    Busca por biseccion el menor numero de opcionales que hay que quitar: los tokens de un
    bloque solo bajan al quitar elementos, asi que la busqueda es exacta.
    """
    if bloque.tokens <= objetivo:
        return
    antes = bloque.tokens
    sustituidos = 0
    if bloque.alternativa is not None:
        # Lo obligatorio no se pierde ni al sustituir: solo se cambia lo opcional.
        sustituidos = sum(1 for e in bloque.elementos if not e.obligatorio)
        bloque.elementos = [e for e in bloque.elementos if e.obligatorio] + bloque.alternativa
        bloque.alternativa = None
        if bloque.tokens <= objetivo:
            paquete._apuntar(  # noqa: SLF001
                bloque.nombre, sustituidos, antes - bloque.tokens, sustituido=True
            )
            return

    opcionales = sum(1 for e in bloque.elementos if not e.obligatorio)
    bajo, alto = 0, opcionales
    tokens = lambda k: estimar(_render(  # noqa: E731
        bloque.nombre, bloque.titulo, bloque.separador,
        _sin_los_ultimos_opcionales(bloque.elementos, k),
    ))
    if tokens(alto) > objetivo:
        bajo = alto  # ni quitandolos todos: se quitan todos y decide el techo del paquete
    while bajo < alto:
        medio = (bajo + alto) // 2
        if tokens(medio) <= objetivo:
            alto = medio
        else:
            bajo = medio + 1
    bloque.elementos = _sin_los_ultimos_opcionales(bloque.elementos, bajo)
    paquete._apuntar(  # noqa: SLF001
        bloque.nombre, sustituidos + bajo, antes - bloque.tokens, sustituido=sustituidos > 0
    )


def ajustar(paquete: Paquete, presupuesto: Presupuesto) -> Paquete:
    """Recorta lo opcional hasta que el paquete quepa, o lanza `PresupuestoExcedido`.

    Primero cada bloque a su propio presupuesto; despues, si el conjunto sigue sin caber, los
    bloques de `orden_de_recorte` en ese orden: el capitulo anterior (que antes cae a su
    resumen), lo recuperado, el estado rodante, el canon y los hechos. Los bloques fijos no se
    tocan, y lo obligatorio de cualquier bloque tampoco: si no cabe, se para.
    """
    for b in paquete.bloques:
        tope = presupuesto.bloques.get(b.nombre)
        if tope is None or b.nombre in presupuesto.fijos:
            continue
        _recortar_bloque(paquete, b, tope)

    for nombre in presupuesto.orden_de_recorte:
        for b in paquete.bloques:
            sobra = paquete.total - presupuesto.techo
            if sobra <= 0:
                break
            if b.nombre == nombre and b.nombre not in presupuesto.fijos:
                _recortar_bloque(paquete, b, max(0, b.tokens - sobra))

    if paquete.total > presupuesto.techo:
        raise PresupuestoExcedido(
            f"El paquete de '{paquete.agente}' ocupa {paquete.total} tokens con solo lo "
            f"obligatorio y el techo es {presupuesto.techo}. No se trunca el canon: hay que "
            "partir la unidad o recomprimir.",
            detalle=paquete.tokens_por_bloque, total=paquete.total, techo=presupuesto.techo,
            recortes=paquete.recortes,
        )

    paquete.bloques = [b for b in paquete.bloques if b.render()]
    return paquete
