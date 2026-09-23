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


def arquitecto(entrada: str, agente: str) -> dict[str, Any]:
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
            "fecha_interna": "dia -240", "descripcion": "La estacion deja de responder.",
            "tipo": "antecedente",
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
    return {"personajes": [
        {**base, "nombre": PERSONAJES[0], "rol": "soldadora", "rol_narrativo": "protagonista",
         "tipo_arco": "positivo", "posicion_tematica": "Salvar el cuerpo es salvar a alguien",
         "faccion": "Cuadrilla Nueve", "secreto": "",
         "relaciones": [{"destino": PERSONAJES[1], "tipo": "se_opone_a"}]},
        {**base, "nombre": PERSONAJES[1], "rol": "capataz", "rol_narrativo": "oponente",
         "tipo_arco": "negativo", "subtipo_arco": "caida",
         "posicion_tematica": "Un cuerpo sin voluntad ya no es nadie",
         "faccion": "Cuadrilla Nueve", "secreto": "Sabia lo del cargamento",
         "relaciones": []},
        {**base, "nombre": PERSONAJES[2], "rol": "tecnica", "rol_narrativo": "aliado",
         "tipo_arco": "plano", "posicion_tematica": "No hay respuesta, solo consecuencias",
         "faccion": "Cuadrilla Nueve", "secreto": "", "relaciones": []},
    ]}


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
             "personajes": PERSONAJES, "dramatiza_tema": True,
             "puntos_de_giro": [
                 {"tipo": "gancho", "posicion": 2.0, "descripcion": "El silencio del canal"},
                 {"tipo": "incidente_incitador", "posicion": 12.0, "descripcion": "El hallazgo"},
                 {"tipo": "punto_medio", "posicion": 50.0, "descripcion": "La regla se revela"},
                 {"tipo": "climax", "posicion": 90.0, "descripcion": "La esclusa"},
                 {"tipo": "resolucion", "posicion": 97.0, "descripcion": "El remolcador"},
             ]},
            {"nombre": "confianza", "tipo": "subtrama",
             "conflicto_central": "Saber quien sigue siendo quien dice ser",
             "personajes": PERSONAJES[:2], "dramatiza_tema": False,
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
    por_escena = max(300, _objetivo_palabras(entrada) // (CAPITULOS * ESCENAS_POR_CAPITULO))
    capitulos = []
    for numero in range(1, CAPITULOS + 1):
        escenas = []
        for orden in range(1, ESCENAS_POR_CAPITULO + 1):
            escenas.append({
                "orden": orden,
                "pov": PERSONAJES[0],
                "lugar": LUGARES[(numero + orden) % len(LUGARES)],
                "reparto": [PERSONAJES[0], PERSONAJES[1]],
                "objetivo": f"Revisar la cubierta {numero}.{orden}",
                "conflicto": "La compuerta no responde al codigo",
                "resultado": "Entra, con una celda menos",
                "valor_inicial": "seguro" if orden == 1 else "expuesto",
                "valor_final": "expuesto" if orden == 1 else "acorralado",
                "tension": 3 + numero,
                "gancho_salida": "Algo respira al otro lado",
                "longitud_prevista": por_escena,
                "analepsis": False,
                "secuencia": f"sec{numero}",
                "objetos": [OBJETO] if orden == 2 else [],
                "beats": [{"tipo": "accion", "cambio": "Fuerza la compuerta"}],
                "secuela": {"reaccion": "Se queda quieta", "dilema": "Avisar o callar",
                            "decision": "Callar"},
            })
        capitulos.append({
            "numero": numero, "acto": min(numero, 3),
            "objetivo": f"Objetivo del capitulo {numero}",
            "pov": PERSONAJES[0],
            "gancho_apertura": "El canal sigue mudo",
            "gancho_cierre": "La luz de la cubierta se apaga sola",
            "escenas": escenas,
        })
    secuencias = [
        {"nombre": f"sec{n}", "acto": min(n, 3),
         "objetivo_intermedio": f"Bloque {n}", "orden": n}
        for n in range(1, CAPITULOS + 1)
    ]
    return {"capitulos": capitulos, "secuencias": secuencias}


def redaccion(entrada: str, agente: str) -> dict[str, Any]:
    cuerpo = (
        "La compuerta cedio con un chasquido seco. Idris apoyo el hombro y conto hasta tres. "
        "El aire del otro lado olia a metal frio y a algo dulce que no supo nombrar. "
        "Vaan la miraba desde el marco sin decir nada, con las manos quietas. "
        "—Pasa tu primero —dijo ella. Nadie se movio durante un rato largo."
    )
    return {
        "escenas": [{"orden": o, "texto": cuerpo} for o in _ordenes(entrada)],
        "notas": "",
    }


def extraccion(entrada: str, agente: str) -> dict[str, Any]:
    ordenes = _ordenes(entrada) or [1]
    capitulo = _capitulo(entrada)
    primera = ordenes[0]
    return {
        "hechos": [{
            "escena_orden": primera, "sujeto_tipo": "lugar", "sujeto_ref": LUGARES[0],
            "atributo": "olor", "valor": "metal frio y algo dulce", "categoria": "fisico",
            "cita": "olia a metal frio", "supersede_a": "",
        }],
        "conocimiento": [{
            "escena_orden": primera, "personaje_ref": PERSONAJES[0],
            "sujeto_ref": LUGARES[0], "atributo": "olor", "postura": "sabe",
            "via": "presencio",
        }],
        "usos_de_conocimiento": [],
        "estados_personaje": [{
            "escena_orden": primera, "personaje_ref": PERSONAJES[0], "condicion": "vivo",
            "salud_fisica": "entera", "estado_psicologico": "alerta", "nivel_confianza": {},
        }],
        "estados_objeto": [{
            "escena_orden": ordenes[-1], "objeto_ref": OBJETO, "poseedor_ref": "",
            "ubicacion_ref": LUGARES[(capitulo + 2) % len(LUGARES)],
        }],
        "eventos": [{
            "escena_orden": o, "fecha_interna": f"dia {capitulo}",
            "orden_interno": capitulo * 10 + o,
            "descripcion": f"Sucesos de la escena {o}", "dramatizado": True,
        } for o in ordenes],
        "siembras": [],
        "amenaza_revelacion": "rastro" if capitulo == 1 else None,
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
    return {
        "resumen": "Hay un conflicto de continuidad en el capitulo.",
        "explicacion_por_conflicto": ["El texto contradice un hecho establecido."],
        "sugerencia": "Reescribir el capitulo respetando lo establecido.",
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
}
