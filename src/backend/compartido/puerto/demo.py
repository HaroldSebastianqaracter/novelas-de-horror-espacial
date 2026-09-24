"""Generadores de salida para PuertoFalso: un pipeline entero sin gastar dinero.

No pretenden escribir bien. Pretenden producir salidas **validas** para que el orquestador,
las puertas y la persistencia se puedan ejercitar de punta a punta, que es lo que dice
RF-PUERTO-07: el pipeline debe correr sin Claude Code instalado.

Viven aqui y no en `tests/` porque correr el pipeline sin Claude Code es una capacidad del
sistema, no una comodidad de la suite: es lo que permite arrancar el worker con
NOVELAS_PUERTO=falso y ver el pipeline entero funcionando.
"""

from __future__ import annotations

import re
from typing import Any

from config import CRITERIOS_OFICIO

LUGARES = ["Puente", "Modulo de carga", "Esclusa"]
PERSONAJES = ["Idris", "Vaan", "Reyes"]
OBJETO = "Baliza"
TICS = ["de repente", "sin previo aviso"]

CAPITULOS = 3
ESCENAS_POR_CAPITULO = 2
#: Un valor que la prosa repite tal cual en cada escena: el extractor lo fija una vez y el
#: resto de escenas lo usan por mencion (RF3-BIB-01).
DISTANCIA_A_LA_ESCLUSA = "doce metros"


def _ordenes(entrada: str) -> list[int]:
    """Saca los numeros de escena del paquete, que es como los ve el agente real."""
    return sorted({int(n) for n in re.findall(r"### Escena (\d+)", entrada)})


def _objetivo_palabras(entrada: str, defecto: int = 5400) -> int:
    """Lee el presupuesto del paquete, como haria el agente real."""
    m = re.search(r"PRESUPUESTO: (\d+) palabras", entrada)
    return int(m.group(1)) if m else defecto


def _capitulo(entrada: str) -> int:
    m = re.search(r"ESCALETA DEL CAPITULO (\d+)", entrada) or re.search(
        r"capitulo (\d+)", entrada
    )
    return int(m.group(1)) if m else 1


# --- Lo que un agente real leeria del encargo en su paquete (specs/spec3.md, 3.2) -------------


def _destinatario(entrada: str) -> str | None:
    """El nombre del destinatario si la novela es un regalo (la marca de compartido.brief)."""
    m = re.search(r"DESTINATARIO \(protagonista, nombre exacto\): (.+?) \(\d+ años", entrada)
    return m.group(1).strip() if m else None


def _edad_destinatario(entrada: str) -> int | None:
    """La edad del destinatario, que es la del protagonista (RF3-BIB-06)."""
    m = re.search(r"DESTINATARIO \(protagonista, nombre exacto\): .+? \((\d+) años", entrada)
    return int(m.group(1)) if m else None


def _reparto(entrada: str) -> list[str]:
    """El reparto de la demo: con encargo, el destinatario ocupa el sitio del protagonista."""
    return [_destinatario(entrada) or PERSONAJES[0], *PERSONAJES[1:]]


def _capitulos_pedidos(entrada: str) -> int:
    m = re.search(r"CAPITULOS: exactamente (\d+)", entrada)
    return int(m.group(1)) if m else CAPITULOS


def _codigos(entrada: str) -> list[str]:
    """Los codigos de los elementos personales que la escaleta tiene que repartir."""
    return re.findall(r"^- ((?:RAS|REC|ALL)\d+) \(", entrada, re.MULTILINE)


def _allegados(entrada: str) -> list[tuple[str, str]]:
    bloque = entrada.split("Allegados que tienen que ser personajes", 1)
    if len(bloque) < 2:
        return []
    return re.findall(r"^- (.+?) \((.+?)\)", bloque[1].split("\n\n", 1)[0], re.MULTILINE)


def arquitecto(entrada: str, agente: str) -> dict[str, Any]:
    nombre = _destinatario(entrada)
    subgenero = re.search(r"Subgenero fijado por el encargo: (\w+)", entrada)
    salida = _arquitecto_base()
    if nombre is not None:
        salida["pregunta_dramatica"] = f"?Saldra {nombre} de la estacion sin perderse a si misma?"
        salida["dedicatoria"] = f"Para {nombre}, que nunca deja un problema a medias."
        # Con encargo, un subgenero que quepa en cualquier intensidad salvo que venga fijado.
        salida["subgenero_dominante"] = subgenero.group(1) if subgenero else "horror_cosmico"
        salida["tipo_final"] = "abierto"
    return salida


