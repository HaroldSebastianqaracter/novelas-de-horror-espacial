"""Evals del extractor contra un capitulo anotado a mano (spec2, fase 10; fila 38 de spec1).

El puntuador y el dataset se prueban aqui con salidas sinteticas, sin gastar nada. La pasada
contra el extractor real va marcada `agente`: cuesta una llamada a Claude Code y no corre por
defecto (`pytest -m agente` para lanzarla, con la aprobacion del autor).
"""

from __future__ import annotations

import contextlib
import copy
from pathlib import Path
from typing import Any

import pytest

from compartido.grafo import normalizar
from compartido.puerto import PuertoTerminal, demo
from orquestador import pipeline
from tareas.extraccion.esquemas import SalidaExtraccion
from tests.entorno import contexto, crear_novela, nueva_bd, puerto_falso
from tests.evals_extraccion import cargar, informe, puntuar

DATASET = cargar()
ESPERADO: dict[str, list[dict[str, Any]]] = DATASET["esperado"]
CANON = {normalizar(n) for n in (*demo.PERSONAJES, *demo.LUGARES, demo.OBJETO)}

#: Umbral de la pasada real. Decision de la spec: el capitulo es corto y cada registro que
#: falta pesa mucho, asi que se mide el total y los hechos, que son lo que la puerta 3 compara.
UMBRAL_TOTAL = 0.8
UMBRAL_HECHOS = 0.75


def _salida_perfecta() -> dict[str, Any]:
    """Una salida sintetica construida desde la anotacion: casa con todo."""
    salida: dict[str, list[dict[str, Any]]] = {}
    campos = {"sujeto": "sujeto_ref", "personaje": "personaje_ref", "objeto": "objeto_ref",
              "ubicacion": "ubicacion_ref", "condicion": "condicion", "nombre": "nombre"}
    for tipo, registros in ESPERADO.items():
        salida[tipo] = []
        for reg in registros:
            extraido: dict[str, Any] = {"escena_orden": reg["escena_orden"]}
            for campo, destino in campos.items():
                if campo in reg:
                    extraido[destino] = reg[campo]
            if "claves" in reg:
                extraido["descripcion"] = " ".join(grupo[0] for grupo in reg["claves"])
            salida[tipo].append(extraido)
    return salida


# --- El dataset esta anclado en su propia prosa --------------------------------------------------


def test_las_escenas_siguen_la_escaleta_de_la_demo() -> None:
    escenas = demo.escaleta("", "extraccion")["capitulos"][0]["escenas"]
    assert [e["lugar"] for e in escenas] == ["Esclusa", "Puente"]
    assert sorted(DATASET["escenas"]) == [str(e["orden"]) for e in escenas]


def test_cada_clave_anotada_esta_en_la_prosa_de_su_escena() -> None:
    for tipo, registros in ESPERADO.items():
        for reg in registros:
            prosa = normalizar(DATASET["escenas"][str(reg["escena_orden"])])
            for grupo in reg.get("claves", []):
                assert any(normalizar(alt) in prosa for alt in grupo), (tipo, reg, grupo)


def test_las_referencias_son_del_canon_y_lo_no_reconocido_no() -> None:
    for tipo, registros in ESPERADO.items():
        for reg in registros:
            for campo in ("sujeto", "personaje", "objeto", "ubicacion"):
                if campo in reg:
                    assert normalizar(reg[campo]) in CANON, (tipo, reg)
    for reg in ESPERADO["entidades_no_reconocidas"]:
        assert normalizar(reg["nombre"]) not in CANON
        assert normalizar(reg["nombre"]) in normalizar(DATASET["escenas"][str(reg["escena_orden"])])


# --- El puntuador --------------------------------------------------------------------------------


def test_una_salida_que_lo_recoge_todo_puntua_uno() -> None:
    recall = puntuar(_salida_perfecta(), ESPERADO)
    assert all(r.valor == 1.0 for r in recall.values()), informe(recall)


def test_una_salida_vacia_puntua_cero() -> None:
    recall = puntuar({}, ESPERADO)
    assert recall["total"].acertados == 0
    assert recall["total"].esperados == sum(len(r) for r in ESPERADO.values())


def test_la_escena_equivocada_no_cuenta() -> None:
    salida = _salida_perfecta()
    for h in salida["hechos"]:
        h["escena_orden"] += 1
    assert puntuar(salida, ESPERADO)["hechos"].acertados == 0


def test_un_hecho_extraido_no_cuenta_dos_veces() -> None:
    salida = {"hechos": [{"escena_orden": 2, "sujeto_ref": "Puente", "atributo": "olor",
                          "valor": "metal frio, algo dulce, luz ambar"}]}
    # Casa con dos esperados (olor y luz), pero es un solo registro.
    assert puntuar(salida, ESPERADO)["hechos"].acertados == 1


def test_tildes_mayusculas_y_nombres_largos_no_penalizan() -> None:
    salida = {
        "hechos": [{"escena_orden": 2, "sujeto_ref": "PUENTE", "atributo": "Iluminación",
                    "valor": "Resplandor ÁMBAR"}],
        "entidades_no_reconocidas": [{"escena_orden": 1, "nombre": "el capitán Oyelaran"}],
    }
    recall = puntuar(salida, ESPERADO)
    assert recall["hechos"].acertados == 1
    assert recall["entidades_no_reconocidas"].acertados == 1


def test_perder_un_registro_baja_el_recall_en_su_parte_exacta() -> None:
    salida = copy.deepcopy(_salida_perfecta())
    salida["hechos"].pop()
    recall = puntuar(salida, ESPERADO)
    assert recall["hechos"].valor == pytest.approx(7 / 8)
    assert recall["conocimiento"].valor == 1.0


# --- La pasada contra el extractor real (no corre por defecto) -----------------------------------


class _Capturado(Exception):
    pass


@pytest.mark.agente
def test_el_extractor_real_cubre_el_capitulo_anotado() -> None:
    """Planifica con el puerto falso, redacta el capitulo anotado y extrae con Claude Code."""
    con, ruta = nueva_bd()
    novela_id = crear_novela(con)
    puerto = puerto_falso(con)
    real = PuertoTerminal(skills_dir=Path(__file__).resolve().parents[3] / ".claude" / "skills")
    capturada: dict[str, Any] = {}

    def redaccion(entrada: str, agente: str) -> dict[str, Any]:
        escenas = [{"orden": int(o), "texto": t} for o, t in DATASET["escenas"].items()]
        return {"escenas": escenas, "notas": ""}

    def extraccion(entrada: str, agente: str) -> dict[str, Any]:
        resultado = real.invocar(agente, entrada, SalidaExtraccion.model_json_schema())
        capturada.update(resultado.salida)
        raise _Capturado

    puerto.registrar("redaccion", redaccion)
    puerto.registrar("extraccion", extraccion)
    with contextlib.suppress(_Capturado):
        pipeline.avanzar(contexto(con, puerto, ruta, novela_id))

    assert capturada, "el extractor real no llego a llamarse"
    recall = puntuar(capturada, ESPERADO)
    print("\n" + informe(recall))
    assert recall["total"].valor >= UMBRAL_TOTAL, informe(recall)
    assert recall["hechos"].valor >= UMBRAL_HECHOS, informe(recall)
