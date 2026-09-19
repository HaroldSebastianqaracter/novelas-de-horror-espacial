"""Antirrepetición determinista (RF-05.5; spec técnica §17.1): coincidencias literales entre capítulos.

Ninguna secuencia de cuatro o más palabras con contenido léxico puede aparecer literalmente en un capítulo
anterior. Lo comprueba código, no el agente: INV-01 restringe al escritor, y este módulo lee todo el manuscrito
desde `validar-capitulo`. Es barato, no llama a ningún modelo y atrapa con certeza el caso literal («el metal
estaba frío», tres capítulos).

Qué cuenta como contenido léxico: una palabra que no es vacía (artículos, preposiciones, conjunciones, pronombres,
auxiliares y adverbios de uso constante) ni neutral. Son neutrales los nombres del registro de sujetos (personajes y
locaciones: nombrar a Kovacs en cada capítulo no es repetirse) y los números. Una secuencia se rechaza cuando trae al
menos `LEXICAS_MINIMAS` palabras con contenido; con una sola, «la puerta de la» saltaría en cada capítulo.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

N_GRAMA = 4
LEXICAS_MINIMAS = 2
MAX_REPORTADAS = 8

PALABRAS_VACIAS = frozenset("""
a al ante bajo cabe con contra de del desde durante en entre hacia hasta mediante para por según sin so sobre tras
y e o u ni pero sino mas aunque porque pues que si como cuando donde mientras apenas
el la lo los las un una unos unas este esta esto estos estas ese esa eso esos esas aquel aquella aquello aquellos aquellas
mi mis tu tus su sus nuestro nuestra nuestros nuestras vuestro vuestra vuestros vuestras mío mía míos mías tuyo tuya suyo suya suyos suyas
yo tú vos usted él ella ello ellos ellas nosotros nosotras vosotros vosotras ustedes me te se nos os le les
quien quienes cual cuales cuyo cuya cuyos cuyas qué quién cuál cuánto cuánta cuántos cuántas cómo dónde cuándo
algo alguien alguno alguna algunos algunas nada nadie ninguno ninguna ningún algún otro otra otros otras
todo toda todos todas cada mucho mucha muchos muchas poco poca pocos pocas tanto tanta tantos tantas tan más menos muy
también tampoco no sí ya aún todavía siempre nunca jamás solo sólo casi
ahí allí aquí acá allá así entonces luego después antes ahora
ser soy eres es somos sois son era eras éramos erais eran fui fuiste fue fuimos fuisteis fueron sería serían sido siendo
estar estoy estás está estamos estáis están estaba estabas estábamos estabais estaban estuvo estuve estuvieron estuviera estaría estado
haber he has ha hemos habéis han había habías habíamos habíais habían hubo hube hubieron habría habrían habido hay
""".split())


@dataclass(frozen=True)
class Coincidencia:
    frase: str  # tal como aparece en el borrador
    cap_origen: int  # el capítulo anterior donde ya estaba
    palabras: int

    def texto(self) -> str:
        return f"«{self.frase}» (cap. {self.cap_origen}, {self.palabras} palabras)"


_PALABRA = re.compile(r"\w+", re.UNICODE)


def tokenizar(texto: str) -> list[tuple[str, int, int]]:
    """(palabra normalizada, inicio, fin) por cada palabra; las posiciones permiten citar la frase original."""
    return [(m.group(0).casefold(), m.start(), m.end()) for m in _PALABRA.finditer(texto)]


def tokens_de_nombres(nombres: list[str] | set[str]) -> set[str]:
    """Los nombres del registro de sujetos, palabra a palabra: neutrales para el conteo léxico."""
    return {t for nombre in nombres for t, _, _ in tokenizar(nombre)}


def es_lexica(palabra: str, neutrales: set[str]) -> bool:
    return not palabra.isdigit() and palabra not in PALABRAS_VACIAS and palabra not in neutrales


def _n_gramas(palabras: list[str], n: int) -> set[tuple[str, ...]]:
    return {tuple(palabras[i:i + n]) for i in range(len(palabras) - n + 1)}


def coincidencias(texto: str, previos: dict[int, str], neutrales: set[str] | None = None, *,
                  n: int = N_GRAMA, lexicas_minimas: int = LEXICAS_MINIMAS) -> list[Coincidencia]:
    """Pasajes de `texto` que repiten literalmente n o más palabras de algún capítulo de `previos` (num -> texto).

    Los n-gramas coincidentes consecutivos se funden en un solo pasaje, para reportar «el metal estaba frío bajo
    la palma» una vez y no cuatro. Un pasaje cuenta solo si trae `lexicas_minimas` palabras con contenido.
    """
    neutrales = neutrales or set()
    toks = tokenizar(texto)
    palabras = [t for t, _, _ in toks]
    if len(palabras) < n:
        return []
    resultado: list[Coincidencia] = []
    vistas: set[tuple[str, int]] = set()
    for cap, previo in sorted(previos.items()):
        gramas = _n_gramas([t for t, _, _ in tokenizar(previo)], n)
        if not gramas:
            continue
        i = 0
        while i <= len(palabras) - n:
            if tuple(palabras[i:i + n]) not in gramas:
                i += 1
                continue
            fin = i  # último índice de arranque de n-grama que sigue coincidiendo
            while fin + 1 <= len(palabras) - n and tuple(palabras[fin + 1:fin + 1 + n]) in gramas:
                fin += 1
            tramo = palabras[i:fin + n]
            if sum(1 for p in tramo if es_lexica(p, neutrales)) >= lexicas_minimas:
                frase = texto[toks[i][1]:toks[fin + n - 1][2]]
                frase = re.sub(r"\s+", " ", frase)
                if (frase.casefold(), cap) not in vistas:
                    vistas.add((frase.casefold(), cap))
                    resultado.append(Coincidencia(frase=frase, cap_origen=cap, palabras=len(tramo)))
            i = fin + n
    resultado.sort(key=lambda c: (texto.casefold().find(c.frase.casefold()), c.cap_origen))
    return resultado


def describir(hallazgos: list[Coincidencia], maximo: int = MAX_REPORTADAS) -> str:
    """El error que recibe el escritor: cuántos pasajes, cuáles y de qué capítulo vienen (RF-05.5)."""
    cuerpo = "; ".join(c.texto() for c in hallazgos[:maximo])
    extra = f"; y {len(hallazgos) - maximo} más" if len(hallazgos) > maximo else ""
    return (f"RF-05.5: {len(hallazgos)} pasaje(s) repiten literalmente {N_GRAMA} o más palabras con contenido de un capítulo "
            f"anterior; reescribilos con otras palabras: {cuerpo}{extra}")
