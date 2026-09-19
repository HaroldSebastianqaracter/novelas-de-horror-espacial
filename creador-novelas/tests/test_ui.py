"""Frontend §15: RF-UI-01 (valida con HarnessConfig antes de escribir) y RF-UI-02 (bloqueo de novela.json con capítulos cerrados)."""

import http.client
import json
import threading
from pathlib import Path
from urllib.parse import urlencode

import pytest

from app import ui, web
from app.config import (CAMPOS_EJECUCION, CAMPOS_NOVELA, HarnessConfig,
                        cargar_config, construir_config)
from app.errores import ConfiguracionInvalidaError, EstadoInvalidoError
from app.orchestrator import checkpoint
from app.rutas import Rutas

DEFAULTS_CFG = dict(ui.DEFAULTS)
from tests.conftest import construir_proyecto

FORM_OK = {
    "idea": "Una estación minera en el cinturón pierde contacto con la Tierra.\r\nLa tripulación oye respirar al casco.",
    "idioma": "es-ES", "persona_narrativa": "tercera_limitada", "tiempo_verbal": "pasado",
    "total_capitulos": "30", "palabras_por_capitulo": "1500", "ventana_resumen_rodante": "2", "cadencia_qa": "3",
    "max_tokens_contexto_escritor": "12000", "max_hechos_por_capitulo": "4",
    "capitulos_por_tanda": "3", "max_llamadas_por_tanda": "30", "registrar_uso": "on",
    "exportar_trazas": "on",
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
    assert ejecucion == {"capitulos_por_tanda": 3, "max_llamadas_por_tanda": 30, "registrar_uso": True,
                         "exportar_trazas": True, "exportar_para_juez": False,
                         "escritor_emite_delta": False, "aristas_en_continuidad": False}
    assert resultado.comando_siguiente == "/generar-premisa"  # 00_referencias/ vacía


def test_campos_vacios_de_ejecucion_son_null_y_checkbox_ausente_es_false(tmp_path, monkeypatch):
    raiz = _raiz_vacia(tmp_path, monkeypatch)
    campos = dict(FORM_OK, capitulos_por_tanda="", max_llamadas_por_tanda="  ")
    campos.pop("registrar_uso")
    ui.procesar_guardado(raiz, campos)
    config = cargar_config(raiz)
    assert config.capitulos_por_tanda is None and config.max_llamadas_por_tanda is None and config.registrar_uso is False


@pytest.mark.parametrize("campo,valor,texto", [
    ("total_capitulos", "0", "total_capitulos"),
    ("total_capitulos", "201", "total_capitulos"),
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
        ui.procesar_guardado(proyecto, dict(FORM_OK, idea="otra idea", total_capitulos="999"))
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
    estado, pagina = _pedir(servidor, "POST", "/guardar", dict(FORM_OK, total_capitulos="0"))
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


def test_la_consola_ofrece_las_cinco_fases_de_preparacion(proyecto, config):
    """El backend sabia lanzar las nueve fases y la pantalla solo ofrecia dos.

    Para empezar una novela habia que volver a la terminal y teclear las cinco skills del preludio
    en orden, que es justo lo que la web venia a evitar.
    """
    html = (Path(__file__).resolve().parents[1] / "app" / "static" / "consola.html").read_text(encoding="utf-8")
    for fase in ("destilar-estilo", "generar-premisa", "generar-sinopsis",
                 "generar-escaleta", "inicializar-estado", "escribir-tanda"):
        assert fase in html, f"la consola no ofrece {fase}"
        assert fase in web.SKILLS or fase in web.VERBOS, f"{fase} no se puede lanzar"


def test_el_formulario_publica_las_cotas_del_esquema(proyecto, config):
    """La hoja dejaba pedir capitulos que el esquema rechazaba y el error salia al guardar.

    Las cotas se leen de HarnessConfig en vez de escribirse en el HTML, para que no puedan quedarse
    atras cuando cambie el esquema.
    """
    limites = ui.limites_de_config()
    assert limites["total_capitulos"] == {"min": 1, "max": 200}
    campo = HarnessConfig.model_fields["total_capitulos"]
    cotas = {getattr(m, "ge", None) for m in campo.metadata} | {getattr(m, "le", None) for m in campo.metadata}
    assert limites["total_capitulos"]["min"] in cotas and limites["total_capitulos"]["max"] in cotas


def test_no_tener_informe_de_qa_no_es_un_error(proyecto, config, servidor):
    estado, cuerpo = _pedir(servidor, "GET", "/api/qa")
    assert estado == 200 and json.loads(cuerpo) is None


def test_la_longitud_de_la_obra_la_elige_el_usuario(proyecto, config):
    """El rango 30-50 no venia de ninguna limitacion del harness: era la decision de que esto
    generaba novelas. Un relato de seis capitulos recibe el mismo tratamiento a menor escala.

    El maximo se conserva por otro motivo: a unos 0,55 $ por capitulo, teclear 300 donde iban 30
    cuesta unos 165 $. Es un seguro contra el error de dedo, no una regla estetica.
    """
    def con(n):
        novela = {k: v for k, v in DEFAULTS_CFG.items() if k in CAMPOS_NOVELA} | {"total_capitulos": n}
        ejecucion = {k: v for k, v in DEFAULTS_CFG.items() if k in CAMPOS_EJECUCION}
        return construir_config(novela, ejecucion)

    for n in (1, 6, 30, 200):
        assert con(n).total_capitulos == n
    for n in (0, 201):
        with pytest.raises(ConfiguracionInvalidaError):
            con(n)


def test_firmar_el_encargo_lleva_a_la_consola_y_no_a_la_terminal(proyecto, config, servidor):
    """La pagina de confirmacion se escribio cuando la web no sabia lanzar fases.

    Decia «En la sesion de Claude Code, teclear: /generar-premisa» y enlazaba de vuelta al
    formulario, asi que despues de encargar un libro parecia que el resto iba por terminal.
    """
    estado, pagina = _pedir(servidor, "POST", "/guardar", dict(FORM_OK, idea="una idea nueva"))
    assert estado == 200
    assert "/consola" in pagina, "la confirmacion no lleva a la consola"
    assert "Volver al encargo" in pagina and "/encargo" in pagina

    # Y la hoja de encargo no se queda en esa pagina: firma por fetch y salta a produccion.
    html = (Path(__file__).resolve().parents[1] / "app" / "static" / "encargo.html").read_text(encoding="utf-8")
    assert 'fetch("/guardar"' in html and 'location.href = "/consola"' in html


def test_un_libro_recien_encargado_ya_existe_en_la_biblioteca(proyecto, config):
    """Firmar el encargo escribe `01_concepto/idea.md` y nada mas: ni titulo, ni premisa, ni
    manifiesto. La biblioteca miraba solo esos tres, asi que el libro recien encargado no aparecia
    y la unica percha visible era la del libro nuevo: parecia que no se habia guardado.
    """
    rutas = Rutas(proyecto)
    # Se vacia todo lo que delata a un libro para partir de una carpeta sin ninguno.
    for archivo in (rutas.idea, rutas.premisa, rutas.manifest):
        if archivo.exists():
            archivo.unlink()
    for n in range(1, 60):
        if rutas.capitulo(n).exists():
            rutas.capitulo(n).unlink()
    assert web.indice(proyecto)["hay_novela"] is False

    rutas.idea.parent.mkdir(parents=True, exist_ok=True)
    rutas.idea.write_text("Una cuadrilla llega a una estación que dejó de responder.", encoding="utf-8")
    indice = web.indice(proyecto)
    assert indice["hay_novela"] is True
    # Sin titulo todavia: lo pone el harness al generar la premisa, no el usuario al encargar.
    assert indice["titulo"] is None and indice["idea"].startswith("Una cuadrilla")


def test_el_lanzador_arma_el_prompt_desde_la_skill(proyecto, config):
    """La pantalla lanzaba `claude -p "/generar-premisa"` y no pasaba nada.

    En modo `-p` un comando con barra se reconoce como comando local, se resuelve y la sesion
    termina sin llamar al modelo: `num_turns: 0`, resultado vacio y, peor, `is_error: false`, asi
    que ni siquiera se notaba. El harness arma ahora el prompt: lee el SKILL.md, resuelve sus
    directivas sin shell --usan `2>/dev/null` y `||`, que PowerShell rechaza-- y manda el cuerpo.
    """
    skill = proyecto / ".claude" / "skills" / "generar-premisa" / "SKILL.md"
    skill.parent.mkdir(parents=True, exist_ok=True)
    skill.write_text("""---
name: generar-premisa
allowed-tools: Read, Write, Bash(.venv/Scripts/python.exe -m app:*)
disable-model-invocation: true
---

Idea del usuario:
!`cat 01_concepto/idea.md 2>/dev/null || echo "(no existe)"`

# Fase 1
Escribi la premisa.
""", encoding="utf-8")

    prompt, herramientas = web.prompt_de_fase(proyecto, "generar-premisa")
    assert "!`" not in prompt, "quedan directivas sin resolver"
    assert not prompt.lstrip().startswith("/"), "no puede empezar por un comando con barra"
    assert "---" not in prompt.split("\n")[0], "el frontmatter no se manda al modelo"
    assert "Read" in herramientas and any(h.startswith("Bash(") for h in herramientas)
    # En Windows la herramienta de shell es PowerShell y el permiso casa por prefijo literal, asi
    # que hay que autorizar la equivalente y con los dos separadores.
    assert any(h.startswith("PowerShell(") and "/" in h for h in herramientas)
    assert any(h.startswith("PowerShell(") and "\\" in h for h in herramientas)


def test_el_lanzador_senala_git_bash_para_que_los_hooks_corran(monkeypatch, tmp_path):
    """En Windows Claude Code ejecuta los hooks con Git Bash; sin él no fallan, simplemente no corren.

    Se descubrió midiendo una tanda real: 28 minutos y 8 $ sin un solo evento de hook, o sea sin H-06
    (confina las escrituras), sin H-10 (registra el uso) y sin H-11 (confina la terminal).
    """
    import os as _os
    bash = tmp_path / "Git" / "bin" / "bash.exe"
    bash.parent.mkdir(parents=True)
    bash.write_text("", encoding="utf-8")

    # Con la variable ya puesta y apuntando a un archivo real, se respeta.
    monkeypatch.setattr(_os, "name", "nt")
    monkeypatch.setenv("CLAUDE_CODE_GIT_BASH_PATH", str(bash))
    assert web.git_bash() == str(bash)
    assert web.entorno_de_lanzamiento()["CLAUDE_CODE_GIT_BASH_PATH"] == str(bash)

    # Apuntando a algo que no existe, se ignora y se busca; sin nada que encontrar, None.
    monkeypatch.setenv("CLAUDE_CODE_GIT_BASH_PATH", str(tmp_path / "no-existe.exe"))
    monkeypatch.setattr(web.shutil, "which", lambda _: None)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "vacio"))
    monkeypatch.setattr(web.Path, "exists", lambda self: False)
    assert web.git_bash() is None


def test_sin_git_bash_la_fase_de_agentes_no_se_lanza(monkeypatch, proyecto, config):
    """Vale más una fase que no arranca que una tanda entera sin su valla de invariantes."""
    import os as _os
    monkeypatch.setattr(_os, "name", "nt")
    monkeypatch.setattr(web, "ejecutable_claude", lambda: "claude.exe")
    monkeypatch.setattr(web, "git_bash", lambda: None)
    web._EN_CURSO.clear()
    with pytest.raises(RuntimeError, match="Git Bash"):
        web.lanzar_fase(proyecto, "escribir-tanda")


def test_la_traza_se_publica_sola_al_cerrar_la_fase_y_se_puede_apagar(monkeypatch, proyecto, config):
    """Publicar era manual, así que no había nada que mirar salvo que alguien se acordara.

    Tres condiciones, y si falta una no se publica y no se molesta: el interruptor de `ejecucion.json`,
    credenciales en el entorno (§16.7) y nunca con cuerpos (§16.6).
    """
    from app import observabilidad as obs
    llamadas = []

    class _ClienteFalso:
        def __init__(self, *a, **k): pass

    def _exportar(raiz, carpeta, cliente, *, con_cuerpos=False, para_juez=False, volcar=None):
        llamadas.append({"carpeta": carpeta.name, "con_cuerpos": con_cuerpos, "para_juez": para_juez})
        class _R:
            class traza: tanda, id = "t", "abc"
            aceptados = 3
        return _R()

    monkeypatch.setattr(obs, "ClienteOTLP", _ClienteFalso)
    monkeypatch.setattr(obs, "credenciales_desde_entorno", lambda *a, **k: object())
    monkeypatch.setattr(obs, "exportar", _exportar)
    # No se toca `resolver_tanda`: publicar «la última tanda» dejaba fuera el preludio, porque
    # durante las cuatro fases de preparación todavía no existe ninguna carpeta `tanda_*` y el
    # exportador fallaba en silencio. Se publica la carpeta de registro en uso, sea cual sea.

    hilo_real = web.threading.Thread

    def _sincrono(target=None, **k):  # el hilo se ejecuta en el sitio para poder afirmar sobre él
        class _H:
            def start(self_): target()
        return _H()

    monkeypatch.setattr(web.threading, "Thread", _sincrono)
    web._publicar_traza(proyecto)
    # X-03.2: `exportar_para_juez` está apagado por defecto, así que la publicación automática no manda
    # los capítulos a Langfuse mientras nadie lo encienda a propósito.
    assert llamadas == [{"carpeta": "preludio", "con_cuerpos": False, "para_juez": False}], "publica sin prosa de la novela"

    # Encendido, la traza lleva lo que el evaluador de Langfuse necesita leer: sin esto la regla del juez
    # no puntúa nada y la pestaña de scores se queda vacía sin decir por qué.
    llamadas.clear()
    rutas_j = Rutas(proyecto)
    ejecucion_j = json.loads(rutas_j.ejecucion_json.read_text(encoding="utf-8"))
    rutas_j.ejecucion_json.write_text(json.dumps(ejecucion_j | {"exportar_para_juez": True}), encoding="utf-8")
    web._publicar_traza(proyecto)
    assert llamadas == [{"carpeta": "preludio", "con_cuerpos": False, "para_juez": True}]
    rutas_j.ejecucion_json.write_text(json.dumps(ejecucion_j), encoding="utf-8")

    # Con el interruptor apagado no sale nada de la máquina.
    llamadas.clear()
    rutas = Rutas(proyecto)
    ejecucion = json.loads(rutas.ejecucion_json.read_text(encoding="utf-8"))
    rutas.ejecucion_json.write_text(json.dumps(ejecucion | {"exportar_trazas": False}), encoding="utf-8")
    web._publicar_traza(proyecto)
    assert llamadas == []

    # Sin credenciales tampoco, y sin romper el cierre de la fase.
    rutas.ejecucion_json.write_text(json.dumps(ejecucion | {"exportar_trazas": True}), encoding="utf-8")
    def _falta(*a, **k):
        raise ConfiguracionInvalidaError("faltan LANGFUSE_PUBLIC_KEY")
    monkeypatch.setattr(obs, "credenciales_desde_entorno", _falta)
    web._publicar_traza(proyecto)  # no lanza
    assert llamadas == []
    monkeypatch.setattr(web.threading, "Thread", hilo_real)


def test_el_consumo_del_orquestador_se_anota_y_llega_a_la_traza(proyecto, config):
    """Langfuse declaraba una cuarta parte del coste real y el preludio no existía allí.

    H-10 solo anota subagentes, así que la sesión que orquesta no aparecía en ninguna parte: en la
    tanda del 18/09 eran 4,21 $ de los 5,52 $ que costó. El resumen de `claude -p` viene agregado
    (sesión + subagentes), de modo que lo suyo es esa suma menos lo que H-10 ya contó.
    """
    import time as _t
    from app import observabilidad as obs
    from app import registro as reg

    carpeta = reg.dir_actual(proyecto)
    carpeta.mkdir(parents=True, exist_ok=True)
    # Un subagente ya anotado por H-10, con su par de eventos.
    reg.evento(proyecto, "agente_inicio", rol="escritor", capitulo=1, agent_id="sub1")
    reg.evento(proyecto, "agente_fin", rol="escritor", capitulo=1, agent_id="sub1")
    with (carpeta / "uso.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"rol": "escritor", "capitulo": 1, "modelo": "claude-opus-5", "agent_id": "sub1",
                             "tokens_entrada": 100, "tokens_salida": 1_000,
                             "tokens_cache_lectura": 50_000, "tokens_cache_creacion": 2_000}) + "\n")

    log = proyecto / "salida.json"
    log.write_text(json.dumps({"type": "result", "subtype": "success", "num_turns": 9,
                               "total_cost_usd": 3.0,
                               "usage": {"input_tokens": 150, "output_tokens": 5_000,
                                         "cache_read_input_tokens": 200_000,
                                         "cache_creation_input_tokens": 9_000}}), encoding="utf-8")
    web._anotar_coste_de_fase(proyecto, "escribir-tanda", str(log), _t.time() - 60)

    filas = [u for u in reg.leer_uso(carpeta) if u["rol"] == "orquestador"]
    assert len(filas) == 1, "el orquestador tiene que quedar anotado como una invocación más"
    # Con el alias «opus» el consumo salía a 0,00 $ en el informe, porque config/precios.json y
    # Langfuse se llevan por el identificador completo. Parecer gratis es peor que no contarlo.
    precios = json.loads((Path(__file__).resolve().parents[1] / "config" / "precios.json")
                         .read_text(encoding="utf-8"))["por_millon"]
    assert filas[0]["modelo"] in precios, "el modelo anotado tiene que tener precio conocido"
    # Lo suyo es el total menos lo que ya contó H-10: si no se restara, se contaría dos veces.
    assert filas[0]["tokens_salida"] == 5_000 - 1_000
    assert filas[0]["tokens_cache_lectura"] == 200_000 - 50_000
    assert filas[0]["turnos"] == 9

    traza = obs.construir_traza(proyecto, carpeta)
    assert "orquestador" in [g.rol for g in traza.generaciones], "el exportador debe publicarlo"


