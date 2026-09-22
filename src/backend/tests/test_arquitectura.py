"""Las reglas de docs/architecture.md, como comprobaciones ejecutables.

Es la propiedad 1 del plan de verificacion, con etiqueta `A`: analisis estatico del arbol de
imports. La arquitectura dice que dos reglas sostienen el corte vertical y que el dia que una
tarea importe de otra el corte ha dejado de existir. Una regla que nadie comprueba se rompe
sola, asi que aqui esta comprobada.
"""

from __future__ import annotations

import ast
import sqlite3
import tempfile
from pathlib import Path

from compartido import db
from compartido.tipos import AGENTES

RAIZ = Path(__file__).resolve().parents[1]
DIR_TAREAS = RAIZ / "tareas"
DIR_COMPARTIDO = RAIZ / "compartido"


def _modulos(carpeta: Path) -> list[Path]:
    return [p for p in carpeta.rglob("*.py") if ".venv" not in p.parts]


def _imports(fichero: Path) -> list[str]:
    arbol = ast.parse(fichero.read_text(encoding="utf-8"), filename=str(fichero))
    nombres: list[str] = []
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            nombres.extend(a.name for a in nodo.names)
        elif isinstance(nodo, ast.ImportFrom):
            if nodo.level:  # import relativo: se resuelve contra su propio paquete
                partes = fichero.relative_to(RAIZ).parts[:-1]
                base = partes[: len(partes) - nodo.level + 1]
                nombres.append(".".join([*base, nodo.module or ""]).rstrip("."))
            elif nodo.module:
                nombres.append(nodo.module)
    return nombres


# --- Corte vertical (RF-COD-03) ------------------------------------------------------------


def test_una_tarea_no_importa_de_otra() -> None:
    """El dia que una tarea importe de otra, el corte vertical ha dejado de existir."""
    fallos: list[str] = []
    for tarea in sorted(p.name for p in DIR_TAREAS.iterdir() if p.is_dir()):
        for fichero in _modulos(DIR_TAREAS / tarea):
            for nombre in _imports(fichero):
                if not nombre.startswith("tareas."):
                    continue
                otra = nombre.split(".")[1]
                if otra != tarea:
                    fallos.append(f"{fichero.relative_to(RAIZ)} importa de tareas.{otra}")
    assert not fallos, "Una tarea importa de otra:\n" + "\n".join(fallos)


# docs/architecture.md nombra DIEZ agentes. El decimo, `revision`, queda fuera de la v1
# (spec1.md, 1.2): las pasadas globales dependen de la revalidacion en cascada, que a su vez
# exige dependencias entre hechos que definitions.md todavia no modela. Se declara aqui para
# que la ausencia sea una divergencia escrita y no un olvido.
AGENTES_ARQUITECTURA = (*AGENTES, "revision")
FUERA_DE_LA_V1 = frozenset({"revision"})


def test_la_lista_de_carpetas_es_la_lista_de_agentes() -> None:
    """La arquitectura dice que la lista de carpetas es la lista de agentes."""
    carpetas = {p.name for p in DIR_TAREAS.iterdir() if p.is_dir() and p.name != "__pycache__"}
    esperadas = set(AGENTES_ARQUITECTURA) - FUERA_DE_LA_V1
    assert carpetas == esperadas, (
        f"Carpetas sin agente: {sorted(carpetas - esperadas)}; "
        f"agentes sin carpeta: {sorted(esperadas - carpetas)}"
    )


def test_cada_agente_de_la_v1_tiene_su_skill() -> None:
    """Cada agente se materializa como una skill de Claude Code, y el puerto la exige."""
    skills = RAIZ.parents[1] / ".claude" / "skills"
    faltan = [a for a in AGENTES if not (skills / a / "SKILL.md").is_file()]
    assert not faltan, f"Agentes sin SKILL.md: {faltan}"


