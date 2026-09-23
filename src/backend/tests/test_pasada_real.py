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

import config
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


def _extraer_presencias(
    con: sqlite3.Connection, g: fabrica.Grafo, *personajes: str
) -> s_extraccion.Descartes:
    """Una extraccion del capitulo 1 que solo registra quien estaba en la escena 1.1."""
    salida = SalidaExtraccion.model_validate({
        "presencias": [{"escena_orden": 1, "personaje_ref": p} for p in personajes],
        "resumen": "La cuadrilla entra en el puente y encuentra la sala vacia.",
        "resumen_breve": "Entran en el puente.",
    })
    return s_extraccion.aplicar(con, g.novela_id, 1, salida, {1: g.escenas[(1, 1)]})


def test_una_presencia_registrada_habilita_lo_que_se_dijo_en_la_escena() -> None:
    """RF3-PAS-09, parada 10: estaba en la escena del hecho aunque la escaleta no lo pusiera."""
    con, _ = nueva_bd()
    g = fabrica.novela_minima(con)
    _extraer_presencias(con, g, "Reyes")
    assert contar(con, "SELECT COUNT(*) FROM presencia_escena WHERE personaje_id = ?",
                  g.personajes["Reyes"]) == 1
    _usar(con, g, "Reyes")
    assert "conocimiento_no_adquirido" not in _puerta_3(con, g)[0]


def test_sin_presencia_registrada_el_uso_sigue_parando() -> None:
    con, _ = nueva_bd()
    g = fabrica.novela_minima(con)
    # Repetir a quien ya esta en el reparto no cambia nada.
    _extraer_presencias(con, g, "Ibarra", "Ibarra")
    _usar(con, g, "Reyes")
    assert "conocimiento_no_adquirido" in _puerta_3(con, g)[0]


def test_una_presencia_de_alguien_fuera_del_canon_se_descarta_con_su_motivo() -> None:
    con, _ = nueva_bd()
    g = fabrica.novela_minima(con)
    descartes = _extraer_presencias(con, g, "Nadie Conocido")
    assert contar(con, "SELECT COUNT(*) FROM presencia_escena") == 0
    assert descartes.recuento["presencias"] == {"personaje_sin_resolver": 1}


#: La regla de RF3-PAS-09, entera: dos frases sueltas sobrevivian a invertirla (validador de
#: 88d5814).
REGLA_DE_LA_PRESENCIA = (
    "**Presencias**: quién está **físicamente** en cada escena, aunque la escaleta no lo "
    "pusiera. Registra a todo personaje del canon que la prosa muestra allí: el que habla, el "
    "que actúa, el que está callado al fondo. Nombrar o recordar a alguien no es estar, y "
    "tampoco oírlo por un canal o verlo en una pantalla desde otro sitio. Con esto se sabe "
    "quién oyó lo que se dijo en la escena: si alguien estaba y no lo registras, más adelante "
    "parecerá que usa lo que nunca recibió; si lo registras sin estar, parecerá que lo recibió."
)


def test_la_skill_pide_las_presencias() -> None:
    from compartido.puerto.terminal import PuertoTerminal
    from config import raiz_repo

    skill = PuertoTerminal(skills_dir=raiz_repo() / ".claude" / "skills").ruta_skill(
        "extraccion").read_text(encoding="utf-8")
    # La seccion entera, hasta la siguiente: un parrafo anadido que la contradiga tambien falla.
    seccion = "**Presencias**" + skill.split("**Presencias**")[1].split("**Estados de objeto**")[0]
    assert seccion.strip() == REGLA_DE_LA_PRESENCIA
    # La descripcion de la skill dice que tambien produce presencias.
    assert "presencias" in skill.split("---")[1]


def test_el_extractor_recibe_a_los_personajes_fuera_del_reparto() -> None:
    """Validador de 88d5814: solo le llegaba el reparto, y el personaje que el redactor mete
    por su cuenta tenia que ir a entidades no reconocidas."""
    import config
    from compartido.contexto import Presupuesto

    con, _ = nueva_bd()
    g = fabrica.novela_minima(con)
    paquete = s_extraccion.paquete(
        con, g.novela_id, 2, {1: "texto", 2: "texto"}, presupuesto=Presupuesto(
            bloques=config.PRESUPUESTO_BLOQUES, techo=config.PRESUPUESTO_PAQUETE),
    )
    # Obligatoria, como el resto del inventario: un recorte no puede quitarla.
    canon = next(b for b in paquete.bloques if b.nombre == "canon")
    assert any(e.obligatorio for e in canon.elementos if e.texto.startswith("Otros personajes"))
    render = paquete.render()
    linea = next(x for x in render.splitlines() if x.startswith("Otros personajes"))
    assert linea.endswith(": Reyes")
    reparto = next(x for x in render.splitlines() if x.startswith("Personajes: "))
    assert "Reyes" not in reparto


