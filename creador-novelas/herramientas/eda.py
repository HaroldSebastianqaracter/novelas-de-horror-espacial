"""EDA del harness sobre 37 corridas y el uso por llamada de las que quedaron archivadas.

El coste NO se toma de `corridas.csv`: se recalcula desde los tokens de cada llamada con la tabla
de precios de hoy. Las cifras del CSV se anotaron con la tabla que hubiera en ese momento y con el
preludio contado dos veces, y las dos cosas se descubrieron haciendo este análisis.
"""
from __future__ import annotations

import csv, json, statistics as st, sys
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

RAIZ = Path(sys.argv[1])
ARBOLES = [Path(p) for p in sys.argv[2].split(";")]
SALIDA = Path(sys.argv[3]); SALIDA.mkdir(parents=True, exist_ok=True)

CAMPOS = ("tokens_entrada", "tokens_salida", "tokens_cache_lectura", "tokens_cache_creacion")
PRECIOS = json.loads((RAIZ / "config" / "precios.json").read_text(encoding="utf-8"))["por_millon"]

TINTA, SUAVE, MALLA = "#1A1D21", "#8A93A0", "#E3E6EA"
ROJO, VERDE = "#B3402F", "#2F7A4F"
COLOR = {"escritor": "#C2703D", "qa": "#3D6FA8", "extractor": "#7E9B4E", "orquestador": "#8A6BA8"}
NL = chr(10)
NOMBRE = {"escritor": "Escritor", "qa": "Revisor", "extractor": "Extractor", "orquestador": "Orquestador"}


def lienzo(ancho=9.2, alto=5.0):
    fig, ax = plt.subplots(figsize=(ancho, alto), dpi=150)
    fig.patch.set_facecolor("white"); ax.set_facecolor("white")
    for l in ("top", "right"): ax.spines[l].set_visible(False)
    for l in ("left", "bottom"): ax.spines[l].set_color(MALLA)
    ax.tick_params(colors=SUAVE, labelsize=9)
    ax.grid(axis="y", color=MALLA, lw=.8); ax.set_axisbelow(True)
    return fig, ax


def guardar(fig, nombre, titulo, subtitulo):
    fig.suptitle(titulo, x=.012, y=.982, ha="left", fontsize=13.5, color=TINTA, weight="bold")
    fig.text(.012, .918, subtitulo, ha="left", fontsize=9.3, color=SUAVE)
    fig.tight_layout(rect=(0, .01, 1, .885))
    fig.savefig(SALIDA / nombre, facecolor="white"); plt.close(fig)
    print(f"   {nombre}")


def num(r, k):
    v = (r.get(k) or "").strip()
    try: return float(v)
    except ValueError: return None


# ------------------------------------------------------------------ carga
corridas, arbol_de = [], {}
for arbol in ARBOLES:
    f = arbol / "corridas.csv"
    if not f.is_file(): continue
    for r in csv.DictReader(open(f, encoding="utf-8")):
        clave = (r["novela"], r["cuando"])
        if clave in arbol_de: continue
        corridas.append(r); arbol_de[clave] = arbol


def uso_de(carpeta: Path):
    """(llamadas, preludio). Solo las tandas por uso.jsonl; el preludio, por fases.jsonl."""
    filas, vistos = [], set()
    reg = carpeta / "07_registro"
    if not reg.is_dir(): return None, 0.0
    for d in sorted(c for c in reg.iterdir() if c.name.startswith("tanda_")):
        u = d / "uso.jsonl"
        if not u.is_file(): continue
        for l in u.read_text(encoding="utf-8").splitlines():
            if not l.strip(): continue
            x = json.loads(l)
            ag = str(x.get("agent_id") or "")
            if ag and ag in vistos: continue
            if ag: vistos.add(ag)
            t = PRECIOS.get(x.get("modelo") or "")
            if not t: continue
            filas.append((x.get("rol") or "?", x.get("capitulo"),
                          sum((x.get(k) or 0) * t[k] / 1_000_000 for k in CAMPOS),
                          x.get("tokens_salida") or 0))
    fj = reg / "fases.jsonl"
    prel = sum(float(json.loads(l).get("coste_usd") or 0)
               for l in fj.read_text(encoding="utf-8").splitlines() if l.strip()) if fj.is_file() else 0.0
    return filas, prel


# La carpeta de una novela puede estar en cualquiera de los árboles, no solo en el que la anotó en
# su corridas.csv: el CSV de `aristas` es el acumulado y lista corridas cuyas carpetas viven en
# `velocidad`. Buscando solo en el árbol del CSV se perdían 30 de las 37.
detalle = {}
for r in corridas:
    nombre = r["carpeta"].replace("\\", "/").split("/")[-1]
    for arbol in ARBOLES:
        filas, prel = uso_de(arbol / nombre)
        if filas:
            detalle[nombre] = (r, filas, prel, sum(c for _, _, c, _ in filas) + prel)
            break