def test_el_registro_solo_anuncia_los_hooks_que_de_verdad_frenaron_algo():
    """La bitácora decía «H-02 bloqueó» siete veces en una tanda donde no se bloqueó nada.

    Un hook deja cuatro decisiones: permitido/bloqueado en PreToolUse y verificado/falla en
    PostToolUse. El filtro era «distinto de permitido», así que cada verificación correcta se
    anunciaba como un bloqueo y la pantalla parecía estar frenando al harness sin parar.
    """
    ruta = r"C:\Users\quien\Desktop\Nueva carpeta\novelas\creador-novelas\06_qa\qa_cap_2.json"
    hook = lambda d: {"tipo": "hook", "id": "H-02", "decision": d, "accion": "Write " + ruta}
    assert web._frase(hook("permitido")) is None
    assert web._frase(hook("verificado")) is None          # verificado NO es un bloqueo
    assert web._frase(hook("bloqueado")).startswith("H-02 bloqueó")
    assert web._frase(hook("falla")).startswith("H-02 rechazó")

    # La ruta se reduce a su nombre de archivo, y no vale partir por espacios: esta novela vive
    # bajo «Nueva carpeta», y así el registro enseñaba «Nueva qa_cap_2.json».
    assert web._corto("Write " + ruta) == "Write qa_cap_2.json"
    # Una ruta relativa dentro de una frase se deja como está: es corta y dice dónde fue el intento.
    motivo = "[H-06] el escritor solo escribe 05_manuscrito/cap_2.md; intentó 06_qa/intruso.md"
    assert "05_manuscrito/cap_2.md" in web._corto(motivo, tope=200)