def test_las_skills_tienen_la_forma_que_pide_la_spec() -> None:
    """RF-SKILL-02: cada SKILL.md lleva que produce, con que criterio, que no hace y el
    formato de salida. Sin la ultima seccion el puerto recibe texto en vez de JSON."""
    skills = RAIZ.parents[1] / ".claude" / "skills"
    fallos: list[str] = []
    for agente in AGENTES:
        texto = (skills / agente / "SKILL.md").read_text(encoding="utf-8").lower()
        if not texto.startswith("---") or "description:" not in texto:
            fallos.append(f"{agente}: sin cabecera con description")
        for seccion in ("## qué no haces", "## formato de salida"):
            if seccion not in texto:
                fallos.append(f"{agente}: falta la seccion '{seccion}'")
        if "únicamente" not in texto:
            fallos.append(f"{agente}: no exige devolver unicamente el objeto JSON")
        if "no tienes herramientas" not in texto:
            fallos.append(f"{agente}: no declara que el agente no tiene herramientas")
    assert not fallos, "Skills mal formadas:\n" + "\n".join(fallos)


def test_ninguna_skill_de_agente_es_la_de_desarrollo() -> None:
    """RF-SKILL-03: `verificacion` sirve para construir el sistema, no forma parte de el."""
    assert "verificacion" not in AGENTES


# --- El borde HTTP (RF-COD-04, RF-COD-05) ---------------------------------------------------


def test_fastapi_solo_en_los_router() -> None:
    """FastAPI es el borde HTTP: no llama al modelo, no orquesta y no toca el grafo."""
    fallos: list[str] = []
    for fichero in [*_modulos(DIR_TAREAS), *_modulos(DIR_COMPARTIDO), *_modulos(RAIZ / "tests")]:
        if fichero.name in ("router.py", "main.py"):
            continue
        for nombre in _imports(fichero):
            if nombre.split(".")[0] in ("fastapi", "starlette"):
                fallos.append(f"{fichero.relative_to(RAIZ)} importa {nombre}")
    assert not fallos, "FastAPI fuera de los router.py:\n" + "\n".join(fallos)


def test_los_router_no_invocan_al_modelo_ni_orquestan() -> None:
    """La API no puede invocar a Claude Code ni por accidente: el orquestador vive en el
    worker y la API ni lo importa."""
    fallos: list[str] = []
    for fichero in [*DIR_TAREAS.rglob("router.py"), RAIZ / "main.py"]:
        if not fichero.exists():
            continue
        for nombre in _imports(fichero):
            if "puerto" in nombre or "orquestador" in nombre:
                fallos.append(f"{fichero.relative_to(RAIZ)} importa {nombre}")
    assert not fallos, "Un router alcanza el puerto o el orquestador:\n" + "\n".join(fallos)


def test_el_worker_no_importa_fastapi() -> None:
    worker = RAIZ / "worker.py"
    if not worker.exists():
        return
    assert not any(n.startswith("fastapi") for n in _imports(worker))


# --- Presupuesto de contexto ---------------------------------------------------------------


def test_el_paquete_cabe_en_el_techo_de_contexto() -> None:
    """100.000 tokens por llamada es la restriccion que da forma al pipeline."""
    import config

    suma = sum(config.PRESUPUESTO_BLOQUES.values())
    assert suma == config.PRESUPUESTO_PAQUETE, (
        f"El reparto por bloques suma {suma} y el total declarado es "
        f"{config.PRESUPUESTO_PAQUETE}"
    )
    assert suma < 100_000, "El paquete no deja sitio para la salida del agente."
    reserva = 100_000 - suma
    assert reserva >= 20_000, f"Solo quedan {reserva} tokens para la salida del agente."


def test_los_bloques_fijos_no_estan_en_el_orden_de_recorte() -> None:
    import config

    solapan = set(config.BLOQUES_FIJOS) & set(config.ORDEN_DE_RECORTE)
    assert not solapan, f"Estos bloques son fijos y a la vez recortables: {sorted(solapan)}"

    conocidos = set(config.PRESUPUESTO_BLOQUES)
    assert set(config.BLOQUES_FIJOS) <= conocidos
    assert set(config.ORDEN_DE_RECORTE) <= conocidos
    sin_clasificar = conocidos - set(config.BLOQUES_FIJOS) - set(config.ORDEN_DE_RECORTE)
    assert not sin_clasificar, f"Bloques sin politica de recorte: {sorted(sin_clasificar)}"


