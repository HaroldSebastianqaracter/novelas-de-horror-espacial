"""Lectura y escritura de artefactos con validación previa a la escritura (spec técnica §4, EX-01).

Reglas de acceso al manuscrito que hace cumplir el código (§2, §10):
- `leer_manuscrito(raiz, n)` la importa quien necesite un capítulo; `agents/escritor.py` NUNCA la importa (INV-01).
- `leer_muestra_manuscrito(raiz, caps)` la importa solo `agents/qa.py` (INV-05).
- `guardar_capitulo` falla si el archivo ya existe (INV-07).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from harness.errores import CapituloCerradoError, EstadoInvalidoError
from harness.rutas import Rutas
from harness.schemas import (
    DeltaExtraccion, FichaPersonajes, LogContinuidad, Manifest, Mundo, Outline, RecursosUsados, ReporteQA,
)
from harness.schemas.outline import EntradaOutline
from harness.state import continuidad as cont

M = TypeVar("M", bound=BaseModel)


# ---------- primitivas JSON ----------

def _formatear(e: ValidationError) -> str:
    return "; ".join(f"{'.'.join(str(p) for p in err['loc']) or '<raíz>'}: {err['msg']}" for err in e.errors())


def validar_texto(texto: str, modelo: type[M], nombre: str) -> M:
    """Valida un texto JSON contra un modelo. Falla con EstadoInvalidoError (EX-01)."""
    try:
        datos = json.loads(texto)
    except json.JSONDecodeError as e:
        raise EstadoInvalidoError(f"EX-01: {nombre} no es JSON válido: {e}") from e
    try:
        return modelo.model_validate(datos)
    except ValidationError as e:
        raise EstadoInvalidoError(f"EX-01: {nombre} no valida contra {modelo.__name__}: {_formatear(e)}") from e


def leer_json(path: Path, modelo: type[M]) -> M | None:
    if not path.exists():
        return None
    return validar_texto(path.read_text(encoding="utf-8"), modelo, path.name)


def serializar(modelo: BaseModel) -> str:
    return modelo.model_dump_json(indent=2) + "\n"


def escribir_json(path: Path, modelo: BaseModel) -> None:
    """Revalida y escribe. La revalidación atrapa mutaciones posteriores a la construcción."""
    try:
        modelo.__class__.model_validate(modelo.model_dump())
    except ValidationError as e:
        raise EstadoInvalidoError(f"EX-01: {path.name} no valida antes de escribirse: {_formatear(e)}") from e
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(serializar(modelo), encoding="utf-8")


# ---------- esquema por ruta (H-02) ----------

def esquema_para(rutas: Rutas, rel: Path) -> type[BaseModel] | None:
    """Devuelve el modelo Pydantic que rige un archivo JSON de 04_estado/ o 06_qa/, o None si no le corresponde ninguno."""
    partes = rel.parts
    if not partes or rel.suffix != ".json":
        return None
    if partes[0] == "04_estado":
        if len(partes) == 2:
            return {
                "manifest.json": Manifest, "personajes.json": FichaPersonajes, "continuidad.json": LogContinuidad,
                "capitulos.json": Outline, "mundo.json": Mundo,
            }.get(partes[1])
        if len(partes) == 3 and partes[1] == "deltas" and partes[2].startswith("delta_cap_"):
            return DeltaExtraccion
        return None
    if partes[0] == "06_qa":
        if len(partes) == 2 and partes[1] == "recursos_usados.json":
            return RecursosUsados
        if len(partes) == 3 and partes[1] == "reportes" and partes[2].startswith("qa_cap_"):
            return ReporteQA
    return None


def validar_archivo(rutas: Rutas, rel: Path) -> str:
    """H-02: valida el archivo contra su esquema. Devuelve el nombre del esquema; falla con EstadoInvalidoError."""
    modelo = esquema_para(rutas, rel)
    if modelo is None:
        raise EstadoInvalidoError(f"EX-01: {rel.as_posix()} no tiene esquema conocido; nada debería escribir ahí")
    path = rutas.raiz / rel
    if not path.exists():
        raise EstadoInvalidoError(f"EX-01: {rel.as_posix()} no existe tras la escritura")
    validar_texto(path.read_text(encoding="utf-8"), modelo, rel.as_posix())
    return modelo.__name__


# ---------- artefactos de estado ----------

def leer_outline(raiz: Path) -> Outline | None:
    return leer_json(Rutas(raiz).capitulos, Outline)


def leer_outline_entry(raiz: Path, n: int) -> EntradaOutline | None:
    outline = leer_outline(raiz)
    return None if outline is None else outline.entrada(n)


def escribir_outline(raiz: Path, outline: Outline) -> None:
    escribir_json(Rutas(raiz).capitulos, outline)


def leer_personajes(raiz: Path) -> FichaPersonajes:
    return leer_json(Rutas(raiz).personajes, FichaPersonajes) or FichaPersonajes({})


def escribir_personajes(raiz: Path, fichas: FichaPersonajes) -> None:
    escribir_json(Rutas(raiz).personajes, fichas)


def leer_mundo(raiz: Path) -> Mundo | None:
    return leer_json(Rutas(raiz).mundo, Mundo)


def escribir_mundo(raiz: Path, mundo: Mundo) -> None:
    escribir_json(Rutas(raiz).mundo, mundo)


def leer_continuidad(raiz: Path) -> LogContinuidad:
    return leer_json(Rutas(raiz).continuidad, LogContinuidad) or LogContinuidad([])


def escribir_continuidad(raiz: Path, log: LogContinuidad) -> None:
    """INV-03 a nivel de código: la versión nueva debe ser superconjunto de la que está en disco."""
    previa = leer_continuidad(raiz)
    ok, motivo = cont.es_superconjunto(previa, log)
    if not ok:
        raise EstadoInvalidoError(f"INV-03: continuidad.json perdería información: {motivo}")
    escribir_json(Rutas(raiz).continuidad, log)


def leer_texto(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def leer_style_guide(raiz: Path) -> str:
    return leer_texto(Rutas(raiz).style_guide)


def leer_tres_actos(raiz: Path) -> str:
    return leer_texto(Rutas(raiz).tres_actos)


def leer_premisa(raiz: Path) -> str:
    return leer_texto(Rutas(raiz).premisa)


def leer_resumen_rodante(raiz: Path) -> str:
    return leer_texto(Rutas(raiz).resumen_rodante)


def escribir_resumen_rodante(raiz: Path, texto: str) -> None:
    path = Rutas(raiz).resumen_rodante
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(texto, encoding="utf-8")


def escribir_texto(path: Path, texto: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(texto, encoding="utf-8")


# ---------- manuscrito ----------

def guardar_capitulo(raiz: Path, n: int, texto: str, *, reemplazar_borrador: bool = False) -> Path:
    """RF-05.4. INV-07: falla si el archivo ya existe, salvo que se pida reemplazar un borrador (reintentos RF-05.2)."""
    path = Rutas(raiz).capitulo(n)
    if path.exists() and not reemplazar_borrador:
        raise CapituloCerradoError(f"INV-07: {path.name} ya existe y no se regenera")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(texto, encoding="utf-8")
    return path


def existe_capitulo(raiz: Path, n: int) -> bool:
    return Rutas(raiz).capitulo(n).exists()


def descartar_borrador(raiz: Path, n: int, ultimo_cerrado: int) -> None:
    """EX-08: elimina el borrador de un capítulo NO cerrado. Nunca toca un capítulo cerrado (INV-07)."""
    if n <= ultimo_cerrado:
        raise CapituloCerradoError(f"INV-07: el capítulo {n} está cerrado; no se descarta")
    path = Rutas(raiz).capitulo(n)
    if path.exists():
        path.unlink()


def leer_manuscrito(raiz: Path, n: int) -> str:
    """Texto de un capítulo. `agents/escritor.py` no debe importar esta función bajo ninguna firma (INV-01)."""
    path = Rutas(raiz).capitulo(n)
    if not path.exists():
        raise FileNotFoundError(f"no existe {path}")
    return path.read_text(encoding="utf-8")


def leer_muestra_manuscrito(raiz: Path, caps: list[int]) -> dict[int, str]:
    """Muestra de varios capítulos. Solo `agents/qa.py` la importa (INV-05)."""
    return {n: leer_manuscrito(raiz, n) for n in caps}


# ---------- QA ----------

def leer_reporte_qa(raiz: Path, n: int) -> ReporteQA | None:
    return leer_json(Rutas(raiz).reporte_qa_json(n), ReporteQA)


def guardar_reporte_qa(raiz: Path, reporte: ReporteQA, texto_md: str | None = None) -> None:
    rutas = Rutas(raiz)
    escribir_json(rutas.reporte_qa_json(reporte.cap_corte), reporte)
    if texto_md is not None:
        escribir_texto(rutas.reporte_qa_md(reporte.cap_corte), texto_md)


def leer_recursos_usados(raiz: Path) -> RecursosUsados:
    return leer_json(Rutas(raiz).recursos_usados, RecursosUsados) or RecursosUsados([])


def escribir_recursos_usados(raiz: Path, recursos: RecursosUsados) -> None:
    escribir_json(Rutas(raiz).recursos_usados, recursos)
