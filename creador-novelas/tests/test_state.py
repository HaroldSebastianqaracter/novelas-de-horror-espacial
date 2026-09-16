"""Capa de estado: continuidad append-only y filtro (RF-05.1, RF-06.3, RF-07.6, INV-03), fichas (RF-06.1/06.2), resumen rodante (RF-06.4, EX-04), repository (EX-01, INV-07)."""

import pytest

from harness.errores import CapituloCerradoError, EstadoInvalidoError
from harness.rutas import Rutas
from harness.schemas import HechoContinuidad, LogContinuidad, Mundo, Personaje, FichaPersonajes
from harness.schemas.outline import EntradaOutline
from harness.state import continuidad as cont
from harness.state import personajes as pers
from harness.state import repository as repo
from harness.state import resumen_rodante as rr


def hecho(sujeto, categoria, texto, cap, validado=True, superado=None):
    return HechoContinuidad(sujeto=sujeto, categoria=categoria, hecho=texto, cap_origen=cap, sujeto_validado=validado, superado_por=superado)


REGISTRO = {"Kovacs", "Ilse", "Puente", "Bodega 4", "mundo"}


def test_agregar_solo_crece_y_fija_cap_origen_y_validacion():
    log = LogContinuidad([hecho("mundo", "mundo", "Oxígeno para 90 días.", 0)])
    nuevos = [HechoContinuidad(sujeto="Kovacs", categoria="personaje", hecho="Se rompió el brazo.", cap_origen=99),
              HechoContinuidad(sujeto="el capitán", categoria="personaje", hecho="Mintió.", cap_origen=99)]
    resultado = cont.agregar(log, nuevos, 7, REGISTRO)
    assert len(resultado) == 3 and len(log) == 1  # no muta el original
    assert resultado.root[1].cap_origen == 7 and resultado.root[1].sujeto_validado
    assert resultado.root[2].sujeto_validado is False  # RF-06.1: se conserva, marcado
    assert not hasattr(cont, "eliminar") and not hasattr(cont, "modificar")


def test_marcar_superado_no_borra_y_es_idempotente():
    log = LogContinuidad([hecho("Kovacs", "personaje", "A", 3), hecho("Ilse", "personaje", "B", 4), hecho("Kovacs", "personaje", "C", 3, superado=3)])
    marcado = cont.marcar_superado(log, [3])
    assert len(marcado) == 3
    assert [h.superado_por for h in marcado.root] == [3, None, 3]
    assert marcado.root[0].hecho == "A" and marcado.root[0].cap_origen == 3
    assert cont.marcar_superado(marcado, [3]) == marcado


def test_filtrar_para_capitulo_incluye_de_mas_nunca_de_menos():
    entrada = EntradaOutline(num=5, titulo="T", objetivo_narrativo="o", personajes=["Kovacs"], locacion="Puente", informacion_nueva="", tension=3)
    log = LogContinuidad([
        hecho("mundo", "mundo", "Regla del universo.", 0),
        hecho("Kovacs", "personaje", "Kovacs herido.", 2),
        hecho("Ilse", "personaje", "Ilse ausente.", 2),  # personaje fuera del capítulo: excluido
        hecho("Puente", "locacion", "El puente sin luz.", 3),
        hecho("Bodega 4", "locacion", "Bodega sellada.", 3),  # otra locación: excluida
        hecho("el médico", "personaje", "Sujeto sin validar.", 4, validado=False),  # entra siempre
        hecho("Kovacs", "personaje", "Hecho superado.", 1, superado=1),  # RF-07.6: no se inyecta
        hecho("mundo", "mundo", "Regla superada.", 0, superado=0),
    ])
    textos = [h.hecho for h in cont.filtrar_para_capitulo(log, entrada)]
    assert textos == ["Regla del universo.", "Kovacs herido.", "El puente sin luz.", "Sujeto sin validar."]
    assert len(log) == 8  # selección de lectura: no escribe


def test_es_superconjunto_detecta_perdida_cambio_y_marca_borrada():
    base = LogContinuidad([hecho("Kovacs", "personaje", "A", 1), hecho("Ilse", "personaje", "B", 2)])
    assert cont.es_superconjunto(base, LogContinuidad(base.root + [hecho("mundo", "mundo", "C", 3)]))[0]
    assert cont.es_superconjunto(base, cont.marcar_superado(base, [1]))[0]  # superado_por nuevo está permitido
    ok, motivo = cont.es_superconjunto(base, LogContinuidad([base.root[1]]))
    assert not ok and "pasó de 2 a 1" in motivo
    ok, motivo = cont.es_superconjunto(base, LogContinuidad([hecho("Kovacs", "personaje", "A modificado", 1), base.root[1]]))
    assert not ok and "cambió" in motivo
    marcado = cont.marcar_superado(base, [1])
    ok, motivo = cont.es_superconjunto(marcado, base)
    assert not ok and "perdió su marca" in motivo


