"""Capa de estado: continuidad append-only y filtro (RF-05.1, RF-06.3, RF-07.6, INV-03), fichas (RF-06.1/06.2), resumen rodante (RF-06.4, EX-04), repository (EX-01, INV-07)."""

import pytest

from app.errores import CapituloCerradoError, EstadoInvalidoError
from app.rutas import Rutas
from app.schemas import HechoContinuidad, LogContinuidad, Mundo, Personaje, FichaPersonajes
from app.schemas.outline import EntradaOutline
from app.state import continuidad as cont
from app.state import personajes as pers
from app.state import repository as repo
from app.state import resumen_rodante as rr


def hecho(sujeto, categoria, texto, cap, validado=True, superado=None, relacionados=None):
    return HechoContinuidad(sujeto=sujeto, categoria=categoria, hecho=texto, cap_origen=cap, sujeto_validado=validado,
                            superado_por=superado, relacionados=relacionados or [])


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
    # X-02.1: con un conjunto de personajes ampliado (los permitidos), entra también el hecho de Ilse,
    # que con la lista de la escaleta quedaba fuera. El filtro incluye de más, nunca de menos.
    ampliado = [h.hecho for h in cont.filtrar_para_capitulo(log, entrada, {"Kovacs", "Ilse"})]
    assert "Ilse ausente." in ampliado and "Kovacs herido." in ampliado


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


def test_resumen_rodante_guarda_todos_y_recorte_a_minimo():
    # X-02.3: el almacenamiento conserva todos los capítulos; la ventana recorta al entregar, no al guardar.
    texto = ""
    for n in range(1, 6):
        texto = rr.agregar(texto, n, f"Resumen {n}.")
    assert rr.capitulos_cubiertos(texto) == [1, 2, 3, 4, 5]
    assert rr.parsear(texto)[0] == (1, "Resumen 1.")
    minimo = rr.recortar_a_minimo(texto)  # EX-04: sigue siendo la última sección
    assert rr.capitulos_cubiertos(minimo) == [5]
    assert rr.recortar_a_minimo("") == ""


def test_resumen_rodante_para_escritor_recorta_los_viejos_a_una_linea():
    # X-02.3: los últimos `ventana` completos; los anteriores, una línea (su primera frase) cada uno.
    texto = ""
    for n in range(1, 6):
        texto = rr.agregar(texto, n, f"Pasó algo en {n}. Y una segunda frase que no debe verse.")
    entregado = rr.para_escritor(texto, ventana=2)
    assert "## Capítulo 4" in entregado and "## Capítulo 5" in entregado  # los dos últimos, completos
    assert "una segunda frase que no debe verse" in entregado.split("## Capítulo 4")[1]  # el completo la conserva
    assert "- Capítulo 1: Pasó algo en 1." in entregado  # los viejos, una línea
    assert "- Capítulo 3: Pasó algo en 3." in entregado
    assert "segunda frase que no debe verse" not in entregado.split("## Capítulo 4")[0]  # los viejos, no
    assert rr.para_escritor("", 2) == ""


def test_resumen_rodante_reemplazar_solo_si_esta_presente():
    texto = rr.agregar(rr.agregar("", 4, "Viejo 4."), 5, "Cinco.")
    nuevo = rr.reemplazar(texto, 4, "Nuevo 4.")
    assert rr.parsear(nuevo) == [(4, "Nuevo 4."), (5, "Cinco.")]
    assert rr.reemplazar(texto, 1, "No está.") == texto  # un capítulo que no se guardó no se agrega


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


# ---------- X-05: aristas entre hechos ----------

def _entrada_cap(n, personajes, locacion="Puente"):
    return EntradaOutline(num=n, titulo="T", objetivo_narrativo="o", personajes=personajes,
                          locacion=locacion, informacion_nueva="", tension=3)


def test_un_hecho_de_otro_llega_si_toca_a_alguien_en_escena():
    """La arista es justo el hecho que hoy se pierde: sujeto ausente, consecuencia presente."""
    entrada = _entrada_cap(5, ["Ruiz"])
    log = LogContinuidad([
        hecho("Volkov", "personaje", "Volkov selló la esclusa y dejó a Ruiz aislada.", 3, relacionados=["Ruiz"]),
        hecho("Volkov", "personaje", "Volkov perdió su linterna.", 3),  # no toca a nadie en escena
    ])
    textos = [h.hecho for h in cont.filtrar_para_capitulo(log, entrada, {"Ruiz"})]
    assert "Volkov selló la esclusa y dejó a Ruiz aislada." in textos
    assert "Volkov perdió su linterna." not in textos


def test_los_hechos_sin_el_campo_siguen_entrando_por_sujeto():
    """Los 385 hechos ya guardados no tienen `relacionados`: no pueden dejar de funcionar."""
    entrada = _entrada_cap(5, ["Kovacs"])
    log = LogContinuidad([hecho("Kovacs", "personaje", "Kovacs herido.", 2)])
    assert log.root[0].relacionados == []
    assert [h.hecho for h in cont.filtrar_para_capitulo(log, entrada, {"Kovacs"})] == ["Kovacs herido."]


def test_el_canon_del_preludio_nunca_se_recorta():
    """cap_origen 0 son las reglas del mundo: recortarlas provoca la contradicción que esto evita."""
    entrada = _entrada_cap(12, ["Kovacs"])
    canon = [hecho("mundo", "mundo", f"Regla {i} del universo.", 0) for i in range(5)]
    tardios = [hecho("Kovacs", "personaje", f"Kovacs hizo la cosa {i}.", 10) for i in range(20)]
    quedan = cont.recortar_a_presupuesto(canon + tardios, entrada, {"Kovacs"}, 12,
                                         tope_tokens=10, coste=lambda h: 5)
    assert [h.hecho for h in quedan] == [h.hecho for h in canon], "el canon entra aunque no quepa nada más"


def test_cuando_aprieta_el_presupuesto_gana_quien_esta_en_escena():
    entrada = _entrada_cap(12, ["Kovacs"])
    en_escena = hecho("Kovacs", "personaje", "Kovacs sangra.", 11)
    lejano = hecho("mundo", "mundo", "Dato de mundo viejo.", 4)
    quedan = cont.recortar_a_presupuesto([lejano, en_escena], entrada, {"Kovacs"}, 12,
                                         tope_tokens=5, coste=lambda h: 5)
    assert [h.hecho for h in quedan] == ["Kovacs sangra."]


def test_la_salida_va_en_orden_de_capitulo_no_de_puntuacion():
    """El escritor tiene que leer una cronología; un ranking le cuenta la historia desordenada."""
    entrada = _entrada_cap(12, ["Kovacs"])
    hechos = [hecho("Kovacs", "personaje", "C tardío.", 11),
              hecho("mundo", "mundo", "A del preludio.", 0),
              hecho("Kovacs", "personaje", "B medio.", 5)]
    quedan = cont.recortar_a_presupuesto(hechos, entrada, {"Kovacs"}, 12,
                                         tope_tokens=1000, coste=lambda h: 5)
    assert [h.cap_origen for h in quedan] == [0, 5, 11]


def test_con_sitio_de_sobra_no_se_recorta_nada():
    """Con 3 capítulos cabe todo: el interruptor no puede cambiar la línea base por accidente."""
    entrada = _entrada_cap(3, ["Kovacs"])
    hechos = [hecho("Kovacs", "personaje", f"Hecho {i}.", i) for i in range(4)]
    quedan = cont.recortar_a_presupuesto(hechos, entrada, {"Kovacs"}, 3,
                                         tope_tokens=100000, coste=lambda h: 5)
    assert len(quedan) == len(hechos)
