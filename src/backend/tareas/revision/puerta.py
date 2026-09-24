"""Las comprobaciones del cambio del lector (specs/spec3.md, RF3-CAM-09).

Deterministas y bloqueantes, antes de la mecanica de siempre y del juez: que el cambio se
aplico, que las citas del revisor existen y que el resto del capitulo no se movio.
"""

from __future__ import annotations

from difflib import SequenceMatcher

from compartido.cambio import Cambio, menciones_de, tapar, veces_protegidos
from compartido.puerta_base import Conflicto, ResultadoPuerta
from compartido.texto import INICIO_DE_FRASE, PALABRA_DE_NOMBRE, veces_termino
from config import CAMBIO_SIMILITUD_MINIMA


def _unir(textos: dict[int, str]) -> str:
    return "\n\n".join(textos[k] for k in sorted(textos))


def similitud(viejo: str, nuevo: str) -> float:
    """Cuanto se parecen dos prosas, por palabras, de 0 a 1 (`difflib`)."""
    return SequenceMatcher(None, viejo.split(), nuevo.split(), autojunk=False).ratio()


def _nombre_que_queda(cambio: Cambio, aprobada: str, texto: str) -> dict[str, int]:
    """Las palabras del nombre viejo que el texto sigue escribiendo, con sus veces.

    Si la palabra tambien sale en minuscula en la prosa aprobada, es una palabra corriente
    («Luna», «la luna»): al empezar frase no cuenta. Dentro del nombre de otra entidad
    («Pedro Reyes» al renombrar a «Reyes») tampoco, ni cuando es el nombre entero de otra
    («Reyes» al renombrar a «Nina Reyes»): lo que cuenta entonces es la frase «Nina Reyes».
    """
    texto = tapar(texto, cambio.protegidos, dejar=(cambio.antes,))
    corrientes = {p.casefold() for p in PALABRA_DE_NOMBRE.findall(aprobada) if p[0].islower()}
    quedan: dict[str, int] = {}
    for parte in cambio.partes_viejas():
        veces = [
            pos for pos in menciones_de(texto, parte)
            if parte.casefold() not in corrientes or not INICIO_DE_FRASE.search(texto, 0, pos)
        ]
        if veces:
            quedan[parte] = len(veces)
    return quedan


def _sin_aplicar_renombrado(cambio: Cambio, capitulo: int, viejo: str, nuevo: str,
                            resumen: str) -> Conflicto | None:
    quedan = _nombre_que_queda(cambio, viejo, nuevo)
    en_resumen = _nombre_que_queda(cambio, viejo, resumen)
    if not quedan and not en_resumen:
        return None
    donde: list[str] = []
    if quedan:
        donde.append("en la prosa " + ", ".join(f"«{p}» ({n})" for p, n in quedan.items()))
    if en_resumen:
        donde.append("en los resumenes " + ", ".join(f"«{p}»" for p in en_resumen))
    return Conflicto(
        comprobacion="cambio_sin_aplicar", capitulo=capitulo,
        descripcion=(
            f"Sigue escrito el nombre viejo ({'; '.join(donde)}). Tiene que decir "
            f"«{cambio.despues}»."
        ),
        datos={"prosa": quedan, "resumenes": en_resumen},
    )


def _toca_otro(cambio: Cambio, capitulo: int, viejo: str, nuevo: str) -> Conflicto | None:
    """Un nombre de otra entidad que la correccion quito o cambio (validador de 58e70f0)."""
    antes = veces_protegidos(viejo, cambio.protegidos, cambio.antes)
    despues = veces_protegidos(nuevo, cambio.protegidos, cambio.antes)
    tocados = {n: (antes[n], despues[n]) for n in antes if despues[n] < antes[n]}
    if not tocados:
        return None
    return Conflicto(
        comprobacion="cambio_toca_otro", capitulo=capitulo,
        descripcion=(
            "La correccion toca el nombre de otra entidad: "
            + ", ".join(f"«{n}» salia {a} vez/veces y ahora {d}" for n, (a, d) in tocados.items())
            + f". Solo cambia «{cambio.antes}»; lo demas es de otro y se queda como estaba."
        ),
        datos={"tocados": {n: {"antes": a, "despues": d} for n, (a, d) in tocados.items()}},
    )


