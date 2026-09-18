"""Fixtures: un proyecto completo en tmp_path con estado de fase 4 listo, y dobles deterministas de los tres agentes (§9)."""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
from pathlib import Path

import pytest

RAIZ_REAL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ_REAL))

from app.config import cargar_config  # noqa: E402
from app.orchestrator import checkpoint  # noqa: E402
from app.rutas import Rutas  # noqa: E402
from app.schemas import FichaPersonajes, LogContinuidad, Mundo, Outline, RecursosUsados, RecursoUsado  # noqa: E402
from app.state import repository as repo  # noqa: E402

PERSONAJES = ["Kovacs", "Ilse", "Dara"]
LOCACIONES = ["Puente", "Bodega 4", "Enfermería"]


def outline_de_prueba(total: int = 30) -> list[dict]:
    entradas = []
    for n in range(1, total + 1):
        # tensión: sube en oleadas; máximo 5 solo en el tercio final (RF-03.2)
        if n >= total - 4:
            tension = 5 if n in (total - 2, total) else 4
        else:
            tension = 1 + (n % 3)
        personajes = [PERSONAJES[(n - 1) % 3]] + ([PERSONAJES[n % 3]] if n % 2 == 0 else [])
        entradas.append({
            "num": n,
            "titulo": f"Capítulo de prueba {n}",
            "objetivo_narrativo": f"Objetivo narrativo del capítulo {n}.",
            "personajes": personajes,
            "locacion": LOCACIONES[(n - 1) % 3],
            "informacion_nueva": f"Dato nuevo {n}.",
            "tension": tension,
        })
    return entradas


def construir_proyecto(raiz: Path, *, con_estado: bool = True, total: int = 30) -> Path:
    """Copia config/ y prompts reales, y arma el estado de las fases 0-4 sin modelo."""
    rutas = Rutas(raiz)
    rutas.crear_carpetas()
    shutil.copytree(RAIZ_REAL / "config", rutas.config, dirs_exist_ok=True)
    (rutas.raiz / ".claude" / "skills").mkdir(parents=True, exist_ok=True)
    for skill in ("prosa-terror-espacial", "formato-delta", "criterios-qa"):
        origen = RAIZ_REAL / ".claude" / "skills" / skill
        if origen.exists():
            shutil.copytree(origen, rutas.skills / skill, dirs_exist_ok=True)
    # Los ajustes de la novela se fijan aquí y no se heredan de `config/`, que pertenece al libro que
    # el usuario tenga cargado. Se descubrió al bajar una novela real a 400 palabras y auditoría cada
    # capítulo: 25 pruebas se cayeron sin que nadie hubiera tocado el código, porque daban por hecho
    # 1500 palabras y un corte cada 3. Una suite no puede depender de qué se esté escribiendo.
    novela = json.loads(rutas.novela_json.read_text(encoding="utf-8"))
    novela.update({
        "total_capitulos": total,
        "palabras_por_capitulo": 1500,
        "cadencia_qa": 3,
        "ventana_resumen_rodante": 2,
        "max_tokens_contexto_escritor": 12000,
        "max_hechos_por_capitulo": 4,
        "idioma": "es-ES",
        "persona_narrativa": "tercera_limitada",
        "tiempo_verbal": "pasado",
    })
    rutas.novela_json.write_text(json.dumps(novela, indent=2), encoding="utf-8")
    ejecucion = json.loads(rutas.ejecucion_json.read_text(encoding="utf-8"))
    ejecucion.update({"capitulos_por_tanda": 3, "max_llamadas_por_tanda": 30, "registrar_uso": True})
    rutas.ejecucion_json.write_text(json.dumps(ejecucion, indent=2), encoding="utf-8")
    if not con_estado:
        return raiz
    repo.escribir_texto(rutas.idea, "Una estación minera en el cinturón pierde contacto con la Tierra.\n")
    repo.escribir_texto(rutas.premisa, "Título: El silencio de Ceres\nLogline: Una tripulación aislada descubre que la estación respira.\nPremisa: Un párrafo de premisa.\n")
    repo.escribir_texto(rutas.style_guide, "# Guía de estilo\n\nTensión 1: rutina. Tensión 3: presión. Tensión 5: amenaza directa.\n")
    repo.escribir_texto(rutas.tres_actos, "## Gancho inicial\n\nLa estación calla.\n\n## Punto medio\n\nAlguien abrió la bodega.\n\n## Clímax / final\n\nKovacs sella el puente.\n")
    repo.escribir_outline(raiz, Outline.model_validate(outline_de_prueba(total)))
    repo.escribir_personajes(raiz, FichaPersonajes.model_validate({
        p: {"estado_fisico": "Sano.", "estado_psicologico": "Alerta.", "secretos_que_conoce": [], "ultima_aparicion": 0}
        for p in PERSONAJES
    }))
    repo.escribir_mundo(raiz, Mundo(reglas=["El soporte vital depende del reactor secundario."], objetos=["Llave de purga"],
                                    linea_de_tiempo=["Día 0: pérdida de contacto."],
                                    locaciones={l: f"Descripción de {l}." for l in LOCACIONES}))
    repo.escribir_continuidad(raiz, LogContinuidad.model_validate([
        {"sujeto": "mundo", "categoria": "mundo", "hecho": "La estación tiene oxígeno para 90 días.", "cap_origen": 0},
        {"sujeto": "Bodega 4", "categoria": "locacion", "hecho": "La Bodega 4 está sellada desde antes de la llegada.", "cap_origen": 0},
        {"sujeto": "Dara", "categoria": "personaje", "hecho": "Dara es la única médica a bordo.", "cap_origen": 0},
    ]))
    repo.escribir_resumen_rodante(raiz, "")
    checkpoint.crear_manifest(raiz, total)
    return raiz


