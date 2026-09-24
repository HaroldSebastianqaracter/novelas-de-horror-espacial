"""La rubrica del LLM-as-judge sobre la novela entera y la revision humana que se le compara.

Corre al terminar la generacion y no bloquea: seis notas de 1 a 5 con justificacion y cita,
un evento si alguna es baja y otro si falla. La revision humana entra por la misma tabla.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from compartido.puerto import demo as agentes_falsos
from compartido.tipos import CRITERIOS_RUBRICA
from evals import rubrica_humana
from orquestador import observabilidad as obs
from orquestador import pipeline
from tareas.rubrica import servicio as s_rubrica
from tareas.rubrica.esquemas import SalidaRubrica
from tests.entorno import cfg_de, crear_novela, nueva_bd, puerto_falso
from tests.test_observabilidad import ClienteFalso


def _notas(nota: int = 3, **por_criterio: int) -> dict[str, Any]:
    return {"notas": [{"criterio": c, "nota": por_criterio.get(c, nota),
                       "justificacion": "Porque si.", "evidencia": "una cita"}
                      for c in CRITERIOS_RUBRICA]}


def _generar(rubrica: object = None, *, activa: bool = True
             ) -> tuple[sqlite3.Connection, Path, int, str]:
    con, ruta = nueva_bd()
    novela_id = crear_novela(con)
    puerto = puerto_falso(con)
    if rubrica is not None:
        puerto.registrar("rubrica", rubrica)  # type: ignore[arg-type]
    ctx = pipeline.Contexto(con=con, puerto=puerto, cfg=cfg_de(ruta, rubrica=activa),
                            novela_id=novela_id)
    return con, ruta, novela_id, pipeline.avanzar(ctx)


def _eventos(con: sqlite3.Connection, tipo: str) -> int:
    return int(con.execute("SELECT COUNT(*) FROM traza_evento WHERE tipo = ?",
                           (tipo,)).fetchone()[0])


# --- El esquema -----------------------------------------------------------------------------


def test_hace_falta_una_nota_por_criterio() -> None:
    SalidaRubrica.model_validate(_notas())
    falta = _notas()
    falta["notas"].pop()
    with pytest.raises(ValidationError):
        SalidaRubrica.model_validate(falta)
    repetida = _notas()
    repetida["notas"][0]["criterio"] = "tono"
    with pytest.raises(ValidationError):
        SalidaRubrica.model_validate(repetida)
    fuera = _notas()
    fuera["notas"][0]["nota"] = 6
    with pytest.raises(ValidationError):
        SalidaRubrica.model_validate(fuera)


# --- En el pipeline -----------------------------------------------------------------------------


def test_al_terminar_la_novela_el_juez_la_puntua() -> None:
    con, _, novela_id, final = _generar()
    assert final in ("completada", "completada_con_avisos")
    filas = con.execute("SELECT criterio, nota, origen, version, evidencia_literal, llamada_id "
                        "FROM evaluacion_rubrica WHERE novela_id = ?", (novela_id,)).fetchall()
    assert sorted(f["criterio"] for f in filas) == sorted(CRITERIOS_RUBRICA)
    assert {(f["nota"], f["origen"], f["version"]) for f in filas} == {(3, "llm", 1)}
    # La demo cita la primera frase de la novela: la evidencia es literal.
    assert {f["evidencia_literal"] for f in filas} == {1}
    assert all(f["llamada_id"] for f in filas)
    assert _eventos(con, "rubrica_baja") == 0


def test_una_nota_baja_avisa_y_no_para() -> None:
    con, _, _, final = _generar(lambda e, a: _notas(4, ritmo=2))
    assert final in ("completada", "completada_con_avisos")
    fila = con.execute("SELECT payload FROM traza_evento WHERE tipo = 'rubrica_baja'").fetchone()
    assert fila is not None and "ritmo" in fila["payload"]


def test_si_la_rubrica_falla_la_novela_sigue_completada() -> None:
    def rota(entrada: str, agente: str) -> dict[str, Any]:
        raise RuntimeError("el juez no contesta")

    con, _, novela_id, final = _generar(rota)
    assert final in ("completada", "completada_con_avisos")
    assert con.execute("SELECT COUNT(*) FROM evaluacion_rubrica").fetchone()[0] == 0
    assert _eventos(con, "rubrica_fallida") == 1
    assert con.execute("SELECT COUNT(*) FROM novela_version WHERE novela_id = ?",
                       (novela_id,)).fetchone()[0] == 1


def test_una_cita_inventada_queda_marcada() -> None:
    con, _, novela_id, _ = _generar(lambda e, a: _notas())
    assert {f[0] for f in con.execute(
        "SELECT evidencia_literal FROM evaluacion_rubrica WHERE novela_id = ?",
        (novela_id,))} == {0}


def test_apagada_no_llama_al_juez() -> None:
    con, _, _, final = _generar(activa=False)
    assert final in ("completada", "completada_con_avisos")
    assert con.execute("SELECT COUNT(*) FROM llamada_modelo WHERE agente = 'rubrica'"
                       ).fetchone()[0] == 0


def test_el_paquete_trae_la_novela_entera() -> None:
    con, ruta, novela_id, _ = _generar(activa=False)
    ctx = pipeline.Contexto(con=con, puerto=puerto_falso(con), cfg=cfg_de(ruta),
                            novela_id=novela_id)
    texto = s_rubrica.paquete(con, novela_id, presupuesto=ctx.presupuesto).render()
    for numero in (1, 2, 3):
        assert f"## Capitulo {numero}" in texto
    for c in CRITERIOS_RUBRICA:
        assert f"`{c}`" in texto
    assert agentes_falsos.rubrica(texto, "rubrica")["notas"][0]["evidencia"] in texto


# --- Langfuse -------------------------------------------------------------------------------


def test_las_notas_salen_a_langfuse_como_scores() -> None:
    con, _, novela_id, _ = _generar()
    with pipeline.transaccion(con):
        s_rubrica.registrar(con, novela_id, _notas(5)["notas"], origen="humano")
    cliente = ClienteFalso()
    obs.Exportador(cliente).exportar(con, novela_id)
    scores = {e["body"]["name"]: e["body"]["value"] for e in cliente.eventos
              if e["type"] == "score-create" and e["body"]["name"].startswith("rubrica")}
    assert scores["rubrica_ritmo"] == 3.0 and scores["rubrica_humana_ritmo"] == 5.0
    assert len([n for n in scores if n.startswith("rubrica_humana_")]) == 6
    trazas = {e["body"]["name"] for e in cliente.eventos if e["type"] == "trace-create"}
    assert "rubrica" in trazas


# --- La revision humana ---------------------------------------------------------------------


def test_la_revision_humana_se_importa_y_se_compara(tmp_path: Path,
                                                    capsys: pytest.CaptureFixture[str]) -> None:
    con, ruta, novela_id, _ = _generar()
    con.close()
    plantilla = tmp_path / "notas.csv"
    assert rubrica_humana.main(["--db", str(ruta), "--novela", str(novela_id),
                                "--plantilla", str(plantilla)]) == 0
    lineas = plantilla.read_text(encoding="utf-8").splitlines()
    assert len(lineas) == 7
    rellenas = [lineas[0]] + [linea.replace(";;;", ";4;Bien;") for linea in lineas[1:]]
    plantilla.write_text("\n".join(rellenas), encoding="utf-8")
    assert rubrica_humana.main(["--db", str(ruta), "--novela", str(novela_id),
                                "--importar", str(plantilla)]) == 0
    salida = capsys.readouterr().out
    assert "| ritmo | 3 | 4 | -1 |" in salida
    assert "Diferencia media absoluta: 1.00" in salida


def test_una_plantilla_a_medias_no_se_importa(tmp_path: Path) -> None:
    plantilla = tmp_path / "notas.csv"
    rubrica_humana.escribir_plantilla(plantilla)
    with pytest.raises(rubrica_humana.PlantillaInvalida, match="continuidad"):
        rubrica_humana.leer_plantilla(plantilla)


def test_la_plantilla_del_repositorio_esta_al_dia(tmp_path: Path) -> None:
    nueva = tmp_path / "p.csv"
    rubrica_humana.escribir_plantilla(nueva)
    versionada = Path(rubrica_humana.__file__).parent / "plantilla_rubrica_humana.csv"
    assert versionada.read_text(encoding="utf-8") == nueva.read_text(encoding="utf-8")


def test_la_cita_se_compara_sin_tipografia() -> None:
    texto = " " + s_rubrica._para_comparar(  # pyright: ignore[reportPrivateUsage]
        "*Algo respira ahi dentro*, penso. «Treinta y dos» —dijo Idoia— y se fue.") + " "
    assert s_rubrica.es_cita_literal("algo respira ahí dentro, pensó", texto)
    assert s_rubrica.es_cita_literal('"Treinta y dos" dijo Idoia', texto)
    assert not s_rubrica.es_cita_literal("el", texto)
    assert not s_rubrica.es_cita_literal("algo que no esta en la novela", texto)


@pytest.mark.parametrize(("codificacion", "separador"), [
    ("utf-8", ","), ("utf-8-sig", ","), ("utf-8-sig", ";"), ("cp1252", ";")])
def test_la_plantilla_se_lee_como_la_guarda_excel(tmp_path: Path, codificacion: str,
                                                   separador: str) -> None:
    filas = [separador.join(rubrica_humana.COLUMNAS)]
    filas += [f"{c}{separador}mide{separador}4{separador}Está bien{separador}"
              for c in CRITERIOS_RUBRICA]
    plantilla = tmp_path / "notas.csv"
    plantilla.write_bytes("\r\n".join(filas).encode(codificacion))
    notas = rubrica_humana.leer_plantilla(plantilla)
    assert [n["nota"] for n in notas] == [4] * 6
    assert notas[0]["justificacion"] == "Está bien"


def test_la_cli_avisa_si_la_novela_no_existe(tmp_path: Path,
                                             capsys: pytest.CaptureFixture[str]) -> None:
    con, ruta, _, _ = _generar(activa=False)
    con.close()
    assert rubrica_humana.main(["--db", str(ruta), "--novela", "99", "--comparar"]) == 1
    assert "No hay ninguna novela 99" in capsys.readouterr().out


def test_el_exportador_sirve_con_bases_anteriores_a_la_rubrica() -> None:
    con, _, novela_id, _ = _generar(activa=False)
    con.execute("DROP TABLE evaluacion_rubrica")
    informe = obs.Exportador(ClienteFalso(), marcar=False).exportar(con, novela_id)
    assert informe.eventos > 0


def test_la_tabla_de_evals_usa_la_ultima_rubrica() -> None:
    from evals import tabla

    con, _, novela_id, _ = _generar()
    with pipeline.transaccion(con):
        s_rubrica.registrar(con, novela_id, _notas(1)["notas"], origen="llm")
    r = tabla.Resultado(nombre="x", proposito="")
    tabla._recoger(con, novela_id, r, canario="")  # pyright: ignore[reportPrivateUsage]
    assert r.celdas["rubrica"].startswith("media 1.0")
