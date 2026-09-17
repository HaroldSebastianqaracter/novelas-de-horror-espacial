"""Frontend §15: RF-UI-01 (valida con HarnessConfig antes de escribir) y RF-UI-02 (bloqueo de novela.json con capítulos cerrados)."""

import http.client
import json
import threading
from pathlib import Path
from urllib.parse import urlencode

import pytest

from app import ui, web
from app.config import cargar_config
from app.errores import ConfiguracionInvalidaError, EstadoInvalidoError
from app.orchestrator import checkpoint
from app.rutas import Rutas
from tests.conftest import construir_proyecto

FORM_OK = {
    "idea": "Una estación minera en el cinturón pierde contacto con la Tierra.\r\nLa tripulación oye respirar al casco.",
    "idioma": "es-ES", "persona_narrativa": "tercera_limitada", "tiempo_verbal": "pasado",
    "total_capitulos": "30", "palabras_por_capitulo": "1500", "ventana_resumen_rodante": "2", "cadencia_qa": "3",
    "max_tokens_contexto_escritor": "12000", "max_hechos_por_capitulo": "4",
    "capitulos_por_tanda": "3", "max_llamadas_por_tanda": "30", "registrar_uso": "on",
    "referencias": "",
}


def _raiz_vacia(tmp_path, monkeypatch):
    raiz = tmp_path / "nueva"
    raiz.mkdir()
    monkeypatch.setenv("HARNESS_RAIZ", str(raiz))
    return raiz


# ---------- estado inicial ----------

def test_sin_config_precarga_defaults_y_no_bloquea(tmp_path, monkeypatch):
    raiz = _raiz_vacia(tmp_path, monkeypatch)
    estado = ui.estado_formulario(raiz)
    assert estado.valores == ui.DEFAULTS
    assert estado.bloqueado is False and estado.motivo_bloqueo is None and estado.capitulos_cerrados == 0
    assert estado.idea == "" and estado.referencias == []
    assert " disabled" not in ui.render_formulario(estado)


def test_con_config_precarga_lo_que_hay_en_disco(proyecto):
    estado = ui.estado_formulario(proyecto)
    assert estado.valores["total_capitulos"] == 30 and estado.valores["capitulos_por_tanda"] == 3
    assert "estación minera" in estado.idea


# ---------- RF-UI-01: validación antes de escribir ----------

def test_guardado_valido_escribe_los_tres_archivos_y_validan(tmp_path, monkeypatch):
    raiz = _raiz_vacia(tmp_path, monkeypatch)
    rutas = Rutas(raiz)
    resultado = ui.procesar_guardado(raiz, dict(FORM_OK))
    assert set(resultado.escritos) == {rutas.idea, rutas.novela_json, rutas.ejecucion_json}
    # idea.md contiene exactamente el texto escrito (con saltos LF)
    assert rutas.idea.read_text(encoding="utf-8") == FORM_OK["idea"].replace("\r\n", "\n")
    config = cargar_config(raiz)  # EX-05 no puede dispararse sobre lo que escribió el frontend
    assert config.total_capitulos == 30 and config.capitulos_por_tanda == 3 and config.registrar_uso is True
    novela = json.loads(rutas.novela_json.read_text(encoding="utf-8"))
    ejecucion = json.loads(rutas.ejecucion_json.read_text(encoding="utf-8"))
    assert set(novela) == {"total_capitulos", "palabras_por_capitulo", "idioma", "persona_narrativa", "tiempo_verbal",
                           "ventana_resumen_rodante", "cadencia_qa", "max_tokens_contexto_escritor", "max_hechos_por_capitulo"}
    assert ejecucion == {"capitulos_por_tanda": 3, "max_llamadas_por_tanda": 30, "registrar_uso": True}
    assert resultado.comando_siguiente == "/generar-premisa"  # 00_referencias/ vacía


