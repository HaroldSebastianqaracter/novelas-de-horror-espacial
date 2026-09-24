"""El paquete del redactor y la escritura de su prosa en el grafo.

Este es el paquete que la arquitectura describe bloque a bloque. Todo lo que entra, entra
porque el orquestador lo selecciono; el agente no busca canon por su cuenta y no tiene
herramientas con las que hacerlo.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from compartido import politica
from compartido.brief import describir_intensidad, linea_destinatario
from compartido.contexto import Elemento, Paquete, Presupuesto, ajustar
from compartido.grafo import insertar, lectura
from compartido.texto import cuenta_personas
from compartido.tipos import como_dict, como_lista

from .esquemas import SalidaRedaccion

AGENTE = "redaccion"


def _instrucciones(con: sqlite3.Connection, novela_id: int, capitulo: int) -> str:
    n = lectura.novela(con, novela_id) or {}
    e = lectura.estilo(con, novela_id) or {}
    tics = lectura.tics_prohibidos(con, novela_id)
    lineas = [
        f"Escribes el capitulo {capitulo} de «{n.get('titulo', '')}».",
        f"Punto de vista por defecto: {n.get('pov_por_defecto', '')}. "
        f"Tiempo verbal: {n.get('tiempo_verbal', '')}.",
        "",
        "ESTILO NARRATIVO (constante en toda la obra):",
        f"- Registro: {e.get('registro', '')}",
        f"- Ritmo de prosa: {e.get('ritmo_prosa', '')}",
        f"- Densidad sensorial: {e.get('densidad_sensorial', '')}",
        f"- Distancia psiquica por defecto: {e.get('distancia_psiquica', '')}",
    ]
    if e.get("convenciones_formato"):
        lineas.append(f"- Convenciones de formato: {e['convenciones_formato']}")
    if tics:
        lineas += ["", "TICS PROHIBIDOS (una sola aparicion devuelve el capitulo entero):"]
        lineas.extend(f"- {t}" for t in tics)
    # spec3, RF3-GRD-03: lo que la puerta 4 va a buscar, para no descubrirlo fallando.
    vetadas = [r.termino for r in politica.reglas(con, novela_id) if r.origen != "brief"]
    if vetadas:
        lineas += ["", "PALABRAS VETADAS (una sola aparicion devuelve el capitulo entero): "
                   + ", ".join(vetadas) + "."]
    fijados = lectura.cambios_aplicados(con, novela_id)
    if fijados:
        # spec3, RF3-CAM-14: sin esto, relanzar tras un cambio podia volver al valor viejo.
        lineas += ["", "LO QUE FIJO EL LECTOR (respetalo siempre): " + " ".join(fijados)]
    brief = lectura.brief(con, novela_id)
    if brief is not None:
        # RF3-PER-03: el protagonista es una persona real y la novela es su regalo.
        lineas += [
            "", "LA NOVELA ES UN REGALO.", linea_destinatario(brief),
            "Escribe su nombre siempre exactamente asi. Sobrevive a la novela.",
        ]
        if brief.intensidad is not None:
            lineas.append(describir_intensidad(brief.intensidad))
        if brief.vetados:
            lineas.append(f"No puede aparecer, de ninguna forma: {', '.join(brief.vetados)}.")
        lineas.append(
            "Los elementos personales de cada escena se integran con naturalidad: que el "
            "destinatario se reconozca, sin que el recuerdo se note pegado."
        )
    return "\n".join(lineas)


def _escaleta(escenas: list[dict[str, Any]]) -> str:
    bloques: list[str] = []
    for e in escenas:
        partes = [
            f"### Escena {e['orden']}"
            + (" (ANALEPSIS: ocurre antes en la cronologia)" if e["analepsis"] else ""),
            f"- POV: {e['pov_nombre']}",
            f"- Lugar: {e['lugar_nombre']}",
            f"- Reparto: {', '.join(e['reparto'])}",
            f"- Objetivo: {e['objetivo']}",
            f"- Conflicto: {e['conflicto']}",
            f"- Resultado: {e['resultado']}",
            f"- Valor en juego: {e['valor_inicial']} -> {e['valor_final']}",
            f"- Tension: {e['tension']}/10",
            f"- Longitud prevista: {e['longitud_prevista']} palabras",
        ]
        if e.get("gancho_salida"):
            partes.append(f"- Gancho de salida: {e['gancho_salida']}")
        if e.get("objetos"):
            partes.append(f"- Objetos presentes: {', '.join(e['objetos'])}")
        if e.get("elementos"):
            partes.append(
                "- Elementos personales que integra (a cada allegado, por su nombre al menos una "
                "vez en la escena; su parentesco solo no basta): " + "; ".join(e["elementos"])
            )
        if e.get("beats"):
            partes.append("- Beats: " + " | ".join(b["cambio"] for b in e["beats"]))
        if e.get("secuela"):
            s = e["secuela"]
            partes.append(
                f"- Secuela: reacciona {s['reaccion']}; duda entre {s['dilema']}; "
                f"decide {s['decision']}"
            )
        bloques.append("\n".join(partes))
    return "\n\n".join(bloques)


_SECCION_PERSONAJES = "### Personajes"
_SECCION_LUGARES = "### Lugares"
_SECCION_AMENAZA = "### La amenaza (sus reglas no se rompen nunca)"
_SECCION_SISTEMAS = "### Sistemas tecnicos (sus limites no se rompen)"
_SECCION_OBJETOS = "### Objetos"
_SECCION_FACCIONES = "### Facciones"
_SECCION_MENORES = "### Nombres menores ya usados"
_SECCION_OTROS = (
    "### Otros personajes que ya han salido (la escaleta no los pone en este capitulo; si la "
    "prosa trae a alguno, que sea como aqui)"
)


def _personaje(p: dict[str, Any]) -> str:
    # RF3-BIB-07: la edad, para que la prosa no la contradiga. Nula en novelas anteriores.
    edad = f", {p['edad']} años" if p.get("edad") is not None else ""
    return (
        f"**{p['nombre']}** ({p['rol_narrativo']}{edad}). Desea {p['deseo']}. "
        f"Necesita {p['necesidad_interna']}. Defecto visible: {p['defecto']}. "
        f"Cree que {p['mentira']}.\nIdiolecto: {p['idiolecto']}"
        + (f"\nGuarda: {p['secreto']}" if p.get("secreto") else "")
    )


def _amenaza(a: dict[str, Any]) -> str:
    try:
        reglas: Any = json.loads(a.get("reglas") or "[]")
    except json.JSONDecodeError:
        reglas = []
    lineas = [str(a["naturaleza"])]
    lineas.extend(
        f"- Puede {r.get('capacidad', '')}. No puede {r.get('limite', '')}. "
        f"Se activa con {r.get('activacion', '')}."
        for r in map(como_dict, como_lista(reglas)) if r
    )
    return "\n".join(lineas)


def _canon(canon: dict[str, list[dict[str, Any]]]) -> list[Elemento]:
    """El canon del capitulo como elementos, de mas a menos relevante (RF2-CTX-11).

    Obligatorios: los personajes que son POV de alguna escena y los lugares de las escenas.
    Opcionales, en el orden en que se recortarian desde el final: el resto del reparto por
    apariciones, la amenaza, los sistemas, los objetos y las facciones.
    """
    pov = [p for p in canon["personajes"] if int(p.get("escenas_pov") or 0) > 0]
    resto = [p for p in canon["personajes"] if int(p.get("escenas_pov") or 0) == 0]
    elementos = [Elemento(_personaje(p), True, _SECCION_PERSONAJES) for p in pov]
    elementos += [
        Elemento(f"**{lugar['nombre']}** ({lugar['tipo']}). {lugar['descripcion']}", True,
                 _SECCION_LUGARES)
        for lugar in canon["lugares"]
    ]
    elementos += [Elemento(_personaje(p), False, _SECCION_PERSONAJES) for p in resto]
    elementos += [Elemento(_amenaza(a), False, _SECCION_AMENAZA) for a in canon["amenaza"]]
    elementos += [
        Elemento(
            f"**{s['nombre']}**. Puede: {s['capacidades']}. Cuesta: {s['costes']}. "
            f"Limites: {s['limites']}", False, _SECCION_SISTEMAS,
        )
        for s in canon["sistemas"]
    ]
    elementos += [
        Elemento(f"**{o['nombre']}**: {o['funcion_narrativa']}", False, _SECCION_OBJETOS)
        for o in canon["objetos"]
    ]
    elementos += [
        Elemento(f"**{f['nombre']}**: {f.get('proposito') or ''}", False, _SECCION_FACCIONES)
        for f in canon["facciones"]
    ]
    return elementos


_SECCION_HECHOS = "### Hechos ya establecidos (no los contradigas)"
_SECCION_CENSO = "### Censo: las cuentas de personas"
#: Cuantos datos de personas entran como mucho, los mas recientes primero (con los de mundo
#: delante, como los ordena `hechos_hasta`).
MAX_DATOS_DE_CENSO = 30
_REGLA_DEL_CENSO = (
    "Toda cifra de personas que escribas (cuantos hay, llegan, se van, se quedan, mueren) "
    "cuadra con este censo. Antes de escribirla, haz la suma: los que tienen nombre mas los "
    "anonimos que cuentan los datos. Si alguien se va o muere en una escena, el total que queda "
    "baja desde ahi. Quien esta lejos (por radio, en otra nave) no cuenta entre los presentes. "
    "Si una escena no cuenta personas, no hace falta que lo haga."
)
_SECCION_CONOCIMIENTO = "### Quien sabe que (nadie puede actuar sobre lo que no ha recibido)"


def _hechos(hechos: list[dict[str, Any]], conocimiento: list[dict[str, Any]]) -> list[Elemento]:
    """Hechos y conocimiento como elementos: obligatorios delante, opcionales al final.

    El conocimiento del reparto es obligatorio entero (RF2-CTX-11), asi que lo unico que se
    puede recortar son los hechos opcionales, en el orden de `lectura.hechos_del_reparto`: los
    de quien esta fuera del reparto, despues los de objetos y facciones, y los de amenaza, mundo
    y novela al final, cada grupo empezando por los mas antiguos.
    """
    def linea(h: dict[str, Any]) -> str:
        return (f"- {h['sujeto_nombre']} · {h['atributo']}: {h['valor']} "
                f"(cap. {h['capitulo_origen']})")

    elementos = [Elemento(linea(h), True, _SECCION_HECHOS) for h in hechos if h["obligatorio"]]
    elementos += [
        Elemento(
            f"- {c['personaje']} {c['postura']} que {c['sujeto_nombre']} · {c['atributo']}: "
            f"{c['valor']} (desde cap. {c['capitulo']}, {c['via']})",
            True, _SECCION_CONOCIMIENTO,
        )
        for c in conocimiento
    ]
    elementos += [
        Elemento(linea(h), False, _SECCION_HECHOS) for h in hechos if not h["obligatorio"]
    ]
    return elementos


def _censo(con: sqlite3.Connection, novela_id: int, capitulo: int) -> list[Elemento]:
    """Las cuentas de personas del canon, para no sumar de memoria (spec3, RF3-PAS-16).

    Solo si el canon ya cuenta personas: sin ningun dato asi, los nombres ya estan en el canon
    del capitulo y el bloque no aportaria nada.
    """
    datos = [
        h for h in lectura.hechos_hasta(con, novela_id, capitulo)
        if cuenta_personas(f"{h['atributo']} {h['valor']}")
    ][:MAX_DATOS_DE_CENSO]
    if not datos:
        return []
    personajes = lectura.censo_de_personajes(con, novela_id, capitulo)

    def estado(c: dict[str, Any]) -> str:
        if c["condicion"] is None:
            return "sin nada registrado"
        return f"{c['condicion']} (desde el cap. {c['capitulo_condicion']})"

    return [
        Elemento(_REGLA_DEL_CENSO, True, _SECCION_CENSO),
        Elemento("Con nombre: " + "; ".join(
            f"{c['nombre']} ({c['rol_narrativo']}), {estado(c)}" for c in personajes
        ) + ".", True, _SECCION_CENSO),
        *(Elemento(f"- {h['sujeto_nombre']} · {h['atributo']}: {h['valor']} "
                   f"(cap. {h['capitulo_origen']})", True, _SECCION_CENSO) for h in datos),
    ]


def paquete(
    con: sqlite3.Connection,
    novela_id: int,
    capitulo: int,
    *,
    presupuesto: Presupuesto,
    criterios_incumplidos: list[dict[str, str]] | None = None,
    recuperado: list[Any] | None = None,
) -> Paquete:
    """Monta el paquete del capitulo y lo ajusta al presupuesto (RF2-CTX-01)."""
    escenas = lectura.escenas_del_capitulo(con, novela_id, capitulo)
    canon = lectura.canon_del_capitulo(con, novela_id, capitulo)
    cap = lectura.capitulo(con, novela_id, capitulo) or {}

    p = Paquete(agente=AGENTE, capitulo=capitulo)
    p.anadir("instrucciones", _instrucciones(con, novela_id, capitulo), "TU ENCARGO Y EL ESTILO")

    cabecera = [
        f"Objetivo del capitulo: {cap.get('objetivo', '')}",
        f"Gancho de apertura: {cap.get('gancho_apertura', '')}",
        f"Gancho de cierre: {cap.get('gancho_cierre', '')}",
    ]
    p.anadir(
        "escaleta",
        "\n".join(cabecera) + "\n\n" + _escaleta(escenas),
        f"ESCALETA DEL CAPITULO {capitulo}",
    )
    elementos_canon = _canon(canon)
    # RF3-PAS-10: quien ya salio y la escaleta no pone aqui. Si el redactor lo trae, que sea
    # como es; opcional, se recorta antes que el reparto.
    elementos_canon += [
        Elemento(_personaje(p), False, _SECCION_OTROS)
        for p in lectura.personajes_fuera_del_reparto(con, novela_id, capitulo)
    ]
    menores = lectura.nombres_menores(con, novela_id, capitulo)
    if menores:
        # RF3-PAS-05: lo que el redactor invento antes y nadie mantenia. Opcional: se recorta
        # antes que el canon de verdad.
        elementos_canon.append(Elemento(
            "Nombres que ya aparecieron en capitulos anteriores (si vuelves a usar alguno, "
            "escribelo exactamente asi): " + ", ".join(menores),
            False, _SECCION_MENORES,
        ))
    p.anadir_elementos("canon", elementos_canon, "CANON DE ESTE CAPITULO", separador="\n\n")
    p.anadir_elementos(
        "hechos",
        # El censo va delante y es obligatorio: sin el, el redactor rehace la suma de memoria
        # en cada intento y a veces se equivoca (novela de tres capitulos, RF3-PAS-16).
        _censo(con, novela_id, capitulo) + _hechos(
            lectura.hechos_del_reparto(con, novela_id, capitulo),
            lectura.conocimiento_del_reparto(con, novela_id, capitulo),
        ),
        "ESTADO ESTABLECIDO",
    )

    siembras = lectura.siembras_vivas(con, novela_id, capitulo)
    if siembras:
        p.anadir(
            "siembras",
            "\n".join(
                f"- [{s['estado']}] {s['elemento']}"
                + (f" (pago previsto hacia el cap. {s['capitulo_pago_previsto']})"
                   if s["capitulo_pago_previsto"] else "")
                for s in siembras
            ),
            "SIEMBRAS VIVAS",
        )

    # El estado rodante se lee en orden cronologico y se recorta por lo mas antiguo.
    rodante = lectura.estado_rodante(con, novela_id, capitulo)
    p.anadir_elementos(
        "estado_rodante",
        [
            Elemento(f"Capitulo {f['numero']}: {f['texto']}", posicion=f["numero"])
            for f in reversed(rodante)
        ],
        "LO QUE HA PASADO HASTA AQUI",
    )
    if capitulo > 1:
        # Primero en caer, y antes de perder parrafos se sustituye por su resumen (RF-CTX-01).
        parrafos = [x for x in lectura.texto_capitulo(con, novela_id, capitulo - 1).split("\n\n")]
        anterior = lectura.capitulo(con, novela_id, capitulo - 1) or {}
        p.anadir_elementos(
            "capitulo_anterior",
            [Elemento(x, posicion=i) for i, x in reversed(list(enumerate(parrafos)))],
            f"TEXTO DEL CAPITULO {capitulo - 1}",
            separador="\n\n",
            alternativa=[Elemento(
                f"(Resumen: el texto completo no cabe.) {anterior.get('resumen') or ''}"
            )] if anterior.get("resumen") else None,
        )

    if recuperado:
        p.anadir_elementos(
            "recuperado",
            [
                Elemento(f"[cap. {f.capitulo}, escena {f.orden}, {f.lugar}]\n{f.texto}")
                for f in recuperado
            ],
            "COMO SE DESCRIBIO ESTO ANTES (no lo repitas ni lo contradigas)",
            separador="\n\n",
        )

    if criterios_incumplidos:
        p.anadir(
            "criterios_incumplidos",
            "\n\n".join(
                f"**{c['criterio']}** (principio {c.get('principio', '')}): "
                f"{c.get('sugerencia', '')}\nEvidencia del intento anterior: "
                f"«{c.get('evidencia', '')}»"
                for c in criterios_incumplidos
            ),
            "LO QUE FALLO EN EL INTENTO ANTERIOR. Reescribe desde la escaleta, no parchees",
        )

    return ajustar(p, presupuesto)


def aplicar(
    con: sqlite3.Connection,
    novela_id: int,
    capitulo: int,
    salida: SalidaRedaccion,
    *,
    intento: int = 1,
    llamada_id: int | None = None,
) -> dict[int, int]:
    """Guarda una version nueva del texto de cada escena. Nunca hace UPDATE (RF-PER-05).

    Devuelve {orden de escena: escena_id}, que es lo que el extractor necesita para referirse
    a las escenas por su numero.
    """
    escenas = lectura.escenas_del_capitulo(con, novela_id, capitulo)
    salida.comprobar_contra_escaleta([e["orden"] for e in escenas])
    por_orden = {int(e["orden"]): int(e["id"]) for e in escenas}

    for escrita in salida.escenas:
        escena_id = por_orden[escrita.orden]
        # Las versiones anteriores dejan de ser vigentes; no se borran, son historia legible.
        con.execute(
            "UPDATE escena_texto SET estado = 'descartada' WHERE escena_id = ? "
            "AND estado = 'vigente'",
            (escena_id,),
        )
        version = int(con.execute(
            "SELECT COALESCE(MAX(version), 0) + 1 FROM escena_texto WHERE escena_id = ?",
            (escena_id,),
        ).fetchone()[0])
        insertar(
            con, "escena_texto", novela_id=novela_id, escena_id=escena_id, version=version,
            texto=escrita.texto, palabras=escrita.palabras, origen="redaccion",
            intento=intento, estado="vigente", llamada_modelo_id=llamada_id,
        )
    return por_orden


def compilar(con: sqlite3.Connection, novela_id: int, capitulo: int) -> int:
    """Concatena las versiones vigentes en orden y guarda el capitulo compilado."""
    filas = con.execute(
        """
        SELECT et.texto FROM escena_texto et
        JOIN escena e   ON e.id = et.escena_id
        JOIN capitulo c ON c.id = e.capitulo_id
        WHERE et.novela_id = ? AND c.numero = ? AND et.estado = 'vigente'
        ORDER BY e.orden
        """,
        (novela_id, capitulo),
    ).fetchall()
    texto = "\n\n* * *\n\n".join(str(f["texto"]) for f in filas)
    cap = lectura.capitulo(con, novela_id, capitulo) or {}
    capitulo_id = int(cap["id"])

    con.execute(
        "UPDATE capitulo_compilado SET estado = 'descartada' WHERE capitulo_id = ? "
        "AND estado = 'vigente'",
        (capitulo_id,),
    )
    version = int(con.execute(
        "SELECT COALESCE(MAX(version), 0) + 1 FROM capitulo_compilado WHERE capitulo_id = ?",
        (capitulo_id,),
    ).fetchone()[0])
    return insertar(
        con, "capitulo_compilado", novela_id=novela_id, capitulo_id=capitulo_id,
        version=version, texto=texto, palabras=len(texto.split()), estado="vigente",
    )