@pytest.fixture
def proyecto(tmp_path, monkeypatch) -> Path:
    raiz = construir_proyecto(tmp_path / "novela")
    monkeypatch.setenv("HARNESS_RAIZ", str(raiz))
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    return raiz


@pytest.fixture
def config(proyecto):
    return cargar_config(proyecto)


class AgentesDobles:
    """Dobles deterministas de los tres subagentes (§9). Escriben lo que un agente real escribiría en disco."""

    def __init__(self, raiz: Path, *, palabras: int = 1500, cortos: set[tuple[int, int]] | None = None,
                 personaje_extra: dict[int, int] | None = None, contradiccion_en: set[int] | None = None,
                 fallar_en: int | None = None):
        self.raiz = raiz
        self.palabras = palabras
        self.cortos = cortos or set()  # (n, intento) que salen cortos (EX-07)
        self.personaje_extra = personaje_extra or {}  # n -> cantidad de extracciones que traen "Vos" (EX-08)
        self.contradiccion_en = contradiccion_en or set()
        self.fallar_en = fallar_en  # n en el que el escritor "muere" (interrupción)
        self.intentos: dict[int, int] = {}
        self.extracciones: dict[int, int] = {}
        self.prompts_escritor: list[str] = []
        self.prompts_qa: list[str] = []

    @staticmethod
    def _n_de_prompt(prompt: str) -> int:
        return int(re.search(r"Capítulo (\d+):", prompt).group(1))

    def generar_capitulo(self, prompt: str) -> str:
        n = self._n_de_prompt(prompt)
        if self.fallar_en == n:
            raise ConnectionError("el escritor se cortó a mitad de tanda")
        self.prompts_escritor.append(prompt)
        self.intentos[n] = self.intentos.get(n, 0) + 1
        cantidad = 300 if (n, self.intentos[n]) in self.cortos else self.palabras
        cuerpo = " ".join(f"v{n}x{i}" for i in range(cantidad - 4))
        return f"Texto del capítulo {n}. {cuerpo}\n"

    def extraer(self, cap_n: str) -> str:
        n = int(re.search(r"cap_(\d+)\.md", cap_n).group(1))
        self.extracciones[n] = self.extracciones.get(n, 0) + 1
        personajes = {"Kovacs": {"estado_fisico": f"Cansado tras el capítulo {n}.", "estado_psicologico": "Tenso.",
                                 "secretos_que_conoce": [f"Secreto del capítulo {n}"], "ultima_aparicion": 0}}
        if self.personaje_extra.get(n, 0) >= self.extracciones[n]:
            personajes["Vos"] = {"estado_fisico": "Aparecido.", "estado_psicologico": "Nuevo.", "secretos_que_conoce": [], "ultima_aparicion": n}
        return json.dumps({
            "personajes": personajes,
            "hechos_nuevos": [
                {"sujeto": "Kovacs", "categoria": "personaje", "hecho": f"Kovacs hizo algo irreversible en el capítulo {n}.", "cap_origen": 99},
                {"sujeto": LOCACIONES[(n - 1) % 3], "categoria": "locacion", "hecho": f"La {LOCACIONES[(n - 1) % 3]} cambió en el capítulo {n}.", "cap_origen": n},
            ],
            "resumen_corto": f"Resumen A del capítulo {n}.\nResumen B del capítulo {n}.\nResumen C del capítulo {n}.",
            # RF-05.5: un recurso que vuelve en todos los capítulos y uno propio de cada uno
            "recursos_narrativos": [
                {"recurso": "el zumbido de los ventiladores como coda de escena", "veces": 1},
                {"recurso": f"imagen propia del capítulo {n}", "veces": 2},
            ],
        }, ensure_ascii=False)

    def ejecutar_corte(self, prompt: str) -> str:
        n = int(re.search(r"Corte de QA en el capítulo (\d+)", prompt).group(1))
        self.prompts_qa.append(prompt)
        rutas = Rutas(self.raiz)
        recursos = repo.leer_recursos_usados(self.raiz)
        recursos = RecursosUsados(list(recursos.root) + [RecursoUsado(recurso=f"imagen del corte {n}", veces=1, caps=[n])])
        repo.escribir_recursos_usados(self.raiz, recursos)
        hallazgos = []
        if n in self.contradiccion_en:
            hallazgos.append({"tipo": "contradiccion", "descripcion": "Dara opera sin ser médica.", "cap_origen": 0})
        reporte = {"cap_corte": n, "hallazgos": hallazgos, "tiene_contradicciones": bool(hallazgos)}
        rutas.reportes_qa.mkdir(parents=True, exist_ok=True)
        rutas.reporte_qa_json(n).write_text(json.dumps(reporte, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        rutas.reporte_qa_md(n).write_text(f"# QA {n}\n\n{len(hallazgos)} hallazgos\n", encoding="utf-8")
        return json.dumps(reporte)


@pytest.fixture
def dobles(proyecto):
    return AgentesDobles(proyecto)


def ejecutar_script_hook(nombre: str, payload: dict, raiz: Path):
    """Ejecuta scripts/hooks/<nombre>.py con el payload por stdin, como lo haría Claude Code."""
    import subprocess

    env = dict(os.environ)
    env["HARNESS_RAIZ"] = str(raiz)
    env.pop("CLAUDE_PROJECT_DIR", None)
    env["PYTHONUTF8"] = "1"
    return subprocess.run(
        [sys.executable, str(RAIZ_REAL / "scripts" / "hooks" / f"{nombre}.py")],
        input=json.dumps(payload), capture_output=True, text=True, encoding="utf-8", env=env, cwd=str(raiz),
    )
