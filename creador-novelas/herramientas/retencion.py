"""¿Respeta cada capítulo los hechos que el escritor tenía delante?

`contradicciones` cuenta lo que QA encontró, y QA mira la muestra del corte, no todo. Con la
configuración de dos agentes quedaron **2 fallos de retención en tres novelas**: demasiado pocos para
decidir si un cambio de prompt mejora algo. Un loop medido sobre dos sucesos no mide, adivina.

Esto los cuenta de otra forma: capítulo a capítulo, se cruza el texto contra la lista exacta de
hechos que su prompt le entregó, y se pregunta cuáles contradice. Tres ventajas sobre esperar a QA:

- **Corre sobre novelas ya escritas.** No genera ninguna, así que medir de nuevo cuesta céntimos y no
  hora y media.
- **Mira los quince capítulos**, no la muestra de cada corte.
- **Da decenas de sucesos** en vez de dos, que es lo que hace falta para comparar dos prompts.

La lista de hechos no se reconstruye ni se recalcula: se lee del prompt que quedó guardado en
`07_registro/`, que es literalmente lo que el escritor leyó. Si el filtro cambia mañana, las
mediciones viejas siguen siendo válidas porque no dependen del filtro de hoy.

**Antes de creerse los números hay que validar el comprobador**: `--validar` lo corre sobre las
contradicciones que QA ya encontró y enseña cuántas reencuentra. Un comprobador que no caza lo que
QA cazó no sirve para decir que un prompt es mejor.

Uso:
    python herramientas/retencion.py 09_archivo/2026-...-esclusas [más novelas]
    python herramientas/retencion.py <novela> --validar
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.web import ejecutable_claude  # noqa: E402

# El mismo formato que `_formatear_hechos` deja en el prompt del escritor. Si cambia allí, aquí deja
# de encontrarse nada, y por eso el informe avisa cuando un prompt no da ni un hecho.
LINEA_HECHO = re.compile(r"^-\s*\[([^\]]*)\]\s*(.+?)\s*$", re.MULTILINE)

# Sonnet y no haiku: con haiku la validación contra QA daba 2 de 5, y se perdía precisamente el caso
# del capítulo 14 que habíamos verificado a mano. Un comprobador con esa memoria no puede decidir si
# un prompt es mejor que otro. Sigue sin ser opus porque la tarea es comparar dos textos, no escribir.
MODELO = "sonnet"

# Los hechos se preguntan en tandas y no los cincuenta de golpe. Con la lista entera en un solo
# prompt, el verificador se dejaba los del medio: exactamente el fallo del escritor que este
# comprobador existe para medir. Doce entran de sobra en su atención y multiplican las llamadas por
# cuatro, que sobre novelas ya escritas cuesta céntimos.
POR_TANDA = 12

PREGUNTA = """Sos un verificador de continuidad. Te doy los hechos establecidos de una novela y UN capítulo.

Decime **cuáles de esos hechos contradice el texto del capítulo**. Un hecho está contradicho solo si
el capítulo afirma algo incompatible con él: que un aparato averiado funciona, que alguien aislado
conversa, que una cifra es otra. No cuenta como contradicción:

- que el capítulo no mencione el hecho (omitir no es contradecir)
- que un personaje se equivoque o mienta, si el texto lo presenta como error suyo
- que el hecho se cumpla de forma distinta a la esperada pero compatible
- **que se consiga el mismo fin por otro medio**. Si el hecho dice que el intercomunicador está
  muerto y el capítulo hace hablar a dos personajes por una línea de diagnóstico, eso NO lo
  contradice: el aparato averiado sigue averiado. Solo cuenta si el capítulo usa **ese mismo** medio.
- **que una regla general se cumpla con matices**. Si el hecho dice que sellar una esclusa aísla el
  módulo, y el capítulo describe algo moviéndose por rutas que quedaron abiertas, eso NO lo
  contradice. Solo cuenta si el capítulo afirma que lo sellado no aisló.

Fuera de esos casos, marcá todo lo que puedas defender citando una frase del capítulo. No hace falta
que sea flagrante: si el texto afirma algo que no cabe con el hecho, cuenta.

Respondé SOLO con un objeto JSON, sin bloque de código ni texto alrededor:

{"contradichos": [{"n": <número del hecho>, "cita": "<la frase del capítulo que lo contradice>"}]}

Si el capítulo no contradice ninguno, respondé {"contradichos": []}.

## Hechos
%(hechos)s

