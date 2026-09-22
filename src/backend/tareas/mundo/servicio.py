"""Lo que el constructor de mundo escribe en el grafo, y el paquete que recibe."""

from __future__ import annotations

import sqlite3

from compartido.grafo import Resolvedor, insertar, lectura

from .esquemas import SalidaMundo

AGENTE = "mundo"


def paquete(con: sqlite3.Connection, novela_id: int) -> str:
    n = lectura.novela(con, novela_id) or {}
    e = lectura.estilo(con, novela_id) or {}
    temas = con.execute(
        "SELECT pregunta_central, verdad_tematica FROM tema WHERE novela_id = ?", (novela_id,)
    ).fetchall()

    lineas = [
        "La novela ya tiene fijado esto:",
        f"- Premisa: {n.get('premisa', '')}",
        f"- Logline: {n.get('logline', '')}",
        f"- Pregunta dramatica: {n.get('pregunta_dramatica', '')}",
        f"- Subgenero dominante: {n.get('subgenero_dominante', '')}",
        f"- Tipo de final: {n.get('tipo_final', '')}",
        "",
        "Tema:",
    ]
    lineas.extend(f"- {t['pregunta_central']} -> {t['verdad_tematica']}" for t in temas)
    lineas += [
        "",
        "Estilo narrativo (aplicalo al escribir descripciones canonicas):",
        f"- Registro: {e.get('registro', '')}",
        f"- Densidad sensorial: {e.get('densidad_sensorial', '')}",
    ]
    restricciones = lectura.restricciones(con, novela_id)
    if restricciones:
        lineas += ["", "Restricciones:"]
        lineas.extend(f"- {k}: {v}" for k, v in sorted(restricciones.items()))
    return "\n".join(lineas)


def aplicar(con: sqlite3.Connection, novela_id: int, salida: SalidaMundo) -> None:
    resolvedor = Resolvedor(con, novela_id)

    m = salida.mundo
    mundo_id = insertar(
        con, "mundo", novela_id=novela_id, nombre=m.nombre, geografia=m.geografia,
        historia=m.historia, culturas=m.culturas, reglas_fisicas=m.reglas_fisicas,
    )

    # Los sistemas van antes que los lugares: un lugar referencia sus sistemas criticos.
    for s in salida.sistemas:
        sid = insertar(
            con, "sistema_tecnologico", novela_id=novela_id, mundo_id=mundo_id, nombre=s.nombre,
            capacidades=s.capacidades, costes=s.costes, limites=s.limites, acceso=s.acceso,
            dureza=s.dureza,
        )
        resolvedor.registrar("sistema_tecnologico", s.nombre, sid)

    for lugar in salida.lugares:
        criticos = [
            i for i in (
                resolvedor.id_de("sistema_tecnologico", nombre)
                for nombre in lugar.sistemas_criticos
            ) if i is not None
        ]
        lid = insertar(
            con, "lugar", novela_id=novela_id, mundo_id=mundo_id, nombre=lugar.nombre,
            tipo=lugar.tipo, descripcion=lugar.descripcion, sistemas_criticos=criticos,
        )
        resolvedor.registrar("lugar", lugar.nombre, lid)

    for f in salida.facciones:
        fid = insertar(
            con, "faccion", novela_id=novela_id, nombre=f.nombre, proposito=f.proposito,
            objetivos=f.objetivos, recursos=f.recursos,
        )
        resolvedor.registrar("faccion", f.nombre, fid)

    tema_id = con.execute(
        "SELECT id FROM tema WHERE novela_id = ? ORDER BY id LIMIT 1", (novela_id,)
    ).fetchone()
    a = salida.amenaza
    insertar(
        con, "amenaza", novela_id=novela_id, tema_id=tema_id["id"] if tema_id else None,
        naturaleza=a.naturaleza, origen=a.origen,
        reglas=[r.model_dump() for r in a.reglas],
    )

    linea_id = insertar(
        con, "linea_de_tiempo", novela_id=novela_id,
        origen=salida.linea_de_tiempo_origen, unidad=salida.linea_de_tiempo_unidad,
    )
    for orden, ev in enumerate(salida.eventos_previos, start=1):
        insertar(
            con, "evento", novela_id=novela_id, linea_de_tiempo_id=linea_id,
            fecha_interna=ev.fecha_interna, orden_interno=-len(salida.eventos_previos) + orden - 1,
            descripcion=ev.descripcion, tipo=ev.tipo, dramatizado=False,
        )
