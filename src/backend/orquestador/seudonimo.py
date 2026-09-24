"""Los nombres del encargo no salen de la maquina (specs/spec3.md, RF3-SEU-01 a 05).

Antes de cada llamada a un agente del pipeline, los nombres del brief (destinatario, quien
regala y allegados), enteros y por partes, se cambian por etiquetas reversibles; al volver la
respuesta, las etiquetas se cambian por los nombres. Asi el modelo trabaja con
`[DESTINATARIO_NOMBRE]` y el grafo, las puertas y la lectura siguen viendo el nombre real. La
busqueda es la del seudonimizador de Langfuse (plegado y fronteras de palabra), con una
diferencia: aqui una forma solo casa si empieza en mayuscula, porque lo que se reescribe es lo
que lee el modelo, y «la luz del pasillo» no puede volverse «la [DESTINATARIO_NOMBRE] del
pasillo» (validador de cd8ab12). La excepcion es un nombre que el brief escribe en minuscula,
que casa en cualquier grafia: asi viaja en los paquetes (validador de 7e88879).
"""

from __future__ import annotations

import re
from typing import Any, cast

from compartido.brief import Brief
from compartido.grafo.escritura import normalizar
from compartido.texto import INICIO_DE_FRASE, PARTICULAS_DE_NOMBRE
from compartido.tipos import como_dict, como_lista

from .observabilidad import ACOMPANAN_A_LA_FIRMA, Seudonimizador, partes_del_nombre, plegar

#: La etiqueta del nombre que tenia una persona del encargo antes de un cambio del lector.
ANTERIOR = "NOMBRE_ANTERIOR"

#: Con que empieza una firma descriptiva de quien regala («tu tía Carmen», «Los García»).
_DETERMINANTES = frozenset({
    "tu", "tus", "su", "sus", "mi", "mis", "vuestro", "vuestra", "vuestros", "vuestras",
    "nuestro", "nuestra", "nuestros", "nuestras", "el", "la", "los", "las", "un", "una",
    "todos", "todas",
})
#: Palabras de una firma descriptiva que no son nombre y no se ocultan sueltas (plegadas).
_NO_SON_NOMBRE = _DETERMINANTES | ACOMPANAN_A_LA_FIRMA | {
    "companero", "companera", "companeros", "companeras", "colega", "colegas", "equipo",
    "clase", "instituto", "colegio", "oficina", "trabajo", "compis",
}