## Capítulo %(num)s
%(texto)s
"""


def hechos_del_prompt(texto: str) -> list[str]:
    return [f"{etiqueta.strip()} {cuerpo.strip()}" for etiqueta, cuerpo in LINEA_HECHO.findall(texto)]


def prompts_por_capitulo(raiz: Path) -> dict[int, str]:
    """El último prompt de cada capítulo: si hubo corrección, es con el que quedó escrito el texto."""
    encontrados: dict[int, tuple[tuple[str, str], str]] = {}
    for p in sorted(raiz.glob("07_registro/tanda_*/prompts/*escritor_cap_*.md")):
        m = re.search(r"escritor_cap_(\d+)\.md$", p.name)
        if not m:
            continue
        n = int(m.group(1))
        orden = (p.parent.parent.name, p.name)
        if n not in encontrados or orden > encontrados[n][0]:
            encontrados[n] = (orden, p.read_text(encoding="utf-8", errors="replace"))
    return {n: t for n, (_, t) in encontrados.items()}


def preguntar(exe: str, prompt: str, cwd: Path, tope_s: float = 180) -> dict:
    # Sin `--allowed-tools`: el verificador solo compara dos textos y devuelve JSON, no toca nada. Y
    # pasarlo vacío, como estaba, deja la bandera sin valor y la llamada devuelve una respuesta sin
    # texto: quince capítulos «sin contradicciones» que en realidad eran quince llamadas fallidas.
    cmd = [exe, "-p", prompt, "--output-format", "json", "--permission-prompts", "none",
           "--model", MODELO]
    try:
        r = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=tope_s)
    except subprocess.TimeoutExpired:
        return {"error": "el verificador no respondió a tiempo"}
    try:
        envoltorio = json.loads(r.stdout or "{}")
    except json.JSONDecodeError:
        return {"error": f"salida no-JSON: {(r.stdout or r.stderr or '')[:160]}"}
    crudo = envoltorio.get("result") if isinstance(envoltorio, dict) else None
    if not isinstance(crudo, str):
        return {"error": "la respuesta no trae texto"}
    # El modelo a veces devuelve el JSON dentro de un bloque; se recorta al primer objeto.
    inicio, fin = crudo.find("{"), crudo.rfind("}")
    if inicio == -1 or fin <= inicio:
        return {"error": f"sin JSON en la respuesta: {crudo[:160]}"}
    try:
        return json.loads(crudo[inicio:fin + 1])
    except json.JSONDecodeError as e:
        return {"error": f"JSON inválido: {e}"}


def analizar(raiz: Path, exe: str, aviso=print) -> dict:
    prompts = prompts_por_capitulo(raiz)
    filas, sin_hechos = [], []
    for n in sorted(prompts):
        cap = raiz / "05_manuscrito" / f"cap_{n}.md"
        if not cap.is_file():
            continue
        hechos = hechos_del_prompt(prompts[n])
        if not hechos:
            sin_hechos.append(n)
            continue
        texto = cap.read_text(encoding="utf-8", errors="replace")
        rotos, fallos = [], []
        for desde in range(0, len(hechos), POR_TANDA):
            tanda = hechos[desde:desde + POR_TANDA]
            listado = "\n".join(f"{desde + i + 1}. {h}" for i, h in enumerate(tanda))
            r = preguntar(exe, PREGUNTA % {"hechos": listado, "num": n, "texto": texto}, raiz)
            if "error" in r:
                fallos.append(r["error"])
                continue
            for x in (r.get("contradichos") or []):
                if not isinstance(x, dict):
                    continue
                i = x.get("n")
                x["hecho"] = hechos[i - 1] if isinstance(i, int) and 1 <= i <= len(hechos) else "(fuera de rango)"
                rotos.append(x)
        # Un solo desliz contradice varios hechos emparentados: en el capítulo 14, «algo quedó
        # encajado y dejó de desplazarse» chocaba con tres hechos distintos sobre cómo se mueve la
        # presencia. Contarlo tres veces mide cuántos hechos hay sobre el tema, no cuántas veces
        # falló el escritor. La unidad es el pasaje, así que se agrupa por la cita.
        vistas: dict[str, dict] = {}
        for x in rotos:
            clave = " ".join(str(x.get("cita") or "").lower().split())[:120]
            if clave in vistas:
                vistas[clave].setdefault("tambien", []).append(x.get("hecho"))
            else:
                vistas[clave] = x
        rotos = list(vistas.values())
        if fallos:
            # Una tanda caída deja el capítulo incompleto, y un capítulo incompleto contado como
            # limpio es justo la mentira que este comprobador tiene que no decir.
            aviso(f"  cap {n}: {len(fallos)} tandas sin veredicto · {r.get('error', '')[:60]}")
            filas.append({"cap": n, "hechos": len(hechos), "contradichos": rotos, "error": "; ".join(fallos[:2])})
            continue
        aviso(f"  cap {n}: {len(hechos)} hechos, {len(rotos)} contradichos")
        filas.append({"cap": n, "hechos": len(hechos), "contradichos": rotos})
    return {"novela": raiz.name, "filas": filas, "prompts_sin_hechos": sin_hechos}


def contradicciones_de_qa(raiz: Path) -> dict[int, int]:
    """Cuántas contradicciones marcó QA en cada corte. Es la vara contra la que se valida."""
    salida: dict[int, int] = {}
    for p in sorted((raiz / "06_qa" / "reportes").glob("qa_cap_*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        n = d.get("cap_corte")
        if isinstance(n, int):
            salida[n] = len([h for h in (d.get("hallazgos") or [])
                             if str(h.get("tipo", "")).lower().startswith("contradic")])
    return salida


def informe(analisis: list[dict], validar: bool = False) -> str:
    lineas, total_h, total_c, errores = [], 0, 0, 0
    for a in analisis:
        h = sum(f.get("hechos", 0) for f in a["filas"])
        c = sum(len(f.get("contradichos") or []) for f in a["filas"])
        errores += sum(1 for f in a["filas"] if f.get("error"))
        total_h, total_c = total_h + h, total_c + c
        lineas.append(f"\n{a['novela']}")
        lineas.append(f"    {len(a['filas'])} capítulos · {h} hechos entregados · {c} contradichos "
                      f"({100 * c / h if h else 0:.1f} % de los hechos)")
        for f in a["filas"]:
            for x in f.get("contradichos") or []:
                lineas.append(f"      cap {f['cap']}: {str(x.get('hecho'))[:90]}")
                lineas.append(f"        «{str(x.get('cita'))[:110]}»")
        if a["prompts_sin_hechos"]:
            lineas.append(f"    AVISO: prompts sin hechos reconocibles: {a['prompts_sin_hechos']}")
    lineas.append(f"\nTOTAL: {total_c} hechos contradichos de {total_h} entregados "
                  f"({100 * total_c / total_h if total_h else 0:.2f} %)")
    if errores:
        lineas.append(f"  ({errores} capítulos sin veredicto por error del verificador)")
    return "\n".join(lineas)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("novelas", nargs="+", type=Path)
    ap.add_argument("--validar", action="store_true",
                    help="compara con lo que QA encontró, para saber si el comprobador sirve")
    ap.add_argument("--veces", type=int, default=1,
                    help="repite la medición y da media y recorrido; con 1 sola el número no es fiable")
    ap.add_argument("--salida", type=Path, help="además, un JSONL con todo el detalle")
    a = ap.parse_args(argv[1:])

    exe = ejecutable_claude()
    if exe is None:
        print("no encuentro el ejecutable `claude`")
        return 1
    validas = [n for n in a.novelas if (n / "05_manuscrito").is_dir()]
    if not validas:
        print("ninguna de esas carpetas tiene 05_manuscrito/")
        return 1

    # Tres pasadas idénticas sobre la misma novela dieron 9, 5 y 7. El verificador es un modelo y no
    # un contador: su número oscila un tercio arriba o abajo. Lo salva que repetirlo cuesta un par de
    # dólares y diez minutos, mientras que reducir el ruido de la otra forma --más novelas-- cuesta
    # 19 $ y hora y media cada una. Por eso se promedia aquí y no allí.
    analisis, repeticiones = [], []
    for n in validas:
        print(f"{n.name}")
        pasadas = [analizar(n, exe) for _ in range(max(1, a.veces))]
        cuentas = [sum(len(f.get("contradichos") or []) for f in p["filas"]) for p in pasadas]
        if len(cuentas) > 1:
            print(f"  {a.veces} pasadas: {cuentas} · media {sum(cuentas) / len(cuentas):.1f} "
                  f"· recorrido {max(cuentas) - min(cuentas)}")
        repeticiones.append({"novela": n.name, "cuentas": cuentas})
        analisis.append(pasadas[0])
    print(informe(analisis))
    if a.veces > 1:
        print("\n== estabilidad ==")
        for r in repeticiones:
            c = r["cuentas"]
            print(f"  {r['novela'][19:]:12} {c} · media {sum(c) / len(c):.1f} · recorrido {max(c) - min(c)}")
        print("El detalle listado arriba es el de la primera pasada; la media es lo que hay que comparar.")

    if a.validar:
        print("\n== validación contra QA ==")
        print("Capítulos donde QA marcó contradicción y qué dice el verificador:")
        for n, res in zip(validas, analisis):
            qa = contradicciones_de_qa(n)
            mio = {f["cap"]: len(f.get("contradichos") or []) for f in res["filas"]}
            for cap, cuantas in sorted(qa.items()):
                if cuantas:
                    print(f"  {n.name[19:]:12} cap {cap:2}: QA {cuantas} · verificador {mio.get(cap, '-')}")
        print("Si el verificador dice 0 donde QA marcó, es blando y sus números no valen para comparar.")

    if a.salida:
        with a.salida.open("w", encoding="utf-8") as fh:
            for x in analisis:
                fh.write(json.dumps(x, ensure_ascii=False) + "\n")
        print(f"\ndetalle en {a.salida}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