def test_las_presencias_recorren_el_pipeline_hasta_la_traza() -> None:
    def extraccion(entrada: str, agente: str) -> dict[str, Any]:
        salida = demo.extraccion(entrada, agente)
        if demo._capitulo(entrada) == 2:
            salida["presencias"] = [
                {"escena_orden": 1, "personaje_ref": "Reyes"},
                {"escena_orden": 9, "personaje_ref": "Reyes"},
                {"escena_orden": 1, "personaje_ref": "Nadie Conocido"},
            ]
        return salida

    con, ruta = nueva_bd()
    novela_id = crear_novela(con)
    puerto = puerto_falso(con)
    puerto.registrar("extraccion", extraccion)
    assert pipeline.avanzar(contexto(con, puerto, ruta, novela_id)) == "completada"
    assert contar(con, """
        SELECT COUNT(*) FROM presencia_escena pr
        JOIN personaje p ON p.id = pr.personaje_id
        JOIN escena_ordinal eo ON eo.escena_id = pr.escena_id
        WHERE p.nombre = 'Reyes' AND eo.capitulo_numero = 2""") == 1
    recuentos = [json.loads(f[0])["recuento"] for f in con.execute(
        "SELECT payload FROM traza_evento WHERE tipo = 'extraccion_descartes' "
        "AND json_extract(payload, '$.capitulo') = 2"
    )]
    assert recuentos[-1]["presencias"] == {"escena_desconocida": 1, "personaje_sin_resolver": 1}


# --- RF3-PAS-10: la ficha para el redactor -------------------------------------------------------


def _con_reyes_visto_en_el_capitulo_1() -> tuple[sqlite3.Connection, fabrica.Grafo]:
    """Reyes no esta en ningun reparto, pero el extractor lo constato en la escena 1.1."""
    con, _ = nueva_bd()
    g = fabrica.novela_minima(con)
    con.execute("INSERT INTO presencia_escena (novela_id, escena_id, personaje_id) "
                "VALUES (?,?,?)", (g.novela_id, g.escenas[(1, 1)], g.personajes["Reyes"]))
    return con, g


def test_el_redactor_conoce_a_quien_ya_salio_fuera_del_reparto() -> None:
    import config
    from compartido.contexto import Presupuesto
    from compartido.grafo import lectura
    from tareas.redaccion import servicio as s_redaccion

    con, g = _con_reyes_visto_en_el_capitulo_1()
    assert [p["nombre"] for p in lectura.personajes_fuera_del_reparto(con, g.novela_id, 2)] \
        == ["Reyes"]
    # En el capitulo 1 todavia no habia salido antes.
    assert lectura.personajes_fuera_del_reparto(con, g.novela_id, 1) == []
    paquete = s_redaccion.paquete(con, g.novela_id, 2, presupuesto=Presupuesto(
        bloques=config.PRESUPUESTO_BLOQUES, techo=config.PRESUPUESTO_PAQUETE))
    canon = next(b for b in paquete.bloques if b.nombre == "canon")
    otros = [e for e in canon.elementos if e.seccion.startswith("### Otros personajes")]
    assert [e.texto.split("**")[1] for e in otros] == ["Reyes"]
    # Opcional: se recorta antes que el reparto.
    assert not any(e.obligatorio for e in otros)
    # Del mas reciente al mas antiguo: el recorte empieza por quien salio hace mas. El
    # capitulo 3 no tiene reparto, asi que todos estan fuera de el.
    assert [p["nombre"] for p in lectura.personajes_fuera_del_reparto(con, g.novela_id, 3)] \
        == ["Ibarra", "Kowalski", "Reyes"]


