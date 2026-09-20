"""De cada contradicción, ¿el escritor tenía delante el hecho que contradijo?

Contar contradicciones no basta para juzgar X-05. Medido el 19/09 sobre dos novelas del mismo brazo
y el mismo código: una dio 5 y otra 1. Con esa variación, una diferencia de una o dos entre brazos no
significa nada, y el experimento se juega a una moneda.

Esto parte las contradicciones en dos clases, que es lo que de verdad se quiere saber:

- **ceguera**: ningún hecho del capítulo que QA señala llegó al prompt del escritor. El filtro se lo
  ocultó y el escritor escribió a ciegas. Es exactamente lo que X-05 ataca.
- **con el hecho delante**: el hecho sí estaba en su prompt y aun así lo contradijo. X-05 no puede
  arreglar esto; es un fallo de atención del modelo, no del filtro.

Un brazo con aristas que reduzca la primera clase y deje igual la segunda demuestra el cambio aunque
el total apenas se mueva.

**De dónde salen los datos.** No de `04_estado/prompts/`, que `archivar` borra por transitorio, sino
del prompt que queda en `07_registro/tanda_*/prompts/`, que es literalmente lo que el escritor leyó.

**Cómo se ata el hallazgo con el hecho.** No por el `cap_origen` que anota QA: en la primera prueba
ese número falló --QA puso 9 en un hallazgo cuyo hecho estaba fichado en el capítulo 8-- y con él la
clasificación salía al revés. Se ata por el texto: de los hechos vigentes anteriores al corte se
elige el que más palabras largas comparte con la descripción del hallazgo, y se mira si **esa línea**
estaba en el prompt. Es una heurística, así que el informe imprime el hecho elegido para que se pueda
comprobar a ojo en vez de creerle.

Un hallazgo cuyo `cap_origen` es el propio capítulo del corte nunca es ceguera: los hechos de un
capítulo se extraen después de escribirlo, así que no podían estar en su prompt.

Uso:
    python herramientas/ceguera_del_filtro.py 09_archivo/2026-...-esclusas [más novelas]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

# Los hechos se renderizan en el prompt como «- [categoria · sujeto · cap. N] texto». Esa línea es el
# contrato con `_formatear_hechos` del escritor; si cambia allí, esto deja de encontrar nada, y por
# eso el informe avisa cuando un prompt no tiene ni un hecho reconocible.
LINEA_HECHO = re.compile(r"^-\s*\[[^\]]*·\s*cap\.\s*(\d+)\]", re.MULTILINE)


def prompts_del_escritor(raiz: Path) -> dict[int, str]:
    """El último prompt de cada capítulo, por número de capítulo.

    El último y no el primero: si hubo corrección, el escritor recibió el capítulo dos veces y la
    que importa es con la que quedó escrito el texto que QA auditó.
    """
    encontrados: dict[int, tuple[str, str]] = {}
    for p in sorted(raiz.glob("07_registro/tanda_*/prompts/*escritor_cap_*.md")):
        m = re.search(r"escritor_cap_(\d+)\.md$", p.name)
        if not m:
            continue
        n = int(m.group(1))
        # El nombre lleva un ordinal delante (001_, 007_): ordena dentro de la tanda, y la carpeta
        # de la tanda ordena entre tandas. La clave compuesta da el orden real de ejecución.
        orden = (p.parent.parent.name, p.name)
        if n not in encontrados or orden > encontrados[n][0]:
            encontrados[n] = (orden, p.read_text(encoding="utf-8", errors="replace"))
    return {n: texto for n, (_, texto) in encontrados.items()}


def caps_de_origen_en_el_prompt(texto: str) -> set[int]:
    return {int(x) for x in LINEA_HECHO.findall(texto)}


def contradicciones(raiz: Path) -> list[dict]:
    salida = []
    for p in sorted((raiz / "06_qa" / "reportes").glob("qa_cap_*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for h in d.get("hallazgos") or []:
            if not str(h.get("tipo", "")).lower().startswith("contradic"):
                continue
            origen = h.get("cap_origen")
            try:
                origen = int(origen)
            except (TypeError, ValueError):
                origen = None
            salida.append({"cap_corte": d.get("cap_corte"), "cap_origen": origen,
                           "descripcion": (h.get("descripcion") or "").strip()})
    return salida


CORTAS = {"que", "del", "las", "los", "una", "uno", "por", "con", "sin", "para", "sobre", "como",
          "este", "esta", "esto", "ese", "esa", "pero", "sus", "mas", "hay", "the", "capitulo",
          "contradice", "establece", "narrador", "vigente", "hecho", "log"}


def _palabras(texto: str) -> set[str]:
    return {p for p in re.findall(r"[a-záéíóúñü]{4,}", (texto or "").lower()) if p not in CORTAS}


def hecho_mas_parecido(descripcion: str, log: list[dict], cap_corte: int) -> dict | None:
    """El hecho del log que más se parece a lo que describe el hallazgo.

    Solo compiten los anteriores al corte: los del propio capítulo se extraen después de escribirlo
    y no podían estar en su prompt, así que emparejar con ellos fabricaría una ceguera falsa.
    """
    objetivo = _palabras(descripcion)
    if not objetivo:
        return None
    mejor, mejor_n = None, 0
    for h in log:
        if (h.get("cap_origen") or 0) >= cap_corte:
            continue
        comunes = len(objetivo & _palabras(h.get("hecho", "")))
        if comunes > mejor_n:
            mejor, mejor_n = h, comunes
    # Con dos palabras en común el parecido es ruido: mejor decir que no se pudo atar.
    return mejor if mejor_n >= 3 else None


def analizar(raiz: Path) -> dict:
    prompts = prompts_del_escritor(raiz)
    try:
        log = json.loads((raiz / "04_estado" / "continuidad.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        log = []
    filas = []
    for c in contradicciones(raiz):
        n = c["cap_corte"]
        texto = prompts.get(n)
        hecho = hecho_mas_parecido(c["descripcion"], log, n or 0)
        if texto is None:
            clase, elegido = "sin prompt guardado", None
        elif hecho is None:
            clase, elegido = "no se pudo atar a un hecho", None
        elif (hecho.get("cap_origen") or 0) == 0:
            # El canon del preludio entra siempre por diseño: nunca es ceguera del filtro.
            clase, elegido = "canon del preludio", hecho.get("hecho")
        elif hecho.get("hecho", "")[:70] in texto:
            clase, elegido = "con el hecho delante", hecho.get("hecho")
        else:
            clase, elegido = "ceguera", hecho.get("hecho")
        filas.append({**c, "clase": clase, "hecho": elegido})
    vacios = [n for n, t in prompts.items() if not caps_de_origen_en_el_prompt(t)]
    return {"novela": raiz.name, "filas": filas, "cortes_con_prompt": len(prompts),
            "prompts_sin_hechos": vacios}


def informe(analisis: list[dict]) -> str:
    lineas = []
    total = Counter()
    for a in analisis:
        cuenta = Counter(f["clase"] for f in a["filas"])
        total.update(cuenta)
        lineas.append(f"\n{a['novela']}  ({len(a['filas'])} contradicciones)")
        for clase, n in cuenta.most_common():
            lineas.append(f"    {clase:24} {n}")
        for f in a["filas"]:
            # Se imprime siempre el hecho elegido, no solo en las cegueras: el emparejamiento es una
            # heurística y quien lea esto tiene que poder desmentirlo de un vistazo.
            if f["clase"] in ("ceguera", "con el hecho delante"):
                lineas.append(f"      [{f['clase']}] cap {f['cap_corte']} · hecho: {(f['hecho'] or '')[:110]}")
        if a["prompts_sin_hechos"]:
            lineas.append(f"    AVISO: prompts sin ningún hecho reconocible: {a['prompts_sin_hechos']}. "
                          "Si son muchos, el formato del prompt cambió y este análisis no vale.")
    lineas.append("\nTOTAL")
    for clase, n in total.most_common():
        lineas.append(f"    {clase:24} {n}")
    ceguera = total.get("ceguera", 0)
    suma = sum(total.values())
    if suma:
        lineas.append(f"\n{ceguera} de {suma} contradicciones ({100 * ceguera / suma:.0f} %) son del tipo "
                      "que X-05 puede arreglar: el hecho no llegó al escritor.")
    return "\n".join(lineas)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("novelas", nargs="+", type=Path)
    a = ap.parse_args(argv[1:])
    validas = [n for n in a.novelas if (n / "06_qa" / "reportes").is_dir()]
    if not validas:
        print("ninguna de esas carpetas tiene 06_qa/reportes/")
        return 1
    print(informe([analizar(n) for n in validas]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