print(f"{len(corridas)} corridas · {len(detalle)} con uso por llamada archivado\n")


def real(r):
    """Coste recalculado si hay archivo; si no, el del CSV."""
    n = r["carpeta"].replace("\\", "/").split("/")[-1]
    return detalle[n][3] if n in detalle else num(r, "coste_usd")


# ------------------------------------------------------------------ 1. lo que el CSV se dejaba
print("== gráficas ==")
comp = [(r, num(r, "coste_usd"), v[3]) for n, v in detalle.items()
        for r in [v[0]] if num(r, "coste_usd")]
fig, ax = lienzo(9.4, 4.6)
desv = sorted(((100 * (b - a) / a, r) for r, a, b in comp), key=lambda x: x[0])
for i, (d, r) in enumerate(desv):
    sonnet_q = r["modelo_orquestador"] == "claude-sonnet-5"
    ax.bar(i, d, color=COLOR["qa"] if sonnet_q else COLOR["escritor"], width=.78)
ax.axhline(0, color=TINTA, lw=1)
ax.set_xticks([]); ax.set_xlabel("las 37 corridas, ordenadas por desvio", color=SUAVE, fontsize=9)
ax.set_ylabel("cuanto se equivoco el registro", color=SUAVE, fontsize=9)
ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:+.0f} %"))
sol = [d for d, r in desv if r["modelo_orquestador"] == "claude-opus-5"]
son = [d for d, r in desv if r["modelo_orquestador"] == "claude-sonnet-5"]
from matplotlib.patches import Patch
ax.legend(handles=[Patch(color=COLOR["escritor"], label=f"orquestador en opus (n={len(sol)})"),
                   Patch(color=COLOR["qa"], label=f"orquestador en sonnet (n={len(son)})")],
          frameon=False, fontsize=9, labelcolor=TINTA, loc="upper left")
ax.text(len(desv) * .06, min(d for d, _ in desv) * .62,
        "cobraba de mas:" + chr(10) + "el preludio, dos veces",
        fontsize=9.3, color=TINTA, va="center")
ax.text(len(desv) * .70, max(d for d, _ in desv) * .62,
        "cobraba de menos: sonnet" + chr(10) + "no estaba en la tabla de precios",
        fontsize=9.3, color=TINTA, va="center", ha="center")
guardar(fig, "coste-registrado-vs-real.png", "El registro de costes se equivocaba en las dos direcciones",
        "Diferencia entre lo que anoto corridas.csv y lo que dicen los tokens, novela a novela")

# ------------------------------------------------------------------ 2. coste por capítulo
por_cap = defaultdict(lambda: defaultdict(list))
n_largas = 0
for n, (r, filas, _p, _t) in detalle.items():
    if r["capitulos"] != "15" or r["variante"] != "aristas-dos-agentes": continue
    n_largas += 1
    acum = defaultdict(lambda: defaultdict(float))
    for rol, cap, c, _tk in filas:
        if cap: acum[int(cap)][rol] += c
    for cap, roles in acum.items():
        for rol, c in roles.items(): por_cap[cap][rol].append(c)

caps = sorted(por_cap)
fig, ax = lienzo()
abajo = [0.0] * len(caps)
for rol in ("escritor", "qa"):
    v = [st.mean(por_cap[c].get(rol, [0])) for c in caps]
    ax.bar(caps, v, bottom=abajo, color=COLOR[rol], label=NOMBRE[rol], width=.72)
    abajo = [a + b for a, b in zip(abajo, v)]
ax.plot(caps, abajo, color=TINTA, lw=1.2, marker="o", ms=3.5, zorder=6)
prim, ult = st.mean(abajo[:3]), st.mean(abajo[-3:])
ax.set_xticks(caps); ax.set_xlabel("capítulo", color=SUAVE, fontsize=9)
ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.2f} $"))
ax.legend(frameon=False, fontsize=9, labelcolor=TINTA, loc="upper left")
salto = 7
ax.axvline(salto - .5, color=SUAVE, lw=1, ls="--", zorder=1)
ax.text(salto - .35, max(abajo) * 1.02, "el salto no es gradual:" + chr(10) + "ocurre entre el 6 y el 7",
        fontsize=9.2, color=TINTA, va="top")
ax.text(1.2, max(abajo) * 1.02, f"caps. 1-3: {prim:.2f} $" + chr(10) + f"caps. 13-15: {ult:.2f} $  ({ult/prim:.1f}x)",
        fontsize=9.2, color=TINTA, va="top")
