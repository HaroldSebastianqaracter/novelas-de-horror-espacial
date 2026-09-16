"""RF-00.2: ningún artefacto de estado contiene 30+ caracteres literales de los ejemplos de 00_referencias/.

Corre sobre el proyecto real (no sobre un tmp). Si 00_referencias/ no existe o está vacía, se salta con motivo
explícito: el resultado es "no ejecutable", nunca "aprobado" (§10).
"""

import re

import pytest

from app.rutas import Rutas
from tests.conftest import RAIZ_REAL

VENTANA = 31


def _normalizar(texto: str) -> str:
    return re.sub(r"\s+", " ", texto).lower()


def test_estado_no_contiene_texto_literal_de_las_referencias():
    rutas = Rutas(RAIZ_REAL)
    referencias = [p for p in rutas.referencias.glob("**/*") if p.is_file() and p.suffix.lower() in (".md", ".txt")]
    if not referencias:
        pytest.skip("RF-00.2 no ejecutable: 00_referencias/ no existe o está vacía en esta máquina")
    corpus = " ".join(_normalizar(p.read_text(encoding="utf-8", errors="replace")) for p in referencias)
    artefactos = [p for carpeta in (rutas.estado, rutas.concepto, rutas.qa) for p in carpeta.rglob("*")
                  if p.is_file() and p.suffix in (".md", ".json") and "prompts" not in p.parts]
    if not artefactos:
        pytest.skip("RF-00.2 no ejecutable: todavía no hay artefactos de estado")
    coincidencias = []
    for artefacto in artefactos:
        texto = _normalizar(artefacto.read_text(encoding="utf-8", errors="replace"))
        for i in range(0, max(0, len(texto) - VENTANA), 7):
            ventana = texto[i:i + VENTANA]
            if len(ventana) == VENTANA and ventana in corpus:
                coincidencias.append((artefacto.name, ventana))
                break
    assert coincidencias == [], f"texto literal de las referencias en el estado: {coincidencias}"