class Mascara:
    """El cambio de nombres por etiquetas y su vuelta, para un brief.

    `anterior` es el nombre viejo de una persona del encargo que el lector acaba de renombrar
    (RF3-CAM-11): el brief ya trae el nuevo, y el viejo sigue en la prosa aprobada.
    """

    def __init__(self, brief: Brief | None, *, anterior: str | None = None) -> None:
        self._originales: dict[str, str] = {}   # etiqueta que produce `ocultar` -> nombre
        self._alias: dict[str, str] = {}        # etiqueta que se acepta al volver -> nombre
        self._roles: list[str] = []
        self._minusculas: set[str] = set()
        formas: dict[str, str] = {}
        grupos = _grupos(brief) if brief is not None else []
        if anterior and grupos:
            grupos.append((ANTERIOR, anterior, False,
                           f"[{ANTERIOR}]: el nombre que tenia antes esa persona. No lo "
                           "escribas: donde estaba, va la etiqueta nueva."))
        for base, nombre, firma, rol in grupos:
            self._anadir(formas, base, nombre, firma=firma, rol=rol)
        # Las formas largas antes que sus partes: «Marta Ibanez» entera, no «[X] Ibanez». Una
        # forma casa en cualquier grafia solo si el brief la escribe en minuscula: entonces es
        # asi como viaja en los paquetes, y ocultarla gana a no tocar «la luz».
        self._busqueda = Seudonimizador.desde_formas(sorted(
            ((f, e, f in self._minusculas) for f, e in formas.items()),
            key=lambda t: len(t[0]), reverse=True,
        ))
        aceptadas = {**self._alias, **self._originales}
        self._vuelta = re.compile(
            r"\[(" + "|".join(re.escape(e[1:-1]) for e in aceptadas) + r")\]", re.IGNORECASE,
        ) if aceptadas else None

    def _anadir(self, formas: dict[str, str], base: str, nombre: str, *, firma: bool,
                rol: str) -> None:
        plegado, posiciones, _ = plegar(nombre)
        completo = " ".join(plegado.split())
        palabras = completo.split(" ")
        # La firma de quien regala se oculta siempre entera, en cualquier grafia, y vuelve tal
        # como la escribio el comprador. Si es descriptiva («tu tía Carmen», «Los García»), sus
        # palabras sueltas se ocultan tambien, salvo determinantes y parentescos, esten en
        # mayuscula o en minuscula (validadores de ac7dc1d y 32b785c).
        descriptiva = firma and bool(palabras) and palabras[0] in _DETERMINANTES
        candidatas = list(partes_del_nombre(nombre, firma=firma))
        if descriptiva:
            candidatas = [f for f in candidatas if f not in _NO_SON_NOMBRE]
        if completo and completo not in candidatas:
            candidatas.append(completo)
        propias = 0
        extra = 2
        for forma in sorted(candidatas, key=plegado.find):
            original = _original(nombre, plegado, posiciones, forma)
            if original is None:
                continue
            if forma in formas:
                continue  # el primero que la reclama se la queda (el destinatario manda)
            if forma == completo:
                etiqueta = f"[{base}]"
            elif descriptiva:
                etiqueta = f"[{base}_{extra}]"
                extra += 1
            elif len(palabras) > 1 and forma == palabras[0]:
                etiqueta = f"[{base}_NOMBRE]"
            elif len(palabras) > 1 and forma == palabras[-1]:
                etiqueta = f"[{base}_APELLIDO]"
            else:
                etiqueta = f"[{base}_{extra}]"
                extra += 1
            formas[forma] = etiqueta
            self._originales[etiqueta] = original if descriptiva else _grafia(original)
            if not original[:1].isupper() or (firma and forma == completo):
                self._minusculas.add(forma)
            propias += 1
        if descriptiva:
            sueltas = [self._originales[formas[f]] for f in candidatas
                       if f != completo and f in formas]
            entera = " ".join(nombre.split())
            self._alias.setdefault(f"[{base}]", entera)
            self._alias.setdefault(f"[{base}_NOMBRE]", sueltas[0] if sueltas else entera)
            self._alias.setdefault(f"[{base}_APELLIDO]", sueltas[-1] if sueltas else entera)
            self._roles.append(rol)
            return
        # Lo que un modelo escribiria por analogia tambien vuelve: `_NOMBRE` de un nombre de
        # una palabra, o la etiqueta de quien regala cuando es un allegado.
        entero = _grafia(" ".join(nombre.split()))
        trozos = entero.split()
        self._alias.setdefault(f"[{base}]", entero)
        self._alias.setdefault(f"[{base}_NOMBRE]", trozos[0] if trozos else entero)
        self._alias.setdefault(f"[{base}_APELLIDO]", trozos[-1] if trozos else entero)
        if propias:
            self._roles.append(rol)
        elif completo in formas:
            self._roles.append(f"{rol.split(':', 1)[1].strip().rstrip('.').capitalize()}: es "
                               f"{formas[completo]}.")

    @property
    def vacia(self) -> bool:
        return not self._originales

    def ocultar(self, texto: str) -> str:
        """El texto con cada nombre del encargo cambiado por su etiqueta."""
        return self._busqueda.texto(texto)

    def restaurar(self, valor: Any) -> Any:
        """La respuesta del agente con cada etiqueta del encargo cambiada por el nombre.

        Recorre textos, listas y diccionarios, tambien sus claves (dos que quedan iguales no
        se pisan). Una etiqueta que no es del encargo se queda: la ve la puerta 4 o la 1.
        """
        if self._vuelta is None:
            return valor
        if isinstance(valor, str):
            texto = valor

            def cambio(m: re.Match[str]) -> str:
                nombre = self._nombre(m.group(1))
                # Al empezar frase, con mayuscula: «tu hermano» vuelve «Tu hermano».
                if nombre[:1].islower() and INICIO_DE_FRASE.search(texto, 0, m.start()):
                    return nombre[:1].upper() + nombre[1:]
                return nombre

            return self._vuelta.sub(cambio, texto)
        if isinstance(valor, dict):
            salida: dict[str, Any] = {}
            for k, v in como_dict(cast(object, valor)).items():
                clave = base = self.restaurar(str(k))
                n = 2
                while clave in salida:
                    clave = f"{base} #{n}"
                    n += 1
                salida[clave] = self.restaurar(v)
            return salida
        if isinstance(valor, list):
            return [self.restaurar(v) for v in como_lista(cast(object, valor))]
        return valor

    def _nombre(self, dentro: str) -> str:
        etiqueta = f"[{dentro.upper()}]"
        return self._originales.get(etiqueta) or self._alias.get(etiqueta) or f"[{dentro}]"

    def leyenda(self) -> str:
        """Lo que el agente tiene que saber de las etiquetas, sin ningun nombre."""
        if self.vacia:
            return ""
        etiquetas = ", ".join(self._originales)
        return self.ocultar(
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
    """La forma, escrita como en el brief (con sus tildes)."""
    patron = r"\s+".join(re.escape(p) for p in forma.split(" "))
    m = re.search(patron, plegado)
    if m is None or m.end() == 0:
        return None
    return nombre[posiciones[m.start()]:posiciones[m.end() - 1] + 1]


def _grafia(texto: str) -> str:
    """Como se escribe el nombre en la prosa: el del brief, salvo que venga todo en minusculas
    o todo en mayusculas, que entonces va con mayuscula inicial en cada trozo («Jean-Luc»,
    «O'Neill»; validadores de cd8ab12 y 7e88879)."""
    if not (texto.islower() or texto.isupper()):
        return texto

    def palabra(p: str, i: int) -> str:
        if i and normalizar(p) in PARTICULAS_DE_NOMBRE:
            return p.lower()
        return "".join(t.capitalize() for t in re.split(r"([-'’])", p))

    return " ".join(palabra(p, i) for i, p in enumerate(texto.split()))