def test_el_redactor_recibe_los_hechos_de_objetos_facciones_y_de_quien_ya_salio() -> None:
    from compartido.grafo import lectura

    con, g = _con_reyes_visto_en_el_capitulo_1()
    faccion = con.execute(
        "INSERT INTO faccion (novela_id, nombre, nombre_clave, proposito) "
        "VALUES (?, 'Turno', 'turno', 'Operar la estacion')", (g.novela_id,)).lastrowid
    con.execute("UPDATE personaje SET faccion_id = ? WHERE id = ?",
                (faccion, g.personajes["Kowalski"]))
    con.execute("INSERT INTO escena_objeto (escena_id, objeto_id) VALUES (?,?)",
                (g.escenas[(2, 1)], g.objetos["Baliza"]))
    # Un objeto que este capitulo no toca no entra, aunque saliera en otro.
    llave = con.execute("INSERT INTO objeto (novela_id, nombre, nombre_clave, funcion_narrativa) "
                        "VALUES (?, 'Llave', 'llave', 'Abre')", (g.novela_id,)).lastrowid
    con.execute("INSERT INTO escena_objeto (escena_id, objeto_id) VALUES (?,?)",
                (g.escenas[(1, 1)], llave))
    # Ni la faccion de quien no esta en el reparto.
    fuera = con.execute(
        "INSERT INTO faccion (novela_id, nombre, nombre_clave, proposito) "
        "VALUES (?, 'Fuera', 'fuera', 'Reparar')", (g.novela_id,)).lastrowid
    con.execute("UPDATE personaje SET faccion_id = ? WHERE id = ?",
                (fuera, g.personajes["Reyes"]))
    for tipo, sujeto_id, sujeto, atributo, valor in (
        ("personaje", g.personajes["Reyes"], "Reyes", "voz", "grave"),
        ("objeto", g.objetos["Baliza"], "Baliza", "bateria", "doce horas"),
        ("faccion", faccion, "Turno", "personas", "cinco"),
        ("objeto", llave, "Llave", "color", "roja"),
        ("faccion", fuera, "Fuera", "personas", "seis"),
    ):
        insertar_hecho(
            con, novela_id=g.novela_id, escena_id=g.escenas[(1, 1)], sujeto_tipo=tipo,
            sujeto_id=sujeto_id, sujeto_nombre=sujeto, atributo=atributo, valor=valor,
            categoria="otro", cita=None, supersede_a=None,
        )

    hechos = {(h["sujeto_nombre"], h["atributo"]): h["obligatorio"]
              for h in lectura.hechos_del_reparto(con, g.novela_id, 2)}
    assert hechos[("Reyes", "voz")] == 0
    assert hechos[("Baliza", "bateria")] == 0
    assert hechos[("Turno", "personas")] == 0
    assert ("Llave", "color") not in hechos
    assert ("Fuera", "personas") not in hechos


def test_los_hechos_de_mundo_se_recortan_los_ultimos() -> None:
    """Mezclados por recencia, los detalles de quien no esta en el reparto sacaban del paquete
    el censo del capitulo 1, que es lo que necesita la regla de las cuentas (validador de
    e810d8f)."""
    from compartido.grafo import lectura

    con, g = _con_reyes_visto_en_el_capitulo_1()
    con.execute("INSERT INTO escena_objeto (escena_id, objeto_id) VALUES (?,?)",
                (g.escenas[(2, 1)], g.objetos["Baliza"]))
    for escena, tipo, sujeto_id, sujeto, atributo in (
        ((1, 1), "mundo", None, "Estacion", "personas a bordo"),
        ((1, 2), "objeto", g.objetos["Baliza"], "Baliza", "bateria"),
        ((1, 2), "personaje", g.personajes["Reyes"], "Reyes", "voz"),
    ):
        insertar_hecho(
            con, novela_id=g.novela_id, escena_id=g.escenas[escena], sujeto_tipo=tipo,
            sujeto_id=sujeto_id, sujeto_nombre=sujeto, atributo=atributo, valor="once",
            categoria="otro", cita=None, supersede_a=None,
        )
    opcionales = [h["sujeto_nombre"] for h in lectura.hechos_del_reparto(con, g.novela_id, 2)
                  if not h["obligatorio"]]
    # El recorte quita desde el final: el mundo, aunque sea el mas antiguo, es lo ultimo.
    assert opcionales == ["Estacion", "Baliza", "Reyes"]


#: Las dos reglas de RF3-PAS-10 en la skill del redactor, enteras.
REGLAS_DEL_REDACTOR = (
    "- **No descuadras una cuenta.** Si alguien cuenta personas, horas, plazos o raciones, la "
    "cuenta sale de los hechos establecidos y cuadra con ellos: si a bordo son once, cinco del "
    "turno y seis de fuera, nadie dice «los siete de fuera»; si el carguero llega en treinta y "
    "una horas, nadie pide algo con cuarenta de antelación. Antes de escribir una cifra que se "
    "deriva de otras, haz la cuenta.\n"
    "- **No traes a nadie de fuera de la escaleta sin su ficha.** Si una escena necesita a "
    "alguien que la escaleta no puso, que sea uno de los otros personajes que ya han salido, "
    "como dicen su ficha y sus hechos, y no otro. Quien está en una escena oye lo que se dice "
    "en ella. Lo que sabía de antes no viene en tu paquete: en la escena actúa sobre lo que oye "
    "allí."
)