def test_campos_vacios_de_ejecucion_son_null_y_checkbox_ausente_es_false(tmp_path, monkeypatch):
    raiz = _raiz_vacia(tmp_path, monkeypatch)
    campos = dict(FORM_OK, capitulos_por_tanda="", max_llamadas_por_tanda="  ")
    campos.pop("registrar_uso")
    ui.procesar_guardado(raiz, campos)
    config = cargar_config(raiz)
    assert config.capitulos_por_tanda is None and config.max_llamadas_por_tanda is None and config.registrar_uso is False


@pytest.mark.parametrize("campo,valor,texto", [
    ("total_capitulos", "10", "total_capitulos"),
    ("total_capitulos", "51", "total_capitulos"),
    ("palabras_por_capitulo", "0", "palabras_por_capitulo"),
    ("palabras_por_capitulo", "muchas", "palabras_por_capitulo"),
    ("cadencia_qa", "", "cadencia_qa"),
    ("persona_narrativa", "segunda", "persona_narrativa"),
    ("capitulos_por_tanda", "0", "capitulos_por_tanda"),
])
def test_configuracion_invalida_se_rechaza_y_nada_llega_al_disco(tmp_path, monkeypatch, campo, valor, texto):
    raiz = _raiz_vacia(tmp_path, monkeypatch)
    rutas = Rutas(raiz)
    with pytest.raises(ConfiguracionInvalidaError, match=texto):
        ui.procesar_guardado(raiz, dict(FORM_OK, **{campo: valor}))
    assert not rutas.idea.exists() and not rutas.novela_json.exists() and not rutas.ejecucion_json.exists()


def test_idea_vacia_se_rechaza(tmp_path, monkeypatch):
    raiz = _raiz_vacia(tmp_path, monkeypatch)
    with pytest.raises(EstadoInvalidoError, match="RF-01.1"):
        ui.procesar_guardado(raiz, dict(FORM_OK, idea="   \r\n"))
    assert not Rutas(raiz).novela_json.exists()


def test_error_de_validacion_no_pisa_una_config_previa(proyecto):
    rutas = Rutas(proyecto)
    antes = (rutas.novela_json.read_bytes(), rutas.ejecucion_json.read_bytes(), rutas.idea.read_bytes())
    with pytest.raises(ConfiguracionInvalidaError):
        ui.procesar_guardado(proyecto, dict(FORM_OK, idea="otra idea", total_capitulos="99"))
    assert (rutas.novela_json.read_bytes(), rutas.ejecucion_json.read_bytes(), rutas.idea.read_bytes()) == antes


# ---------- referencias (RF-00.2) ----------

def test_copia_referencias_y_sugiere_destilar_estilo(tmp_path, monkeypatch):
    raiz = _raiz_vacia(tmp_path, monkeypatch)
    origen = tmp_path / "ejemplos"
    origen.mkdir()
    (origen / "uno.txt").write_text("El casco crujía.", encoding="utf-8")
    (origen / "dos.md").write_text("# Ejemplo\n\nNadie respondió.", encoding="utf-8")
    (origen / "ignorar.pdf").write_bytes(b"%PDF")
    suelto = tmp_path / "suelto.txt"
    suelto.write_text("Suelto.", encoding="utf-8")
    resultado = ui.procesar_guardado(raiz, dict(FORM_OK, referencias=f"{origen}\r\n\"{suelto}\"\r\n"))
    nombres = sorted(p.name for p in resultado.copiados)
    assert nombres == ["dos.md", "suelto.txt", "uno.txt"]
    assert (Rutas(raiz).referencias / "uno.txt").read_text(encoding="utf-8") == "El casco crujía."
    assert resultado.comando_siguiente == "/destilar-estilo"
    assert ui.estado_formulario(raiz).referencias == ["dos.md", "suelto.txt", "uno.txt"]


def test_referencia_inexistente_se_rechaza_sin_escribir(tmp_path, monkeypatch):
    raiz = _raiz_vacia(tmp_path, monkeypatch)
    with pytest.raises(ConfiguracionInvalidaError, match="no existe"):
        ui.procesar_guardado(raiz, dict(FORM_OK, referencias=str(tmp_path / "no_esta.txt")))
    assert not Rutas(raiz).idea.exists() and not Rutas(raiz).novela_json.exists()


