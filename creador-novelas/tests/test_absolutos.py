"""Hechos iniciales que la propia novela tiene que desmentir.

Tres de las cuatro novelas de la corrida de velocidad murieron por esto: la fase 4 anotaba como ley
del mundo justo lo que la trama existe para revelar como falso, el capítulo del giro lo desmentía y
QA paraba la novela. No era cosa de las premisas; con las premisas ya suavizadas volvió a pasar.
"""

from __future__ import annotations

import json

import pytest

from app import cli
from app.errores import EstadoInvalidoError
from app.rutas import Rutas
from app.schemas import LogContinuidad
from app.state import continuidad as cont


def _log(*hechos: str, cap_origen: int = 0) -> LogContinuidad:
    return LogContinuidad.model_validate([
        {"sujeto": "mundo", "categoria": "mundo", "hecho": h, "cap_origen": cap_origen}
        for h in hechos
    ])


@pytest.mark.parametrize("hecho, motivo", [
    ("Entre la bodega y la sala de máquinas no hay ningún pasillo de servicio.",
     "niega la existencia de algo"),
    ("El pasajero contesta con exactitud a todo y nunca pregunta nada.",
     "declara que algo no pasa nunca"),
    ("La esclusa exterior no se abre en ningún caso desde dentro.",
     "declara una excepción imposible"),
    ("Nadie puede salir del casco sin que lo selle otra persona.",
     "declara que nadie puede algo"),
])
def test_se_detecta_lo_que_el_giro_tendra_que_negar(hecho, motivo):
    encontrados = cont.absolutos_que_la_trama_desmentira(_log(hecho))
    assert encontrados == [(hecho, motivo)]


@pytest.mark.parametrize("hecho", [
    # La negación es del documento, no del mundo: descubrir que el plano estaba incompleto es el
    # giro, y no contradice nada.
    "Los planos de a bordo no recogen ningún pasillo entre la bodega y la sala de máquinas.",
    "El registro de accesos no tiene ninguna entrada anterior a las cero seis cuarenta.",
    "El sondeo previo no encontró ninguna veta en ese cuadrante.",
    # Reglas que la novela entera puede sostener sin despeinarse.
    "El salvamento sin reclamante es dinero limpio según la ley de puerto.",
    "El soporte vital depende del reactor secundario y sus filtros se desgastan a ritmo medible.",
])
def test_no_se_marca_lo_que_habla_de_un_registro_ni_lo_que_se_sostiene(hecho):
    assert cont.absolutos_que_la_trama_desmentira(_log(hecho)) == []


def test_los_hechos_que_llegan_por_extraccion_no_se_juzgan_aqui():
    # Un hecho de un capítulo describe lo que ese capítulo estableció; si más tarde algo lo niega,
    # eso es trabajo de QA y no de la fase 4.
    assert cont.absolutos_que_la_trama_desmentira(
        _log("Nunca se volvió a oír el motor de estribor.", cap_origen=3)) == []


def test_guardar_continuidad_rechaza_la_ley_del_mundo_y_dice_como_arreglarla(proyecto, tmp_path, capsys):
    rutas = Rutas(proyecto)
    rutas.continuidad.unlink(missing_ok=True)  # la fase 4 escribe sobre un log vacío

    borrador = tmp_path / "continuidad.json"
    borrador.write_text(json.dumps([
        {"sujeto": "mundo", "categoria": "mundo", "cap_origen": 0,
         "hecho": "Entre la bodega y la sala de máquinas no hay ningún pasillo de servicio."},
    ]), encoding="utf-8")

    parser = cli.construir_parser()
    args = parser.parse_args(["guardar", "continuidad", "--desde", str(borrador)])
    with pytest.raises(EstadoInvalidoError) as e:
        args.fn(args, proyecto)

    # El mensaje tiene que enseñar, no solo negarse: quien lo lee es un agente que va a reescribir
    # el archivo, y sin el ejemplo reformula mal y vuelve a chocar.
    assert "ley del mundo" in str(e.value)
    assert "los planos de a bordo no recogen" in str(e.value).lower()