def test_la_skill_del_redactor_lleva_las_reglas_de_la_cuenta_y_de_la_ficha() -> None:
    from compartido.puerto.terminal import PuertoTerminal
    from config import raiz_repo

    skill = PuertoTerminal(skills_dir=raiz_repo() / ".claude" / "skills").ruta_skill(
        "redaccion").read_text(encoding="utf-8")
    assert REGLAS_DEL_REDACTOR in skill
    assert skill.count("No descuadras una cuenta") == 1


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


# --- RF3-PAS-12: el juez de oficio comprueba las cuentas -----------------------------------------


@pytest.mark.parametrize(("valor", "cifra"), [
    ("once: cinco del turno y seis fuera", True),
    ("llega en 31 horas", True),
    ("cuarenta de antelacion", True),
    # «un», «una» y «medio» tambien son articulos o adjetivos.
    ("una mancha oscura en el casco", False),
    ("medio sumergido en el hielo", False),
    ("grises", False),
    # Validador de a65c01d: cantidades que tambien sirven para las cuentas.
    ("llega en 31h", True),
    ("una docena de bombonas", True),
    ("la mitad de la cuadrilla", True),
    ("en menos de un minuto", True),
    ("una hora de aire", True),
    ("a la par del casco", False),
])
def test_un_hecho_da_una_cantidad(valor: str, cifra: bool) -> None:
    from compartido.texto import tiene_cifra

    assert tiene_cifra(valor) is cifra


def test_el_juez_recibe_los_hechos_con_cifras() -> None:
    import config
    from compartido.contexto import Presupuesto
    from tareas.oficio import servicio as s_oficio

    con, _ = nueva_bd()
    g = fabrica.novela_minima(con)
    ids: dict[str, int] = {}
    for escena, tipo, sujeto_id, sujeto, atributo, valor in (
        ((1, 1), "mundo", None, "Estacion", "personas a bordo", "once: cinco y seis"),
        ((1, 1), "personaje", g.personajes["Kowalski"], "Kowalski", "raciones", "doce"),
        ((1, 2), "personaje", g.personajes["Kowalski"], "Kowalski", "turnos", "tres"),
        ((2, 1), "personaje", g.personajes["Reyes"], "Reyes", "horas sin dormir", "treinta"),
        ((1, 2), "personaje", g.personajes["Reyes"], "Reyes", "voz", "grave"),
    ):
        ids[atributo] = insertar_hecho(
            con, novela_id=g.novela_id, escena_id=g.escenas[escena], sujeto_tipo=tipo,
            sujeto_id=sujeto_id, sujeto_nombre=sujeto, atributo=atributo, valor=valor,
            categoria="otro", cita=None, supersede_a=None,
        )
    # Una cifra sustituida ya no es canon: con ella el juez daria un `falla` falso.
    insertar_hecho(
        con, novela_id=g.novela_id, escena_id=g.escenas[(1, 2)], sujeto_tipo="personaje",
        sujeto_id=g.personajes["Kowalski"], sujeto_nombre="Kowalski", atributo="raciones",
        valor="ninguna", categoria="otro", cita=None, supersede_a=ids["raciones"],
    )
    paquete = s_oficio.paquete(con, g.novela_id, 2, "La prosa.", presupuesto=Presupuesto(
        bloques=config.PRESUPUESTO_BLOQUES, techo=config.PRESUPUESTO_PAQUETE))
    hechos = next(b for b in paquete.bloques if b.nombre == "hechos")
    lineas = [e.texto for e in hechos.elementos if not e.obligatorio]
    # El mundo primero y despues del mas reciente al mas antiguo, que es lo que decide que
    # sobrevive al recorte; los del propio capitulo tambien, porque la cuenta puede descuadrar
    # dentro de el; sin cifra o sustituidos, fuera.
    assert lineas == ["- Estacion · personas a bordo: once: cinco y seis (cap. 1)",
                      "- Reyes · horas sin dormir: treinta (cap. 2)",
                      "- Kowalski · turnos: tres (cap. 1)"]
    render = paquete.render()
    assert "HECHOS ESTABLECIDOS CON CIFRAS" in render
    assert "cuentas_cuadran" in render
    # En el capitulo 1 todavia no hay nada del 2.
    paquete_1 = s_oficio.paquete(con, g.novela_id, 1, "La prosa.", presupuesto=Presupuesto(
        bloques=config.PRESUPUESTO_BLOQUES, techo=config.PRESUPUESTO_PAQUETE))
    assert "horas sin dormir" not in paquete_1.render()