guardar(fig, "coste-por-capitulo.png", "Escribir el capítulo 15 cuesta el doble que el capítulo 1",
        f"Media de {n_largas} novelas de 15 capítulos · dos agentes, orquestador en sonnet · "
        "el preludio no aparece porque no es de ningún capítulo")

# ------------------------------------------------------------------ 3. emparejado
pn = defaultdict(dict)
for r in corridas:
    if r["capitulos"] == "3" and r["variante"]: pn[r["novela"]][r["variante"]] = r
brazos = [("dos-agentes", "Quitar el extractor\n(dos agentes)"),
          ("orquestador-sonnet", "Orquestador en sonnet\n(siguen tres agentes)"),
          ("dos-agentes-sonnet", "Las dos cosas\na la vez")]
fig, axes = plt.subplots(1, 2, figsize=(10.6, 4.9), dpi=150)
fig.patch.set_facecolor("white")
for ax, campo, rotulo in ((axes[0], "minutos", "reloj (min)"), (axes[1], "coste", "coste ($)")):
    ax.set_facecolor("white")
    for l in ("top", "right"): ax.spines[l].set_visible(False)
    for l in ("left", "bottom"): ax.spines[l].set_color(MALLA)
    ax.tick_params(colors=SUAVE, labelsize=9); ax.grid(axis="y", color=MALLA, lw=.8); ax.set_axisbelow(True)
    for i, (v, _e) in enumerate(brazos):
        pares = []
        for n in pn:
            if "base" in pn[n] and v in pn[n]:
                a = real(pn[n]["base"]) if campo == "coste" else num(pn[n]["base"], campo)
                b = real(pn[n][v]) if campo == "coste" else num(pn[n][v], campo)
                if a and b: pares.append((a, b))
        if not pares: continue
        for a, b in pares:
            ax.plot([i - .17, i + .17], [a, b], color=SUAVE, lw=.9, alpha=.5, marker="o", ms=3, mfc="white")
        ma, mb = st.mean(a for a, _ in pares), st.mean(b for _, b in pares)
        ax.plot([i - .17, i + .17], [ma, mb], color=TINTA, lw=2.6, marker="o", ms=6, zorder=6)
        pct = 100 * (mb - ma) / ma
        ax.text(i, max(ma, mb) * 1.09, f"{pct:+.0f} %", ha="center", fontsize=12, weight="bold",
                color=ROJO if pct > -4 else VERDE)
        ax.text(i, min(ma, mb) * .82, f"n={len(pares)}", ha="center", fontsize=8.5, color=SUAVE)
    ax.set_xticks(range(len(brazos)))
    ax.set_xticklabels([e for _, e in brazos], fontsize=8.8, color=TINTA)
    ax.set_ylabel(rotulo, color=SUAVE, fontsize=9)
    ax.set_xlim(-.55, len(brazos) - .45)
fig.suptitle("El ahorro es el modelo del orquestador, no quitar el extractor", x=.012, y=.982,
             ha="left", fontsize=13.5, color=TINTA, weight="bold")
fig.text(.012, .918, "Cada línea gris es una premisa medida en las dos variantes; la negra es la media. "
                     "Siempre contra `base` sobre la misma premisa.", ha="left", fontsize=9.3, color=SUAVE)
fig.tight_layout(rect=(0, .01, 1, .885))
fig.savefig(SALIDA / "emparejado.png", facecolor="white"); plt.close(fig)
print("   emparejado.png")

# ------------------------------------------------------------------ 4. premisa
# El eje va en desviacion sobre la media de cada columna, no en minutos. Con minutos, las novelas
# de 15 capitulos parecian mas dispersas --16 min de recorrido frente a 9-- cuando en proporcion
# son la mitad de dispersas: el ojo leia lo contrario de lo que decia la etiqueta.
fig, ax = lienzo(9.2, 4.6)
g2 = [("base", "base" + NL + "3 ag. + opus"), ("dos-agentes-sonnet", "dos agentes" + NL + "+ sonnet"),
      ("sin-aristas", "15 caps" + NL + "sin aristas"), ("aristas-dos-agentes", "15 caps" + NL + "con aristas")]
etiquetas = []
for i, (v, et) in enumerate(g2):
    mins = [num(r, "minutos") for r in corridas
            if r["variante"] == v and r["completa"] == "1" and num(r, "minutos")]
    if not mins: continue
    m = st.mean(mins)
    rel = [100 * (x - m) / m for x in mins]
    ax.vlines(i, min(rel), max(rel), color=SUAVE, lw=1.4)
    ax.scatter([i] * len(rel), rel, s=46, color=COLOR["escritor"], zorder=5, edgecolor="white", lw=.8)
    ax.scatter([i], [0], s=160, marker="_", color=TINTA, lw=2.6, zorder=6)
    ax.text(i, max(rel) + 3.4, f"{max(rel)-min(rel):.0f} %", ha="center", fontsize=13, weight="bold", color=TINTA)
    etiquetas.append(et + NL + f"media {m:.0f} min")