# ---------- RF-UI-02: bloqueo con capítulos cerrados ----------

def _cerrar_capitulos(raiz, n):
    m = checkpoint.leer_manifest(raiz)
    checkpoint.escribir_manifest(raiz, m.model_copy(update={"ultimo_capitulo_cerrado": n}))


def test_manifiesto_sin_cerrados_no_bloquea(proyecto):
    assert ui.estado_formulario(proyecto).bloqueado is False


def test_con_cerrados_los_campos_de_novela_salen_deshabilitados_con_motivo(proyecto):
    _cerrar_capitulos(proyecto, 5)
    estado = ui.estado_formulario(proyecto)
    assert estado.bloqueado is True and estado.capitulos_cerrados == 5
    assert "INV-04" in estado.motivo_bloqueo and "5 capítulos cerrados" in estado.motivo_bloqueo
    pagina = ui.render_formulario(estado)
    assert pagina.count("<fieldset disabled>") == 2  # voz narrativa y dimensionamiento
    assert "INV-04" in pagina
    # la idea y ejecucion.json siguen editables
    assert "<textarea name='idea' required" in pagina
    assert "<fieldset>" in pagina and "name='capitulos_por_tanda'" in pagina.split("<fieldset>", 1)[1]


def test_bloqueado_rechaza_cambios_en_novela_y_conserva_el_archivo(proyecto):
    _cerrar_capitulos(proyecto, 5)
    rutas = Rutas(proyecto)
    antes = rutas.novela_json.read_bytes()
    with pytest.raises(EstadoInvalidoError, match="INV-04.*total_capitulos"):
        ui.procesar_guardado(proyecto, dict(FORM_OK, total_capitulos="40"))
    assert rutas.novela_json.read_bytes() == antes


def test_bloqueado_permite_idea_y_ejecucion(proyecto):
    _cerrar_capitulos(proyecto, 5)
    rutas = Rutas(proyecto)
    antes = rutas.novela_json.read_bytes()
    campos = {"idea": "Idea corregida entre tandas.", "capitulos_por_tanda": "", "max_llamadas_por_tanda": "12"}
    resultado = ui.procesar_guardado(proyecto, campos)  # los campos deshabilitados no viajan en el POST
    assert rutas.novela_json not in resultado.escritos and rutas.novela_json.read_bytes() == antes
    assert rutas.idea.read_text(encoding="utf-8") == "Idea corregida entre tandas."
    config = cargar_config(proyecto)
    assert config.capitulos_por_tanda is None and config.max_llamadas_por_tanda == 12 and config.registrar_uso is False
    assert config.total_capitulos == 30  # intacto


def test_bloqueado_acepta_los_mismos_valores_de_novela(proyecto):
    _cerrar_capitulos(proyecto, 2)
    ui.procesar_guardado(proyecto, dict(FORM_OK))  # todos los valores de novela coinciden con el disco
    assert cargar_config(proyecto).total_capitulos == 30


# ---------- servidor HTTP (solo 127.0.0.1) ----------

@pytest.fixture
def servidor(proyecto):
    srv = ui.crear_servidor(proyecto, 0)
    hilo = threading.Thread(target=srv.serve_forever, daemon=True)
    hilo.start()
    yield srv
    srv.shutdown()
    srv.server_close()


def _pedir(srv, metodo, ruta, campos=None):
    con = http.client.HTTPConnection(*srv.server_address, timeout=5)
    cuerpo = urlencode(campos).encode("utf-8") if campos is not None else None
    cabeceras = {"Content-Type": "application/x-www-form-urlencoded"} if cuerpo else {}
    con.request(metodo, ruta, body=cuerpo, headers=cabeceras)
    resp = con.getresponse()
    datos = resp.read().decode("utf-8")
    con.close()
    return resp.status, datos


def test_servidor_escucha_solo_en_loopback(servidor):
    assert servidor.server_address[0] == "127.0.0.1"