def test_el_plano_enciende_a_los_agentes_que_de_verdad_trabajan():
    """Reconstruido de la tanda del 18/09, donde el plano encendía una cubierta y la equivocada.

    Dos fallos a la vez: `preparar-capitulo` abre al escritor y al extractor en el mismo segundo
    -deja los dos prompts listos- y la pantalla encendía solo el último abierto, así que la bodega
    de hechos se iluminaba mientras redactaba el escritor. Y desde que el corte de QA se solapa con
    el capítulo siguiente hay dos agentes a la vez, y uno se quedaba a oscuras.
    """
    ev = lambda ts, tipo, rol, cap: {"ts": f"2026-09-18T{ts}+02:00", "tipo": tipo, "rol": rol, "capitulo": cap}
    linea = [
        ev("10:30:36", "agente_inicio", "escritor", 1),
        ev("10:30:36", "agente_inicio", "extractor", 1),   # solo se preparó su prompt
    ]
    assert [a[0] for a in web._agentes_activos(linea)] == ["escritor"]

    linea.append(ev("10:32:29", "agente_fin", "escritor", 1))
    assert [a[0] for a in web._agentes_activos(linea)] == ["extractor"]  # ahora sí le toca

    linea += [ev("10:34:32", "agente_fin", "extractor", 1),
              ev("10:34:44", "agente_inicio", "qa", 1),
              ev("10:34:56", "agente_inicio", "escritor", 2),
              ev("10:34:56", "agente_inicio", "extractor", 2)]
    # El corte del capítulo 1 y la escritura del 2, en paralelo: las dos cubiertas encendidas.
    assert [a[0] for a in web._agentes_activos(linea)] == ["qa", "escritor"]

    linea.append(ev("10:36:58", "agente_fin", "qa", 1))
    assert [a[0] for a in web._agentes_activos(linea)] == ["escritor"]


