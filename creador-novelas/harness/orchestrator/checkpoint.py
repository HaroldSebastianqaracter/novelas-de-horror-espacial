"""Manifiesto de ejecución y reanudación (spec técnica §5; RF-CFG-04, RF-07.4, EX-06, INV-07)."""

from __future__ import annotations

from pathlib import Path

from harness.config import HarnessConfig
from harness.errores import ConfiguracionInconsistenteError, ManifiestoInconsistenteError, PausadoPorQAError
from harness.rutas import Rutas
from harness.schemas import Manifest
from harness.state import repository as repo


def leer_manifest(raiz: Path) -> Manifest | None:
    return repo.leer_json(Rutas(raiz).manifest, Manifest)


def exigir_manifest(raiz: Path) -> Manifest:
    m = leer_manifest(raiz)
    if m is None:
        raise ManifiestoInconsistenteError("no existe 04_estado/manifest.json: la fase 3 (escaleta) no se ejecutó")
    return m


def escribir_manifest(raiz: Path, manifest: Manifest) -> None:
    repo.escribir_json(Rutas(raiz).manifest, manifest)


def crear_manifest(raiz: Path, total_capitulos_esperado: int, prompts_hash: dict[str, str] | None = None) -> Manifest:
    m = Manifest(ultimo_capitulo_cerrado=0, total_capitulos_esperado=total_capitulos_esperado,
                 prompts_hash=prompts_hash or {})
    escribir_manifest(raiz, m)
    return m


def leer_estado(raiz: Path) -> str | None:
    m = leer_manifest(raiz)
    return None if m is None else m.estado


def _actualizar(raiz: Path, **cambios) -> Manifest:
    m = exigir_manifest(raiz).model_copy(update=cambios)
    escribir_manifest(raiz, m)
    return m


def verificar_reanudable(raiz: Path, config: HarnessConfig) -> Manifest:
    """RF-CFG-04, RF-07.4, EX-06, §5: todo lo que impide reanudar, en orden."""
    m = exigir_manifest(raiz)
    if m.editado_a_mano():
        raise ManifiestoInconsistenteError(
            f"§5: el manifiesto está en_progreso pero el reporte {m.reporte_qa_pendiente} sigue sin resolver; "
            "solo `resolver` puede cerrarlo"
        )
    if m.estado == "pausado_por_qa":
        raise PausadoPorQAError(
            f"EX-02: la tanda está pausada por el reporte {m.reporte_qa_pendiente}; resolvelo con `resolver`"
        )
    if m.reextraccion_pendiente:
        raise PausadoPorQAError(
            f"RF-07.6: quedan capítulos por reextraer {m.reextraccion_pendiente}; corré /resolver-qa y `resolver --cerrar`"
        )
    if m.ultimo_capitulo_cerrado > 0 and m.total_capitulos_esperado != config.total_capitulos:
        raise ConfiguracionInconsistenteError(
            f"EX-06: la escaleta se generó con total_capitulos = {m.total_capitulos_esperado} y la configuración "
            f"dice {config.total_capitulos}, con {m.ultimo_capitulo_cerrado} capítulos cerrados"
        )
    outline = repo.leer_outline(raiz)
    if outline is not None and m.ultimo_capitulo_cerrado > 0 and len(outline) != config.total_capitulos:
        raise ConfiguracionInconsistenteError(
            f"EX-06: capitulos.json tiene {len(outline)} entradas y la configuración dice {config.total_capitulos}"
        )
    return m


def detectar_punto_de_reanudacion(raiz: Path, config: HarnessConfig) -> int:
    """RF-CFG-04, INV-07: ultimo_capitulo_cerrado + 1."""
    return verificar_reanudable(raiz, config).ultimo_capitulo_cerrado + 1


def marcar_capitulo_cerrado(raiz: Path, n: int) -> Manifest:
    m = exigir_manifest(raiz)
    if n != m.ultimo_capitulo_cerrado + 1:
        raise ManifiestoInconsistenteError(
            f"INV-07: se intentó cerrar el capítulo {n} con ultimo_capitulo_cerrado = {m.ultimo_capitulo_cerrado}"
        )
    return _actualizar(raiz, ultimo_capitulo_cerrado=n, capitulo_activo=None, ultimo_error=None)


def registrar_qa(raiz: Path, n: int) -> Manifest:
    return _actualizar(raiz, ultimo_qa_ejecutado=n)


def pausar_por_qa(raiz: Path, n: int) -> Manifest:
    """RF-07.4: el nombre del reporte pendiente es `qa_cap_N`."""
    return _actualizar(raiz, estado="pausado_por_qa", reporte_qa_pendiente=f"qa_cap_{n}", ultimo_qa_ejecutado=n)


