"""El banco de contraejemplos de la puerta 3 (specs/spec3.md, 3.10: RF3-BAN-01 a RF3-BAN-05).

Cada caso fija lo que la puerta hace hoy. Si un cambio hace que deje de detectar una
contradiccion, o que empiece a parar un caso limpio, este test falla: el banco se actualiza a
conciencia, con su entrada en el registro de iteraciones.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from evals import banco_puerta3 as banco


@pytest.fixture(scope="module")
def base(tmp_path_factory: pytest.TempPathFactory) -> banco.Base:
    return banco.construir_base(tmp_path_factory.mktemp("banco"))


@pytest.mark.parametrize("caso", banco.CASOS, ids=[c.id for c in banco.CASOS])
def test_cada_caso_hace_lo_que_el_banco_dice(base: banco.Base, caso: banco.Caso) -> None:
    r = banco.evaluar_caso(base, caso)
    assert r.bloqueantes == set(caso.esperado.bloqueantes), (caso.id, r.bloqueantes)
    assert set(caso.esperado.avisos) <= r.avisos, (caso.id, r.avisos)


def test_los_casos_estan_bien_formados() -> None:
    ids = [c.id for c in banco.CASOS]
    assert len(ids) == len(set(ids))
    for c in banco.CASOS:
        # Una contradiccion que hoy no para, o un limpio que para, dice por que.
        falla = (c.verdad == "contradiccion") != bool(c.esperado.bloqueantes)
        assert bool(c.punto_ciego) == falla, c.id
    assert {c.verdad for c in banco.CASOS} == {"contradiccion", "limpio"}


def test_un_caso_no_ve_lo_que_cambio_otro(base: banco.Base) -> None:
    contradiccion = next(c for c in banco.CASOS if c.id == "C01")
    limpio = next(c for c in banco.CASOS if c.id == "L01")
    assert banco.evaluar_caso(base, contradiccion).detectado
    assert not banco.evaluar_caso(base, limpio).detectado


def test_las_metricas_salen_de_los_casos(base: banco.Base) -> None:
    a = banco.Caso("A", "x", "contradiccion", "", lambda c, b: None, banco.Esperado())
    informe = banco.Informe([
        banco.Resultado(a, {"continuidad_factual"}, set()),
        banco.Resultado(a, set(), set()),
        banco.Resultado(banco.Caso("B", "control", "limpio", "", a.mutar, banco.Esperado()),
                        {"presencia_imposible"}, set()),
    ])
    assert informe.recall == 0.5
    assert informe.falsos_positivos == 1.0
    assert informe.por_subtipo() == {"x": (1, 2)}
    assert "Recall sobre las contradicciones: 50%" in informe.tabla()
    con_aviso = banco.Informe([banco.Resultado(a, set(), {"cifra_sin_hecho"})] * 2)
    assert con_aviso.avisos() == {"cifra_sin_hecho": 2}
    assert "- cifra_sin_hecho: 2" in con_aviso.tabla()


def test_el_comando_sale_con_1_si_un_caso_se_desvia(
    base: banco.Base, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import banco_contraejemplos

    c01 = next(c for c in banco.CASOS if c.id == "C01")
    desviado = banco.Caso("X", c01.subtipo, c01.verdad, "", c01.mutar, banco.Esperado())
    correr = banco.correr
    monkeypatch.setattr(banco, "correr", lambda: correr(base, [desviado]))
    assert banco_contraejemplos.main() == 1
    assert "DESVIADO X" in capsys.readouterr().out


def test_el_comando_imprime_la_tabla_y_sale_limpio() -> None:
    backend = Path(__file__).resolve().parents[1]
    r = subprocess.run(
        [sys.executable, "banco_contraejemplos.py"], cwd=backend, capture_output=True,
        text=True, encoding="utf-8", timeout=600, check=False,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert "| C01 |" in r.stdout and "Recall sobre las contradicciones" in r.stdout