def test_el_orquestador_corre_con_un_modelo_fijado(monkeypatch, proyecto, config):
    """El orquestador no redacta: llama verbos y despacha subagentes, y heredaba el modelo de la cuenta.

    En la tanda del 17/09 eso fueron 5,76 $ de 8,05 (72 %) para un trabajo mecánico, más que todo lo
    que costó escribir la novela. Los subagentes declaran su modelo aparte, así que fijarlo acá no
    cambia con qué se escribe el texto.
    """
    import os as _os
    capturado = {}

    class _Proc:
        pid = 1234

        def poll(self):
            return None

    def _popen(cmd, **kw):
        capturado["cmd"] = cmd
        return _Proc()

    skill = proyecto / ".claude" / "skills" / "generar-premisa"
    skill.mkdir(parents=True, exist_ok=True)
    (skill / "SKILL.md").write_text(
        "---\nname: generar-premisa\nallowed-tools: Read, Write\n---\n\n# Fase 1\nEscribí la premisa.\n",
        encoding="utf-8")

    monkeypatch.setattr(_os, "name", "posix")  # sin la comprobación de Git Bash, que es de Windows
    monkeypatch.setattr(web, "ejecutable_claude", lambda: "claude.exe")
    monkeypatch.setattr(web.subprocess, "Popen", _popen)
    web._EN_CURSO.clear()
    web.lanzar_fase(proyecto, "generar-premisa")
    cmd = capturado["cmd"]
    assert "--model" in cmd and cmd[cmd.index("--model") + 1] == web.MODELO_ORQUESTADOR
    web._EN_CURSO.clear()


