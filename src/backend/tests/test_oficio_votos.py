"""El juez de oficio vota (specs/spec3.md, RF3-JUE-02).

Con una sola muestra, el veredicto del juez real sobre el mismo capitulo cambio de una llamada a
otra. Tres muestras por intento, dos mas si alguna discrepa, y manda la mayoria.
"""

from __future__ import annotations

from typing import Any

import config
from compartido.puerto import demo
from orquestador import pipeline
from tareas.oficio import puerta as p_oficio
from tareas.oficio.esquemas import SalidaOficio
from tests.entorno import contexto, crear_novela, nueva_bd, puerto_falso


def _juicio(*fallan: str) -> SalidaOficio:
    salida = demo.oficio("", "oficio")
    for v in salida["veredictos"]:
        if v["criterio"] in fallan:
            v.update(veredicto="falla", evidencia=f"cita de {v['criterio']}",
                     sugerencia="cambialo")
    return SalidaOficio.model_validate(salida)


def test_la_mayoria_manda_y_los_votos_quedan() -> None:
    juicios = [_juicio("cliche"), _juicio("cliche"), _juicio(), _juicio(), _juicio("cliche")]
    juicio, votos = p_oficio.votar(juicios)
    assert [v.criterio for v in juicio.incumplidos] == ["cliche"]
    assert juicio.incumplidos[0].evidencia == "cita de cliche"
    assert votos["cliche"] == (3, 5) and votos["voz_constante"] == (0, 5)
    juicio, votos = p_oficio.votar(juicios[1:4])
    assert juicio.pasa and votos["cliche"] == (1, 3)


def test_con_empate_falla() -> None:
    juicio, _ = p_oficio.votar([_juicio("cliche"), _juicio()])
    assert not juicio.pasa


def test_discrepan_si_alguna_muestra_dice_otra_cosa() -> None:
    assert not p_oficio.discrepan([_juicio(), _juicio(), _juicio()])
    assert not p_oficio.discrepan([_juicio("cliche")] * 3)
    assert p_oficio.discrepan([_juicio(), _juicio("cliche"), _juicio()])


def test_un_juicio_dividido_avisa_aunque_pase() -> None:
    from compartido.puerta_base import ResultadoPuerta

    juicio, votos = p_oficio.votar([_juicio("cliche"), _juicio(), _juicio()])
    r = p_oficio.combinar(ResultadoPuerta(puerta=4, conflictos=[]), juicio, votos)
    assert r.pasa
    [aviso] = [c for c in r.avisos if c.comprobacion == "juicio_dividido"]
    assert aviso.datos["votos"] == {"cliche": [1, 3]}


def _pipeline_con_juez(veredictos_en_contra: list[bool]) -> tuple[Any, list[str]]:
    """El juez del capitulo 1 falla `cliche` en las llamadas marcadas; el resto, siempre pasa."""
    con, ruta = nueva_bd()
    novela_id = crear_novela(con)
    puerto = puerto_falso(con)
    llamadas: list[str] = []

    def juez(entrada: str, agente: str) -> dict[str, Any]:
        salida = demo.oficio(entrada, agente)
        if demo._capitulo(entrada) == 1:
            n = len(llamadas)
            llamadas.append(entrada)
            if n < len(veredictos_en_contra) and veredictos_en_contra[n]:
                for v in salida["veredictos"]:
                    if v["criterio"] == "cliche":
                        v.update(veredicto="falla", evidencia="la sangre se le helo",
                                 sugerencia="cambialo")
        return salida

    puerto.registrar("oficio", juez)
    final = pipeline.avanzar(contexto(con, puerto, ruta, novela_id))
    return (con, novela_id, final), llamadas


def test_una_muestra_en_contra_pide_dos_mas_y_pasa() -> None:
    (con, novela_id, final), llamadas = _pipeline_con_juez([True, False, False])
    assert final in ("completada", "completada_con_avisos")
    assert len(llamadas) == config.OFICIO_MUESTRAS_SI_DISCREPAN
    detalle = str(con.execute(
        "SELECT detalle FROM resultado_puerta WHERE novela_id = ? AND puerta = 4 AND capitulo = 1",
        (novela_id,)).fetchone()[0])
    assert "juicio_dividido" in detalle


def test_la_mayoria_en_contra_devuelve_el_capitulo() -> None:
    (con, novela_id, _), llamadas = _pipeline_con_juez([True, True, False, True, False])
    # Tres de cinco en contra: el primer intento falla y el segundo, unanime, pasa.
    assert len(llamadas) == config.OFICIO_MUESTRAS_SI_DISCREPAN + config.OFICIO_MUESTRAS
    veredictos = [str(f[0]) for f in con.execute(
        "SELECT veredicto FROM resultado_puerta WHERE novela_id = ? AND puerta = 4 "
        "AND capitulo = 1 ORDER BY id", (novela_id,))]
    assert veredictos[0] == "falla" and veredictos[-1] != "falla"


def test_unanimes_no_se_piden_mas() -> None:
    _, llamadas = _pipeline_con_juez([])
    assert len(llamadas) == config.OFICIO_MUESTRAS


def test_una_muestra_es_un_voto_aunque_repita_un_criterio() -> None:
    """Validador de 5da56ac: contar veredictos dejaba que una muestra que repite un criterio
    pesara varias veces y diera la vuelta a la mayoria de muestras."""
    repetida = _juicio()
    cliche = next(v for v in repetida.veredictos if v.criterio == "cliche")
    repetida = SalidaOficio(veredictos=[*repetida.veredictos, cliche, cliche])
    juicios = [_juicio("cliche"), _juicio("cliche"), _juicio("cliche"), _juicio(), repetida]
    juicio, votos = p_oficio.votar(juicios)
    assert votos["cliche"] == (3, 5)
    assert not juicio.pasa


def test_la_evidencia_es_de_una_muestra_de_la_mayoria() -> None:
    juicio, _ = p_oficio.votar([_juicio(), _juicio("cliche"), _juicio("cliche")])
    assert juicio.incumplidos[0].evidencia == "cita de cliche"


def test_los_votos_van_en_el_conflicto() -> None:
    from compartido.puerta_base import ResultadoPuerta

    juicio, votos = p_oficio.votar([_juicio("cliche"), _juicio("cliche"), _juicio()])
    r = p_oficio.combinar(ResultadoPuerta(puerta=4, conflictos=[]), juicio, votos)
    [c] = [c for c in r.bloqueantes if c.comprobacion == "juicio:cliche"]
    assert c.datos["votos"] == [2, 3]