ax.axhline(0, color=MALLA, lw=1)
ax.set_xticks(range(len(etiquetas))); ax.set_xticklabels(etiquetas, fontsize=9, color=TINTA)
ax.set_xlim(-.5, len(etiquetas) - .5)
ax.set_ylabel("desviacion sobre la media de su columna", color=SUAVE, fontsize=9)
ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:+.0f} %"))
guardar(fig, "premisa-vs-arquitectura.png", "La premisa mueve el reloj tanto como la arquitectura",
        "Dentro de cada columna la variante no cambia: lo que se ve es la premisa y el azar.")

# ------------------------------------------------------------------ 5. fiabilidad
fig, ax = lienzo(9.4, 3.2)
orden = sorted(corridas, key=lambda r: r["cuando"])
for i, r in enumerate(orden):
    ok = r["completa"] == "1"
    ax.scatter(i, 0, s=95, marker="o" if ok else "X", color=VERDE if ok else ROJO, zorder=5)
fallos = sum(1 for r in orden if r["completa"] != "1")
corte = next(i for i, r in enumerate(orden) if all(x["completa"] == "1" for x in orden[i:]))
ax.axvline(corte - .5, color=TINTA, lw=1, ls="--")
ax.text(corte + .4, .5, f"desde aquí, {len(orden)-corte} corridas seguidas sin un fallo",
        fontsize=10, color=VERDE, va="center")
ax.text(corte - .9, .5, f"{fallos} de las primeras {corte}\nno terminaron", fontsize=10,
        color=ROJO, va="center", ha="right")
ax.set_ylim(-1, 1.1); ax.set_yticks([]); ax.grid(False)
ax.spines["left"].set_visible(False)
ax.set_xticks([0, len(orden) - 1]); ax.set_xticklabels(["18/09", "20/09"], color=SUAVE)
guardar(fig, "fiabilidad.png", "Las corridas que se caen son historia",
        "Aspa roja = la novela no llegó al final. No dice nada sobre si el texto salió coherente.")

# ------------------------------------------------------------------ números
print("\n== números para el documento ==")
for campo, et in (("minutos", "reloj"),):
    pass
for v, _e in brazos:
    pares = [(real(pn[n]["base"]), real(pn[n][v])) for n in pn if "base" in pn[n] and v in pn[n]]
    parm = [(num(pn[n]["base"], "minutos"), num(pn[n][v], "minutos")) for n in pn
            if "base" in pn[n] and v in pn[n]]
    if not pares: continue
    ma, mb = st.mean(a for a, _ in parm), st.mean(b for _, b in parm)
    ca, cb = st.mean(a for a, _ in pares), st.mean(b for _, b in pares)
    print(f"  {v:22} n={len(pares)}  reloj {ma:5.1f}->{mb:5.1f} ({100*(mb-ma)/ma:+5.1f} %)"
          f"   coste {ca:5.2f}->{cb:5.2f} ({100*(cb-ca)/ca:+5.1f} %)")

s3 = [r for r in corridas if r["variante"] == "dos-agentes-sonnet" and r["capitulos"] == "3"]
s15 = [r for r in corridas if r["variante"] == "aristas-dos-agentes"]
p3 = st.mean(real(r) / 3 for r in s3 if real(r))
p15 = st.mean(real(r) / 15 for r in s15 if real(r))
print(f"  $/capítulo, 2 agentes+sonnet:  3 caps {p3:.2f}   15 caps {p15:.2f}  ({100*(p15-p3)/p3:+.0f} %)")
print(f"  coste por capítulo: primeros 3 {prim:.2f} $  últimos 3 {ult:.2f} $  ({ult/prim:.1f}×)")
prel = [v[2] for v in detalle.values() if v[0]["capitulos"] == "15"]
tot15 = [v[3] for v in detalle.values() if v[0]["capitulos"] == "15"]
print(f"  preludio: {st.mean(prel):.2f} $ ({100*st.mean(prel)/st.mean(tot15):.0f} % de una novela de 15)")
for capn in ("3", "15"):
    rs = [r for r in corridas if r["capitulos"] == capn and r["completa"] == "1"]
    e = st.mean(num(r, "escritor_tokens_salida") or 0 for r in rs)
    q = st.mean(num(r, "qa_tokens_salida") or 0 for r in rs)
    print(f"  {capn:>2} caps (n={len(rs)}): escritor {e:7.0f} tok · revisor {q:7.0f} tok · "
          f"revisor/escritor {q/e:.2f}")