def test_la_tanda_autoriza_edit_para_que_el_reintento_no_reescriba_el_capitulo(proyecto, config):
    """Spec-X 01: el escritor corrige los pasajes de RF-05.5 con Edit, no reescribiendo 1.400 palabras.

    La skill no lo autorizaba, así que el Edit se denegaba y el escritor caía en Write: se midió en una
    tanda real, con los dos Edit denegados en el log del lanzamiento. H-06 confina el Edit al capítulo
    del escritor igual que el Write, así que autorizarlo no amplía a dónde puede escribir.
    """
    from app.hooks import HERRAMIENTAS_ESCRITURA
    assert "Edit" in HERRAMIENTAS_ESCRITURA, "sin esto, autorizar Edit daría una escritura sin valla"
    skill = Path(__file__).resolve().parents[1] / ".claude" / "skills" / "escribir-tanda" / "SKILL.md"
    herramientas = web._herramientas(skill.read_text(encoding="utf-8"))
    assert "Edit" in herramientas and "Write" in herramientas


def test_las_directivas_se_resuelven_sin_shell(proyecto, config):
    """`cat`, `ls -1` y su alternativa `|| echo`, sin pasar por bash ni por PowerShell."""
    (proyecto / "hay.txt").write_text("contenido", encoding="utf-8")
    assert web._resolver_directiva(proyecto, "cat hay.txt") == "contenido"
    assert web._resolver_directiva(proyecto, 'cat no.txt 2>/dev/null || echo "(no está)"') == "(no está)"
    assert web._resolver_directiva(proyecto, 'ls -1 no_existe 2>/dev/null || echo "(vacía)"') == "(vacía)"