def test_get_muestra_el_formulario_y_post_guarda(servidor, proyecto):
    estado, pagina = _pedir(servidor, "GET", "/encargo-simple")
    assert estado == 200 and "name='idea'" in pagina and "value='1500'" in pagina
    estado, pagina = _pedir(servidor, "POST", "/guardar", dict(FORM_OK, idea="Idea desde el navegador."))
    assert estado == 200 and "Guardado" in pagina and "config/novela.json" in pagina and "/generar-premisa" in pagina
    assert Rutas(proyecto).idea.read_text(encoding="utf-8") == "Idea desde el navegador."


def test_post_invalido_devuelve_400_con_el_motivo_y_no_escribe(servidor, proyecto):
    rutas = Rutas(proyecto)
    antes = rutas.novela_json.read_bytes()
    estado, pagina = _pedir(servidor, "POST", "/guardar", dict(FORM_OK, total_capitulos="7"))
    assert estado == 400 and "No se guardó nada" in pagina and "total_capitulos" in pagina
    assert rutas.novela_json.read_bytes() == antes


def test_get_bloqueado_muestra_campos_deshabilitados(servidor, proyecto):
    _cerrar_capitulos(proyecto, 3)
    estado, pagina = _pedir(servidor, "GET", "/encargo-simple")
    assert estado == 200 and "<fieldset disabled>" in pagina and "INV-04" in pagina


def test_rutas_desconocidas_dan_404(servidor):
    assert _pedir(servidor, "GET", "/otra")[0] == 404
    assert _pedir(servidor, "POST", "/otra", {})[0] == 404


def test_el_indice_marca_lo_escrito_lo_cerrado_y_el_corte(proyecto, config):
    """La cinta de capítulos de la lectura sale del disco, no de lo que dijo ningún agente."""
    indice = web.indice(proyecto)
    assert indice["total_capitulos"] == len(indice["capitulos"])
    for c in indice["capitulos"]:
        assert c["escrito"] == Rutas(proyecto).capitulo(c["num"]).exists()


def test_el_capitulo_no_escrito_no_se_inventa(proyecto, config):
    faltan = [c["num"] for c in web.indice(proyecto)["capitulos"] if not c["escrito"]]
    if faltan:
        assert web.capitulo(proyecto, faltan[0]) is None


def test_los_hechos_del_margen_son_los_fijados_en_ese_capitulo(proyecto, config):
    """Cada hecho del margen tiene que venir de ese capítulo: el margen dice «lo que se fijó aquí»."""
    escritos = [c["num"] for c in web.indice(proyecto)["capitulos"] if c["escrito"]]
    if not escritos:
        pytest.skip("el proyecto de prueba no tiene capítulos escritos")
    cap = web.capitulo(proyecto, escritos[0])
    crudo = json.loads((Rutas(proyecto).continuidad).read_text(encoding="utf-8")) if Rutas(proyecto).continuidad.exists() else []
    hechos = crudo.get("root") if isinstance(crudo, dict) else crudo
    esperados = [h["hecho"] for h in (hechos or []) if isinstance(h, dict) and h.get("cap_origen") == escritos[0]]
    assert [h["hecho"] for h in cap["hechos"]] == esperados


def test_el_encargo_solo_congela_lo_que_congela_INV_04(proyecto, config, servidor):
    """La pantalla no puede ser mas restrictiva que el harness.

    Con capitulos cerrados, INV-04 vuelve inmutable `config/novela.json`, pero la idea y
    `config/ejecucion.json` siguen editables. Si la API no dijera que campos son de cada grupo, la
    hoja tendria que adivinarlo y acabaria bloqueando de mas.
    """
    estado, cuerpo = _pedir(servidor, "GET", "/api/formulario")
    datos = json.loads(cuerpo)
    assert estado == 200
    assert set(datos["campos_novela"]).isdisjoint(datos["campos_ejecucion"])
    assert "total_capitulos" in datos["campos_novela"]
    assert "capitulos_por_tanda" in datos["campos_ejecucion"]
    assert "idea" not in datos["campos_novela"]


