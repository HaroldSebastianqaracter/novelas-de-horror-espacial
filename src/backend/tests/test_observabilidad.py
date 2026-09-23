"""Observabilidad con Langfuse (specs/spec3.md, 3.4: RF3-OBS-01 a RF3-OBS-10).

Ningun test sale a la red: el exportador recibe un cliente que guarda los eventos, y el cliente
HTTP se prueba con un transporte simulado de httpx. Lo que se comprueba es lo que el primer
harness no garantizaba: que el coste es el del puerto, que los identificadores no chocan ni se
duplican, que un fallo de Langfuse no toca el pipeline, y ademas que los nombres del encargo no
salen de la maquina.
"""

from __future__ import annotations

import json
import re
import sqlite3
import tempfile
from pathlib import Path
from typing import Any

import httpx
import pytest

import config
from compartido.grafo import insertar
from orquestador import observabilidad as obs
from orquestador import pipeline
from tests.entorno import contar, contexto, crear_novela, nueva_bd, puerto_falso
from tests.test_personalizacion import crear


class ClienteFalso:
    """Guarda lo que se enviaria. `fallar` hace que el siguiente envio lance."""

    def __init__(self) -> None:
        self.eventos: list[dict[str, Any]] = []
        self.prompts: dict[tuple[str, str], int] = {}
        self.creados: list[tuple[str, str]] = []
        self.fallar = False

    def enviar(self, eventos: list[dict[str, Any]]) -> None:
        if self.fallar:
            raise obs.ErrorLangfuse("Langfuse caido")
        self.eventos.extend(eventos)

    def version_de_prompt(self, nombre: str, etiqueta: str) -> int | None:
        return self.prompts.get((nombre, etiqueta))

    def crear_prompt(self, nombre: str, texto: str, etiqueta: str) -> int:
        version = 1 + sum(1 for n, _ in self.prompts if n == nombre)
        self.prompts[(nombre, etiqueta)] = version
        self.creados.append((nombre, etiqueta))
        return version

    def comprobar(self) -> None:
        return None

    def de_tipo(self, tipo: str) -> list[dict[str, Any]]:
        return [e["body"] for e in self.eventos if e["type"] == tipo]


def _novela_con_langfuse(
    cliente: ClienteFalso, *, con_brief: bool = False
) -> tuple[sqlite3.Connection, int, str]:
    con, ruta = nueva_bd()
    novela_id = crear(con, ruta, capitulos=3) if con_brief else crear_novela(con)
    ctx = contexto(con, puerto_falso(con), ruta, novela_id)
    ctx.exportador = obs.Exportador(cliente)
    final = pipeline.avanzar(ctx)
    return con, novela_id, final


@pytest.fixture(scope="module")
def con_brief() -> tuple[sqlite3.Connection, int, ClienteFalso]:
    cliente = ClienteFalso()
    con, novela_id, final = _novela_con_langfuse(cliente, con_brief=True)
    assert final in ("completada", "completada_con_avisos")
    return con, novela_id, cliente


# --- RF3-OBS-01 y RF3-OBS-02: configuracion ------------------------------------------------------


def test_sin_claves_no_hay_exportador() -> None:
    _, ruta = nueva_bd()
    from tests.entorno import cfg_de

    cfg = cfg_de(ruta)
    assert not cfg.langfuse_activo and obs.exportador_desde(cfg) is None
    claves = {"langfuse_public_key": "pk", "langfuse_secret_key": "sk"}
    assert cfg_de(ruta, **claves).langfuse_activo
    # Validador: con el puerto falso (demos y tests) no se exporta aunque haya claves.
    assert obs.exportador_desde(cfg_de(ruta, puerto="falso", **claves)) is None
    assert obs.exportador_desde(cfg_de(ruta, puerto="terminal", **claves)) is not None


