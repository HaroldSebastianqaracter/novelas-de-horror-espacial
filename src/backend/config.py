"""Configuracion del backend. Un solo sitio donde se leen variables de entorno (RF-PROC-02)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

PREFIJO = "NOVELAS_"


def _env(nombre: str, defecto: str | None = None) -> str | None:
    return os.environ.get(PREFIJO + nombre, defecto)


def _env_int(nombre: str, defecto: int) -> int:
    bruto = _env(nombre)
    if bruto is None or bruto == "":
        return defecto
    try:
        return int(bruto)
    except ValueError as exc:
        raise ConfiguracionInvalida(f"{PREFIJO}{nombre} no es un entero: {bruto!r}") from exc


def _env_bool(nombre: str, defecto: bool) -> bool:
    bruto = _env(nombre)
    if bruto is None or bruto == "":
        return defecto
    return bruto.strip().lower() in {"1", "true", "si", "sí", "yes", "on"}


class ConfiguracionInvalida(Exception):
    """La configuracion del entorno no permite arrancar."""


# --- Presupuesto de contexto (RF-CTX-01, RF2-CTX-12) --------------------------------------
# Cifras PROVISIONALES. Se fijan midiendo un capitulo real; la traza guarda los tokens
# estimados por bloque para poder hacerlo (RF-PUERTO-08). Estos son los valores POR DEFECTO:
# el paquete los recibe de `Config`, nunca de aqui.
PRESUPUESTO_BLOQUES: dict[str, int] = {
    "instrucciones": 8_000,
    "escaleta": 6_000,
    "canon": 20_000,
    "hechos": 16_000,
    "siembras": 2_000,
    "estado_rodante": 10_000,
    "capitulo_anterior": 6_000,
    "recuperado": 4_000,
    "criterios_incumplidos": 2_000,
    # La prosa del capitulo, que leen el extractor y el juez de oficio (no el redactor).
    "prosa": 10_000,
}

# Techo por llamada al modelo (NOVELAS_PRESUPUESTO_TOKENS) y lo que se reserva de el para la
# salida del agente y la sobrecarga de Claude Code. El paquete dispone del resto.
TECHO_POR_LLAMADA = 100_000
RESERVA_SALIDA = 26_000
PRESUPUESTO_PAQUETE = TECHO_POR_LLAMADA - RESERVA_SALIDA

#: Que bloques puede llevar el paquete de cada agente. La suma de sus presupuestos no puede
#: pasar del paquete: si pasara, un paquete lleno a tope no cabria nunca.
BLOQUES_POR_AGENTE: dict[str, tuple[str, ...]] = {
    "redaccion": (
        "instrucciones", "escaleta", "canon", "hechos", "siembras", "estado_rodante",
        "capitulo_anterior", "recuperado", "criterios_incumplidos",
    ),
    "extraccion": ("instrucciones", "canon", "hechos", "siembras", "prosa"),
    "oficio": ("instrucciones", "canon", "escaleta", "prosa", "criterios_incumplidos"),
}

# Bloques que nunca se recortan, y orden en que caen los que si (RF-CTX-01).
BLOQUES_FIJOS = frozenset(
    {"instrucciones", "escaleta", "siembras", "criterios_incumplidos", "prosa"}
)
ORDEN_DE_RECORTE = ("capitulo_anterior", "recuperado", "estado_rodante", "canon", "hechos")

# --- Puerta 4 mecanica (RF-PIPE-13) ------------------------------------------------------
PALABRAS_FILTRO: tuple[str, ...] = (
    "vio", "veia", "veía", "oyo", "oyó", "oia", "oía", "sintio", "sintió", "sentia", "sentía",
    "noto", "notó", "notaba", "se dio cuenta", "se daba cuenta", "empezo a", "empezó a",
    "comenzo a", "comenzó a", "pudo ver", "podia ver", "podía ver", "parecia que", "parecía que",
)

MARCADORES_PENDIENTES: tuple[str, ...] = ("TODO", "XXX", "[[", "<<", "FIXME", "PENDIENTE")

# --- Compatibilidad subgenero / tipo de final (RF-PIPE-05, principios 52 y 54) ------------
FINALES_POR_SUBGENERO: dict[str, frozenset[str]] = {
    "terror_corporal": frozenset({"tragico", "agridulce", "victoria_pirrica", "ambiguo"}),
    "infeccion": frozenset({"tragico", "victoria_pirrica", "abierto", "agridulce"}),
    "horror_cosmico": frozenset({"ambiguo", "abierto", "tragico", "victoria_pirrica"}),
    "slasher_espacial": frozenset({"cerrado", "victoria_pirrica", "abierto"}),
    "ia_hostil": frozenset({"cerrado", "victoria_pirrica", "tragico", "ambiguo"}),
    "supervivencia": frozenset({"agridulce", "victoria_pirrica", "cerrado"}),
}

CRITERIOS_OFICIO: tuple[str, ...] = (
    "voz_constante",
    "distancia_psiquica",
    "emocion_no_nombrada",
    "dialogo_con_subtexto",
    "voces_distinguibles",
    "escena_se_gana_su_lugar",
    "cliche",
    "tropos_con_causalidad",
)

# --- Embeddings (RF-CTX-10) ---------------------------------------------------------------
# Multilingue a proposito: la novela es en castellano y los modelos pequenos mas citados
# (bge-small-en, all-MiniLM-L6-v2, potion-base-8M) son de ingles.
#
# El preferido es el de fastembed. En una maquina sin el redistribuible de Visual C++,
# onnxruntime no carga y `vectores.construir` cae solo al de model2vec, que es numpy puro.
# Que modelo se acabo usando de verdad queda en la tabla indice_estado.
MODELO_EMBEDDING_PREFERIDO = "intfloat/multilingual-e5-small"

MAX_INTENTOS_CAPITULO = 3
UMBRAL_HILO_LATENTE = 6
CAPITULOS_RESUMEN_COMPLETO = 3


@dataclass(frozen=True)
class Config:
    """Configuracion efectiva del proceso."""

    db_path: Path
    claude_bin: str
    skills_dir: Path
    poll_segundos: int
    timeout_agente_segundos: int
    presupuesto_tokens: int
    puerto: Literal["terminal", "falso"]
    puerto_falso_dir: Path | None
    # La dimension NO se configura: es una propiedad del modelo, y un valor de entorno que
    # pueda contradecirla es un fallo esperando. El indice la toma del embedder y la escribe
    # en la tabla indice_estado.
    embedding_modelo: str
    vectores_activos: bool
    presupuesto_bloques: dict[str, int] = field(default_factory=lambda: dict(PRESUPUESTO_BLOQUES))

    @property
    def presupuesto_paquete(self) -> int:
        """Lo que puede ocupar un paquete: el techo por llamada menos la reserva (RF2-CTX-12)."""
        return self.presupuesto_tokens - RESERVA_SALIDA


def raiz_repo() -> Path:
    """Raiz del repositorio: tres niveles por encima de este fichero (src/backend/config.py)."""
    return Path(__file__).resolve().parents[2]


def cargar() -> Config:
    """Lee el entorno y devuelve la configuracion. Lanza ConfiguracionInvalida si falta algo."""
    db_bruto = _env("DB_PATH")
    if not db_bruto:
        raise ConfiguracionInvalida(
            f"{PREFIJO}DB_PATH es obligatoria: ruta del fichero SQLite de la novela."
        )

    puerto = (_env("PUERTO", "terminal") or "terminal").strip().lower()
    if puerto not in {"terminal", "falso"}:
        raise ConfiguracionInvalida(f"{PREFIJO}PUERTO debe ser 'terminal' o 'falso', no {puerto!r}")

    skills_bruto = _env("SKILLS_DIR")
    skills_dir = Path(skills_bruto) if skills_bruto else raiz_repo() / ".claude" / "skills"

    falso_bruto = _env("PUERTO_FALSO_DIR")

    presupuesto_tokens = _env_int("PRESUPUESTO_TOKENS", TECHO_POR_LLAMADA)
    if presupuesto_tokens <= RESERVA_SALIDA:
        raise ConfiguracionInvalida(
            f"{PREFIJO}PRESUPUESTO_TOKENS={presupuesto_tokens} no deja sitio al paquete: "
            f"{RESERVA_SALIDA} tokens se reservan para la salida del agente."
        )

    return Config(
        db_path=Path(db_bruto).expanduser(),
        claude_bin=_env("CLAUDE_BIN", "claude") or "claude",
        skills_dir=skills_dir,
        poll_segundos=_env_int("POLL_SEGUNDOS", 2),
        timeout_agente_segundos=_env_int("TIMEOUT_AGENTE_SEGUNDOS", 1800),
        presupuesto_tokens=presupuesto_tokens,
        puerto=puerto,  # type: ignore[arg-type]
        puerto_falso_dir=Path(falso_bruto).expanduser() if falso_bruto else None,
        embedding_modelo=_env("EMBEDDING_MODELO", MODELO_EMBEDDING_PREFERIDO)
        or MODELO_EMBEDDING_PREFERIDO,
        vectores_activos=_env_bool("VECTORES", True),
    )
