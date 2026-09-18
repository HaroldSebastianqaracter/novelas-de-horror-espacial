"""Interfaz de línea de comandos (spec técnica §8.2).

Capa externa: status · resolver · ensamblar · archivar · guardar · ui · exportar-traza (RF-09, después de la tanda).
Capa interna (la usa la skill /escribir-tanda, un tramo del loop por verbo): tanda · preparar-capitulo ·
registrar-escritor · aplicar-delta · descartar-borrador · preparar-qa · cerrar-qa.
Capa de validación (la ejecuta cada agente sobre su propio artefacto, RF-08.4): validar-capitulo ·
validar-delta · validar-reporte. Solo lectura; el verbo que aplica vuelve a validar.

Convención de salida: líneas legibles y, al final, `RESULTADO: <clave> [campo=valor ...]` para que la skill
decida el paso siguiente sin interpretar prosa. Errores: `ERROR <Tipo>: motivo` por stderr y código 1.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import warnings
from pathlib import Path

import time

from app import archivo, registro, validacion
from app.agents import extractor as ag_extractor, qa as ag_qa
from app.config import HarnessConfig, cargar_config, cargar_proveedores
from app.errores import ConfiguracionInvalidaError, EstadoInvalidoError, HarnessError, PausadoPorQAError
from app.orchestrator import checkpoint, cursor as cur, loop
from app.rutas import Rutas, raiz_desde_entorno
from app.schemas import FichaPersonajes, LogContinuidad, Mundo, Outline
from app.state import continuidad as cont
from app.state import personajes as pers
from app.state import repository as repo

ARTEFACTOS = ("idea", "style_guide", "premisa", "tres_actos", "outline", "personajes", "mundo", "continuidad")


def _formatear_valor(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    return json.dumps(v, ensure_ascii=False)


def _resultado(clave: str, **campos) -> None:
    extra = " ".join(f"{k}={_formatear_valor(v)}" for k, v in campos.items())
    print(f"RESULTADO: {clave}" + (f" {extra}" if extra else ""))


def _leer_entrada(args) -> str:
    if getattr(args, "desde", None):
        return Path(args.desde).read_text(encoding="utf-8")
    datos = sys.stdin.read()
    if not datos.strip():
        raise ConfiguracionInvalidaError("no se recibió contenido ni por --desde ni por stdin")
    return datos


def _config(raiz: Path, override: int | None = None) -> HarnessConfig:
    return cargar_config(raiz, capitulos_por_tanda=override)


# ---------- capa externa ----------

def cmd_status(args, raiz: Path) -> int:
    print(checkpoint.texto_status(raiz))
    try:
        config = _config(raiz)
        print(f"- configuración: {config.total_capitulos} capítulos x {config.palabras_por_capitulo} palabras · "
              f"{config.idioma} · {config.persona_narrativa} · {config.tiempo_verbal} · cadencia_qa {config.cadencia_qa} · "
              f"tanda {config.capitulos_por_tanda or 'hasta el final'} · tope llamadas {config.max_llamadas_por_tanda or 'sin tope'}")
    except HarnessError as e:
        print(f"- configuración: {e}")
    proveedores = cargar_proveedores(raiz)
    if proveedores.get("estado"):
        print(f"- proveedores.json: {proveedores['estado']}")
    cursor = cur.leer(raiz)
    if cursor:
        print(f"- tanda en curso: inicio {cursor.inicio}, cerrados {cursor.cerrados}, tope {cursor.tope or 'sin tope'}, llamadas {cursor.llamadas}")
    from app import hooks  # import tardío: hooks importa validacion y agentes

    aviso = hooks.aviso_h11(raiz)
    if aviso:
        print(aviso)
    print(registro.texto_status(raiz))  # RF-08.5: el registro de la última tanda, no solo el manifiesto
    return 0


def cmd_ensamblar(args, raiz: Path) -> int:
    """Concatena los capítulos cerrados con su título (§8.2). Solo lee 05_manuscrito/ y capitulos.json."""
    rutas = Rutas(raiz)
    m = checkpoint.exigir_manifest(raiz)
    outline = repo.leer_outline(raiz)
    if outline is None:
        raise EstadoInvalidoError("no existe capitulos.json; no hay títulos que anteponer")
    partes: list[str] = []
    titulo_novela = _titulo_desde_premisa(repo.leer_premisa(raiz))
    if titulo_novela:
        partes.append(f"# {titulo_novela}\n")
    for n in range(1, m.ultimo_capitulo_cerrado + 1):
        entrada = outline.entrada(n)
        titulo = entrada.titulo if entrada else f"Capítulo {n}"
        partes.append(f"## {n}. {titulo}\n\n{repo.leer_manuscrito(raiz, n).strip()}\n")
    salida = Path(args.salida)
    if not salida.is_absolute():
        salida = raiz / salida
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text("\n".join(partes) + ("\n" if partes else ""), encoding="utf-8")
    print(f"{m.ultimo_capitulo_cerrado} capítulos ensamblados en {salida}")
    _resultado("ensamblado", capitulos=m.ultimo_capitulo_cerrado, salida=str(salida))
    return 0


def cmd_archivar(args, raiz: Path) -> int:
    """Guarda la novela terminada en 09_archivo/ y deja el árbol listo para la siguiente.

    No borra nada: mueve. Por eso no exige que git tenga el trabajo confirmado, al contrario que el
    botón de borrar de la pantalla.
    """
    r = archivo.archivar(raiz, nombre=args.nombre, forzar=args.forzar)
    resumen = r["resumen"]
    reloj, calidad = resumen["reloj"], resumen["calidad"]
    print(f"archivada en {r['carpeta']} ({r['entradas']} entradas movidas)")
    print(f"- {resumen['capitulos']['cerrados']} capítulos cerrados, palabras {resumen['capitulos']['palabras']}")
    if reloj["total_s"] is not None:
        print(f"- reloj: {reloj['total_s'] / 60:.1f} min "
              f"(preludio {(reloj['preludio_s'] or 0) / 60:.1f}, tandas {(reloj['tandas_s'] or 0) / 60:.1f})")
    for rol, fila in resumen["agentes"].items():
        print(f"  · {rol}: {fila['invocaciones']} invocaciones, {fila['segundos'] / 60:.1f} min, "
              f"{fila['tokens_salida']} tokens de salida")
    print(f"- calidad: {calidad['contradicciones']} contradicciones en {calidad['cortes_qa']} cortes, "
          f"{calidad['reintentos_de_escritor']} reintentos de escritor")
    _resultado("archivado", carpeta=r["carpeta"], capitulos=resumen["capitulos"]["cerrados"],
               segundos=reloj["total_s"], contradicciones=calidad["contradicciones"])
    return 0


def _titulo_desde_premisa(texto: str) -> str | None:
    m = re.search(r"(?im)^#*\s*\**\s*t[íi]tulo\s*\**\s*[:\-]\s*(.+?)\s*$", texto)
    if m:
        return m.group(1).strip().strip("*").strip()
    m = re.search(r"(?im)^#+\s*t[íi]tulo\s*$\n+\s*(.+?)\s*$", texto)
    return m.group(1).strip() if m else None


def cmd_resolver(args, raiz: Path) -> int:
    """RF-07.4 + RF-07.6 en tres pasos (§8.2)."""
    rutas = Rutas(raiz)
    m = checkpoint.exigir_manifest(raiz)
    if args.cerrar:
        if args.reporte or args.capitulos or args.sin_cambios:
            raise ConfiguracionInvalidaError("--cerrar no se combina con --reporte, --capitulos ni --sin-cambios")
        if m.estado != "pausado_por_qa":
            raise PausadoPorQAError("no hay ninguna pausa por QA que cerrar")
        nuevo = checkpoint.cerrar_resolucion(raiz)
        print(f"reporte resuelto; manifiesto en {nuevo.estado}")
        _resultado("resuelto", estado=nuevo.estado)
        return 0

    if not args.reporte:
        raise ConfiguracionInvalidaError("indicá --reporte qa_cap_N (o --cerrar para el paso 3)")
    if bool(args.capitulos) == bool(args.sin_cambios):
        raise ConfiguracionInvalidaError("--capitulos y --sin-cambios son mutuamente excluyentes y uno es obligatorio: el harness no adivina qué se corrigió")
    if m.estado != "pausado_por_qa":
        raise PausadoPorQAError(f"el manifiesto está en {m.estado}; no hay pausa por QA que resolver")
    if args.reporte != m.reporte_qa_pendiente:
        raise PausadoPorQAError(f"el reporte pendiente es {m.reporte_qa_pendiente}, no {args.reporte}")
    if m.reextraccion_pendiente:
        raise PausadoPorQAError(f"ya hay una resolución en curso con capítulos pendientes {m.reextraccion_pendiente}; corré /resolver-qa y luego --cerrar")
    n_reporte = int(args.reporte.split("_")[-1])
    if not rutas.reporte_qa_json(n_reporte).exists():
        raise EstadoInvalidoError(f"no existe {rutas.reporte_qa_json(n_reporte).as_posix()}")

    if args.sin_cambios:
        checkpoint.iniciar_resolucion(raiz, args.reporte, [])
        nuevo = checkpoint.cerrar_resolucion(raiz)
        print("revisado sin cambios: nada que reextraer; manifiesto en en_progreso")
        _resultado("resuelto", estado=nuevo.estado)
        return 0

    capitulos = sorted({int(c) for c in args.capitulos.split(",") if c.strip()})
    for c in capitulos:
        if c < 1 or c > m.ultimo_capitulo_cerrado:
            raise ConfiguracionInvalidaError(f"el capítulo {c} no está cerrado (último cerrado: {m.ultimo_capitulo_cerrado})")
        if not rutas.capitulo(c).exists():
            raise EstadoInvalidoError(f"no existe {rutas.capitulo(c).as_posix()}")
    log = cont.marcar_superado(repo.leer_continuidad(raiz), capitulos)
    repo.escribir_continuidad(raiz, log)  # INV-03: marca, no borra
    nuevo = checkpoint.iniciar_resolucion(raiz, args.reporte, capitulos)
    superados = sum(1 for h in log.root if h.cap_origen in capitulos and h.superado_por is not None)
    print(f"{superados} hechos marcados como superados; reextracción pendiente: {nuevo.reextraccion_pendiente}")
    print("paso 2: corré /resolver-qa para reextraer cada capítulo; paso 3: `python -m app resolver --cerrar`")
    _resultado("reextraccion_pendiente", capitulos=nuevo.reextraccion_pendiente, capitulo_activo=nuevo.capitulo_activo)
    return 0


def cmd_guardar(args, raiz: Path) -> int:
    """Fases 0-4: persiste con validación (EX-01) lo que generó la skill. Rechaza tocar artefactos inmutables con capítulos cerrados."""
    rutas = Rutas(raiz)
    rutas.crear_carpetas()
    contenido = _leer_entrada(args)
    m = checkpoint.leer_manifest(raiz)
    cerrados = m.ultimo_capitulo_cerrado if m else 0
    artefacto = args.artefacto

    if artefacto in ("outline", "personajes", "mundo", "continuidad", "style_guide", "tres_actos", "premisa") and cerrados > 0:
        raise EstadoInvalidoError(f"INV-04: {artefacto} es inmutable con {cerrados} capítulos cerrados")

    if artefacto == "idea":
        if not contenido.strip():
            raise EstadoInvalidoError("RF-01.1: la idea no puede estar vacía")
        repo.escribir_texto(rutas.idea, contenido)
        destino = rutas.idea
    elif artefacto == "style_guide":
        _verificar_style_guide(rutas, contenido)
        repo.escribir_texto(rutas.style_guide, contenido)
        destino = rutas.style_guide
    elif artefacto == "premisa":
        faltan = [c for c in ("t[íi]tulo", "logline", "premisa") if not re.search(rf"(?im)^\W*{c}\b", contenido)]
        if faltan:
            raise EstadoInvalidoError(f"RF-01.1: premisa.md debe llevar título, logline y premisa; faltan: {faltan}")
        if not _titulo_desde_premisa(contenido):
            raise EstadoInvalidoError("RF-01.1: el título está vacío o no tiene la forma `Título: ...`")
        repo.escribir_texto(rutas.premisa, contenido)
        destino = rutas.premisa
    elif artefacto == "tres_actos":
        faltan = [c for c in ("gancho", "punto medio", "cl[íi]max") if not re.search(rf"(?i){c}", contenido)]
        if faltan:
            raise EstadoInvalidoError(f"RF-02.1: tres_actos.md debe nombrar gancho inicial, punto medio y clímax/final; faltan: {faltan}")
        repo.escribir_texto(rutas.tres_actos, contenido)
        destino = rutas.tres_actos
    elif artefacto == "outline":
        config = _config(raiz)
        outline = repo.validar_texto(contenido, Outline, "capitulos.json")
        if len(outline) != config.total_capitulos:
            raise EstadoInvalidoError(f"RF-CFG-01: el outline tiene {len(outline)} entradas y total_capitulos es {config.total_capitulos}")
        if not outline.tension_maxima_en_tercio_final():
            raise EstadoInvalidoError("RF-03.2: el máximo de tension debe ocurrir en el tercio final del outline")
        repo.escribir_outline(raiz, outline)
        if m is None:
            checkpoint.crear_manifest(raiz, len(outline))
        else:
            checkpoint.escribir_manifest(raiz, m.model_copy(update={"total_capitulos_esperado": len(outline)}))
        destino = rutas.capitulos
    elif artefacto == "personajes":
        fichas = repo.validar_texto(contenido, FichaPersonajes, "personajes.json")
        outline = repo.leer_outline(raiz)
        if outline is None:
            raise EstadoInvalidoError("RF-04.1: primero hay que guardar el outline")
        faltan = pers.sin_ficha(fichas, outline)
        if faltan:
            raise EstadoInvalidoError(f"RF-04.1: personajes del outline sin ficha: {faltan}")
        repo.escribir_personajes(raiz, fichas)
        destino = rutas.personajes
    elif artefacto == "mundo":
        mundo = repo.validar_texto(contenido, Mundo, "mundo.json")
        outline = repo.leer_outline(raiz)
        if outline is None:
            raise EstadoInvalidoError("RF-04.2: primero hay que guardar el outline")
        faltan = [l for l in outline.locaciones_mencionadas() if l not in mundo.locaciones]
        if faltan:
            raise EstadoInvalidoError(f"RF-04.2: locaciones del outline ausentes de mundo.json: {faltan}")
        if not (mundo.reglas or mundo.objetos or mundo.linea_de_tiempo):
            raise EstadoInvalidoError("RF-04.2: mundo.json no puede estar vacío")
        repo.escribir_mundo(raiz, mundo)
        destino = rutas.mundo
    elif artefacto == "continuidad":
        log = repo.validar_texto(contenido, LogContinuidad, "continuidad.json")
        if repo.leer_continuidad(raiz).root:
            raise EstadoInvalidoError("RF-04.3: continuidad.json ya tiene hechos; después de la fase 4 solo crece por extracción")
        registro = pers.sujetos_conocidos(repo.leer_personajes(raiz), repo.leer_mundo(raiz))
        malos = [h for h in log.root if h.cap_origen != 0]
        if malos:
            raise EstadoInvalidoError("RF-04.3: los hechos iniciales llevan cap_origen = 0 (derivados de la premisa, previos al capítulo 1)")
        absolutos = cont.absolutos_que_la_trama_desmentira(log)
        if absolutos:
            detalle = "; ".join(f"«{h[:90]}» ({motivo})" for h, motivo in absolutos)
            raise EstadoInvalidoError(
                "RF-04.3: hay hechos iniciales escritos como ley del mundo, y son los que la novela "
                f"tiene que desmentir para tener giro: {detalle}. Reformulalos como lo que un "
                "registro recoge, lo que alguien sabe o lo que se ha medido. «No hay ningún pasillo "
                "entre la bodega y la sala de máquinas» cierra la puerta al capítulo que lo "
                "encuentra; «los planos de a bordo no recogen ningún pasillo entre la bodega y la "
                "sala de máquinas» es cierto para siempre y no cierra ninguna.")
        hechos = [cont.validar_sujeto(h, registro) for h in log.root]
        repo.escribir_continuidad(raiz, LogContinuidad(hechos))
        destino = rutas.continuidad
        if not rutas.resumen_rodante.exists():
            repo.escribir_resumen_rodante(raiz, "")
    else:
        raise ConfiguracionInvalidaError(f"artefacto desconocido: {artefacto}; opciones: {', '.join(ARTEFACTOS)}")

    print(f"{artefacto} guardado en {destino.relative_to(raiz).as_posix()}")
    _resultado("guardado", artefacto=artefacto, ruta=destino.relative_to(raiz).as_posix())
    return 0


def _verificar_style_guide(rutas: Rutas, contenido: str) -> None:
    """RF-00.1: ninguna oración copiada literalmente de los ejemplos (ventanas de 30+ caracteres, RF-00.2)."""
    if not contenido.strip():
        raise EstadoInvalidoError("RF-00.1: style_guide.md no puede estar vacío")
    referencias = [p for p in rutas.referencias.glob("**/*") if p.is_file() and p.suffix.lower() in (".md", ".txt")]
    if not referencias:
        warnings.warn("RF-00.2: 00_referencias/ está vacía; la verificación de copia literal no es ejecutable")
        return
    corpus = " ".join(re.sub(r"\s+", " ", p.read_text(encoding="utf-8", errors="replace")).lower() for p in referencias)
    normalizado = re.sub(r"\s+", " ", contenido).lower()
    for i in range(0, max(1, len(normalizado) - 30), 10):
        ventana = normalizado[i:i + 31]
        if len(ventana) >= 31 and ventana in corpus:
            raise EstadoInvalidoError(f"RF-00.2: style_guide.md contiene texto literal de las referencias: {ventana!r}")


# ---------- capa interna ----------

def cmd_tanda(args, raiz: Path) -> int:
    if args.accion == "iniciar":
        if args.capitulos is not None and args.hasta_el_final:
            raise ConfiguracionInvalidaError("--capitulos y --hasta-el-final son excluyentes")
        config = _config(raiz, args.capitulos)
        cursor = loop.iniciar_tanda(raiz, config, args.capitulos, args.hasta_el_final)
        decision = loop.evaluar_siguiente(raiz, config, cursor)
        print(f"tanda iniciada desde el capítulo {cursor.inicio}; tope {cursor.tope or 'hasta el final'}; "
              f"tope de llamadas {cursor.max_llamadas or 'sin tope'}")
        if decision.motivo != "seguir":
            cur.borrar(raiz, decision.motivo)
            _resultado(decision.motivo, cerrados=0)
        else:
            _resultado("seguir", siguiente=decision.siguiente)
        return 0
    config = _config(raiz)
    resultado = loop.tanda_siguiente(raiz, config)
    for aviso in resultado.avisos:
        print(f"aviso: {aviso}")
    if resultado.motivo == "seguir":
        _resultado("seguir", siguiente=resultado.siguiente, cerrados=resultado.cerrados)
    else:
        print(f"fin de tanda: {resultado.motivo}; capítulos cerrados en esta tanda: {resultado.cerrados}")
        _resultado(resultado.motivo, cerrados=resultado.cerrados)
    return 0


def cmd_preparar_capitulo(args, raiz: Path) -> int:
    config = _config(raiz)
    contexto = loop.preparar_capitulo(raiz, config, args.n, args.feedback)
    rutas = Rutas(raiz)
    print(f"contexto del capítulo {args.n}: {contexto.tokens_estimados} tokens estimados ({contexto.metodo_estimacion}) "
          f"de {contexto.limite}; {len(contexto.hechos_inyectados)} hechos inyectados; "
          f"{contexto.recursos_inyectados} recursos narrativos agotados (RF-05.5)"
          + ("; resumen rodante recortado (EX-04)" if contexto.resumen_recortado else ""))
    print(f"prompt en {rutas.prompt_escritor(args.n).relative_to(raiz).as_posix()}; el escritor debe escribir "
          f"{rutas.capitulo(args.n).relative_to(raiz).as_posix()}; prompt del extractor en "
          f"{rutas.prompt_extractor(args.n).relative_to(raiz).as_posix()}")
    _resultado("contexto_listo", n=args.n, prompt=rutas.prompt_escritor(args.n).relative_to(raiz).as_posix(),
               prompt_extractor=rutas.prompt_extractor(args.n).relative_to(raiz).as_posix(),
               tokens=contexto.tokens_estimados, hechos=len(contexto.hechos_inyectados))
    return 0


def cmd_preparar_extractor(args, raiz: Path) -> int:
    config = _config(raiz)
    path = loop.preparar_extractor(raiz, config, args.n)
    print(f"prompt del extractor para el capítulo {args.n} en {path.relative_to(raiz).as_posix()}")
    _resultado("extractor_listo", n=args.n, prompt=path.relative_to(raiz).as_posix())
    return 0


def cmd_registrar_escritor(args, raiz: Path) -> int:
    config = _config(raiz)
    with warnings.catch_warnings(record=True) as avisos:
        warnings.simplefilter("always")
        r = loop.registrar_escritor(raiz, config, args.n, args.linea)
    for a in avisos:
        print(f"aviso: {a.message}")
    print(f"cap_{r.n}.md: {r.palabras} palabras" + ("" if r.dentro_de_rango else f"; {r.mensaje}"))
    if r.reintentar:
        _resultado("reintentar_longitud", n=r.n, palabras=r.palabras, feedback=r.mensaje)
    else:
        _resultado("borrador_aceptado", n=r.n, palabras=r.palabras, dentro_de_rango=r.dentro_de_rango)
    return 0


def cmd_aplicar_delta(args, raiz: Path) -> int:
    config = _config(raiz)
    if args.retorno is not None:  # RF-08.1: la línea de confirmación del extractor, si el orquestador la pasa
        registro.guardar_retorno(raiz, "extractor", args.n, args.retorno)  # §5.1: el retorno textual, valga o no
        retorno = ag_extractor.parsear_retorno_extractor(args.retorno)
        if retorno.n != args.n:
            raise EstadoInvalidoError(f"RF-08.1: el extractor declaró delta_cap_{retorno.n}.json y el capítulo es {args.n}")
    texto = Path(args.desde).read_text(encoding="utf-8") if args.desde else None
    r = loop.aplicar_delta(raiz, config, args.n, texto, reextraccion=args.reextraccion)
    if r.regenerar:
        print(f"EX-08: personajes fuera del registro en delta.personajes: {r.claves_no_previstas}; regenerar el capítulo {r.n}")
        _resultado("regenerar_capitulo", n=r.n, claves=r.claves_no_previstas)
        return 0
    if r.sujetos_no_validados:
        print(f"aviso: hechos con sujeto fuera del registro (se conservan con sujeto_validado=false): {r.sujetos_no_validados}")
    if args.reextraccion:
        m = checkpoint.exigir_manifest(raiz)
        print(f"capítulo {r.n} reextraído: {r.hechos_agregados} hechos nuevos; pendientes: {m.reextraccion_pendiente}")
        _resultado("reextraido", n=r.n, pendientes=m.reextraccion_pendiente)
        return 0
    print(f"capítulo {r.n} cerrado: {r.hechos_agregados} hechos nuevos" + ("; toca corte de QA" if r.toca_qa else ""))
    _resultado("capitulo_cerrado", n=r.n, toca_qa=r.toca_qa)
    return 0


def cmd_descartar_borrador(args, raiz: Path) -> int:
    loop.descartar_borrador(raiz, args.n)
    print(f"borrador del capítulo {args.n} descartado")
    _resultado("borrador_descartado", n=args.n)
    return 0


def cmd_preparar_qa(args, raiz: Path) -> int:
    config = _config(raiz)
    prep = loop.preparar_qa(raiz, config, args.n)
    rutas = Rutas(raiz)
    print(f"corte de QA en el capítulo {prep.n}; muestra: capítulos {prep.caps_muestra}")
    print(f"prompt en {rutas.prompt_qa(prep.n).relative_to(raiz).as_posix()}")
    _resultado("qa_listo", n=prep.n, muestra=prep.caps_muestra, prompt=rutas.prompt_qa(prep.n).relative_to(raiz).as_posix())
    return 0


def cmd_cerrar_qa(args, raiz: Path) -> int:
    config = _config(raiz)
    if args.retorno is not None:  # RF-08.1: el resumen de hasta cinco líneas de QA, si el orquestador lo pasa
        registro.guardar_retorno(raiz, "qa", args.n, args.retorno)  # §5.1
        ag_qa.parsear_retorno_qa(args.retorno)
    r = loop.cerrar_qa(raiz, config, args.n)
    conteo = r.reporte.conteo_por_tipo()
    print(f"QA cap. {r.reporte.cap_corte}: {conteo['contradiccion']} contradicciones, {conteo['repeticion']} repeticiones; "
          f"entropía bigramas {r.metricas['entropia_bigramas']}, tasa de conflicto {r.metricas['tasa_conflicto']}")
    if r.pausado:
        print("EX-02: la tanda queda pausada hasta que el usuario resuelva el reporte (RF-07.4)")
        _resultado("pausado_por_qa", n=r.reporte.cap_corte, reporte=f"qa_cap_{r.reporte.cap_corte}")
    else:
        _resultado("qa_sin_contradicciones", n=r.reporte.cap_corte, repeticiones=conteo["repeticion"])
    return 0


def cmd_ui(args, raiz: Path) -> int:
    from app import ui  # import tardío: es lo único que levanta un servidor (§15)

    return ui.servir(raiz, args.puerto)


def cmd_exportar_traza(args, raiz: Path) -> int:
    """RF-09 / §16: publica el registro de una tanda en Langfuse, después de la tanda y nunca dentro de ella."""
    from app import observabilidad  # import tardío: es lo único que habla por red

    carpeta = observabilidad.resolver_tanda(raiz, args.tanda)
    volcar = Path(args.volcar) if args.volcar else None
    if volcar is not None and not volcar.is_absolute():
        volcar = raiz / volcar
    cliente = None
    if not args.solo_volcar:
        cliente = observabilidad.ClienteHTTP(observabilidad.credenciales_desde_entorno())  # §16.7: falla antes de leer nada
    elif volcar is None:
        raise ConfiguracionInvalidaError("--solo-volcar exige --volcar <archivo>: sin destino no hay nada que hacer")
    r = observabilidad.exportar(raiz, carpeta, cliente, con_cuerpos=args.con_cuerpos, volcar=volcar)
    t = r.traza
    print(f"tanda {t.tanda} -> trace {t.id} ({'con' if t.con_cuerpos else 'sin'} cuerpos de prompts y retornos)")
    print(f"metadatos: {json.dumps(t.metadatos, ensure_ascii=False)}")
    print(f"{len(t.capitulos)} capítulos (spans), {len(t.generaciones)} invocaciones (generations), {t.eventos} eventos, "
          f"{len(t.puntuaciones)} puntuaciones; {len(t.lote)} objetos de ingesta")
    print(observabilidad.tabla_consumo(t))
    print("puntuaciones: " + ", ".join(f"{k}={v}" for k, v in t.puntuaciones.items()))
    if r.volcado is not None:
        print(f"lote volcado en {r.volcado}")
    if cliente is None:
        _resultado("volcado", tanda=t.tanda, trace_id=t.id, objetos=len(t.lote), archivo=str(r.volcado))
        return 0
    print(f"publicado en {cliente.credenciales.host}: {r.aceptados} objetos aceptados en {r.lotes} lote(s)")
    _resultado("exportado", tanda=t.tanda, trace_id=t.id, objetos=len(t.lote), aceptados=r.aceptados, lotes=r.lotes)
    return 0


# ---------- capa de validación (RF-08.4): la ejecuta el agente sobre su propio artefacto ----------

def _imprimir_validacion(r: validacion.ResultadoValidacion, raiz: Path, n: int) -> int:
    """Solo lectura: comprueba y devuelve el error, nunca corrige ni persiste. Código 1 si no valida."""
    registro.evento(raiz, "validacion", rol=r.rol, artefacto=r.artefacto, valido=r.valido, errores=r.errores,
                    avisos=r.avisos or None, datos=r.datos or None, capitulo=n)  # §5.1; `datos` alimenta desvio_longitud (§16.4)
    for aviso in r.avisos:
        print(f"aviso: {aviso}")
    if r.valido:
        datos = " ".join(f"{k}={_formatear_valor(v)}" for k, v in r.datos.items())
        print(f"{r.artefacto} valida" + (f" ({datos})" if datos else ""))
        _resultado("valido", rol=r.rol, artefacto=r.artefacto, **r.datos)
        return 0
    print(f"{r.artefacto} NO valida; corregí exactamente esto y volvé a ejecutar el mismo comando:")
    for i, error in enumerate(r.errores, 1):
        print(f"  {i}. {error}")
    _resultado("invalido", rol=r.rol, artefacto=r.artefacto, errores=r.errores)
    return 1


def cmd_validar_capitulo(args, raiz: Path) -> int:
    return _imprimir_validacion(validacion.validar_capitulo(raiz, _config(raiz), args.n), raiz, args.n)


def cmd_validar_delta(args, raiz: Path) -> int:
    return _imprimir_validacion(validacion.validar_delta(raiz, _config(raiz), args.n), raiz, args.n)


def cmd_validar_reporte(args, raiz: Path) -> int:
    return _imprimir_validacion(validacion.validar_reporte(raiz, args.n), raiz, args.n)


# ---------- parser ----------

def construir_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m app", description="Harness generador de novelas de terror espacial")
    p.add_argument("--raiz", help="raíz del proyecto (por defecto HARNESS_RAIZ, CLAUDE_PROJECT_DIR o el directorio actual)")
    sub = p.add_subparsers(dest="comando", required=True)

    sub.add_parser("status", help="manifiesto, cursor si existe, ultimo_error; no genera nada").set_defaults(fn=cmd_status)

    r = sub.add_parser("resolver", help="RF-07.4 + RF-07.6 en tres pasos")
    r.add_argument("--reporte")
    r.add_argument("--capitulos", help="capítulos corregidos, separados por coma")
    r.add_argument("--sin-cambios", action="store_true")
    r.add_argument("--cerrar", action="store_true")
    r.set_defaults(fn=cmd_resolver)

    e = sub.add_parser("ensamblar", help="concatena los capítulos cerrados con su título")
    e.add_argument("--salida", required=True)
    e.set_defaults(fn=cmd_ensamblar)

    a = sub.add_parser("archivar", help="cierra la novela: la mueve a 09_archivo/ con su resumen y vacía el árbol")
    a.add_argument("--nombre", help="nombre de la carpeta; por defecto sale del título de la premisa")
    a.add_argument("--forzar", action="store_true", help="archiva aunque haya una tanda en curso o QA pausado")
    a.set_defaults(fn=cmd_archivar)

    g = sub.add_parser("guardar", help="fases 0-4: persiste con validación un artefacto generado por la skill")
    g.add_argument("artefacto", choices=ARTEFACTOS)
    g.add_argument("--desde", help="archivo con el contenido; si falta, se lee stdin")
    g.set_defaults(fn=cmd_guardar)

    u = sub.add_parser("ui", help="formulario local de entrada (§15)")
    u.add_argument("--puerto", type=int, default=8765)
    u.set_defaults(fn=cmd_ui)

    x = sub.add_parser("exportar-traza", help="RF-09: publica el registro de una tanda en Langfuse (después de la tanda, nunca dentro)")
    x.add_argument("tanda", help="carpeta de 07_registro/ (tanda_<ts>) o `ultima`")
    x.add_argument("--con-cuerpos", action="store_true", help="incluye prompts y retornos (§16.6); por defecto no sale prosa")
    x.add_argument("--volcar", help="además, escribe el lote de ingesta completo en este archivo JSON")
    x.add_argument("--solo-volcar", action="store_true", help="no publica: solo escribe el archivo de --volcar (nada sale de la máquina)")
    x.set_defaults(fn=cmd_exportar_traza)

    t = sub.add_parser("tanda", help="verbos del cursor de tanda")
    t.add_argument("accion", choices=("iniciar", "siguiente"))
    t.add_argument("--capitulos", type=int, help="pisa capitulos_por_tanda del archivo (RF-CFG-03)")
    t.add_argument("--hasta-el-final", action="store_true")
    t.set_defaults(fn=cmd_tanda)

    pc = sub.add_parser("preparar-capitulo")
    pc.add_argument("n", type=int)
    pc.add_argument("--feedback", help="desvío de longitud del intento anterior (EX-07)")
    pc.set_defaults(fn=cmd_preparar_capitulo)

    pe = sub.add_parser("preparar-extractor", help="prompt del extractor para el capítulo en curso o uno en reextracción")
    pe.add_argument("n", type=int)
    pe.set_defaults(fn=cmd_preparar_extractor)

    re_ = sub.add_parser("registrar-escritor")
    re_.add_argument("n", type=int)
    re_.add_argument("linea", help="línea de retorno del escritor (RF-08.1)")
    re_.set_defaults(fn=cmd_registrar_escritor)

    ad = sub.add_parser("aplicar-delta")
    ad.add_argument("n", type=int)
    ad.add_argument("--reextraccion", action="store_true", help="RF-07.6 paso 2")
    ad.add_argument("--desde", help="archivo con el JSON; por defecto 04_estado/deltas/delta_cap_N.json")
    ad.add_argument("--retorno", help="línea de retorno del extractor (RF-08.1); se valida antes de aplicar")
    ad.set_defaults(fn=cmd_aplicar_delta)

    db = sub.add_parser("descartar-borrador")
    db.add_argument("n", type=int)
    db.set_defaults(fn=cmd_descartar_borrador)

    pq = sub.add_parser("preparar-qa")
    pq.add_argument("n", type=int)
    pq.set_defaults(fn=cmd_preparar_qa)

    cq = sub.add_parser("cerrar-qa")
    cq.add_argument("n", type=int)
    cq.add_argument("--retorno", help="mensaje final de QA, hasta cinco líneas (RF-08.1); se valida antes de cerrar")
    cq.set_defaults(fn=cmd_cerrar_qa)

    for verbo, fn, ayuda in (("validar-capitulo", cmd_validar_capitulo, "escritor: longitud ±20 %, solo prosa, personajes en escena"),
                             ("validar-delta", cmd_validar_delta, "extractor: esquema, sujetos, tope de hechos"),
                             ("validar-reporte", cmd_validar_reporte, "qa: esquema de ReporteQA y recursos_usados.json")):
        v = sub.add_parser(verbo, help=f"RF-08.4, solo lectura; {ayuda}")
        v.add_argument("n", type=int)
        v.set_defaults(fn=fn)
    return p


def main(argv: list[str] | None = None) -> int:
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8")
        except Exception:
            pass
    args = construir_parser().parse_args(argv)
    raiz = Path(args.raiz).resolve() if args.raiz else raiz_desde_entorno()
    argumentos = [a for a in (argv if argv is not None else sys.argv[1:]) if a != args.comando]
    inicio = time.perf_counter()
    resultado = "ok"
    try:
        codigo = args.fn(args, raiz)
        if codigo not in (0, None):
            resultado = f"codigo {codigo}"
        return codigo
    except (HarnessError, FileNotFoundError) as e:
        print(f"ERROR {type(e).__name__}: {e}", file=sys.stderr)
        resultado = f"error {type(e).__name__}"
        _registrar_error_seguro(raiz, e, args)
        return 1
    finally:
        if args.comando != "ui":  # el formulario no es un tramo de la tanda
            _registrar_verbo_seguro(raiz, args.comando, argumentos, resultado, int((time.perf_counter() - inicio) * 1000),
                                    getattr(args, "n", None))


def _registrar_verbo_seguro(raiz: Path, verbo: str, argumentos: list[str], resultado: str, ms: int, capitulo: int | None) -> None:
    """Evento `verbo` (§5.1). El registro nunca hace fallar al verbo que registra."""
    try:
        registro.evento(raiz, "verbo", verbo=verbo, args=argumentos, resultado=resultado, ms=ms, capitulo=capitulo)
    except Exception as e:  # noqa: BLE001
        print(f"[registro] no se pudo anotar el verbo {verbo}: {e}", file=sys.stderr)


def _registrar_error_seguro(raiz: Path, e: BaseException, args) -> None:
    """Evento `error` con traza (§5.1): quien detiene la tanda lo deja escrito."""
    try:
        registro.evento_error(raiz, e, verbo=args.comando, capitulo=getattr(args, "n", None))
    except Exception as e2:  # noqa: BLE001
        print(f"[registro] no se pudo anotar el error: {e2}", file=sys.stderr)