def _arquitecto_base() -> dict[str, Any]:
    return {
        "premisa": "Mantener un cuerpo vivo a cualquier precio acaba costando la voluntad.",
        "logline": "Una soldadora de casco llega a una estacion muda y descubre que lo que "
                   "respira dentro ya no es su tripulacion.",
        "pregunta_dramatica": "?Saldra Idris de la estacion sin repetir lo que hizo?",
        "tema_central": "El deber frente a la perdida",
        "subgenero_dominante": "terror_corporal",
        "tipo_final": "victoria_pirrica",
        "pov_por_defecto": "tercera_limitada",
        "tiempo_verbal": "pasado",
        "titulo_propuesto": "Cerro Quince",
        "temas": [{
            "pregunta_central": "?Es salvar un cuerpo lo mismo que salvar a la persona?",
            "verdad_tematica": "Un cuerpo conservado sin consentimiento no es un rescate.",
        }],
        "motivos": [{
            "simbolo": "El sellante de casco",
            "significado_inicial": "Herramienta que cierra una fuga.",
            "significado_final": "Instrumento que devuelve el contorno matando.",
        }],
        "estilo": {
            "registro": "sobrio y tecnico",
            "ritmo_prosa": "frases medias con cortes bruscos en tension",
            "densidad_sensorial": "alta en olfato y temperatura",
            "distancia_psiquica": "cercana, con retiradas al abrir escena",
            "tics_prohibidos": TICS,
            "convenciones_formato": "raya de dialogo",
        },
    }


def mundo(entrada: str, agente: str) -> dict[str, Any]:
    return {
        "mundo": {
            "nombre": "Estacion Cerro Quince",
            "geografia": "Tres cubiertas en anillo alrededor de un nucleo de carga.",
            "historia": "Reabastecimiento de rutas largas; muda desde hace ocho meses.",
            "culturas": "Cuadrillas de mantenimiento por turnos.",
            "reglas_fisicas": "Sin atmosfera fuera del casco. El sonido no se propaga.",
        },
        "sistemas": [{
            "nombre": "Soporte vital",
            "capacidades": "Recicla atmosfera para doce personas.",
            "costes": "Una celda de las cuatro por cada ciclo completo.",
            "limites": "Por debajo de dos celdas no cubre mas de una cubierta.",
            "acceso": "Cualquiera de la cuadrilla.",
            "dureza": "duro",
        }],
        "lugares": [
            {"nombre": LUGARES[0], "tipo": "control", "descripcion": "Consolas y ventanal.",
             "sistemas_criticos": ["Soporte vital"]},
            {"nombre": LUGARES[1], "tipo": "almacen", "descripcion": "Pasillo largo y frio.",
             "sistemas_criticos": []},
            {"nombre": LUGARES[2], "tipo": "transito", "descripcion": "Doble compuerta.",
             "sistemas_criticos": ["Soporte vital"]},
        ],
        "facciones": [{
            "nombre": "Cuadrilla Nueve", "proposito": "Mantenimiento contratado",
            "objetivos": "Cobrar y volver", "recursos": "Un remolcador y herramienta",
        }],
        "amenaza": {
            "naturaleza": "Una presencia que conserva cuerpos y sustituye su voluntad.",
            "origen": "Llego en un cargamento sin manifiesto.",
            "reglas": [
                {"capacidad": "Mantener vivo un cuerpo danado",
                 "limite": "No puede cruzar el vacio",
                 "activacion": "Contacto con tejido expuesto"},
                {"capacidad": "Imitar la conducta reciente del huesped",
                 "limite": "No reproduce recuerdos anteriores al contacto",
                 "activacion": "Cuando se le pregunta por el pasado"},
                {"capacidad": "Extender el contagio por contacto",
                 "limite": "No atraviesa el sellante curado",
                 "activacion": "Piel contra piel"},
            ],
            "encarna_tema": "El miedo a soltar a quien ya se fue.",
        },
        "linea_de_tiempo_origen": "dia 0 del acoplamiento",
        "linea_de_tiempo_unidad": "dia",
        "eventos_previos": [{
            "fecha_interna": "dia -240", "dia": -240,
            "descripcion": "La estacion deja de responder.", "tipo": "antecedente",
        }],
    }