def test_guardar_continuidad_acepta_el_mismo_hecho_dicho_sobre_el_plano(proyecto, tmp_path):
    rutas = Rutas(proyecto)
    rutas.continuidad.unlink(missing_ok=True)

    borrador = tmp_path / "continuidad.json"
    borrador.write_text(json.dumps([
        {"sujeto": "mundo", "categoria": "mundo", "cap_origen": 0,
         "hecho": "Los planos de a bordo no recogen ningún pasillo entre la bodega y la sala de máquinas."},
    ]), encoding="utf-8")

    parser = cli.construir_parser()
    args = parser.parse_args(["guardar", "continuidad", "--desde", str(borrador)])
    assert args.fn(args, proyecto) == 0
    assert "planos" in rutas.continuidad.read_text(encoding="utf-8")


# ---------- personajes en dos sitios a la vez ----------

def _guardar_continuidad(raiz, tmp_path, hechos):
    Rutas(raiz).continuidad.unlink(missing_ok=True)
    borrador = tmp_path / "continuidad.json"
    borrador.write_text(json.dumps(hechos), encoding="utf-8")
    args = cli.construir_parser().parse_args(["guardar", "continuidad", "--desde", str(borrador)])
    return args.fn(args, raiz)


def test_un_hecho_no_puede_situar_a_un_personaje_lejos_de_su_capitulo(proyecto, tmp_path):
    # El proyecto de pruebas pone a Kovacs en el capítulo 1, que transcurre en el Puente.
    with pytest.raises(EstadoInvalidoError) as e:
        _guardar_continuidad(proyecto, tmp_path, [
            {"sujeto": "Kovacs", "categoria": "personaje", "cap_origen": 0,
             "hecho": "Kovacs tiene asignada la guardia de la Bodega 4 durante toda la travesía."},
        ])

    # El escritor no puede preguntar ni leer capítulos anteriores: el salto que nadie narra lo
    # rellena él a ciegas, y con 400 palabras lo cuenta a saltos y se contradice.
    assert "dos sitios a la vez" in str(e.value)
    assert "Bodega 4" in str(e.value) and "Puente" in str(e.value)
    assert "narrar el paso" in str(e.value)


def test_el_mismo_hecho_vale_si_narra_el_paso(proyecto, tmp_path):
    assert _guardar_continuidad(proyecto, tmp_path, [
        {"sujeto": "Kovacs", "categoria": "personaje", "cap_origen": 0,
         "hecho": "Kovacs tiene asignada la guardia de la Bodega 4 y sube al Puente al empezar su turno."},
    ]) == 0


def test_no_se_marca_un_hecho_que_no_nombra_ninguna_locacion(proyecto, tmp_path):
    assert _guardar_continuidad(proyecto, tmp_path, [
        {"sujeto": "Kovacs", "categoria": "personaje", "cap_origen": 0,
         "hecho": "Kovacs lleva catorce meses a bordo y conoce el ruido de cada mamparo."},
    ]) == 0


def test_el_caso_real_de_abordaje_se_detecta():
    from app.schemas import Outline
    from app.state import continuidad as cont
    outline = Outline.model_validate([
        {"num": 1, "titulo": "La esclusa", "objetivo_narrativo": "Presentar y romper la rutina.",
         "personajes": ["Duna Oyarzo", "Ibarra"], "locacion": "Vereda Sur - pasillo del nivel dos",
         "informacion_nueva": "Algo entra.", "tension": 4},
    ])
    log = LogContinuidad.model_validate([
        {"sujeto": "Duna Oyarzo", "categoria": "personaje", "cap_origen": 0,
         "hecho": "Duna Oyarzo tiene asignada la guardia del puente en la noche del cuarto día."},
    ])
    # Las locaciones se llaman «Vereda Sur - puente» y el hecho dice «la guardia del puente»: la
    # comparación tiene que mirar también la cola del nombre, que es como la nombra la prosa.
    r = cont.personajes_en_dos_sitios(log, outline, ["Vereda Sur - puente", "Vereda Sur - pasillo del nivel dos"])
    assert r == [("Duna Oyarzo", "Vereda Sur - puente", "Vereda Sur - pasillo del nivel dos", 1)]
