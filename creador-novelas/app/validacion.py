"""Validadores por rol (RF-08.4; spec técnica §8.2, capa de validación).

Un solo código para dos usos: el agente lo ejecuta desde su bucle (`python -m app validar-<rol> N`) y el
verbo del orquestador que aplica (`registrar-escritor`, `aplicar-delta`, `cerrar-qa`) lo vuelve a ejecutar.
Los tres son de solo lectura: comprueban y devuelven errores, nunca corrigen ni persisten.

También vive aquí `capitulo_de_invocacion`, la única función que resuelve a qué capítulo pertenece una
invocación de agente; la comparten H-05, H-06, H-07, H-10 y H-11 (§13.3).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from app import antirrepeticion
from app.agents import escritor, extractor
from app.config import INTERPRETE, ROLES, VERBO_POR_ROL, HarnessConfig, comando_validador  # noqa: F401  (re-export)
from app.errores import EstadoInvalidoError
from app.orchestrator import checkpoint
from app.rutas import Rutas
from app.schemas import ReporteQA
from app.state import personajes as pers
from app.state import repository as repo


def capitulo_de_invocacion(raiz: Path, rol: str | None) -> int:
    """El capítulo al que pertenece la invocación de un agente (§13.3, H-05/H-11).

    escritor y extractor: `capitulo_activo` del manifiesto si está fijado (reextracción, §8.2) y
    `ultimo_capitulo_cerrado + 1` si no. qa: `ultimo_capitulo_cerrado`, porque su corte evalúa el que acaba de cerrarse.
    """
    m = checkpoint.leer_manifest(raiz)
    if m is None:
        return 0 if rol == "qa" else 1
    return m.ultimo_capitulo_cerrado if rol == "qa" else m.capitulo_actual()


@dataclass
class ResultadoValidacion:
    rol: str
    artefacto: str  # ruta relativa del artefacto validado
    errores: list[str] = field(default_factory=list)  # vacío = válido
    avisos: list[str] = field(default_factory=list)  # no invalidan: sujetos sin validar, EX-08 detectado
    datos: dict = field(default_factory=dict)  # conteos útiles para el mensaje final del agente

    @property
    def valido(self) -> bool:
        return not self.errores


# ---------- escritor ----------

def _tokens_nombre(nombre: str) -> list[str]:
    return [t for t in re.findall(r"\w+", nombre) if len(t) >= 3]


def validar_capitulo(raiz: Path, config: HarnessConfig, n: int) -> ResultadoValidacion:
    """RF-08.4 escritor: el borrador existe, es solo prosa, respeta la longitud (EX-07) y trae a los personajes en escena."""
    rutas = Rutas(raiz)
    r = ResultadoValidacion(rol="escritor", artefacto=rutas.capitulo(n).relative_to(raiz).as_posix())
    if not rutas.capitulo(n).exists():
        r.errores.append(f"RF-05.4: no existe {r.artefacto}; escribí el capítulo con Write antes de validar")
        return r
    texto = rutas.capitulo(n).read_text(encoding="utf-8")
    palabras = escritor.contar_palabras(texto)
    r.datos["palabras"] = palabras
    ok, mensaje = escritor.evaluar_longitud(palabras, config)
    if not ok:
        r.errores.append(mensaje)
    encabezados = [l for l in texto.splitlines() if l.lstrip().startswith("#")]
    if encabezados:
        r.errores.append(f"el archivo lleva solo prosa: quitá los encabezados ({encabezados[0].strip()[:40]!r})")
    entrada = repo.leer_outline_entry(raiz, n)
    if entrada is not None:
        texto_bajo = texto.lower()
        ausentes = [p for p in entrada.personajes
                    if not any(t.lower() in texto_bajo for t in _tokens_nombre(p))]
        if ausentes:  # aviso, no error: un personaje puede estar en escena sin que su nombre aparezca literal
            r.avisos.append(f"RF-03.1: personajes en escena que no aparecen por su nombre en el capítulo: {', '.join(ausentes)}")
        registro = list(repo.leer_personajes(raiz).root.keys())
        r.datos["personajes_en_escena"] = list(entrada.personajes)
        r.datos["personajes_detectados"] = [p for p in registro
                                            if any(t.lower() in texto_bajo for t in _tokens_nombre(p))]
    # RF-05.5 / §17.1: ninguna secuencia de 4+ palabras con contenido léxico repetida literalmente de un capítulo anterior.
    # Lo lee código, no el agente: INV-01 restringe al escritor, no a este validador.
    previos = {k: repo.leer_manuscrito(raiz, k) for k in range(1, n) if repo.existe_capitulo(raiz, k)}
    if previos:
        mundo = repo.leer_mundo(raiz)
        nombres = list(repo.leer_personajes(raiz).root.keys()) + (mundo.nombres_locaciones() if mundo else [])
        hallazgos = antirrepeticion.coincidencias(texto, previos, antirrepeticion.tokens_de_nombres(nombres))
        r.datos["repeticiones_literales"] = len(hallazgos)
        if hallazgos:
            r.errores.append(antirrepeticion.describir(hallazgos))
    return r


# ---------- extractor ----------

def validar_delta(raiz: Path, config: HarnessConfig, n: int) -> ResultadoValidacion:
    """RF-08.4 extractor: el delta existe, es JSON del esquema, respeta el tope de hechos y usa el registro de sujetos.

    Un personaje fuera del registro en `personajes` NO es error del extractor: es EX-08 del borrador y se informa
    como aviso para que el extractor no lo esconda. Un `sujeto` fuera del registro tampoco: se conserva sin validar.
    """
    rutas = Rutas(raiz)
    r = ResultadoValidacion(rol="extractor", artefacto=rutas.delta(n).relative_to(raiz).as_posix())
    if not rutas.delta(n).exists():
        r.errores.append(f"no existe {r.artefacto}; escribí el delta con Write antes de validar")
        return r
    try:
        delta = extractor.parsear_delta(rutas.delta(n).read_text(encoding="utf-8"))
        registro = pers.sujetos_conocidos(repo.leer_personajes(raiz), repo.leer_mundo(raiz))
        validado = extractor.validar_delta(delta, registro, config, n)
    except EstadoInvalidoError as e:
        r.errores.append(str(e))
        return r
    r.datos["hechos"] = len(validado.delta.hechos_nuevos)
    r.datos["personajes"] = len(validado.delta.personajes)
    if validado.sujetos_no_validados:
        r.avisos.append(f"sujetos fuera del registro (se conservan con sujeto_validado=false): {validado.sujetos_no_validados}")
    if validado.claves_no_previstas:
        # Que alguna clave sea nueva es EX-08 y se avisa: el harness regenera el capítulo más
        # adelante. Que NO se reconozca ninguna es otra cosa: un delta cuyo reparto entero es ajeno
        # al libro no es un delta con un fallo, es el delta de otro libro. Las marcas de tiempo no
        # bastan para distinguirlo --una copia del árbol las iguala-- y esto no depende del reloj.
        # Desde dos: con un solo nombre nuevo y ninguno conocido no hay reparto del que hablar, y un
        # capítulo que presenta a alguien es normal. Dos o más desconocidos y cero conocidos ya no.
        if len(validado.claves_no_previstas) == len(validado.delta.personajes) >= 2:
            r.errores.append(
                f"ninguno de los personajes del delta está en el registro de esta novela: "
                f"{validado.claves_no_previstas}. Es el delta de otro libro; borralo y volvé a emitirlo")
            return r
        r.avisos.append(f"EX-08: claves de personajes fuera del registro: {validado.claves_no_previstas}; "
                        "no las quites: el harness regenera el capítulo")
    return r


def cargar_delta_validado(raiz: Path, config: HarnessConfig, n: int, texto: str | None = None) -> extractor.DeltaValidado:
    """Lo que usa `aplicar-delta`: el mismo parseo y la misma validación que `validar-delta`, y falla con EX-01."""
    rutas = Rutas(raiz)
    if texto is None:
        if not rutas.delta(n).exists():
            raise EstadoInvalidoError(f"no existe {rutas.delta(n).relative_to(raiz).as_posix()}: el extractor debe escribirlo y validarlo (RF-08.4)")
        texto = rutas.delta(n).read_text(encoding="utf-8")
    delta = extractor.parsear_delta(texto)
    registro = pers.sujetos_conocidos(repo.leer_personajes(raiz), repo.leer_mundo(raiz))
    return extractor.validar_delta(delta, registro, config, n)


# ---------- qa ----------

def validar_reporte(raiz: Path, n: int) -> ResultadoValidacion:
    """RF-08.4 qa: qa_cap_N.json valida contra ReporteQA con cap_corte = N, existe el .md y recursos_usados.json valida."""
    rutas = Rutas(raiz)
    r = ResultadoValidacion(rol="qa", artefacto=rutas.reporte_qa_json(n).relative_to(raiz).as_posix())
    try:
        reporte = repo.leer_reporte_qa(raiz, n)
    except EstadoInvalidoError as e:
        r.errores.append(str(e))
        reporte = None
    if reporte is None and not r.errores:
        r.errores.append(f"RF-07.2: no existe {r.artefacto}")
    if reporte is not None:
        if reporte.cap_corte != n:
            r.errores.append(f"RF-07.2: el reporte dice cap_corte = {reporte.cap_corte} y el corte es {n}")
        conteo = reporte.conteo_por_tipo()
        r.datos.update(contradicciones=conteo["contradiccion"], repeticiones=conteo["repeticion"],
                       tiene_contradicciones=reporte.tiene_contradicciones)
    if not rutas.reporte_qa_md(n).exists():
        r.errores.append(f"RF-07.2: no existe {rutas.reporte_qa_md(n).relative_to(raiz).as_posix()}")
    if not rutas.recursos_usados.exists():
        r.errores.append(f"RF-07.5: no existe {rutas.recursos_usados.relative_to(raiz).as_posix()}; es obligatorio aunque no haya repeticiones")
    else:
        try:
            repo.leer_recursos_usados(raiz)
        except EstadoInvalidoError as e:
            r.errores.append(str(e))
    return r


def exigir_reporte(raiz: Path, n: int) -> ReporteQA:
    """Lo que usa `cerrar-qa`: la misma comprobación que `validar-reporte`, y falla con EX-01."""
    r = validar_reporte(raiz, n)
    if not r.valido:
        raise EstadoInvalidoError("; ".join(r.errores))
    reporte = repo.leer_reporte_qa(raiz, n)
    assert reporte is not None
    return reporte