def elenco(entrada: str, agente: str) -> dict[str, Any]:
    base = {
        "deseo": "Terminar el contrato y largarse",
        "necesidad_interna": "Aceptar que no pudo salvar a nadie",
        "fantasma": "Mantuvo respirando a su hermano contra su voluntad",
        "herida": "La culpa de haberlo prolongado",
        "mentira": "Rendirse es lo mismo que matar",
        "defecto": "No suelta nunca, aunque haga dano",
        "idiolecto": "Frases cortas, vocabulario de taller",
    }
    prota, oponente, aliado = _reparto(entrada)
    edad_prota = _edad_destinatario(entrada)
    personajes: list[dict[str, Any]] = [
        {**base, "nombre": prota, "rol": "soldadora", "rol_narrativo": "protagonista",
         "edad": 38 if edad_prota is None else edad_prota,
         "tipo_arco": "positivo", "posicion_tematica": "Salvar el cuerpo es salvar a alguien",
         "faccion": "Cuadrilla Nueve", "secreto": "",
         "relaciones": [{"destino": oponente, "tipo": "se_opone_a"}]},
        {**base, "nombre": oponente, "rol": "capataz", "rol_narrativo": "oponente", "edad": 52,
         "tipo_arco": "negativo", "subtipo_arco": "caida",
         "posicion_tematica": "Un cuerpo sin voluntad ya no es nadie",
         "faccion": "Cuadrilla Nueve", "secreto": "Sabia lo del cargamento",
         "relaciones": []},
        {**base, "nombre": aliado, "rol": "tecnica", "rol_narrativo": "aliado", "edad": 29,
         "tipo_arco": "plano", "posicion_tematica": "No hay respuesta, solo consecuencias",
         "faccion": "Cuadrilla Nueve", "secreto": "", "relaciones": []},
    ]
    # Con encargo, cada allegado obligatorio es un personaje (RF3-PER-03).
    for nombre, relacion in _allegados(entrada):
        personajes.append({
            **base, "nombre": nombre, "rol": relacion, "rol_narrativo": "aliado", "edad": 7,
            "tipo_arco": "plano", "posicion_tematica": f"Lo que {prota} no quiere perder: {nombre}",
            "faccion": "", "secreto": "", "relaciones": [],
        })
    return {"personajes": personajes}


def estructura(entrada: str, agente: str) -> dict[str, Any]:
    return {
        "actos": [
            {"numero": 1, "funcion_narrativa": "Llegada y normalidad aparente"},
            {"numero": 2, "funcion_narrativa": "La estacion se cierra sobre ellos"},
            {"numero": 3, "funcion_narrativa": "Elegir a quien se deja ir"},
        ],
        "hilos": [
            {"nombre": "principal", "tipo": "principal",
             "conflicto_central": "Salir de la estacion sin repetir lo de su hermano",
             "personajes": _reparto(entrada), "dramatiza_tema": True,
             "puntos_de_giro": [
                 {"tipo": "gancho", "posicion": 2.0, "descripcion": "El silencio del canal"},
                 {"tipo": "incidente_incitador", "posicion": 12.0, "descripcion": "El hallazgo"},
                 {"tipo": "punto_medio", "posicion": 50.0, "descripcion": "La regla se revela"},
                 {"tipo": "climax", "posicion": 90.0, "descripcion": "La esclusa"},
                 {"tipo": "resolucion", "posicion": 97.0, "descripcion": "El remolcador"},
             ]},
            {"nombre": "confianza", "tipo": "subtrama",
             "conflicto_central": "Saber quien sigue siendo quien dice ser",
             "personajes": _reparto(entrada)[:2], "dramatiza_tema": False,
             "puntos_de_giro": [
                 {"tipo": "primer_umbral", "posicion": 25.0, "descripcion": "La primera duda"},
                 {"tipo": "crisis", "posicion": 82.0, "descripcion": "La prueba del sellante"},
             ]},
        ],
        "siembras": [
            {"elemento": "El sellante de casco de dos componentes", "hilo": "principal",
             "capitulo_pago_previsto": 3},
        ],
        "objetos": [{"nombre": OBJETO, "funcion_narrativa": "Prueba de que alguien estuvo antes"}],
    }


