"""X-04: el escritor entrega el capítulo y su delta en la misma invocación.

El extractor se lleva 12 de los 18 minutos de una novela para sacar cuatro hechos de un capítulo que
el escritor acaba de escribir. Esto elimina esa invocación. Va detrás de un interruptor porque el
delta pasa a describir lo que el escritor quiso escribir en vez de lo que escribió, y eso hay que
medirlo contra la base antes de creérselo.
"""

from __future__ import annotations

import json

import pytest

from app import cli, hooks
from app.agents import escritor
from app.config import cargar_config, comando_validador
from app.rutas import Rutas


def _con_delta(raiz, activo: bool = True):
    ruta = Rutas(raiz).ejecucion_json
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    datos["escritor_emite_delta"] = activo
    ruta.write_text(json.dumps(datos, indent=2), encoding="utf-8")
    return cargar_config(raiz)


def test_el_interruptor_viene_apagado(proyecto):
    # La línea base corre con esto en falso: encenderlo tiene que ser una decisión, no un descuido.
    assert cargar_config(proyecto).escritor_emite_delta is False


def test_h11_le_cambia_el_comando_al_escritor_pero_le_sigue_dejando_uno_solo():
    # Abrirle la valla a dos comandos era la alternativa, y esa puerta no se cierra sola.
    assert comando_validador("escritor", 3) == ".venv/Scripts/python.exe -m app validar-capitulo 3"
    assert comando_validador("escritor", 3, con_delta=True) == \
        ".venv/Scripts/python.exe -m app validar-capitulo 3 --con-delta"
    # A los otros roles no les cambia nada: el delta no es asunto suyo.
    assert comando_validador("extractor", 3, con_delta=True) == \
        ".venv/Scripts/python.exe -m app validar-delta 3"


def test_el_prompt_del_escritor_le_encarga_el_delta_solo_si_esta_encendido(proyecto):
    apagado = escritor.ensamblar_contexto(1, _con_delta(proyecto, False), proyecto).texto
    assert "de eso se encarga otro agente" in apagado
    assert "--con-delta" not in apagado

    encendido = escritor.ensamblar_contexto(1, _con_delta(proyecto, True), proyecto).texto
    assert "delta de extracción" in encendido
    assert "04_estado/deltas/delta_cap_1.json" in encendido
    assert "--con-delta" in encendido
    # El registro de sujetos con los nombres canónicos, que es lo que el extractor recibía y el
    # escritor no tenía: sin él inventaría claves y el delta no validaría.
    assert "Kovacs" in encendido and "Puente" in encendido
    # Y el aviso que protege lo único que de verdad se arriesga aquí.
    assert "no lo que pensabas escribir" in encendido


def test_h06_le_deja_escribir_el_delta_solo_si_esta_encendido(proyecto, monkeypatch):
    from app.orchestrator import checkpoint
    checkpoint.fijar_capitulo_activo(proyecto, 1)
    payload = {"tool_name": "Write", "agent_id": "a1", "agent_type": "escritor",
               "tool_input": {"file_path": str(Rutas(proyecto).delta(1))}}

    _con_delta(proyecto, False)
    assert hooks.decidir_pre_tool_use(payload, proyecto).bloquear is True

    _con_delta(proyecto, True)
    assert hooks.decidir_pre_tool_use(payload, proyecto).bloquear is False


def test_h06_sigue_sin_dejarle_escribir_nada_mas(proyecto):
    from app.orchestrator import checkpoint
    checkpoint.fijar_capitulo_activo(proyecto, 1)
    _con_delta(proyecto, True)
    # Dos archivos y ninguno más: ni el delta de otro capítulo, ni el estado, ni el manuscrito ajeno.
    for ruta in (Rutas(proyecto).delta(2), Rutas(proyecto).continuidad, Rutas(proyecto).capitulo(2)):
        payload = {"tool_name": "Write", "agent_id": "a1", "agent_type": "escritor",
                   "tool_input": {"file_path": str(ruta)}}
        assert hooks.decidir_pre_tool_use(payload, proyecto).bloquear is True, ruta


def test_preparar_capitulo_le_dice_al_orquestador_si_hay_extractor(proyecto, capsys):
    _con_delta(proyecto, True)
    args = cli.construir_parser().parse_args(["preparar-capitulo", "1"])
    args.fn(args, proyecto)
    # Quien orquesta no lee la config: la línea RESULTADO le dice si despachar al extractor o no.
    assert "delta_del_escritor=true" in capsys.readouterr().out


def test_validar_capitulo_con_delta_valida_las_dos_cosas(proyecto, tmp_path, capsys):
    from app.state import repository as repo
    config = _con_delta(proyecto, True)
    rutas = Rutas(proyecto)
    repo.escribir_texto(rutas.capitulo(1), "Palabra " * config.palabras_por_capitulo)

    args = cli.construir_parser().parse_args(["validar-capitulo", "1", "--con-delta"])
    assert args.fn(args, proyecto) == 1  # el capítulo puede valer, pero el delta no está
    assert "delta" in capsys.readouterr().out.lower()


def test_no_se_anuncia_un_extractor_que_no_va_a_correr(proyecto):
    from app import registro
    from app.orchestrator import loop
    config = _con_delta(proyecto, True)
    registro.iniciar_tanda(proyecto, {})
    loop.preparar_extractor(proyecto, config, 1)

    # El prompt se deja listo por si hay que caer al extractor, pero anunciar su arranque dejaba un
    # agente abierto para siempre: el plano enseñaba fantasmas y el resumen contaba invocaciones
    # que no ocurrieron.
    ev = registro.leer_eventos(registro.dir_actual(proyecto))
    assert [e for e in ev if e.get("rol") == "extractor"] == []
    assert Rutas(proyecto).prompt_extractor(1).is_file()


def test_el_delta_que_valida_el_escritor_se_anota_como_suyo(proyecto, capsys):
    import json as _json
    from app.state import repository as repo
    config = _con_delta(proyecto, True)
    repo.escribir_texto(Rutas(proyecto).capitulo(1), "Palabra " * config.palabras_por_capitulo)
    Rutas(proyecto).deltas_trabajo.mkdir(parents=True, exist_ok=True)
    Rutas(proyecto).delta(1).write_text(_json.dumps({
        "personajes": {}, "hechos_nuevos": [], "resumen_corto": "Pasó algo.", "recursos_narrativos": [],
    }), encoding="utf-8")

    args = cli.construir_parser().parse_args(["validar-capitulo", "1", "--con-delta"])
    args.fn(args, proyecto)
    # El rol lo fija el verbo y no quien lo ejecuta: sin corregirlo, el registro anotaba un
    # extractor que en esta corrida no existe.
    assert (chr(114)+chr(111)+chr(108)+chr(61)+chr(34)+chr(101)+chr(115)+chr(99)+chr(114)+chr(105)+chr(116)+chr(111)+chr(114)+chr(34)) in capsys.readouterr().out