def test_ningun_campo_de_ejecucion_se_pierde_al_guardar():
    """El encargo del corredor pasa por el formulario: lo que no llegue aquí se apaga en silencio.

    `aristas_en_continuidad` se añadió a CAMPOS_EJECUCION y no a `_ejecucion_desde_formulario`, que
    enumeraba las claves a mano. Como una casilla desmarcada llega ausente y ausente vale False, el
    interruptor se apagaba al guardar y la vuelta del loop habría corrido como su propio control.
    """
    from app.config import CAMPOS_EJECUCION
    from app.corredor import campos_de_encargo
    from app.ui import _ejecucion_desde_formulario

    encendidos = {c: True for c in CAMPOS_EJECUCION if c not in ("capitulos_por_tanda", "max_llamadas_por_tanda")}
    campos = campos_de_encargo({"idea": "x", "config": {**encendidos, "capitulos_por_tanda": 3}})
    guardado = _ejecucion_desde_formulario(campos)

    assert set(guardado) == set(CAMPOS_EJECUCION), "hay campos de ejecución que el formulario no guarda"
    for clave in encendidos:
        assert guardado[clave] is True, f"{clave} llegó encendido al formulario y se guardó apagado"


def test_el_formulario_suelto_pinta_todos_los_interruptores(proyecto):
    """Pintaba uno de los cinco a mano, así que guardar ahí apagaba los otros cuatro sin avisar."""
    html = ui.render_formulario(ui.estado_formulario(proyecto))
    for clave, valor in ui.DEFAULTS.items():
        if isinstance(valor, bool):
            assert f"name='{clave}'" in html, f"{clave} no tiene casilla: guardar aquí lo apagaría"