def escaleta(entrada: str, agente: str) -> dict[str, Any]:
    # La longitud por escena sale del presupuesto, no de una constante: si no, la puerta 2
    # rechaza la escaleta por desviarse del objetivo, con razon.
    total = _capitulos_pedidos(entrada)
    prota, oponente, _ = _reparto(entrada)
    # Los elementos del encargo, repartidos en orden por las escenas: si hay mas elementos
    # que escenas, alguna lleva varios.
    codigos = _codigos(entrada)
    n_escenas = total * ESCENAS_POR_CAPITULO
    reparto_elementos = {
        k: codigos[k::n_escenas] for k in range(n_escenas)
    }
    por_escena = max(300, _objetivo_palabras(entrada) // (total * ESCENAS_POR_CAPITULO))
    capitulos: list[dict[str, Any]] = []
    for numero in range(1, total + 1):
        escenas: list[dict[str, Any]] = []
        for orden in range(1, ESCENAS_POR_CAPITULO + 1):
            escenas.append({
                "orden": orden,
                "pov": prota,
                "lugar": LUGARES[(numero + orden) % len(LUGARES)],
                "reparto": [prota, oponente],
                "objetivo": f"Revisar la cubierta {numero}.{orden}",
                "conflicto": "La compuerta no responde al codigo",
                "resultado": "Entra, con una celda menos",
                "valor_inicial": "seguro" if orden == 1 else "expuesto",
                "valor_final": "expuesto" if orden == 1 else "acorralado",
                "tension": min(10, 3 + numero),
                "gancho_salida": "Algo respira al otro lado",
                "longitud_prevista": por_escena,
                "analepsis": False,
                "secuencia": f"sec{numero}",
                "objetos": [OBJETO] if orden == 2 else [],
                "elementos": reparto_elementos[
                    (numero - 1) * ESCENAS_POR_CAPITULO + orden - 1
                ],
                "beats": [{"tipo": "accion", "cambio": "Fuerza la compuerta"}],
                "secuela": {"reaccion": "Se queda quieta", "dilema": "Avisar o callar",
                            "decision": "Callar"},
            })
        capitulos.append({
            "numero": numero, "acto": min(numero, 3),
            "objetivo": f"Objetivo del capitulo {numero}",
            "pov": prota,
            "gancho_apertura": "El canal sigue mudo",
            "gancho_cierre": "La luz de la cubierta se apaga sola",
            "escenas": escenas,
        })
    secuencias = [
        {"nombre": f"sec{n}", "acto": min(n, 3),
         "objetivo_intermedio": f"Bloque {n}", "orden": n}
        for n in range(1, total + 1)
    ]
    return {"capitulos": capitulos, "secuencias": secuencias}


def redaccion(entrada: str, agente: str) -> dict[str, Any]:
    # Nombra a los allegados que la escaleta le pide integrar, como exige la puerta 4
    # (spec3, RF3-VAL-03).
    allegados = dict.fromkeys(re.findall(r"ALL\d+: ([^(;\n]+?) \(", entrada))
    cuerpo = (
        f"La compuerta cedio con un chasquido seco. {_reparto(entrada)[0]} apoyo el hombro y "
        "conto hasta tres. "
        "El aire del otro lado olia a metal frio y a algo dulce que no supo nombrar. "
        "Vaan la miraba desde el marco sin decir nada, con las manos quietas. "
        f"La esclusa quedaba a {DISTANCIA_A_LA_ESCLUSA} y nadie queria recorrerlos. "
        "—Pasa tu primero —dijo ella. Nadie se movio durante un rato largo."
    ) + "".join(f" {nombre} esperaba al otro lado." for nombre in allegados)
    return {
        "escenas": [{"orden": o, "texto": cuerpo} for o in _ordenes(entrada)],
        "notas": "",
    }


#: Cinco atributos por sujeto, repetidos igual en cada capitulo: la puerta 3 tiene pares que
#: comparar aunque ninguno choque (RF2-DEMO-01).
RASGOS_DEL_PUENTE = (
    ("olor", "metal frio y algo dulce"), ("luz", "ambar intermitente"),
    ("sonido", "zumbido de los reles"), ("estado de la consola", "apagada salvo navegacion"),
    ("suelo", "rejilla con escarcha"),
)
RASGOS_DE_IDRIS = (
    ("color de pelo", "castano corto"), ("estatura", "alta"), ("voz", "ronca"),
    ("mano dominante", "izquierda"),
)
#: La quinta, una cadena de tres supersesiones: cada capitulo sustituye al anterior.
HERIDA_DE_IDRIS = ("corte abierto", "corte infectado", "cicatriz rosada")
SIEMBRA = "El sellante de casco de dos componentes"
ESTADOS_DE_LA_SIEMBRA = ("sembrada", "regada", "pagada")
REVELACION = ("rastro", "efecto", "vislumbre")


def _elementos_integrados(entrada: str) -> list[dict[str, Any]]:
    """Cada elemento del encargo del capitulo, integrado con las primeras palabras de su escena
    como cita (RF3-ELE-01): el redactor falso no escribe los recuerdos, y la cita tiene que
    estar en la escena."""
    escenas = dict(re.findall(r"### Escena (\d+)[^\n]*\n\n(.*?)(?=\n\n### Escena|\n\n## |\Z)",
                              entrada, re.S))
    salida: list[dict[str, Any]] = []
    for codigo, orden in re.findall(r"^- ([A-Z]+\d+) \([a-z]+, escena (\d+)\)",
                                    _bloque(entrada, "ELEMENTOS DEL ENCARGO EN ESTE CAPITULO"),
                                    re.M):
        palabras = escenas.get(orden, "").split()[:6]
        if palabras:
            salida.append({"escena_orden": int(orden), "codigo": codigo,
                           "cita": " ".join(palabras)})
    return salida


def extraccion(entrada: str, agente: str) -> dict[str, Any]:
    """Una extraccion que ejercita cada comprobacion de la puerta 3 sin disparar ninguna.

    Por capitulo: los mismos cinco rasgos de dos sujetos, una herida que evoluciona por
    supersesion, conocimiento que se adquiere y se usa despues, una sorpresa repetida (que es
    aviso), el objeto que se traslada con su traslado registrado, eventos con orden interno,
    la siembra que se planta, se riega y se paga, y dos hilos que se abren y se cierran en
    orden inverso. En el ultimo capitulo muere un personaje que no vuelve a aparecer.
    """
    ordenes = _ordenes(entrada) or [1]
    capitulo = _capitulo(entrada)
    indice = min(max(capitulo, 1), CAPITULOS) - 1
    primera, ultima = ordenes[0], ordenes[-1]
    idris, vaan, reyes = _reparto(entrada)

    def hecho(sujeto_tipo: str, sujeto: str, atributo: str, valor: str,
              supersede: str = "") -> dict[str, Any]:
        return {
            "escena_orden": primera, "sujeto_tipo": sujeto_tipo, "sujeto_ref": sujeto,
            "atributo": atributo, "valor": valor, "categoria": "fisico",
            "cita": f"{atributo}: {valor}", "supersede_a": supersede,
        }

    hechos = [hecho("lugar", LUGARES[0], a, v) for a, v in RASGOS_DEL_PUENTE]
    hechos += [hecho("personaje", idris, a, v) for a, v in RASGOS_DE_IDRIS]
    hechos.append(hecho(
        "personaje", idris, "herida en la mano", HERIDA_DE_IDRIS[indice],
        supersede="herida en la mano" if capitulo > 1 else "",
    ))
    if capitulo == 1:
        # Solo se fija una vez: las demas escenas lo usan por mencion, no por reafirmacion.
        hechos.append({
            **hecho("lugar", LUGARES[2], "distancia al puente", DISTANCIA_A_LA_ESCLUSA),
            "categoria": "distancia",
        })

    def sabe(personaje: str, via: str, postura: str = "sabe") -> dict[str, Any]:
        return {"escena_orden": primera, "personaje_ref": personaje, "sujeto_ref": LUGARES[0],
                "atributo": "olor", "postura": postura, "via": via}

    def usa(personaje: str) -> dict[str, Any]:
        return {"escena_orden": ultima, "personaje_ref": personaje,
                "sujeto_ref": LUGARES[0], "atributo": "olor"}

    conocimiento: list[dict[str, Any]] = []
    usos: list[dict[str, Any]] = []
    if capitulo == 1:
        conocimiento.append(sabe(idris, "presencio"))
    elif capitulo == 2:
        # Idris vuelve a «enterarse» de lo que ya sabia: sorpresa imposible, que es aviso.
        conocimiento += [sabe(vaan, "se_lo_contaron", "cree"), sabe(idris, "presencio")]
        usos.append(usa(idris))
    else:
        usos.append(usa(vaan))

    estados: list[dict[str, Any]] = [{
        "escena_orden": primera, "personaje_ref": idris, "condicion": "herido",
        "salud_fisica": HERIDA_DE_IDRIS[indice], "estado_psicologico": "alerta",
        "nivel_confianza": {},
    }]
    if capitulo == CAPITULOS:
        estados.append({
            "escena_orden": ultima, "personaje_ref": reyes, "condicion": "muerto",
            "salud_fisica": "sin constantes", "estado_psicologico": "", "nivel_confianza": {},
        })

    hilos: list[dict[str, Any]] = []
    if capitulo == 1:
        hilos = [{"escena_orden": primera, "hilo": 1, "nuevo_estado": "abierto"},
                 {"escena_orden": ultima, "hilo": 2, "nuevo_estado": "abierto"}]
    elif capitulo == 2:
        hilos = [{"escena_orden": primera, "hilo": 2, "nuevo_estado": "complicando"}]
    elif capitulo == CAPITULOS:
        # Se cierra primero lo ultimo que se abrio.
        hilos = [{"escena_orden": primera, "hilo": 2, "nuevo_estado": "resuelto"},
                 {"escena_orden": ultima, "hilo": 1, "nuevo_estado": "resuelto"}]

    return {
        "hechos": hechos,
        "elementos": _elementos_integrados(entrada),
        "conocimiento": conocimiento,
        "usos_de_conocimiento": usos,
        "estados_personaje": estados,
        "estados_objeto": [{
            "escena_orden": ultima, "objeto_ref": OBJETO, "poseedor_ref": "",
            "ubicacion_ref": LUGARES[(capitulo + 2) % len(LUGARES)],
        }],
        "eventos": [{
            "escena_orden": o, "fecha_interna": f"dia {capitulo}", "dia": capitulo,
            "orden_interno": capitulo * 10 + o,
            "descripcion": f"Sucesos de la escena {o}", "dramatizado": True,
        } for o in ordenes],
        "siembras": [{
            "escena_orden": primera, "siembra_ref": SIEMBRA,
            "nuevo_estado": ESTADOS_DE_LA_SIEMBRA[indice],
        }],
        "hilos": hilos,
        "amenaza_revelacion": REVELACION[indice],
        "entidades_no_reconocidas": [],
        "resumen": (
            f"En el capitulo {capitulo} la cuadrilla fuerza una compuerta y encuentra la "
            "cubierta vacia, con un olor que nadie sabe nombrar."
        ),
        "resumen_breve": f"Capitulo {capitulo}: fuerzan la compuerta y la cubierta esta vacia.",
    }


def oficio(entrada: str, agente: str) -> dict[str, Any]:
    return {"veredictos": [
        {"criterio": c, "veredicto": "pasa", "evidencia": "", "sugerencia": ""}
        for c in CRITERIOS_OFICIO
    ]}


def continuidad(entrada: str, agente: str) -> dict[str, Any]:
    # Una opinion por conflicto numerado del paquete (spec3, RF3-JUE-01).
    numeros = [int(n) for n in re.findall(r"^(\d+)\. \[", entrada, re.MULTILINE)]
    return {
        "resumen": "Hay un conflicto de continuidad en el capitulo.",
        "explicacion_por_conflicto": ["El texto contradice un hecho establecido."] * len(numeros),
        "opiniones": [{"conflicto": n, "parece": "real",
                       "motivo": "La prosa dice lo contrario de lo establecido."}
                      for n in numeros],
        "sugerencia": "Reescribir el capitulo respetando lo establecido.",
    }



# --- Entrevistador (specs/spec3.md, RF3-ENT-07) -----------------------------------------------
#
# Responde de forma determinista a un guion: toma la ultima respuesta del comprador como el
# valor del campo por el que se pregunto, con la respuesta entera (o cada trozo separado por
# «;») como cita. No valida nada: si el valor no sirve para ese campo, lo descarta el codigo,
# que es justo lo que hay que poder probar.

_CAMPOS_DE_CONTRADICCION = {
    "edad_bajo_intensidad": ["intensidad", "destinatario.edad"],
    "subgenero_exige_intensidad": ["subgenero", "intensidad"],
    "elemento_con_vetado": [],
}
_LISTAS = {"destinatario.rasgos", "recuerdos", "vetados"}
_PREGUNTAS = {
    "destinatario.nombre": "¿Como se llama la persona a la que regalas la novela?",
    "destinatario.edad": "¿Cuantos años tiene?",
    "destinatario.pronombres": "¿Como nos referimos a ella: el, ella o neutro?",
    "destinatario.rasgos": "Cuentame como es: rasgos de caracter o fisicos, separados por «;».",
    "recuerdos": "Dame uno o varios recuerdos suyos, separados por «;».",
    "ocasion": "¿Para que ocasion es? (cumpleanos, aniversario, boda, jubilacion, navidad, otra)",
    "quien_regala": "¿Quien firma el regalo?",
    "intensidad": "¿Cuanto miedo quieres que pase? (atmosferico, tension, intenso)",
    "tono": "¿Que tono prefieres? (sobrio, emotivo, humor_negro, aventura)",
}


def _bloque(entrada: str, titulo: str) -> str:
    m = re.search(rf"## {re.escape(titulo)}[^\n]*\n\n(.*?)(?=\n\n## |\Z)", entrada, re.S)
    return m.group(1).strip() if m else ""


def entrevistador(entrada: str, agente: str) -> dict[str, Any]:
    texto = re.search(r"<<<TEXTO_DEL_COMPRADOR\n(.*?)\nTEXTO_DEL_COMPRADOR>>>", entrada, re.S)
    if texto:
        frases = [f.strip() for f in re.split(r"(?<=[.!?])\s+|\n+", texto.group(1)) if f.strip()]
        return {"actualizaciones": [
            {"campo": "recuerdos", "valor": f, "cita": f} for f in frases if len(f.split()) >= 4
        ], "pregunta": ""}

    campo = _bloque(entrada, "LA ULTIMA PREGUNTA ERA SOBRE")
    respuesta = _bloque(entrada, "ULTIMA RESPUESTA DEL COMPRADOR")
    actualizaciones: list[dict[str, Any]] = []
    quitar = re.match(r"quita (?:el vetado |el recuerdo |a )?(.+)$", respuesta, re.IGNORECASE)
    if quitar and campo in ("elemento_con_vetado", "correccion"):
        # «quita arañas»: se retira de los vetados, que es como se resuelve la contradiccion.
        actualizaciones.append({"campo": "vetados", "operacion": "quitar",
                                "valor": quitar.group(1).strip(), "cita": respuesta})
    elif respuesta and not respuesta.startswith("(") and not campo.startswith("("):
        if campo == "correccion" and ":" in respuesta:
            campo, _, respuesta = (x.strip() for x in respuesta.partition(":"))
        candidatos = _CAMPOS_DE_CONTRADICCION.get(campo, [campo])
        for c in candidatos:
            if c == "allegados":
                nombre, _, relacion = respuesta.partition(",")
                actualizaciones.append({"campo": c, "valor": nombre.strip(),
                                        "relacion": relacion.strip(), "cita": respuesta})
            elif c in _LISTAS:
                actualizaciones += [
                    {"campo": c, "valor": t.strip(), "cita": t.strip()}
                    for t in respuesta.split(";") if t.strip()
                ]
            else:
                actualizaciones.append({"campo": c, "valor": respuesta, "cita": respuesta})

    pendientes = _bloque(entrada, "PENDIENTES").splitlines()
    pregunta = ""
    # El primer pendiente tras aplicar lo de este turno lo decide el codigo; aqui se pregunta
    # por el primero de la lista, que es lo que haria el agente real con lo que ve.
    if pendientes and "(ninguno)" not in pendientes[0]:
        linea = pendientes[0].lstrip("- ")
        clave = linea.split(":", 1)[1].strip() if linea.startswith("FALTA") else ""
        pregunta = _PREGUNTAS.get(clave, f"Hay que resolver esto: {linea}")
    return {"actualizaciones": actualizaciones, "pregunta": pregunta}


# --- El cambio del lector (specs/spec3.md, 3.8) ------------------------------------------------
#
# El interprete toma como valor nuevo lo que la peticion pone entre comillas latinas, o su
# ultima palabra, y lo aplica al primer candidato. El revisor sustituye lo viejo por lo nuevo
# como palabra completa y cita cada sitio. Nada de esto sabe castellano: basta para recorrer el
# camino entero con el puerto falso.

_PETICION = re.compile(r"<<<PETICION_DEL_LECTOR\n(.*?)\nPETICION_DEL_LECTOR>>>", re.S)
_CANDIDATO = re.compile(
    r"^- (?:entidad=(\w+) entidad_id=(\d+): .*|hecho_id=(\d+): .*)$", re.M)
_NO_ADMISIBLES = ("triste", "alegre", "estilo", "tono")


def interprete(entrada: str, agente: str) -> dict[str, Any]:
    m = _PETICION.search(entrada)
    peticion = m.group(1).strip() if m else ""
    comillas = re.search(r"«([^»]+)»", peticion)
    palabras = re.findall(r"[^\W\d_][\w'-]*", peticion)
    valor = comillas.group(1) if comillas else (palabras[-1] if palabras else "")
    candidato = _CANDIDATO.search(_bloque(entrada, "CANDIDATOS"))
    if candidato is None or not valor or any(p in peticion.lower() for p in _NO_ADMISIBLES):
        return {"admisible": False, "motivo": "No es un cambio de un dato de la novela."}
    if candidato.group(3):
        return {"admisible": True, "motivo": "Cambia el valor del hecho.",
                "tipo": "cambiar_hecho", "hecho_id": int(candidato.group(3)),
                "valor_nuevo": valor}
    return {"admisible": True, "motivo": "Renombra la entidad.", "tipo": "renombrar",
            "entidad": candidato.group(1), "entidad_id": int(candidato.group(2)),
            "nombre_nuevo": valor}


def rubrica(entrada: str, agente: str) -> dict[str, Any]:
    """Un 3 en cada criterio, con la primera frase de la novela como evidencia literal."""
    from compartido.tipos import CRITERIOS_RUBRICA

    prosa = _bloque(entrada, "LA NOVELA")
    frase = next((linea.strip() for linea in prosa.splitlines()
                  if linea.strip() and not linea.startswith("#")), "La novela")
    evidencia = frase.split(".")[0][:200] or "La novela"
    return {"notas": [
        {"criterio": c, "nota": 3, "justificacion": "Correcta, sin destacar (demo).",
         "evidencia": evidencia}
        for c in CRITERIOS_RUBRICA
    ]}


def revision(entrada: str, agente: str) -> dict[str, Any]:
    from compartido.cambio import Cambio, sustituir_nombres

    cambio = _bloque(entrada, "EL CAMBIO")
    nombre = re.search(r"«([^»]+)» se llama ahora «([^»]+)»", cambio)
    dato = re.search(r"vale ahora «([^»]+)» \(antes, «([^»]+)»\)", cambio)
    no_toques = re.search(r"No toques (.*?): es otro nombre", cambio)
    protegidos = tuple(re.findall(r"«([^»]+)»", no_toques.group(1))) if no_toques else ()
    if nombre:
        mapa = Cambio(tipo="renombrar", antes=nombre.group(1), despues=nombre.group(2),
                      protegidos=protegidos).mapa()
        nuevo_valor = nombre.group(2)
    elif dato:
        mapa = {dato.group(2): dato.group(1)}
        nuevo_valor = dato.group(1)
    else:
        mapa, nuevo_valor = {}, ""

    def corregir(texto: str) -> str:
        return sustituir_nombres(texto, mapa, protegidos)

    prosa = _bloque(entrada, "PROSA APROBADA")
    escenas: list[dict[str, Any]] = []
    citas: list[str] = []
    for orden, texto in re.findall(r"\[escena (\d+)\]\n(.*?)(?=\n\n\[escena \d+\]|\Z)",
                                   prosa, re.S):
        corregido = corregir(texto.strip())
        escenas.append({"orden": int(orden), "texto": corregido})
        if corregido != texto.strip() and nuevo_valor:
            i = corregido.find(nuevo_valor)
            # Por palabras enteras: cortar por letras podia partir una etiqueta de la
            # seudonimizacion («[DESTINATARIO_NOM»), que ya no se restaura y deja la cita sin
            # casar con la prosa (spec3, RF3-SEU; lo vio a1 en la demo del cambio del lector).
            ini = corregido.rfind(" ", 0, max(0, i - 20)) + 1 if i > 20 else 0
            fin = corregido.find(" ", i + len(nuevo_valor) + 20)
            cita = corregido[ini:fin if fin >= 0 else len(corregido)]
            if cita not in texto:
                citas.append(cita)
    resumenes = _bloque(entrada, "RESUMENES DEL CAPITULO")
    resumen = re.search(r"Resumen: (.*?)\n\nResumen breve:", resumenes, re.S)
    breve = re.search(r"Resumen breve: (.*)", resumenes, re.S)
    relleno = "El capitulo sigue como estaba."
    return {
        "escenas": escenas,
        "resumen": corregir(resumen.group(1).strip()) if resumen and resumen.group(1).strip()
        else relleno,
        "resumen_breve": corregir(breve.group(1).strip()) if breve and breve.group(1).strip()
        else relleno,
        "citas": citas,
    }


TODOS = {
    "arquitecto": arquitecto,
    "mundo": mundo,
    "elenco": elenco,
    "estructura": estructura,
    "escaleta": escaleta,
    "redaccion": redaccion,
    "extraccion": extraccion,
    "oficio": oficio,
    "continuidad": continuidad,
    "entrevistador": entrevistador,
    "interprete": interprete,
    "revision": revision,
    "rubrica": rubrica,
}