def test_el_veredicto_exige_las_cuentas() -> None:
    from pydantic import ValidationError

    from tareas.oficio.esquemas import SalidaOficio

    salida = demo.oficio("", "oficio")
    # Nueve veredictos, con uno repetido en lugar del de las cuentas.
    otros = [v for v in salida["veredictos"] if v["criterio"] != "cuentas_cuadran"]
    salida["veredictos"] = [*otros, otros[0]]
    with pytest.raises(ValidationError, match="cuentas_cuadran"):
        SalidaOficio.model_validate(salida)


#: El criterio de RF3-PAS-12 en la skill del juez, entero.
CRITERIO_DE_LAS_CUENTAS = (
    "**`cuentas_cuadran`** — Toda cifra de la prosa que se deriva de otras cuadra con ellas: "
    "personas, horas, plazos, distancias, raciones. Haz cada cuenta. Cuadra con los hechos "
    "establecidos que te llegan («once a bordo: cinco del turno y seis de fuera» no admite «los "
    "siete de fuera»; un carguero que llega en treinta y una horas no admite un aviso con "
    "cuarenta de antelación) y cuadra dentro del capítulo (si eran diez y embarcan cuatro, "
    "quedan seis, no siete). Una cifra equivocada solo pasa si la propia escena la marca como "
    "error del personaje: otro lo corrige, él mismo rectifica o el narrador lo señala. Que el "
    "personaje pudiera mentir o redondear no basta si nada en el texto lo dice; en la duda, "
    "falla. La evidencia es la cita de la prosa; la sugerencia nombra el hecho o la cifra con "
    "la que no cuadra."
)


def test_la_skill_del_juez_lleva_el_criterio_de_las_cuentas() -> None:
    from compartido.puerto.terminal import PuertoTerminal
    from config import CRITERIOS_OFICIO, raiz_repo

    skill = PuertoTerminal(skills_dir=raiz_repo() / ".claude" / "skills").ruta_skill(
        "oficio").read_text(encoding="utf-8")
    assert CRITERIO_DE_LAS_CUENTAS in skill
    # Cada criterio de la lista cerrada tiene su parrafo, y la skill no dice otro numero.
    for criterio in CRITERIOS_OFICIO:
        assert f"**`{criterio}`**" in skill, criterio
    assert "ocho" not in skill
    # Ya no le dice que no busque ninguna contradiccion.
    assert "No buscas contradicciones:" not in skill


def test_un_fallo_de_las_cuentas_vuelve_al_redactor_con_la_evidencia() -> None:
    con, ruta = nueva_bd()
    novela_id = crear_novela(con)
    puerto = puerto_falso(con)
    veces = {"n": 0}

    def juez(entrada: str, agente: str) -> dict[str, Any]:
        salida = demo.oficio(entrada, agente)
        veces["n"] += 1
        if veces["n"] <= config.OFICIO_MUESTRAS:  # las muestras del primer intento
            salida["veredictos"] = [
                v if v["criterio"] != "cuentas_cuadran" else {
                    "criterio": "cuentas_cuadran", "veredicto": "falla",
                    "evidencia": "los siete de fuera",
                    "sugerencia": "A bordo son once: cinco del turno y seis de fuera.",
                }
                for v in salida["veredictos"]
            ]
        return salida

    puerto.registrar("oficio", juez)
    assert pipeline.avanzar(contexto(con, puerto, ruta, novela_id)) == "completada"
    oficio = [i["entrada"] for i in puerto.invocaciones if i["agente"] == "oficio"]
    assert "HECHOS ESTABLECIDOS CON CIFRAS" in oficio[0]
    redacciones = [i["entrada"] for i in puerto.invocaciones
                   if i["agente"] == "redaccion" and demo._capitulo(i["entrada"]) == 1]
    assert len(redacciones) == 2
    assert "los siete de fuera" in redacciones[1]
    assert "cuentas_cuadran" in redacciones[1]
