"""Lo que enseño la primera pasada real (specs/spec3.md, 3.11: RF3-PAS-01 a RF3-PAS-06).

Los casos salen de la pasada del 23 de septiembre sobre `novela_real.db`: un valor compuesto
que el extractor guardo tal cual, la variante de un lugar del canon, el nombre del propio mundo
tomado por entidad desconocida y un nombre menor que avisaba en cada capitulo.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

import pytest

from compartido.grafo import Resolvedor, clave_laxa, insertar_hecho
from compartido.puerto import demo
from orquestador import pipeline
from tareas.continuidad import puerta as p_continuidad
from tareas.extraccion import servicio as s_extraccion
from tareas.extraccion.esquemas import PALABRAS_RESUMEN, PALABRAS_VALOR, SalidaExtraccion
from tests import fabrica
from tests.entorno import contar, contexto, crear_novela, nueva_bd, puerto_falso

#: Un valor real de la pasada: doce palabras con tres datos dentro.
COMPUESTO = "doce por minuto, saturacion en ochenta y uno, once minutos hasta confusion"


def _salida(*valores: str) -> dict[str, Any]:
    return {
        "hechos": [
            {"escena_orden": 1, "sujeto_tipo": "personaje", "sujeto_ref": "Trebo",
             "atributo": f"dato {i}", "valor": v}
            for i, v in enumerate(valores)
        ],
        "resumen": "La cuadrilla entra en el anillo y encuentra la sala vacia.",
        "resumen_breve": "Entran en el anillo.",
    }


# --- RF3-PAS-01: un hecho, un dato ---------------------------------------------------------------


def test_un_valor_largo_no_invalida_la_salida_y_queda_contado() -> None:
    """La reanudacion de la pasada real acabo en `error`: el rechazo tiraba la extraccion entera
    por tres valores de once palabras. Un limite blando no rechaza (como el resumen)."""
    salida = SalidaExtraccion.model_validate(_salida("grises", COMPUESTO, COMPUESTO + " y mas"))
    assert len(salida.hechos) == 3
    assert [h.atributo for h in salida.valores_largos] == ["dato 1", "dato 2"]


def test_diez_palabras_no_son_largas_y_once_si() -> None:
    assert PALABRAS_VALOR == 10
    diez = " ".join(["palabra"] * 10)
    assert SalidaExtraccion.model_validate(_salida("doce por minuto", diez)).valores_largos == []
    assert len(SalidaExtraccion.model_validate(_salida(diez + " mas")).valores_largos) == 1


def test_un_valor_largo_entra_con_aviso_y_la_novela_sigue() -> None:
    once = "constantes leidas en la grabacion del registro del dia mil ochocientos"

    def extraccion(entrada: str, agente: str) -> dict[str, Any]:
        salida = demo.extraccion(entrada, agente)
        if demo._capitulo(entrada) == 2:
            salida["hechos"].append({
                "escena_orden": 1, "sujeto_tipo": "objeto", "sujeto_ref": demo.OBJETO,
                "atributo": "contenido", "valor": once, "categoria": "otro",
            })
        return salida

    con, ruta = nueva_bd()
    novela_id = crear_novela(con)
    puerto = puerto_falso(con)
    puerto.registrar("extraccion", extraccion)
    assert pipeline.avanzar(contexto(con, puerto, ruta, novela_id)) == "completada"
    assert contar(con, "SELECT COUNT(*) FROM hecho WHERE valor = ?", once) == 1
    detalle = json.loads(con.execute(
        "SELECT detalle FROM resultado_puerta WHERE puerta = 3 AND capitulo = 2"
    ).fetchone()[0])
    avisos = [c for c in detalle["conflictos"] if c["comprobacion"] == "valor_compuesto"]
    assert len(avisos) == 1 and avisos[0]["aviso"]
    correcciones = [json.loads(f[0]).get("correcciones") for f in con.execute(
        "SELECT payload FROM traza_evento WHERE tipo = 'extraccion_descartes' "
        "AND json_extract(payload, '$.capitulo') = 2"
    )]
    assert correcciones[0]["valor_largo"] == 1


def test_el_esquema_declara_el_limite_sin_patron() -> None:
    """El limite va en la descripcion. Como `pattern`, Claude Code reintentaba por dentro la
    salida estructurada: en la reanudacion, tres turnos y 1,75 $ por extraccion."""
    esquema = SalidaExtraccion.model_json_schema()
    assert f"{PALABRAS_VALOR} palabras como mucho" in json.dumps(esquema, ensure_ascii=False)
    assert "pattern" not in esquema["$defs"]["HechoExtraido"]["properties"]["valor"]


# --- RF3-PAS-01: un valor vigente compuesto, de antes del limite ---------------------------------

#: El valor vigente real que paro el capitulo 3 en la reanudacion de la pasada.
AMBIENTE = ("treinta y un grados y ochenta por ciento de humedad; olor dulce a fruta pasada y "
            "cloro con algo debajo que no es vegetal")


def _con_ambiente_compuesto(
    valor: str = AMBIENTE,
) -> tuple[sqlite3.Connection, fabrica.Grafo, int]:
    con, _ = nueva_bd()
    g = fabrica.novela_minima(con)
    hid = insertar_hecho(
        con, novela_id=g.novela_id, escena_id=g.escenas[(1, 1)], sujeto_tipo="lugar",
        sujeto_id=g.lugares["Puente"], sujeto_nombre="Puente", atributo="ambiente interior",
        valor=valor, categoria="fisico", cita=None, supersede_a=None,
    )
    return con, g, hid


def _extraer_en_2_1(con: sqlite3.Connection, g: fabrica.Grafo, valor: str) -> None:
    salida = SalidaExtraccion.model_validate({
        "hechos": [{"escena_orden": 1, "sujeto_tipo": "lugar", "sujeto_ref": "Puente",
                    "atributo": "ambiente interior", "valor": valor, "cita": valor}],
        "resumen": "La cuadrilla vuelve al puente y el aire sigue igual de pesado.",
        "resumen_breve": "Vuelven al puente.",
    })
    s_extraccion.aplicar(con, g.novela_id, 2, salida, {1: g.escenas[(2, 1)]})


def test_una_parte_de_un_valor_compuesto_es_una_reafirmacion() -> None:
    con, g, hid = _con_ambiente_compuesto()
    _extraer_en_2_1(con, g, "treinta y un grados y ochenta por ciento de humedad")
    assert contar(con, "SELECT COUNT(*) FROM hecho WHERE atributo = 'ambiente interior'") == 1
    assert contar(con, "SELECT COUNT(*) FROM hecho_uso WHERE hecho_id = ? AND via = 'reafirma'",
                  hid) == 1
    conflictos = p_continuidad.evaluar(con, g.novela_id, 2).bloqueantes
    assert "continuidad_factual" not in {c.comprobacion for c in conflictos}


@pytest.mark.parametrize("valor", [
    "dieciocho grados y aire seco",
    # Validador: un trozo que quita la negacion afirma lo contrario del canon.
    "algo debajo que es vegetal",
    "es vegetal",
    # Validador: trozos de una o dos palabras casan con casi cualquier compuesto.
    "humedad",
    "de",
])
def test_lo_que_no_es_un_trozo_valido_del_compuesto_sigue_contradiciendo(valor: str) -> None:
    con, g, _ = _con_ambiente_compuesto()
    _extraer_en_2_1(con, g, valor)
    conflictos = p_continuidad.evaluar(con, g.novela_id, 2).bloqueantes
    assert "continuidad_factual" in {c.comprobacion for c in conflictos}


def test_un_trozo_detras_de_un_negador_no_es_una_parte() -> None:
    vigente = "pasillo largo y frio, sin olor a quemado ni rastro de humo en el aire"
    assert s_extraccion._parte_de_un_compuesto(vigente, "pasillo largo y frio")
    assert not s_extraccion._parte_de_un_compuesto(vigente, "olor a quemado")
    assert not s_extraccion._parte_de_un_compuesto(vigente, "rastro de humo")
    # Un valor vigente corto no es compuesto: ahi manda la comparacion exacta de siempre.
    assert not s_extraccion._parte_de_un_compuesto("pasillo largo y frio", "pasillo largo y")


#: El valor vigente real de la parada 8 del relanzamiento (capitulo 2 de la novela real).
LIBRO = ("sector 6 a Otxoa al ciento quince por ciento; sectores 5 y 7, turno de trabajo, al "
         "noventa; responsable I. Aldama")


def test_cada_segmento_trozo_del_compuesto_es_una_reafirmacion() -> None:
    """El extractor se quedo con el primer y el ultimo segmento y se salto el del medio."""
    parte = s_extraccion._parte_de_un_compuesto
    assert parte(LIBRO, "sector 6 a Otxoa al ciento quince por ciento; responsable I. Aldama")
    assert parte(LIBRO, "sectores 5 y 7, turno de trabajo, al noventa; responsable I. Aldama")
    # Con varios segmentos, cada uno es un segmento entero del vigente: uno que no esta, uno
    # recortado o uno cambiado tumban el valor entero.
    assert not parte(LIBRO, "sector 6 a Otxoa al ciento quince por ciento; responsable J. Perez")
    assert not parte(LIBRO, "sector 6 a Otxoa al ciento quince por ciento; Aldama")
    negado = "sala cerrada sin luz de emergencia; ruido de bombas bajo el suelo metalico"
    assert not parte(negado, "sala cerrada sin luz; luz de emergencia")
    assert not parte(negado, "sala cerrada sin luz; ruido de bombas")
    # Un solo trozo sigue valiendo, pero dentro de un segmento y sin negador delante.
    assert parte(negado, "ruido de bombas bajo el suelo")
    assert not parte(negado, "luz de emergencia")


_A, _B, _C = (s.strip() for s in LIBRO.split(";"))


@pytest.mark.parametrize("nuevo", [
    # Validador de ac534bd: trozos de datos distintos juntos cambian a quien va cada valor.
    "sector 6 a Otxoa; turno de trabajo, al noventa",
    "sectores 5 y 7; al ciento quince por ciento",
    # Segmentos recortados o que cruzan el «;» del vigente.
    "responsable I. Aldama; sector 6 a Otxoa",
    "por ciento sectores 5 y 7",
    # Validador de 0913640: segmentos ENTEROS fuera de orden o repetidos.
    f"{_C}; {_A}",
    f"{_A}; {_A}",
    f"{_B}; {_A}",
    f"{_A}; {_C}; {_C}",
])
def test_recombinar_trozos_del_compuesto_sigue_contradiciendo(nuevo: str) -> None:
    assert not s_extraccion._parte_de_un_compuesto(LIBRO, nuevo)


def test_los_segmentos_enteros_en_orden_son_una_reafirmacion() -> None:
    parte = s_extraccion._parte_de_un_compuesto
    assert parte(LIBRO, f"{_A}; {_B}; {_C}")
    assert parte(LIBRO, f"{_B}; {_C}")


@pytest.mark.parametrize(("vigente", "nuevo"), [
    # Validador de 0913640: negadores que faltaban.
    ("ningun rastro de sangre en el suelo del modulo; luces de emergencia encendidas",
     "rastro de sangre en el suelo"),
    ("nadie ha entrado en la bodega desde el despegue; puerta sellada por fuera",
     "ha entrado en la bodega"),
    ("la baliza tampoco emite senal de socorro en ninguna frecuencia conocida",
     "emite senal de socorro"),
    ("todos los tripulantes vivos salvo el piloto de relevo del turno de noche",
     "el piloto de relevo"),
    # El negador que cierra el segmento anterior.
    ("no; hay aire respirable en la bodega fria del sector siete",
     "hay aire respirable en la bodega"),
])
def test_un_trozo_detras_de_cualquier_negador_no_es_una_parte(vigente: str, nuevo: str) -> None:
    assert not s_extraccion._parte_de_un_compuesto(vigente, nuevo)


def test_un_trozo_no_corta_una_cifra() -> None:
    parte = s_extraccion._parte_de_un_compuesto
    assert not parte(LIBRO, "sector 6 a Otxoa al ciento")
    assert not parte(LIBRO, "quince por ciento")
    assert not parte(LIBRO, "7, turno de trabajo, al noventa")
    assert parte(LIBRO, "a Otxoa al ciento quince por ciento")
    assert parte(LIBRO, "sectores 5 y 7, turno de trabajo")


@pytest.mark.parametrize(("nuevo", "contradice"), [
    (f"{_A}; {_C}", False),
    (f"{_C}; {_A}", True),
])
def test_la_parada_8_pasa_por_la_puerta_3(nuevo: str, contradice: bool) -> None:
    con, g, _ = _con_ambiente_compuesto(LIBRO)
    _extraer_en_2_1(con, g, nuevo)
    conflictos = p_continuidad.evaluar(con, g.novela_id, 2).bloqueantes
    assert ("continuidad_factual" in {c.comprobacion for c in conflictos}) is contradice


def test_la_atribucion_cruzada_dentro_de_un_solo_segmento_contradice() -> None:
    vigente = "la capitana Vela lleva el traje rojo y el ingeniero Soto lleva el traje gris"
    assert not s_extraccion._parte_de_un_compuesto(vigente, "la capitana Vela; lleva el traje gris")
    assert s_extraccion._parte_de_un_compuesto(vigente, "la capitana Vela lleva el traje rojo")


#: La regla de RF3-PAS-07, entera: comparar frases sueltas dejaba pasar una skill que la
#: invertia sin quitarlas (validador de 5ffcbe6).
REGLA_DEL_USO = (
    "Un uso es actuar sobre el dato **tal como consta**. Si el personaje calcula con sus "
    "propios datos una cifra o un valor que se parece a un hecho del canon, aunque compartan "
    "una palabra o un número, eso no es un uso de ese hecho, y tampoco es conocimiento de él: "
    "una cifra que coincide no es el mismo dato. Registra la cuenta como un hecho **del "
    "personaje** (su estimación, su cálculo), con un atributo propio, y no como un hecho del "
    "sujeto sobre el que calcula: lo que un personaje estima no es canon del mundo. Solo si la "
    "escena muestra que llega al dato registrado exacto, el mismo valor en las mismas "
    "condiciones, es conocimiento por la vía `dedujo`; y si además actúa sobre él, regístralo "
    "también como uso. Ejemplo: «cuarenta horas para diez personas son veintiséis de planta», "
    "dicho por quien hace la cuenta, ni usa ni deduce el dato «déficit a las veintiséis horas "
    "con once personas»: es la estimación de ese personaje, con otra gente y otra pregunta. Si "
    "más adelante vuelve a estimar lo mismo con otra cifra, usa el mismo atributo con "
    "`supersede_a`: una estimación que cambia no contradice."
)


def test_el_extractor_recibe_la_regla_del_uso_entera() -> None:
    """RF3-PAS-07, parada 9, por el mismo camino por el que el puerto lee la skill.

    La seccion de los usos entera: un parrafo anadido que dijera lo contrario tambien falla.
    """
    from compartido.puerto.terminal import PuertoTerminal
    from config import raiz_repo

    puerto = PuertoTerminal(skills_dir=raiz_repo() / ".claude" / "skills")
    skill = puerto.ruta_skill("extraccion").read_text(encoding="utf-8")
    seccion = skill.split("**Usos de conocimiento**")[1].split("**Estados de personaje**")[0]
    parrafos = [p.strip() for p in seccion.split("\n\n") if p.strip()]
    assert len(parrafos) == 2
    # La regla de siempre: un uso se registra aunque el personaje ya supiera el dato.
    assert "hay que registrarlo aunque el personaje ya lo supiera de antes" in parrafos[0]
    assert parrafos[1] == REGLA_DEL_USO


def _puerta_3(con: sqlite3.Connection, g: fabrica.Grafo) -> tuple[set[str], set[str]]:
    r = p_continuidad.evaluar(con, g.novela_id, 2)
    return {c.comprobacion for c in r.bloqueantes}, {c.comprobacion for c in r.avisos}


def _conocer(con: sqlite3.Connection, g: fabrica.Grafo, quien: str, via: str) -> None:
    con.execute(
        "INSERT INTO estado_conocimiento (novela_id, personaje_id, hecho_id, escena_id, postura,"
        " via) VALUES (?,?,?,?, 'sabe', ?)",
        (g.novela_id, g.personajes[quien], g.hechos["ojos"], g.escenas[(2, 1)], via),
    )


def _usar(con: sqlite3.Connection, g: fabrica.Grafo, quien: str) -> None:
    con.execute(
        "INSERT INTO uso_conocimiento (novela_id, personaje_id, hecho_id, escena_id) "
        "VALUES (?,?,?,?)",
        (g.novela_id, g.personajes[quien], g.hechos["ojos"], g.escenas[(2, 1)]),
    )


def test_la_salida_que_pide_la_regla_del_uso_no_para() -> None:
    """Parada 9: el uso falso para; la cuenta como hecho del personaje, sin uso, no."""
    con, _ = nueva_bd()
    g = fabrica.novela_minima(con)
    _usar(con, g, "Reyes")
    assert "conocimiento_no_adquirido" in _puerta_3(con, g)[0]

    con, _ = nueva_bd()
    g = fabrica.novela_minima(con)
    insertar_hecho(
        con, novela_id=g.novela_id, escena_id=g.escenas[(2, 1)], sujeto_tipo="personaje",
        sujeto_id=g.personajes["Reyes"], sujeto_nombre="Reyes",
        atributo="estimacion del color de ojos de Ibarra", valor="grises o azules",
        categoria="otro", cita=None, supersede_a=None,
    )
    bloqueantes, _ = _puerta_3(con, g)
    assert not bloqueantes & {"conocimiento_no_adquirido", "continuidad_factual"}


def test_una_deduccion_de_lo_que_no_presencio_habilita_el_uso_pero_avisa() -> None:
    con, _ = nueva_bd()
    g = fabrica.novela_minima(con)
    _conocer(con, g, "Reyes", "dedujo")
    _usar(con, g, "Reyes")
    bloqueantes, avisos = _puerta_3(con, g)
    assert "conocimiento_no_adquirido" not in bloqueantes
    assert "deduccion_por_verificar" in avisos


def _reyes_de_pov(con: sqlite3.Connection, g: fabrica.Grafo) -> None:
    con.execute("UPDATE escena SET pov_id = ? WHERE id = ?",
                (g.personajes["Reyes"], g.escenas[(1, 1)]))


def _reyes_actua(con: sqlite3.Connection, g: fabrica.Grafo) -> None:
    con.execute(
        "INSERT INTO estado_personaje (novela_id, personaje_id, escena_id, condicion) "
        "VALUES (?,?,?, 'vivo')",
        (g.novela_id, g.personajes["Reyes"], g.escenas[(1, 1)]),
    )


def _reyes_usa_alli(con: sqlite3.Connection, g: fabrica.Grafo) -> None:
    con.execute(
        "INSERT INTO uso_conocimiento (novela_id, personaje_id, hecho_id, escena_id) "
        "VALUES (?,?,?,?)",
        (g.novela_id, g.personajes["Reyes"], g.hechos["ojos"], g.escenas[(1, 1)]),
    )


def _reyes_lo_ignora(con: sqlite3.Connection, g: fabrica.Grafo) -> None:
    con.execute("UPDATE estado_conocimiento SET postura = 'ignora' WHERE via = 'dedujo'")


@pytest.mark.parametrize(("quien", "via", "preparar"), [
    ("Ibarra", "dedujo", None),  # estaba en el reparto de la escena del hecho
    ("Reyes", "se_lo_contaron", None),  # no lo deduce
    # Validador de d6b64b9: la presencia de RF2-PIPE-30 (POV, reparto o actuar en la escena).
    ("Reyes", "dedujo", _reyes_de_pov),
    ("Reyes", "dedujo", _reyes_actua),
    ("Reyes", "dedujo", _reyes_usa_alli),
    # Una postura que no habilita usos no calla a nadie.
    ("Reyes", "dedujo", _reyes_lo_ignora),
])
def test_solo_avisa_la_deduccion_de_lo_que_no_presencio(
    quien: str, via: str, preparar: Any
) -> None:
    con, _ = nueva_bd()
    g = fabrica.novela_minima(con)
    _conocer(con, g, quien, via)
    if preparar is not None:
        preparar(con, g)
    assert "deduccion_por_verificar" not in _puerta_3(con, g)[1]


def test_partir_el_compuesto_con_supersede_a_no_contradice() -> None:
    """Lo que pide la marca [COMPUESTO]: cada dato en su hecho, sustituyendo al compuesto."""
    con, g, hid = _con_ambiente_compuesto()
    salida = SalidaExtraccion.model_validate({
        "hechos": [
            {"escena_orden": 1, "sujeto_tipo": "lugar", "sujeto_ref": "Puente",
             "atributo": atributo, "valor": valor, "supersede_a": "ambiente interior"}
            for atributo, valor in (
                ("temperatura interior", "treinta y un grados"),
                ("olor interior", "fruta pasada y cloro"),
            )
        ],
        "resumen": "La cuadrilla vuelve al puente y el aire sigue igual de pesado.",
        "resumen_breve": "Vuelven al puente.",
    })
    s_extraccion.aplicar(con, g.novela_id, 2, salida, {1: g.escenas[(2, 1)]})
    assert contar(con, "SELECT COUNT(*) FROM hecho WHERE supersede_a = ?", hid) == 2
    conflictos = p_continuidad.evaluar(con, g.novela_id, 2).bloqueantes
    assert "continuidad_factual" not in {c.comprobacion for c in conflictos}


def test_el_paquete_marca_los_valores_compuestos() -> None:
    import config
    from compartido.contexto import Presupuesto

    con, g, _ = _con_ambiente_compuesto()
    render = s_extraccion.paquete(
        con, g.novela_id, 2, {1: "texto", 2: "texto"}, presupuesto=Presupuesto(
            bloques=config.PRESUPUESTO_BLOQUES, techo=config.PRESUPUESTO_PAQUETE),
    ).render()
    assert f"ambiente interior = {AMBIENTE} [COMPUESTO]" in render
    assert "color de ojos = grises [COMPUESTO]" not in render


# --- RF3-PAS-02: el resumen --------------------------------------------------------------------


def test_el_esquema_pide_un_resumen_mas_corto_que_el_limite() -> None:
    esquema = json.dumps(SalidaExtraccion.model_json_schema(), ensure_ascii=False)
    assert "unas 160 palabras" in esquema
    # El recorte actua por encima de 250, no de 200 (el test de test_deuda.py deriva de aqui).
    largo = "La cuadrilla avanza. " * 90  # 270 palabras
    assert PALABRAS_RESUMEN == 250
    resumen = SalidaExtraccion.model_validate({**_salida(), "resumen": largo}).resumen
    assert len(resumen.split()) == 249


# --- RF3-PAS-04: variantes de un nombre del canon -----------------------------------------------


def test_la_clave_laxa_ignora_puntuacion_articulos_y_preposiciones() -> None:
    assert clave_laxa("Bodega fría del sector 7") == clave_laxa("Bodega fría, sector 7")
    assert clave_laxa("la Operadora") == clave_laxa("la operadora") == "operadora"
    assert clave_laxa("Malla-3") == "malla 3"
    # La eñe sigue siendo una letra.
    assert clave_laxa("Peña") != clave_laxa("Pena")


def test_una_letra_designa_y_no_se_quita() -> None:
    """Hallazgo del validador: con «a» e «y» como palabras vacias, tres sitios eran uno."""
    claves = {clave_laxa(n) for n in ("Anillo A", "Anillo Y", "Anillo")}
    assert len(claves) == 3
    con, _ = nueva_bd()
    g = fabrica.novela_minima(con)
    assert Resolvedor(con, g.novela_id).id_de("lugar", "Puente A") is None


def test_el_resolvedor_acepta_una_variante_solo_si_no_es_ambigua() -> None:
    con, _ = nueva_bd()
    g = fabrica.novela_minima(con)
    r = Resolvedor(con, g.novela_id)
    assert r.id_de("lugar", "el modulo de la carga") == g.lugares["Modulo de carga"]
    assert r.por_variante == [("lugar", "el modulo de la carga")]
    # Dos lugares con la misma clave laxa: no decide por su cuenta.
    con.execute(
        "INSERT INTO lugar (novela_id, mundo_id, nombre, nombre_clave) "
        "SELECT novela_id, mundo_id, 'Modulo, carga', 'modulo, carga' FROM lugar WHERE id = ?",
        (g.lugares["Puente"],),
    )
    assert Resolvedor(con, g.novela_id).id_de("lugar", "el modulo de la carga") is None


# --- RF3-PAS-03 a RF3-PAS-06: los nombres menores sobre la demo ---------------------------------


@pytest.fixture(scope="module")
def demo_con_nombres() -> tuple[sqlite3.Connection, int, list[dict[str, Any]]]:
    """El capitulo 1 inventa nombres como en la pasada real; el 2 repite uno y trae dos nuevos,
    uno de ellos parecido a un lugar del canon («Puente A» no es «Puente»)."""
    por_capitulo = {
        1: ["Estacion Cerro Quince", "Berila IV", "berila iv", "Modulo, carga"],
        2: ["Berila IV", "Malla-3", "Puente A"],
    }

    def extraccion(entrada: str, agente: str) -> dict[str, Any]:
        salida = demo.extraccion(entrada, agente)
        salida["entidades_no_reconocidas"] = [
            {"escena_orden": 1, "nombre": n} for n in por_capitulo.get(demo._capitulo(entrada), [])
        ]
        return salida

    con, ruta = nueva_bd()
    novela_id = crear_novela(con)
    puerto = puerto_falso(con)
    puerto.registrar("extraccion", extraccion)
    assert pipeline.avanzar(contexto(con, puerto, ruta, novela_id)) == "completada"
    return con, novela_id, puerto.invocaciones


def test_solo_se_registran_los_nombres_que_no_son_del_canon_ni_repetidos(
    demo_con_nombres: tuple[sqlite3.Connection, int, list[dict[str, Any]]],
) -> None:
    con, _, _ = demo_con_nombres
    registrados = [
        (int(f[0]), str(f[1])) for f in con.execute(
            "SELECT eo.capitulo_numero, en.nombre FROM entidad_no_reconocida en "
            "JOIN escena_ordinal eo ON eo.escena_id = en.escena_id ORDER BY en.id"
        )
    ]
    # El mundo, la variante del lugar y la repeticion con minuscula no entran.
    assert registrados == [
        (1, "Berila IV"), (2, "Berila IV"), (2, "Malla-3"), (2, "Puente A"),
    ]
    correcciones = [json.loads(f[0]).get("correcciones") for f in con.execute(
        "SELECT payload FROM traza_evento WHERE tipo = 'extraccion_descartes' "
        "AND json_extract(payload, '$.capitulo') = 1"
    )]
    assert correcciones[0]["entidad_del_canon"] == 2
    assert correcciones[0]["entidad_repetida"] == 1
    # Comprobar el canon no pasa por el resolvedor: no cuenta dos veces en la traza.
    assert "nombre_por_variante" not in correcciones[0]


def test_un_nombre_menor_solo_avisa_la_primera_vez(
    demo_con_nombres: tuple[sqlite3.Connection, int, list[dict[str, Any]]],
) -> None:
    con, novela_id, _ = demo_con_nombres
    avisos: dict[int, list[str]] = {}
    for f in con.execute(
        "SELECT capitulo, detalle FROM resultado_puerta WHERE novela_id = ? AND puerta = 3",
        (novela_id,),
    ):
        avisos[int(f[0])] = [
            c["datos"]["nombre"] for c in json.loads(f[1])["conflictos"]
            if c["comprobacion"] == "entidad_fuera_de_canon"
        ]
    assert avisos[1] == ["Berila IV"]
    assert avisos[2] == ["Malla-3", "Puente A"]


def test_el_redactor_y_el_extractor_reciben_los_nombres_menores_y_el_mundo(
    demo_con_nombres: tuple[sqlite3.Connection, int, list[dict[str, Any]]],
) -> None:
    _, _, invocaciones = demo_con_nombres

    def entradas(agente: str, capitulo: int) -> list[str]:
        return [i["entrada"] for i in invocaciones
                if i["agente"] == agente and demo._capitulo(i["entrada"]) == capitulo]

    for agente in ("redaccion", "extraccion"):
        assert all("Berila IV" not in e for e in entradas(agente, 1)), agente
        assert all("Berila IV" in e for e in entradas(agente, 2)), agente
        assert all("Malla-3" in e for e in entradas(agente, 3)), agente
    assert all("Estacion Cerro Quince" in e for e in entradas("extraccion", 1))