def marcar_completo(raiz: Path) -> Manifest:
    return _actualizar(raiz, estado="completo", capitulo_activo=None)


def registrar_intentos(raiz: Path, n: int, intentos: int) -> Manifest:
    m = exigir_manifest(raiz)
    intentos_por_capitulo = dict(m.intentos_por_capitulo)
    intentos_por_capitulo[str(n)] = max(intentos, intentos_por_capitulo.get(str(n), 0))
    return _actualizar(raiz, intentos_por_capitulo=intentos_por_capitulo)


def registrar_error(raiz: Path, texto: str) -> Manifest:
    return _actualizar(raiz, ultimo_error=texto)


def limpiar_error(raiz: Path) -> Manifest:
    return _actualizar(raiz, ultimo_error=None)


def fijar_capitulo_activo(raiz: Path, n: int | None) -> Manifest:
    return _actualizar(raiz, capitulo_activo=n)


def actualizar_prompts_hash(raiz: Path, hashes: dict[str, str]) -> Manifest:
    return _actualizar(raiz, prompts_hash=hashes)


def iniciar_resolucion(raiz: Path, reporte: str, capitulos: list[int]) -> Manifest:
    """RF-07.6 paso 1 (parte del manifiesto): deja la lista pendiente y el primer capítulo como activo."""
    return _actualizar(raiz, reextraccion_pendiente=sorted(set(capitulos)), resolucion_iniciada=True,
                       capitulo_activo=min(capitulos) if capitulos else None)


def quitar_reextraccion(raiz: Path, n: int) -> Manifest:
    m = exigir_manifest(raiz)
    pendientes = [k for k in m.reextraccion_pendiente if k != n]
    return _actualizar(raiz, reextraccion_pendiente=pendientes, capitulo_activo=pendientes[0] if pendientes else None)


def cerrar_resolucion(raiz: Path) -> Manifest:
    """RF-07.6 paso 3: único código que pone reporte_qa_pendiente = null (§10)."""
    m = exigir_manifest(raiz)
    if not m.resolucion_iniciada:
        raise PausadoPorQAError(
            "RF-07.6: el paso 3 exige haber declarado antes qué se corrigió: `resolver --reporte X --capitulos a,b` o `--sin-cambios`"
        )
    if m.reextraccion_pendiente:
        raise PausadoPorQAError(f"RF-07.6: quedan capítulos por reextraer: {m.reextraccion_pendiente}")
    return _actualizar(raiz, estado="en_progreso", reporte_qa_pendiente=None, capitulo_activo=None,
                       resolucion_iniciada=False, ultimo_error=None)


def texto_status(raiz: Path) -> str:
    """Salida de `status` y de H-01 (RF-08.3)."""
    rutas = Rutas(raiz)
    lineas = ["ESTADO DE LA NOVELA (python -m harness status)"]
    m = leer_manifest(raiz)
    if m is None:
        lineas.append("- manifiesto: no existe; la novela no llegó a la fase 3 (escaleta)")
        for nombre, path in (("style_guide", rutas.style_guide), ("premisa", rutas.premisa),
                             ("tres_actos", rutas.tres_actos), ("capitulos.json", rutas.capitulos)):
            lineas.append(f"- {nombre}: {'existe' if path.exists() else 'falta'}")
        return "\n".join(lineas)
    lineas.append(f"- estado: {m.estado}")
    lineas.append(f"- ultimo_capitulo_cerrado: {m.ultimo_capitulo_cerrado} de {m.total_capitulos_esperado}")
    lineas.append(f"- ultimo_qa_ejecutado: {m.ultimo_qa_ejecutado}")
    lineas.append(f"- reporte_qa_pendiente: {m.reporte_qa_pendiente or 'ninguno'}")
    if m.reextraccion_pendiente:
        lineas.append(f"- reextraccion_pendiente: {m.reextraccion_pendiente} (corré /resolver-qa)")
    lineas.append(f"- capitulo_activo: {m.capitulo_actual()}" + (" (por defecto: siguiente al cerrado)" if m.capitulo_activo is None else ""))
    if m.intentos_por_capitulo:
        lineas.append(f"- intentos_por_capitulo: {m.intentos_por_capitulo}")
    if m.editado_a_mano():
        lineas.append("- ATENCIÓN: manifiesto inconsistente (en_progreso con reporte pendiente); no se reanuda")
    if m.ultimo_error:
        lineas.append(f"- ultimo_error: {m.ultimo_error}")
    if rutas.cursor.exists():
        lineas.append(f"- cursor de tanda presente en {rutas.cursor.as_posix()} (una tanda quedó a mitad; `tanda iniciar` lo recalcula)")
    return "\n".join(lineas)