def test_el_capitulo_anterior_cae_antes_que_el_canon() -> None:
    """La arquitectura fija la prioridad: el texto del capitulo anterior es el primero en
    caer, y el canon no se trunca nunca sin haber recortado antes lo elastico."""
    import config

    orden = list(config.ORDEN_DE_RECORTE)
    assert orden[0] == "capitulo_anterior"
    assert orden.index("estado_rodante") < orden.index("canon")
    assert orden.index("canon") < orden.index("hechos")


# --- Persistencia --------------------------------------------------------------------------


def _con() -> sqlite3.Connection:
    return db.preparar(Path(tempfile.mkdtemp()) / "novela.db")


def test_estan_todas_las_tablas_que_nombra_la_arquitectura() -> None:
    esperadas = {
        # Canon
        "novela", "restriccion", "mundo", "sistema_tecnologico", "lugar", "personaje",
        "faccion", "amenaza", "objeto", "linea_de_tiempo", "tema", "motivo",
        "estilo_narrativo",
        # Estructura
        "acto", "capitulo", "secuencia", "escena", "secuela", "beat", "punto_de_giro",
        "hilo", "siembra",
        # Estado
        "hecho", "estado_conocimiento", "estado_personaje", "estado_objeto", "evento",
        # Texto
        "escena_texto", "capitulo_compilado",
        # Cola y traza
        "intencion", "ejecucion", "llamada_modelo", "resultado_puerta",
    }
    con = _con()
    presentes = {
        f[0] for f in con.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    faltan = esperadas - presentes
    assert not faltan, f"Tablas de la arquitectura que no existen: {sorted(faltan)}"


def test_el_estado_es_append_only_con_escena_de_origen() -> None:
    """Es lo que hace que revertir al capitulo N sea borrar por escena de origen."""
    con = _con()
    for tabla in (
        "hecho", "estado_conocimiento", "uso_conocimiento", "estado_personaje",
        "estado_objeto", "siembra_estado", "hilo_estado", "amenaza_revelacion",
        "entidad_no_reconocida",
    ):
        columnas = {f["name"] for f in con.execute(f"PRAGMA table_info({tabla})")}
        assert "escena_id" in columnas, f"{tabla} no registra su escena de origen"


def test_lo_que_cambia_durante_la_redaccion_no_es_columna_mutable() -> None:
    """Siembra.estado, HiloNarrativo.estado y Amenaza.nivelRevelacion se derivan de su tabla
    de estado. Como columnas, un UPDATE de prosa podria alterarlas sin dejar rastro."""
    con = _con()
    for tabla, columna in (
        ("siembra", "estado"),
        ("hilo", "estado"),
        ("amenaza", "nivel_revelacion"),
        ("lugar", "presencia_actual"),
    ):
        columnas = {f["name"] for f in con.execute(f"PRAGMA table_info({tabla})")}
        assert columna not in columnas, (
            f"{tabla}.{columna} es una columna mutable; deberia derivarse de su tabla de estado"
        )


def test_el_texto_se_versiona_y_no_se_actualiza() -> None:
    con = _con()
    for tabla in ("escena_texto", "capitulo_compilado"):
        columnas = {f["name"] for f in con.execute(f"PRAGMA table_info({tabla})")}
        assert "version" in columnas and "estado" in columnas


def test_la_api_no_puede_escribir() -> None:
    """El worker escribe, la API solo lee. Lo impone el motor, no la disciplina."""
    ruta = Path(tempfile.mkdtemp()) / "novela.db"
    db.preparar(ruta)
    solo_lectura = db.conectar(ruta, solo_lectura=True)
    try:
        solo_lectura.execute("INSERT INTO novela (titulo) VALUES ('x')")
        raise AssertionError("La conexion de solo lectura ha dejado escribir")
    except sqlite3.OperationalError:
        pass


def test_wal_y_busy_timeout() -> None:
    con = _con()
    assert con.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    assert int(con.execute("PRAGMA busy_timeout").fetchone()[0]) > 0
    assert int(con.execute("PRAGMA foreign_keys").fetchone()[0]) == 1