def test_las_cuatro_pantallas_se_sirven(proyecto, config, servidor):
    for ruta in ("/", "/encargo", "/consola", "/lectura"):
        estado, _ = _pedir(servidor, "GET", ruta)
        assert estado == 302, f"{ruta} deberia redirigir a su HTML, devolvio {estado}"
    for archivo in ("vestuario.html", "encargo.html", "consola.html", "lectura.html"):
        estado, _ = _pedir(servidor, "GET", "/static/" + archivo)
        assert estado == 200, f"{archivo} no se sirve"


def test_la_redireccion_conserva_la_consulta(proyecto, config, servidor):
    """`/lectura?cap=4` perdia el capitulo y abria siempre el ultimo."""
    conexion = http.client.HTTPConnection("127.0.0.1", servidor.server_address[1])
    conexion.request("GET", "/lectura?cap=4")
    respuesta = conexion.getresponse()
    assert respuesta.status == 302
    assert respuesta.getheader("Location") == "/static/lectura.html?cap=4"
    conexion.close()


def test_no_se_borra_la_novela_con_trabajo_fuera_de_git(proyecto, config, monkeypatch):
    """El borrado solo es reversible mientras lo borrado este confirmado en git.

    La primera version partia cada linea de `git status --porcelain` por el primer espacio, y una
    modificacion sin indexar es « M ruta»: el estado salia vacio y la guarda dejaba pasar
    exactamente el caso que tenia que detener. Borro una novela de verdad al probarla.
    """
    monkeypatch.setattr(web, "_hay_cambios_sin_guardar", lambda raiz: ["05_manuscrito/cap_1.md"])
    with pytest.raises(RuntimeError, match="sin confirmar"):
        web.borrar_novela(proyecto)
    # Con `forzar` se borra igual: la guarda protege del descuido, no del que insiste.
    web.borrar_novela(proyecto, forzar=True)


def test_el_parseo_de_git_status_detecta_las_modificaciones_sin_indexar():
    salida = " M creador-novelas/05_manuscrito/cap_1.md\nM  otro.md\n?? nuevo.md\n"
    filas = [(l[:2], l[3:].strip()) for l in salida.splitlines()]
    assert [r for e, r in filas if e.strip() and e != "!!"] == [
        "creador-novelas/05_manuscrito/cap_1.md", "otro.md", "nuevo.md"]


def test_borrar_se_lleva_la_idea_y_la_premisa(proyecto, config):
    """Si `01_concepto/` sobrevive, la novela nueva hereda la premisa de la vieja.

    Se descubrio borrando de verdad: el vestuario seguia anunciando «El casco frio del Falcon»
    despues del borrado, porque el titulo se extrae de 01_concepto/premisa.md.
    """
    assert "01_concepto" in web.CARPETAS_DE_NOVELA
    rutas = Rutas(proyecto)
    rutas.idea.parent.mkdir(parents=True, exist_ok=True)
    rutas.idea.write_text("una idea vieja", encoding="utf-8")
    web.borrar_novela(proyecto, forzar=True)
    assert not rutas.idea.exists()
    # Lo que no se toca: sin git detras, borrarlo seria irreversible.
    assert (proyecto / "config").is_dir() and (proyecto / "00_referencias").is_dir()


def test_las_cuatro_pantallas_llevan_la_misma_navegacion(proyecto, config):
    """Sin barra no hay forma de ir de una pantalla a otra: se llegaba y no se podia volver."""
    estatico = Path(__file__).resolve().parents[1] / "app" / "static"
    for archivo in ("vestuario.html", "encargo.html", "consola.html", "lectura.html"):
        html = (estatico / archivo).read_text(encoding="utf-8")
        assert 'class="ir"' in html, f"{archivo} no lleva navegación"
        for destino in ('href="/"', 'href="/encargo"', 'href="/consola"', 'href="/lectura"'):
            assert destino in html, f"{archivo} no enlaza {destino}"
        # La seccion activa se deduce del nombre del archivo: las rutas bonitas son redirecciones
        # a /static/*.html, asi que comparar con location.pathname nunca acertaria.
        assert "vestuario.html" in html and "location.pathname.split" in html
