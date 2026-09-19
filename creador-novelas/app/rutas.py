"""Resolución de rutas del proyecto. Todas son relativas a la raíz de `creador-novelas/` (spec técnica §2)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def raiz_desde_entorno(cwd: str | os.PathLike | None = None) -> Path:
    """Raíz del proyecto: HARNESS_RAIZ (tests), CLAUDE_PROJECT_DIR (hooks) o el directorio actual."""
    for var in ("HARNESS_RAIZ", "CLAUDE_PROJECT_DIR"):
        valor = os.environ.get(var)
        if valor:
            return Path(valor).resolve()
    return Path(cwd or Path.cwd()).resolve()


@dataclass(frozen=True)
class Rutas:
    raiz: Path

    # carpetas
    @property
    def referencias(self) -> Path:
        return self.raiz / "00_referencias"

    @property
    def concepto(self) -> Path:
        return self.raiz / "01_concepto"

    @property
    def estado(self) -> Path:
        return self.raiz / "04_estado"

    @property
    def manuscrito(self) -> Path:
        return self.raiz / "05_manuscrito"

    @property
    def qa(self) -> Path:
        return self.raiz / "06_qa"

    @property
    def reportes_qa(self) -> Path:
        return self.qa / "reportes"

    @property
    def registro(self) -> Path:
        return self.raiz / "07_registro"

    @property
    def config(self) -> Path:
        return self.raiz / "config"

    @property
    def prompts_config(self) -> Path:
        return self.config / "prompts"

    @property
    def skills(self) -> Path:
        return self.raiz / ".claude" / "skills"

    @property
    def tanda(self) -> Path:
        return self.raiz / ".tanda"

    @property
    def prompts_trabajo(self) -> Path:
        return self.estado / "prompts"

    @property
    def deltas_trabajo(self) -> Path:
        return self.estado / "deltas"

    # artefactos de estado
    @property
    def style_guide(self) -> Path:
        return self.estado / "style_guide.md"

    @property
    def idea(self) -> Path:
        return self.concepto / "idea.md"

    @property
    def premisa(self) -> Path:
        return self.concepto / "premisa.md"

    @property
    def tres_actos(self) -> Path:
        return self.estado / "tres_actos.md"

    @property
    def capitulos(self) -> Path:
        return self.estado / "capitulos.json"

    @property
    def personajes(self) -> Path:
        return self.estado / "personajes.json"

    @property
    def mundo(self) -> Path:
        return self.estado / "mundo.json"

    @property
    def continuidad(self) -> Path:
        return self.estado / "continuidad.json"

    @property
    def resumen_rodante(self) -> Path:
        return self.estado / "resumen_rodante.md"

    @property
    def recursos_narrativos(self) -> Path:
        return self.estado / "recursos_narrativos.json"  # RF-05.5 / §17.2: lo acumula aplicar-delta

    @property
    def manifest(self) -> Path:
        return self.estado / "manifest.json"

    @property
    def uso(self) -> Path:
        return self.estado / "uso.jsonl"

    @property
    def recursos_usados(self) -> Path:
        return self.qa / "recursos_usados.json"

    @property
    def metricas_qa(self) -> Path:
        return self.qa / "metricas.jsonl"

    # configuración
    @property
    def novela_json(self) -> Path:
        return self.config / "novela.json"

    @property
    def ejecucion_json(self) -> Path:
        return self.config / "ejecucion.json"

    @property
    def proveedores_json(self) -> Path:
        return self.config / "proveedores.json"

    # transitorios
    @property
    def cursor(self) -> Path:
        return self.tanda / "cursor.json"

    @property
    def hooks_estado(self) -> Path:
        return self.tanda / "hooks.json"

    @property
    def continuidad_previa(self) -> Path:
        return self.tanda / "continuidad.prev.json"

    # por capítulo
    def capitulo(self, n: int) -> Path:
        return self.manuscrito / f"cap_{n}.md"

    def prompt_escritor(self, n: int) -> Path:
        return self.prompts_trabajo / f"escritor_cap_{n}.md"

    def hechos_inyectados(self, n: int) -> Path:
        return self.prompts_trabajo / f"escritor_cap_{n}.hechos.json"

    def prompt_extractor(self, n: int) -> Path:
        return self.prompts_trabajo / f"extractor_cap_{n}.md"

    def prompt_qa(self, n: int) -> Path:
        return self.prompts_trabajo / f"qa_cap_{n}.md"

    def delta(self, n: int) -> Path:
        return self.deltas_trabajo / f"delta_cap_{n}.json"

    def reporte_qa_md(self, n: int) -> Path:
        return self.reportes_qa / f"qa_cap_{n}.md"

    def reporte_qa_json(self, n: int) -> Path:
        return self.reportes_qa / f"qa_cap_{n}.json"

    def relativa(self, ruta: str | os.PathLike | None) -> Path | None:
        """Ruta relativa a la raíz, o None si queda fuera del proyecto o no se dio ruta."""
        if ruta is None or str(ruta) == "":
            return None
        candidata = Path(ruta)
        if not candidata.is_absolute():
            candidata = self.raiz / candidata
        try:
            return candidata.resolve().relative_to(self.raiz.resolve())
        except ValueError:
            return None

    def crear_carpetas(self) -> None:
        for carpeta in (self.referencias, self.concepto, self.estado, self.manuscrito, self.reportes_qa,
                        self.config, self.prompts_config, self.prompts_trabajo, self.deltas_trabajo):
            carpeta.mkdir(parents=True, exist_ok=True)


def es_ruta_manuscrito(rel: Path | None) -> bool:
    return rel is not None and len(rel.parts) > 0 and rel.parts[0] == "05_manuscrito"


def numero_capitulo(rel: Path | None) -> int | None:
    """Devuelve N si la ruta relativa es 05_manuscrito/cap_N.md."""
    if not es_ruta_manuscrito(rel) or len(rel.parts) != 2:
        return None
    nombre = rel.parts[1]
    if nombre.startswith("cap_") and nombre.endswith(".md"):
        try:
            return int(nombre[4:-3])
        except ValueError:
            return None
    return None


def bajo(rel: Path | None, *carpeta: str) -> bool:
    """True si la ruta relativa está dentro de la carpeta dada (p. ej. bajo(rel, '06_qa'))."""
    return rel is not None and len(rel.parts) >= len(carpeta) and tuple(rel.parts[: len(carpeta)]) == carpeta