def _sin_aplicar_hecho(cambio: Cambio, capitulo: int, viejo: str, nuevo: str,
                       resumen: str) -> Conflicto | None:
    antes = veces_termino(viejo, cambio.antes)
    queda = veces_termino(nuevo, cambio.antes)
    puesto = veces_termino(nuevo, cambio.despues)
    en_resumen = veces_termino(resumen, cambio.antes) > 0
    if not (antes > 0 and (queda >= antes or puesto == 0)) and not en_resumen:
        return None
    return Conflicto(
        comprobacion="cambio_sin_aplicar", capitulo=capitulo,
        descripcion=(
            f"La prosa aprobada escribia «{cambio.antes}» {antes} vez/veces; la corregida, "
            f"{queda}, y «{cambio.despues}», {puesto}"
            + ("; los resumenes siguen diciendo el valor viejo" if en_resumen else "")
            + f". Donde decia «{cambio.antes}» tiene que decir «{cambio.despues}»."
        ),
        datos={"antes": antes, "queda": queda, "nuevo": puesto, "en_resumenes": en_resumen},
    )


def _citas(capitulo: int, viejo: str, nuevo: str, citas: list[str]) -> Conflicto | None:
    malas = [c for c in citas if c not in nuevo or c in viejo]
    sin_citas = nuevo != viejo and not citas
    if not malas and not sin_citas:
        return None
    partes: list[str] = []
    if malas:
        partes.append("Estas citas no estan en la prosa corregida, o ya estaban en la aprobada: "
                      + "; ".join(f"«{c[:80]}»" for c in malas) + ".")
    if sin_citas:
        partes.append("La prosa cambio y no trae ninguna cita del cambio.")
    partes.append("Cita, literal, cada sitio de la prosa corregida donde aplicaste el cambio.")
    return Conflicto(
        comprobacion="cambio_sin_cita", capitulo=capitulo, descripcion=" ".join(partes),
        datos={"citas_malas": malas, "sin_citas": sin_citas},
    )


def comprobar(
    cambio: Cambio,
    capitulo: int,
    viejo: dict[int, str],
    nuevo: dict[int, str],
    resumenes: tuple[str, str],
    citas: list[str],
    aprobados: tuple[str, str] = ("", ""),
) -> ResultadoPuerta:
    """Las comprobaciones del cambio sobre un capitulo corregido (RF3-CAM-09).

    `resumenes` son los corregidos y `aprobados`, los de antes del cambio.
    """
    if sorted(nuevo) != sorted(viejo):
        return ResultadoPuerta(puerta=4, conflictos=[Conflicto(
            comprobacion="cambio_escenas", capitulo=capitulo,
            descripcion=(
                f"El capitulo tiene las escenas {sorted(viejo)} y la correccion trae "
                f"{sorted(nuevo)}: devuelve exactamente las mismas."
            ),
            datos={"esperadas": sorted(viejo), "recibidas": sorted(nuevo)},
        )])

    texto_viejo, texto_nuevo = _unir(viejo), _unir(nuevo)
    resumen = "\n".join(resumenes)
    conflictos: list[Conflicto] = []
    otro = None
    resumenes_aprobados = "\n".join(aprobados)
    if cambio.tipo == "renombrar":
        aplicado = _sin_aplicar_renombrado(cambio, capitulo, texto_viejo, texto_nuevo, resumen)
        otro = _toca_otro(cambio, capitulo, f"{texto_viejo}\n{resumenes_aprobados}",
                          f"{texto_nuevo}\n{resumen}")
    elif cambio.literal:
        aplicado = _sin_aplicar_hecho(cambio, capitulo, texto_viejo, texto_nuevo, resumen)
    else:
        aplicado = None
    for c in (aplicado, otro, _citas(capitulo, texto_viejo, texto_nuevo, citas)):
        if c is not None:
            conflictos.append(c)

    parecido = round(similitud(texto_viejo, texto_nuevo), 3)
    if parecido < CAMBIO_SIMILITUD_MINIMA:
        conflictos.append(Conflicto(
            comprobacion="cambio_desborda", capitulo=capitulo,
            descripcion=(
                f"La correccion se parece a la prosa aprobada un {parecido:.0%}, y tiene que "
                f"parecerse al menos un {CAMBIO_SIMILITUD_MINIMA:.0%}: cambia solo lo que toca "
                "el cambio."
            ),
            datos={"similitud": parecido, "minima": CAMBIO_SIMILITUD_MINIMA},
        ))
    return ResultadoPuerta(puerta=4, conflictos=conflictos)
