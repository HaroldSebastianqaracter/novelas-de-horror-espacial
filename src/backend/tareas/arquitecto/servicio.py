"""Lo que el arquitecto escribe en el grafo, y el paquete que recibe."""

from __future__ import annotations

import sqlite3

from compartido.grafo import actualizar, insertar, lectura

from .esquemas import SalidaArquitecto

AGENTE = "arquitecto"


def paquete(con: sqlite3.Connection, novela_id: int) -> str:
    """Solo las restricciones y la semilla: el arquitecto no tiene canon del que partir."""
    n = lectura.novela(con, novela_id) or {}
    restricciones = lectura.restricciones(con, novela_id)

    lineas = ["Restricciones de la obra:"]
    lineas.extend(f"- {tipo}: {valor}" for tipo, valor in sorted(restricciones.items()))
    if not restricciones:
        lineas.append("- (ninguna)")
    if n.get("titulo"):
        lineas.append(f"\nTitulo provisional: {n['titulo']}")
    if n.get("semilla_premisa"):
        lineas.append(f"\nSemilla de premisa: {n['semilla_premisa']}")
    return "\n".join(lineas)


def aplicar(con: sqlite3.Connection, novela_id: int, salida: SalidaArquitecto) -> None:
    """Escribe la salida en el grafo. Corre dentro de la transaccion del orquestador."""
    actualizar(
        con, "novela", novela_id,
        premisa=salida.premisa,
        logline=salida.logline,
        pregunta_dramatica=salida.pregunta_dramatica,
        tema_central=salida.tema_central,
        subgenero_dominante=salida.subgenero_dominante,
        tipo_final=salida.tipo_final,
        pov_por_defecto=salida.pov_por_defecto,
        tiempo_verbal=salida.tiempo_verbal,
    )
    if salida.titulo_propuesto:
        fila = con.execute("SELECT titulo FROM novela WHERE id = ?", (novela_id,)).fetchone()
        if fila is None or not str(fila["titulo"]).strip():
            actualizar(con, "novela", novela_id, titulo=salida.titulo_propuesto)

    primer_tema: int | None = None
    for tema in salida.temas:
        tid = insertar(
            con, "tema", novela_id=novela_id,
            pregunta_central=tema.pregunta_central, verdad_tematica=tema.verdad_tematica,
        )
        primer_tema = primer_tema or tid

    for motivo in salida.motivos:
        insertar(
            con, "motivo", novela_id=novela_id, tema_id=primer_tema, simbolo=motivo.simbolo,
            significado_inicial=motivo.significado_inicial,
            significado_final=motivo.significado_final,
        )

    e = salida.estilo
    insertar(
        con, "estilo_narrativo", novela_id=novela_id, registro=e.registro,
        ritmo_prosa=e.ritmo_prosa, densidad_sensorial=e.densidad_sensorial,
        distancia_psiquica=e.distancia_psiquica, tics_prohibidos=e.tics_prohibidos,
        convenciones_formato=e.convenciones_formato,
    )