def test_escribir_continuidad_rechaza_perder_hechos(proyecto):
    log = repo.leer_continuidad(proyecto)
    assert len(log) == 3
    with pytest.raises(EstadoInvalidoError, match="INV-03"):
        repo.escribir_continuidad(proyecto, LogContinuidad(log.root[:2]))
    assert len(repo.leer_continuidad(proyecto)) == 3


def test_sujetos_conocidos_y_claves_no_previstas():
    fichas = FichaPersonajes({"Kovacs": Personaje(estado_fisico="a", estado_psicologico="b", ultima_aparicion=0)})
    mundo = Mundo(reglas=[], objetos=[], linea_de_tiempo=[], locaciones={"Puente": "x"})
    registro = pers.sujetos_conocidos(fichas, mundo)
    assert registro == {"Kovacs", "Puente", "mundo"}
    assert pers.claves_no_previstas({"Kovacs": fichas.root["Kovacs"], "el capitán": fichas.root["Kovacs"]}, registro) == ["el capitán"]


def test_aplicar_delta_personajes_une_secretos_y_fija_ultima_aparicion():
    fichas = FichaPersonajes({"Kovacs": Personaje(estado_fisico="Sano", estado_psicologico="Calmo", secretos_que_conoce=["s1"], ultima_aparicion=2)})
    cambio = {"Kovacs": Personaje(estado_fisico="Herido", estado_psicologico="Tenso", secretos_que_conoce=["s2", "s1"], ultima_aparicion=0)}
    nuevas = pers.aplicar_delta(fichas, cambio, 7)
    k = nuevas.root["Kovacs"]
    assert (k.estado_fisico, k.estado_psicologico, k.ultima_aparicion) == ("Herido", "Tenso", 7)
    assert k.secretos_que_conoce == ["s1", "s2"]
    assert fichas.root["Kovacs"].ultima_aparicion == 2  # no muta


def test_resumen_rodante_ventana_nunca_excede_y_recorte_a_minimo():
    texto = ""
    for n in range(1, 6):
        texto = rr.agregar(texto, n, f"Resumen {n}.", ventana=3)
        assert len(rr.capitulos_cubiertos(texto)) <= 3
    assert rr.capitulos_cubiertos(texto) == [3, 4, 5]
    assert rr.parsear(texto)[0] == (3, "Resumen 3.")
    minimo = rr.recortar_a_minimo(texto)
    assert rr.capitulos_cubiertos(minimo) == [5]
    assert rr.recortar_a_minimo("") == ""


def test_resumen_rodante_reemplazar_solo_si_esta_en_ventana():
    texto = rr.agregar(rr.agregar("", 4, "Viejo 4.", 3), 5, "Cinco.", 3)
    nuevo = rr.reemplazar(texto, 4, "Nuevo 4.")
    assert rr.parsear(nuevo) == [(4, "Nuevo 4."), (5, "Cinco.")]
    assert rr.reemplazar(texto, 1, "Fuera de ventana.") == texto


def test_guardar_capitulo_inv07_y_descartar_borrador(proyecto):
    repo.guardar_capitulo(proyecto, 1, "texto")
    with pytest.raises(CapituloCerradoError):
        repo.guardar_capitulo(proyecto, 1, "otro")
    repo.guardar_capitulo(proyecto, 1, "otro", reemplazar_borrador=True)
    assert repo.leer_manuscrito(proyecto, 1) == "otro"
    with pytest.raises(CapituloCerradoError):
        repo.descartar_borrador(proyecto, 1, ultimo_cerrado=1)
    repo.descartar_borrador(proyecto, 1, ultimo_cerrado=0)
    assert not repo.existe_capitulo(proyecto, 1)


def test_validar_archivo_por_ruta(proyecto):
    from pathlib import Path

    rutas = Rutas(proyecto)
    assert repo.validar_archivo(rutas, Path("04_estado/manifest.json")) == "Manifest"
    assert repo.validar_archivo(rutas, Path("04_estado/continuidad.json")) == "LogContinuidad"
    rutas.personajes.write_text('{"Kovacs": {"estado_fisico": 1}}', encoding="utf-8")
    with pytest.raises(EstadoInvalidoError, match="FichaPersonajes"):
        repo.validar_archivo(rutas, Path("04_estado/personajes.json"))
    (rutas.estado / "raro.json").write_text("{}", encoding="utf-8")
    with pytest.raises(EstadoInvalidoError, match="esquema conocido"):
        repo.validar_archivo(rutas, Path("04_estado/raro.json"))