def test_el_env_se_carga_sin_pisar_el_entorno(monkeypatch: pytest.MonkeyPatch) -> None:
    fichero = Path(tempfile.mkdtemp()) / ".env"
    fichero.write_text(
        "# comentario\nLANGFUSE_PUBLIC_KEY=\"pk-desde-fichero\"\n\nNOVELAS_PUERTO=falso\n"
        "LANGFUSE_HOST=https://otro.example\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.setenv("LANGFUSE_HOST", "https://ya-fijado.example")
    monkeypatch.delenv("NOVELAS_PUERTO", raising=False)
    config.cargar_dotenv(fichero)
    import os

    assert os.environ["LANGFUSE_PUBLIC_KEY"] == "pk-desde-fichero"
    assert os.environ["LANGFUSE_HOST"] == "https://ya-fijado.example"
    assert os.environ["NOVELAS_PUERTO"] == "falso"


# --- RF3-OBS-03 a RF3-OBS-06: que se envia ------------------------------------------------------


def test_una_generacion_por_llamada_y_una_sesion_por_novela(
    con_brief: tuple[sqlite3.Connection, int, ClienteFalso],
) -> None:
    con, novela_id, cliente = con_brief
    llamadas = contar(con, "SELECT COUNT(*) FROM llamada_modelo WHERE novela_id = ?", novela_id)
    generaciones = cliente.de_tipo("generation-create")
    assert len([g for g in generaciones if g["name"] != "entrevistador"]) == llamadas
    trazas = cliente.de_tipo("trace-create")
    assert {t["sessionId"] for t in trazas} == {
        obs.sesion_de(obs.clave_de_novela(con, novela_id))
    }
    assert {"planificacion", "capitulo-1", "capitulo-2", "capitulo-3", "cierre"} <= {
        t["name"] for t in trazas
    }
    roles = {g["name"]: g["metadata"]["rol"] for g in generaciones}
    assert roles["redaccion"] == "writer" and roles["arquitecto"] == "planner"
    assert roles["oficio"] == "editor"


def test_los_identificadores_no_se_repiten_y_son_deterministas(
    con_brief: tuple[sqlite3.Connection, int, ClienteFalso],
) -> None:
    _, novela_id, cliente = con_brief
    ids = [e["body"]["id"] for e in cliente.eventos if e["type"] != "trace-create"]
    assert len(ids) == len(set(ids))
    assert obs.id_estable(novela_id, "llamada_modelo", 1) == obs.id_estable(
        novela_id, "llamada_modelo", 1
    )
    assert obs.id_estable(1, "llamada_modelo", 1) != obs.id_estable(2, "llamada_modelo", 1)


def test_la_novela_1_de_dos_bases_no_comparte_identificadores() -> None:
    """Validador: con el id solo, `novela.db` y `novela_real.db` se pisaban en Langfuse (la
    colision del primer harness, commit b87775d)."""
    import time

    ids: list[set[str]] = []
    sesiones: list[str] = []
    for _ in range(2):
        con, ruta = nueva_bd()
        novela_id = crear_novela(con)
        insertar(con, "llamada_modelo", novela_id=novela_id, agente="redaccion", capitulo=1,
                 sistema="s", entrada="p", estado="ok", metadatos="{}", salida_cruda="{}")
        cliente = ClienteFalso()
        obs.Exportador(cliente).exportar(con, novela_id)
        ids.append({e["body"]["id"] for e in cliente.eventos})
        sesiones.append(cliente.de_tipo("trace-create")[0]["sessionId"])
        time.sleep(1.1)  # `datetime('now')` tiene resolucion de segundo
    assert not ids[0] & ids[1]
    assert sesiones[0] != sesiones[1]


def test_la_fecha_de_una_traza_no_cambia_al_reenviarla() -> None:
    con, _ = nueva_bd()
    novela_id = crear_novela(con)

    def llamada() -> None:
        insertar(con, "llamada_modelo", novela_id=novela_id, agente="redaccion", capitulo=1,
                 sistema="s", entrada="p", estado="ok", metadatos="{}", salida_cruda="{}")

    llamada()
    con.execute("UPDATE llamada_modelo SET creado_en = '2026-09-23 10:00:00'")
    exportador = obs.Exportador(ClienteFalso())
    primero = ClienteFalso()
    exportador.cliente = primero
    exportador.exportar(con, novela_id)
    llamada()
    segundo = ClienteFalso()
    exportador.cliente = segundo
    exportador.exportar(con, novela_id)
    fechas = {t["timestamp"] for c in (primero, segundo) for t in c.de_tipo("trace-create")}
    assert fechas == {"2026-09-23T10:00:00Z"}
    # El sobre lleva un id nuevo en cada envio; el cuerpo, el mismo.
    assert primero.eventos[0]["id"] != segundo.eventos[0]["id"]
    assert primero.eventos[0]["body"]["id"] == segundo.eventos[0]["body"]["id"]


def test_las_puertas_llegan_como_spans_y_scores(
    con_brief: tuple[sqlite3.Connection, int, ClienteFalso],
) -> None:
    con, novela_id, cliente = con_brief
    evaluaciones = contar(con, "SELECT COUNT(*) FROM resultado_puerta WHERE novela_id = ?",
                          novela_id)
    assert len(cliente.de_tipo("span-create")) == evaluaciones
    nombres = {s["name"] for s in cliente.de_tipo("score-create")}
    assert {"puerta_1", "puerta_2", "puerta_3", "puerta_4", "puerta_5",
            "puerta_3_bloqueantes", "puerta_3_avisos"} <= nombres
    # La demo repite en el capitulo 2 algo que un personaje ya sabia: la comprobacion que avisa
    # llega como su propio score, a 0.
    sorpresas = [s for s in cliente.de_tipo("score-create") if s["name"] == "sorpresa_imposible"]
    assert sorpresas and all(s["value"] == 0.0 for s in sorpresas)


def test_los_terminos_vetados_llegan_con_sus_hallazgos() -> None:
    """spec3, RF3-GRD-04: el registro del guardrail llega a Langfuse, no solo el score."""
    from compartido.puerta_base import Conflicto, ResultadoPuerta

    con, _ = nueva_bd()
    novela_id = crear_novela(con)
    hallazgo = {"termino": "tortura", "origen": "global", "forma": "tortura",
                "fragmento": "marcas de tortura en", "inicio": 10, "fin": 17}
    ResultadoPuerta(puerta=4, conflictos=[Conflicto(
        comprobacion="termino_vetado", capitulo=1, descripcion="Terminos vetados.",
        datos={"politica": "abc", "hallazgos": [hallazgo]},
    )]).registrar(con, novela_id, capitulo=1, intento=1)
    cliente = ClienteFalso()
    obs.Exportador(cliente).exportar(con, novela_id)
    [span] = cliente.de_tipo("span-create")
    [conflicto] = span["metadata"]["conflictos"]
    assert conflicto["politica"] == {"politica": "abc", "hallazgos": [hallazgo]}


def test_el_coste_es_el_del_puerto_y_nunca_parece_gratis() -> None:
    con, _ = nueva_bd()
    novela_id = crear_novela(con)

    def llamada(metadatos: dict[str, Any]) -> None:
        insertar(con, "llamada_modelo", novela_id=novela_id, agente="redaccion", capitulo=1,
                 sistema="skill", entrada="paquete", estado="ok",
                 metadatos=json.dumps(metadatos), salida_cruda="{}")

    llamada({"total_cost_usd": 0.61, "num_turns": 2,
             "modelUsage": {"claude-opus-5": {"costUSD": 0.61}}})
    llamada({"num_turns": 2})
    llamada({"puerto": "falso"})
    cliente = ClienteFalso()
    obs.Exportador(cliente).exportar(con, novela_id)
    real, sin_coste, falso = cliente.de_tipo("generation-create")
    assert real["costDetails"] == {"total": 0.61} and real["model"] == "claude-opus-5"
    assert real["level"] == "DEFAULT" and real["metadata"]["num_turns"] == 2
    assert sin_coste["level"] == "WARNING" and sin_coste["metadata"]["coste_desconocido"]
    assert "costDetails" not in sin_coste
    assert falso["costDetails"] == {"total": 0.0} and falso["level"] == "DEFAULT"


def test_cada_skill_es_un_prompt_versionado_por_su_huella() -> None:
    con, _ = nueva_bd()
    novela_id = crear_novela(con)
    for sistema in ("skill v1", "skill v1", "skill v2"):
        insertar(con, "llamada_modelo", novela_id=novela_id, agente="extraccion", capitulo=1,
                 sistema=sistema, entrada="p", estado="ok", metadatos="{}", salida_cruda="{}")
    cliente = ClienteFalso()
    obs.Exportador(cliente).exportar(con, novela_id)
    assert len(cliente.creados) == 2
    versiones = [g["promptVersion"] for g in cliente.de_tipo("generation-create")]
    assert versiones == [1, 1, 2]
    assert {g["promptName"] for g in cliente.de_tipo("generation-create")} == {
        "storymaker-extraccion"
    }


# --- RF3-OBS-07: seudonimizacion -----------------------------------------------------------------


def test_ningun_nombre_del_encargo_sale_de_la_maquina(
    con_brief: tuple[sqlite3.Connection, int, ClienteFalso],
) -> None:
    _, _, cliente = con_brief
    enviado = json.dumps(cliente.eventos, ensure_ascii=False)
    for nombre in ("Marta", "Ibáñez", "Ibanez", "Nala", "Andrés", "Andres"):
        assert not re.search(rf"(?<!\w){nombre}(?!\w)", enviado, re.IGNORECASE), nombre
    assert "[DESTINATARIO]" in enviado and "[ALLEGADO_1]" in enviado


def test_el_seudonimizador_cubre_partes_tildes_y_mayusculas() -> None:
    from compartido.brief import Brief
    from tests.test_brief import brief_ejemplo

    s = obs.Seudonimizador(Brief.model_validate(brief_ejemplo()))
    texto = "MARTA Ibanez habla con Andres; ibáñez mira a Nala. Martajena no es nadie."
    assert s.texto(texto) == (
        "[DESTINATARIO] habla con [QUIEN_REGALA]; [DESTINATARIO] mira a [ALLEGADO_1]. "
        "Martajena no es nadie."
    )
    assert obs.Seudonimizador(None).texto("Marta") == "Marta"


def _brief_con(**nombres: Any) -> Any:
    from compartido.brief import Brief
    from tests.test_brief import brief_ejemplo

    datos = brief_ejemplo()
    datos["destinatario"] = {**datos["destinatario"], "nombre": nombres["destinatario"]}
    datos["quien_regala"] = nombres["regala"]
    datos["allegados"] = [{**datos["allegados"][0], "nombre": nombres["allegado"]}]
    return Brief.model_validate(datos)


def test_un_brief_sin_tildes_cubre_la_prosa_con_tildes() -> None:
    """Validador: las variantes solo quitaban tildes; «Ramon» en el brief dejaba pasar «Ramón»."""
    s = obs.Seudonimizador(_brief_con(destinatario="Ramon Pinto", regala="Jose Luis",
                                      allegado="Ines"))
    assert s.texto("Ramón llamó a José y a Inés.") == (
        "[DESTINATARIO] llamó a [QUIEN_REGALA] y a [ALLEGADO_1]."
    )


def test_las_claves_de_un_diccionario_tambien_se_seudonimizan() -> None:
    """Validador: `nivel_confianza` va por personaje, con nombres como claves."""
    s = obs.Seudonimizador(_brief_con(destinatario="Ramon Pinto", regala="Jose Luis",
                                      allegado="Ines"))
    salida = s.valor({"nivel_confianza": {"Ramón": "alta", "Inés": "baja", "Vaan": "media"}})
    assert salida == {"nivel_confianza": {
        "[DESTINATARIO]": "alta", "[ALLEGADO_1]": "baja", "Vaan": "media",
    }}


def test_las_particulas_de_un_nombre_compuesto_no_se_sustituyen_sueltas() -> None:
    s = obs.Seudonimizador(_brief_con(destinatario="Maria de los Angeles Soto",
                                      regala="Luis", allegado="Kiko"))
    assert s.texto("Todos los tripulantes miraron a Ángeles.") == (
        "Todos los tripulantes miraron a [DESTINATARIO]."
    )


def test_texto_descompuesto_y_apostrofos_tipograficos() -> None:
    import unicodedata

    s = obs.Seudonimizador(_brief_con(destinatario="Zoe O'Hara", regala="Luis", allegado="Kiko"))
    assert s.texto(unicodedata.normalize("NFD", "Zoé ríe.")) == "[DESTINATARIO] ríe."
    assert s.texto("La señora O’Hara llega.") == "La señora [DESTINATARIO] llega."


@pytest.mark.parametrize(("destinatario", "prosa", "esperado"), [
    # Validador (segundo rechazo): marcas que no son las del castellano, en los dos sentidos.
    # Algunos casos ya pasaban antes y quedan como guarda de regresion.
    ("João Prado", "Joao entra.", "[DESTINATARIO] entra."),
    ("Joao Prado", "João entra.", "[DESTINATARIO] entra."),
    ("Antonin Dvořák", "Dvorak entra.", "[DESTINATARIO] entra."),
    ("Ångel Ruiz", "Angel entra.", "[DESTINATARIO] entra."),
    ("Nguyễn Thi", "Nguyen entra.", "[DESTINATARIO] entra."),
    ("Ştefan Pop", "Ștefan entra.", "[DESTINATARIO] entra."),
    ("Łukasz Nowak", "Lukasz entra.", "[DESTINATARIO] entra."),
    ("Lukasz Nowak", "Łukasz entra.", "[DESTINATARIO] entra."),
    # Un digito o un guion bajo no hacen de un nombre otra palabra.
    ("Marta Ibáñez", "marta_ibanez entra.", "[DESTINATARIO]_[DESTINATARIO] entra."),
    ("Marta Ibáñez", "Marta2 entra.", "[DESTINATARIO]2 entra."),
    # Partes pegadas a un apostrofo, y el apellido entero con su apostrofo.
    ("Lia D'Angelo", "Angelo entra.", "[DESTINATARIO] entra."),
    ("Lia D'Angelo", "D’Angelo entra.", "[DESTINATARIO] entra."),
    ("Sean O'Brien", "Brien entra.", "[DESTINATARIO] entra."),
    # Caracteres que no se ven partiendo el nombre.
    ("Marta Ibáñez", "Mar­ta entra.", "[DESTINATARIO] entra."),
    ("Marta Ibáñez", "Mar​ta entra.", "[DESTINATARIO] entra."),
])
def test_el_nombre_no_se_escapa_por_marcas_fronteras_ni_invisibles(
    destinatario: str, prosa: str, esperado: str
) -> None:
    s = obs.Seudonimizador(_brief_con(destinatario=destinatario, regala="Luis", allegado="Kiko"))
    assert s.texto(prosa) == esperado


@pytest.mark.parametrize(("regala", "prosa", "esperado"), [
    # Validador (tercer rechazo): la firma de quien regala es texto libre, con puntuacion.
    ("Andrés, tu hermano", "Con cariño de Andrés.", "Con cariño de [QUIEN_REGALA]."),
    ("Tus padres (Lucía y Andrés)", "Lucía y Andrés te quieren.",
     "[QUIEN_REGALA] y [QUIEN_REGALA] te quieren."),
    ("Andrés/Lucía", "Andrés llega.", "[QUIEN_REGALA] llega."),
    ("Andrés.", "Andrés llega.", "[QUIEN_REGALA] llega."),
    ("Ana‐Belén Soto", "Belén llega.", "[QUIEN_REGALA] llega."),
    ("Ana–Belén Soto", "Belén llega.", "[QUIEN_REGALA] llega."),
])
def test_el_nombre_del_brief_se_trocea_por_cualquier_puntuacion(
    regala: str, prosa: str, esperado: str
) -> None:
    s = obs.Seudonimizador(_brief_con(destinatario="Marta Ibáñez", regala=regala,
                                      allegado="Kiko"))
    assert s.texto(prosa) == esperado


def test_lo_que_acompana_a_la_firma_no_se_sustituye_suelto() -> None:
    s = obs.Seudonimizador(_brief_con(destinatario="Marta Ibáñez", regala="Andrés, tu hermano",
                                      allegado="Kiko"))
    assert s.texto("Tu hermano Andrés.") == "Tu hermano [QUIEN_REGALA]."


@pytest.mark.parametrize(("destinatario", "prosa", "esperado"), [
    # Marcas bidi en el brief, tal como llegan al pegar un nombre desde un contacto.
    ("‎Marta Ibáñez‎", "Marta Ibáñez despierta. Marta grita.",
     "[DESTINATARIO] despierta. [DESTINATARIO] grita."),
    ("‪Marta Ibáñez‬", "Marta grita.", "[DESTINATARIO] grita."),
    # Lo que no se ve partiendo el nombre en la prosa: bidi, CGJ, selector de variante, U+2062.
    ("Marta Ibáñez", "Mar‎ta grita.", "[DESTINATARIO] grita."),
    ("Marta Ibáñez", "Mar͏ta grita.", "[DESTINATARIO] grita."),
    ("Marta Ibáñez", "Mar️ta grita.", "[DESTINATARIO] grita."),
    ("Marta Ibáñez", "Mar⁢ta grita.", "[DESTINATARIO] grita."),
    # Apostrofos que Unicode clasifica como letra.
    ("Sean O'Hara", "OʼHara entra.", "[DESTINATARIO] entra."),
    ("Sean OʼHara", "Hara entra.", "[DESTINATARIO] entra."),
    # Un invisible o un cambio a mayuscula entre dos partes pegadas.
    # El invisible entre las dos se conserva: no es del nombre.
    ("Marta Ibáñez", "Marta​Ibáñez entra.", "[DESTINATARIO]​[DESTINATARIO] entra."),
    ("Marta Ibáñez", "MartaIbáñez entra.", "[DESTINATARIO][DESTINATARIO] entra."),
    ("Marta Ibáñez", "regaloParaMarta entra.", "regaloPara[DESTINATARIO] entra."),
    # Mayusculas matematicas y de tipo letra.
    ("Marta Ibáñez", "\U0001d40carta y ℳarta.", "[DESTINATARIO] y [DESTINATARIO]."),
])
def test_ni_lo_que_no_se_ve_ni_las_letras_raras_dejan_pasar_el_nombre(
    destinatario: str, prosa: str, esperado: str
) -> None:
    s = obs.Seudonimizador(_brief_con(destinatario=destinatario, regala="Luis", allegado="Kiko"))
    assert s.texto(prosa) == esperado


@pytest.mark.parametrize(("destinatario", "prosa", "esperado"), [
    # Validador (cuarto rechazo): la lista de la firma dejaba pasar nombres de pila reales.
    ("Tia Soto", "Tia grita.", "[DESTINATARIO] grita."),
    ("Una Ferrer", "Una grita.", "[DESTINATARIO] grita."),
    ("Primo Vidal", "Primo grita.", "[DESTINATARIO] grita."),
    ("Rosa Amigo", "Amigo grita.", "[DESTINATARIO] grita."),
    # Un caracter de formato en el brief separa dos partes, o va dentro de una.
    ("Marta​Ibáñez", "Marta grita. Ibáñez calla.", "[DESTINATARIO] grita. [DESTINATARIO] calla."),
    ("Mar­ta Soto", "Marta grita.", "[DESTINATARIO] grita."),
    # Mayusculas seguidas de una parte capitalizada.
    ("Marta Ibáñez", "MARTAIbáñez grita.", "[DESTINATARIO][DESTINATARIO] grita."),
    ("Marta Ibáñez", "regaloPARAMarta grita.", "regaloPARA[DESTINATARIO] grita."),
    # Un simbolo que pliega a letras pegado al nombre, y un relleno dentro.
    ("Marta Ibáñez", "Marta™ grita. №Marta.", "[DESTINATARIO]™ grita. №[DESTINATARIO]."),
    ("Marta Ibáñez", "Marㅤta grita.", "[DESTINATARIO] grita."),
    # El cierre de un aislamiento bidi no es del nombre.
    ("Marta Ibáñez", "⁨Marta⁩ grita.", "⁨[DESTINATARIO]⁩ grita."),
])
def test_cuarta_revision_del_seudonimizador(destinatario: str, prosa: str, esperado: str) -> None:
    s = obs.Seudonimizador(_brief_con(destinatario=destinatario, regala="Luis", allegado="Kiko"))
    assert s.texto(prosa) == esperado


@pytest.mark.parametrize(("regala", "prosa", "esperado"), [
    # Lo que acompana a la firma, en minuscula, no se sustituye suelto.
    ("Con todo mi cariño, Andrés", "Con todo el cariño, Andrés.",
     "Con todo el cariño, [QUIEN_REGALA]."),
    ("De parte de Andrés, feliz cumpleaños", "Feliz cumpleaños de parte de Andrés.",
     "Feliz cumpleaños de parte de [QUIEN_REGALA]."),
    # En mayuscula puede ser un nombre: se sustituye.
    ("Tía Rosa", "Tía llega.", "[QUIEN_REGALA] llega."),
])
def test_la_firma_distingue_lo_que_acompana_de_un_nombre(
    regala: str, prosa: str, esperado: str
) -> None:
    s = obs.Seudonimizador(_brief_con(destinatario="Marta Ibáñez", regala=regala,
                                      allegado="Kiko"))
    assert s.texto(prosa) == esperado


@pytest.mark.parametrize(("destinatario", "prosa", "esperado"), [
    # Validador (quinta revision): una particula que es un nombre se escapaba.
    ("Van Ferrer", "Van grita.", "[DESTINATARIO] grita."),
    ("Del Soto", "Del grita.", "[DESTINATARIO] grita."),
    # ...pero en minuscula en la prosa no es el nombre.
    ("Van Ferrer", "Ellos van al puente del sector.", "Ellos van al puente del sector."),
    # Una particula en minuscula en el brief no es el nombre...
    ("Ludo van Berk", "Ellos van. Berk grita.", "Ellos van. [DESTINATARIO] grita."),
    # ...salvo que lo abra, o que el brief este todo en minuscula (sexta revision).
    ("van Ferrer", "Van grita. Ellos van.", "[DESTINATARIO] grita. Ellos van."),
    ("van ferrer", "Van grita. Ferrer calla.", "[DESTINATARIO] grita. [DESTINATARIO] calla."),
    ("marta ibáñez", "marta_ibanez grita.", "[DESTINATARIO]_[DESTINATARIO] grita."),
    # Un nombre de una palabra que es particula casa solo en mayuscula, entero incluido.
    ("Van", "Van grita. Ellos van.", "[DESTINATARIO] grita. Ellos van."),
    ("van", "Van grita. Ellos van.", "[DESTINATARIO] grita. Ellos van."),
    # El brief con las partes pegadas en camelCase.
    ("MartaIbáñez", "Marta grita. Ibáñez calla.", "[DESTINATARIO] grita. [DESTINATARIO] calla."),
    ("MARTAIbáñez", "Marta grita. Ibáñez calla.", "[DESTINATARIO] grita. [DESTINATARIO] calla."),
    # Dos fronteras suaves de papel distinto en el brief: todas las lecturas.
    ("Marta​Ibá­ñez", "Ibáñez calla.", "[DESTINATARIO] calla."),
    ("Mar­ta​Ibáñez", "Marta grita.", "[DESTINATARIO] grita."),
    ("Marta​Ibáñez​So­to", "Soto calla.", "[DESTINATARIO] calla."),
    # Lo que solo sale de partir por un corte invisible casa solo en mayuscula.
    ("Mar­ta Soto", "El mar estaba en calma.", "El mar estaba en calma."),
    # Un digrafo de titulo abre palabra.
    ("Džemal Horvat", "regaloParaǅemal grita.", "regaloPara[DESTINATARIO] grita."),
])
def test_quinta_revision_del_seudonimizador(destinatario: str, prosa: str, esperado: str) -> None:
    s = obs.Seudonimizador(_brief_con(destinatario=destinatario, regala="Luis", allegado="Kiko"))
    assert s.texto(prosa) == esperado


@pytest.mark.parametrize(("regala", "prosa", "esperado"), [
    # Una palabra de dedicatoria que abre la firma en mayuscula casa solo en mayuscula.
    ("Feliz cumpleaños, Andrés", "Qué feliz estaba. Andrés llega.",
     "Qué feliz estaba. [QUIEN_REGALA] llega."),
    # Validador (sexta revision): cualquier palabra en minuscula de la firma, este o no en la
    # lista, casa solo en mayuscula.
    ("Un abrazo enorme de tu hermano Andrés", "Una nave enorme. Andrés llega.",
     "Una nave enorme. [QUIEN_REGALA] llega."),
    ("Con cariño, tu hermano que te quiere, Andrés", "Nadie te quiere aquí.",
     "Nadie te quiere aquí."),
])
def test_la_firma_no_ensucia_la_prosa_con_su_dedicatoria(
    regala: str, prosa: str, esperado: str
) -> None:
    s = obs.Seudonimizador(_brief_con(destinatario="Marta Ibáñez", regala=regala,
                                      allegado="Kiko"))
    assert s.texto(prosa) == esperado


def test_muchos_aciertos_no_se_funden_mal() -> None:
    """Miles de aciertos seguidos salen bien. Mide la correccion de la fusion, no su coste."""
    s = obs.Seudonimizador(_brief_con(destinatario="Marta Ibáñez", regala="Luis",
                                      allegado="Kiko"))
    texto = "Marta y Kiko miran a Luis. " * 3000
    assert s.texto(texto) == "[DESTINATARIO] y [ALLEGADO_1] miran a [QUIEN_REGALA]. " * 3000


def test_un_caracter_que_pliega_a_varios_no_corrompe_la_salida() -> None:
    s = obs.Seudonimizador(_brief_con(destinatario="Anna Pérez", regala="Luis",
                                      allegado="Clara"))
    assert s.texto("Ann℀lara llega.") == "[DESTINATARIO][ALLEGADO_1] llega."


def test_dos_claves_con_la_misma_etiqueta_no_se_pisan() -> None:
    s = obs.Seudonimizador(_brief_con(destinatario="Marta Ibáñez", regala="Luis",
                                      allegado="Kiko"))
    assert s.valor({"Marta": "alta", "Ibáñez": "baja"}) == {
        "[DESTINATARIO]": "alta", "[DESTINATARIO] #2": "baja",
    }


def test_las_partes_de_un_allegado_tambien_se_sustituyen() -> None:
    s = obs.Seudonimizador(_brief_con(destinatario="Marta Ibáñez", regala="Luis",
                                      allegado="Kiko Soler"))
    assert s.texto("Soler y Kiko.") == "[ALLEGADO_1] y [ALLEGADO_1]."


def test_una_letra_pegada_sigue_haciendo_otra_palabra() -> None:
    s = obs.Seudonimizador(_brief_con(destinatario="Marta Ibáñez", regala="Luis",
                                      allegado="Kiko"))
    assert s.texto("Martina y Luisa miran a Marta.") == "Martina y Luisa miran a [DESTINATARIO]."


# --- RF3-OBS-08: cuando se envia, y que un fallo no toca nada ------------------------------------


def test_lo_enviado_no_se_vuelve_a_enviar(
    con_brief: tuple[sqlite3.Connection, int, ClienteFalso],
) -> None:
    con, novela_id, _ = con_brief
    segundo = ClienteFalso()
    assert obs.Exportador(segundo).exportar(con, novela_id) == obs.Informe(0, 0)
    assert contar(con, "SELECT COUNT(*) FROM langfuse_envio WHERE novela_id = ?", novela_id) > 0


def test_un_fallo_de_langfuse_no_para_el_pipeline_y_se_reintenta() -> None:
    cliente = ClienteFalso()
    cliente.fallar = True
    con, novela_id, final = _novela_con_langfuse(cliente)
    assert final == "completada"
    assert contar(con, "SELECT COUNT(*) FROM traza_evento WHERE tipo = 'langfuse_fallo'") > 0
    assert contar(con, "SELECT COUNT(*) FROM langfuse_envio") == 0
    cliente.fallar = False
    informe = obs.Exportador(cliente).exportar(con, novela_id)
    assert informe.filas == contar(
        con, "SELECT (SELECT COUNT(*) FROM llamada_modelo) + (SELECT COUNT(*) FROM "
             "resultado_puerta)"
    )


def test_el_comando_no_escribe_en_la_base() -> None:
    cliente = ClienteFalso()
    con, novela_id, _ = _novela_con_langfuse(ClienteFalso())
    antes = contar(con, "SELECT COUNT(*) FROM langfuse_envio")
    informe = obs.Exportador(cliente, marcar=False).exportar(con, novela_id)
    assert informe.filas > 0
    assert contar(con, "SELECT COUNT(*) FROM langfuse_envio") == antes


# --- El cliente HTTP, con un transporte simulado -------------------------------------------------


def _cliente(manejador: Any) -> obs.ClienteHTTP:
    return obs.ClienteHTTP("https://cloud.langfuse.com", "pk", "sk",
                           transporte=httpx.MockTransport(manejador))


def test_el_cliente_envia_con_autenticacion_y_detecta_rechazos_parciales() -> None:
    vistos: list[httpx.Request] = []

    def manejador(peticion: httpx.Request) -> httpx.Response:
        vistos.append(peticion)
        return httpx.Response(207, json={"successes": [], "errors": [{"id": "x", "status": 400}]})

    with pytest.raises(obs.ErrorLangfuse, match="rechazo 1 de 1"):
        _cliente(manejador).enviar([{"id": "e", "type": "trace-create", "body": {"id": "t"}}])
    assert vistos[0].url.path == "/api/public/ingestion"
    assert vistos[0].headers["authorization"].startswith("Basic ")


def test_el_cliente_busca_y_crea_prompts() -> None:
    def manejador(peticion: httpx.Request) -> httpx.Response:
        if peticion.method == "GET":
            return httpx.Response(404, json={"message": "not found"})
        return httpx.Response(201, json={"version": 3})

    cliente = _cliente(manejador)
    assert cliente.version_de_prompt("storymaker-redaccion", "sha-abc") is None
    assert cliente.crear_prompt("storymaker-redaccion", "texto", "sha-abc") == 3
