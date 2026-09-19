"""Convierte una novela del harness en un libro LaTeX compilable.

El manuscrito que deja el harness es prosa plana en UTF-8: sin encabezados, sin marcas de
capítulo, con raya española para el diálogo y algún `*cursiva*` suelto. Todo lo que hace un libro
—portada, índice, apertura de capítulo, caja de texto— vive fuera del manuscrito, repartido entre
`01_concepto/premisa.md` (título y logline) y `04_estado/capitulos.json` (los títulos de la
escaleta). Este script junta las tres cosas y las mete en `herramientas/plantillas-latex/libro.tex`.

Dos decisiones que conviene tener presentes al leer el código:

- **El diseño no está aquí.** La plantilla es un `.tex` con marcadores `{{...}}` y la sustitución
  es un `replace` literal. Quien quiera otra tipografía o otra portada edita la plantilla; este
  fichero solo decide qué texto va en cada hueco.
- **Escapar es lo único que no puede fallar.** El texto lo escribe un modelo y puede traer
  cualquier carácter. Un `%` sin escapar no rompe la compilación: se come en silencio el resto de
  la línea y el libro sale con una frase menos. Por eso el escapado va antes que cualquier otra
  transformación, y las marcas propias (`\\emph`, `\\raya`) se inyectan después, sobre texto ya
  seguro.

Uso:
    python herramientas/a_latex.py 09_archivo/2026-09-18T13-03-10_el-pasajero-del-vacio
    python herramientas/a_latex.py <novela> --salida libro.tex --pdf
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

PLANTILLA_POR_DEFECTO = Path(__file__).resolve().parent / "plantillas-latex" / "libro.tex"

# En este orden: tectonic se trae solo lo que le falta y no deja basura; latexmk sabe cuántas
# pasadas hacen falta; xelatex va antes que pdflatex porque la plantilla tira de fontspec cuando
# puede. El último es el que está en cualquier instalación vieja.
MOTORES = ("tectonic", "latexmk", "xelatex", "pdflatex")


class ErrorDeConversion(Exception):
    """Fallo esperable (falta un fichero, el JSON no es JSON). Se imprime, no se traza."""


# ---------------------------------------------------------------------------
# Lectura de la novela
# ---------------------------------------------------------------------------

def _leer_texto(ruta: Path) -> str:
    """Lee UTF-8 y normaliza los saltos de línea.

    Los manuscritos del harness vienen con CRLF (se escriben en Windows). Si no se normaliza, el
    `\\r` sobrevive hasta el `.tex` y aparece como espacio fantasma al final de cada párrafo.
    """
    try:
        crudo = ruta.read_bytes()
    except OSError as exc:
        raise ErrorDeConversion(f"no se puede leer {ruta}: {exc}") from exc
    # `errors="replace"` en vez de reventar: preferimos un libro con un carácter raro a ninguno.
    texto = crudo.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")
    # El NUL se quita porque `escapar` lo usa como centinela interno; en prosa no pinta nada.
    return texto.replace(_CENTINELA, "")


def _campo(texto: str, etiqueta: str) -> str:
    """El valor de un campo `Etiqueta: ...` de premisa.md, hasta el siguiente campo o línea vacía.

    Se corta también en `\\n<palabra>:` porque los campos van seguidos sin línea en blanco en
    algunas premisas, y sin ese corte la logline se llevaría por delante la premisa entera.
    """
    m = re.search(rf"^{etiqueta}\s*:\s*(.+?)(?=\n\s*\n|\n\w+\s*:|\Z)",
                  texto, re.MULTILINE | re.DOTALL)
    return " ".join(m.group(1).split()) if m else ""


def leer_premisa(raiz: Path) -> tuple[str, str]:
    """Saca (título, logline) de `01_concepto/premisa.md`.

    El fichero es de campos etiquetados (`Título:`, `Logline:`, `Premisa:`) y cada campo puede
    ocupar varias líneas hasta el siguiente campo o la siguiente línea en blanco. Si falta el
    fichero o el título, no se aborta: una novela a medio archivar sigue mereciendo un PDF, así que
    se cae al nombre de la carpeta y se avisa por stderr.
    """
    ruta = raiz / "01_concepto" / "premisa.md"
    titulo, logline = "", ""
    if ruta.exists():
        texto = _leer_texto(ruta)
        titulo = _campo(texto, r"T[íi]tulo")
        logline = _campo(texto, r"Logline")
    if not titulo:
        # El nombre de carpeta es `2026-09-18T13-03-10_el-pasajero-del-vacio`: el sello de tiempo
        # no dice nada al lector, así que solo se queda con la parte legible.
        resto = raiz.name.split("_", 1)[-1]
        titulo = resto.replace("-", " ").strip().capitalize() or raiz.name
        _avisar(f"sin «Título:» en premisa.md; se usa «{titulo}»")
    return titulo, logline


def leer_escaleta(raiz: Path) -> dict[int, str]:
    """Mapa {número de capítulo: título} desde `04_estado/capitulos.json`.

    La escaleta es opcional a propósito. Hay novelas archivadas sin ella (se cortaron antes de
    escribirla) y el manuscrito existe igual; en ese caso los capítulos salen solo numerados.
    """
    ruta = raiz / "04_estado" / "capitulos.json"
    if not ruta.exists():
        _avisar("sin capitulos.json: los capítulos irán sin título")
        return {}
    try:
        datos = json.loads(_leer_texto(ruta))
    except json.JSONDecodeError as exc:
        _avisar(f"capitulos.json ilegible ({exc}); los capítulos irán sin título")
        return {}
    # El harness lo escribe como lista, pero alguna versión lo envolvió en {"capitulos": [...]}.
    if isinstance(datos, dict):
        datos = datos.get("capitulos", [])
    titulos: dict[int, str] = {}
    if isinstance(datos, list):
        for i, cap in enumerate(datos, start=1):
            if not isinstance(cap, dict):
                continue
            try:
                num = int(cap.get("num", i))
            except (TypeError, ValueError):
                num = i
            titulo = str(cap.get("titulo") or "").strip()
            if titulo:
                titulos[num] = titulo
    return titulos


def leer_capitulos(raiz: Path) -> list[tuple[int, str]]:
    """Los `05_manuscrito/cap_N.md` que existan, ordenados por número.

    Se toma como fuente el disco y no `manifest.json`. El manifiesto dice cuántos capítulos quedaron
    *cerrados*, que es otra cosa: hay archivos con un borrador de más (se cortó la corrida durante
    el QA) y otros con un hueco en medio. Se incluye lo que hay y se avisa de las dos anomalías,
    porque un salto de numeración en el libro es algo que el lector nota y el script no puede
    arreglar.
    """
    carpeta = raiz / "05_manuscrito"
    if not carpeta.is_dir():
        raise ErrorDeConversion(f"no hay manuscrito en {carpeta}")
    encontrados: list[tuple[int, str]] = []
    for ruta in carpeta.glob("cap_*.md"):
        m = re.fullmatch(r"cap_(\d+)", ruta.stem)
        if m:
            encontrados.append((int(m.group(1)), _leer_texto(ruta)))
    encontrados.sort(key=lambda par: par[0])
    if not encontrados:
        raise ErrorDeConversion(f"no hay ningún cap_N.md en {carpeta}")

    numeros = [n for n, _ in encontrados]
    huecos = [n for n in range(numeros[0], numeros[-1] + 1) if n not in numeros]
    if huecos:
        _avisar(f"faltan capítulos {huecos}: el libro saldrá con el salto")
    cerrados = _capitulos_cerrados(raiz)
    if cerrados is not None and numeros[-1] > cerrados:
        _avisar(f"el capítulo {numeros[-1]} no está cerrado en el manifiesto; se incluye igual")
    return encontrados


def _capitulos_cerrados(raiz: Path) -> int | None:
    ruta = raiz / "04_estado" / "manifest.json"
    if not ruta.exists():
        return None
    try:
        return int(json.loads(_leer_texto(ruta)).get("ultimo_capitulo_cerrado"))
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Texto a LaTeX
# ---------------------------------------------------------------------------

# La barra invertida es el caso enredado: su sustituto (`\textbackslash{}`) lleva llaves dentro, y
# las llaves también hay que escaparlas. Se haga en el orden que se haga, una regla pisa a la otra.
# Se rompe el nudo con un centinela: la barra se cambia por un carácter que no puede aparecer en un
# manuscrito, se escapa todo lo demás tranquilamente, y al final el centinela se convierte en la
# macro de verdad.
_CENTINELA = "\x00"

_ESCAPES = (
    ("\\", _CENTINELA),
    ("{", r"\{"),
    ("}", r"\}"),
    ("&", r"\&"),
    ("%", r"\%"),
    ("$", r"\$"),
    ("#", r"\#"),
    ("_", r"\_"),
    ("~", r"\textasciitilde{}"),
    ("^", r"\textasciicircum{}"),
    # No rompen la compilación, pero en T1 salen como glifos que nadie pidió (`<` y `>` sobre todo).
    ("<", r"\textless{}"),
    (">", r"\textgreater{}"),
    ("|", r"\textbar{}"),
)

# Caracteres que sí existen en el texto pero que conviene traducir a la macro equivalente: los
# puntos suspensivos como glifo único quedan demasiado apretados, y el espacio duro tiene que
# seguir siéndolo al pasar por LaTeX.
_TRADUCCIONES = (
    ("\u2026", r"\dots{}"),
    ("\u00a0", "~"),
)


def escapar(texto: str) -> str:
    """Neutraliza todo lo que LaTeX interpretaría.

    Se aplica al texto crudo, antes de cualquier otra cosa. A partir de aquí el resto del módulo
    puede inyectar macros sin miedo, porque nada de lo que venga del manuscrito puede ya
    confundirse con una de ellas.
    """
    for origen, destino in _ESCAPES:
        texto = texto.replace(origen, destino)
    for origen, destino in _TRADUCCIONES:
        texto = texto.replace(origen, destino)
    return texto.replace(_CENTINELA, r"\textbackslash{}")


# Un párrafo que solo tiene asteriscos, rayas o puntos es un corte de escena, no prosa.
_CORTE_DE_ESCENA = re.compile(r"^(?:\*|\#|·|—|–|-|\.){1,9}$")


def normalizar_dialogo(parrafo: str) -> str:
    """Pone la raya española donde toca, con sus espacios.

    La raya (—) no es el guión inglés y no se comporta igual: abre el parlamento **pegada** a la
    primera palabra y cierra el inciso pegada a la última, sin espacio por dentro. El modelo casi
    siempre lo hace bien, pero a veces escribe `- Sin registro` o `algo — dijo`, y eso en un libro
    se ve. Se normalizan tres cosas y ninguna más, para no reescribirle la prosa a nadie:

    1. guión o raya al principio del párrafo -> raya pegada a la palabra;
    2. raya que abre inciso con espacio detrás -> se le quita el espacio;
    3. raya que cierra inciso con espacio delante de un signo de puntuación -> se le quita.
    """
    # (1) Apertura: `-`, `--`, `–` o `—` con o sin espacio. Se acepta el guión suelto porque es el
    # error típico, pero solo en la primera posición: a mitad de línea un guión es un guión.
    parrafo = re.sub(r"^[\-–—]{1,3}[ \t]*", "—", parrafo)
    # (2) Raya con espacio a los dos lados: abre inciso, así que se pega a lo que viene.
    parrafo = re.sub(r"(?<=[ \t])—[ \t]+", "—", parrafo)
    # (3) Raya seguida de puntuación con espacio delante: cierra inciso, se pega a lo anterior.
    parrafo = re.sub(r"[ \t]+—(?=[.,;:!?)»\"]|$)", "—", parrafo)
    return parrafo


def _cursivas(parrafo: str) -> str:
    """`*así*` -> `\\emph{así}`.

    Es el único resto de markdown que aparece en los manuscritos (nombres de nave, sobre todo).
    El patrón exige que el asterisco de apertura no lleve espacio detrás y el de cierre no lo lleve
    delante; así un asterisco suelto usado como corte de escena o como énfasis a medias se queda
    como asterisco en vez de tragarse media página buscando pareja.
    """
    return re.sub(r"\*(?=\S)(.+?)(?<=\S)\*", r"\\emph{\1}", parrafo)


def parrafos(texto: str) -> list[str]:
    """Parte el capítulo en párrafos: línea en blanco separa, salto simple no.

    Dentro de un párrafo los saltos se convierten en espacio porque en LaTeX un salto de línea ya
    es un espacio, y dejarlos tal cual solo ensucia el `.tex` al inspeccionarlo.
    """
    bloques = re.split(r"\n[ \t]*\n+", texto.strip())
    return [" ".join(b.split()) for b in bloques if b.strip()]


def convertir_capitulo(texto: str) -> str:
    """El cuerpo LaTeX de un capítulo, sin su apertura."""
    # Se acumulan pares (separador_previo, texto). El separador importa: `\escena` termina con un
    # `\noindent` para el párrafo que viene, y una línea en blanco detrás lo anularía —cerraría el
    # párrafo antes de que empiece— dejando la sangría que justamente queríamos quitar.
    salida: list[str] = []
    for bruto in parrafos(texto):
        if _CORTE_DE_ESCENA.match(bruto):
            salida.append("\\escena")
            continue
        # Escapar primero, siempre. A partir de esta línea el texto ya no puede hacer daño.
        p = _cursivas(normalizar_dialogo(escapar(bruto)))
        # La marca de diálogo es un gancho de diseño: hoy `\dialogo` no cambia nada, pero permite
        # rediseñar todos los parlamentos desde la plantilla sin volver a convertir la novela.
        if p.startswith("—"):
            # `\raya` impide que la raya se quede sola al final del renglón.
            p = "\\dialogo{\\raya " + p[1:].lstrip() + "}"
        salida.append(p)
    if not salida:
        # Un capítulo vacío no debe tumbar el libro ni desaparecer sin dejar rastro: se marca.
        _avisar("capítulo sin texto: se deja una nota en el libro")
        salida.append("\\emph{[Capítulo sin texto.]}")
    return _unir(salida)


def _unir(bloques: list[str]) -> str:
    """Une párrafos con línea en blanco, salvo detrás de una macro que abre el párrafo siguiente."""
    texto = bloques[0]
    for anterior, actual in zip(bloques, bloques[1:]):
        texto += ("\n" if anterior.startswith("\\escena") else "\n\n") + actual
    return texto


def construir_cuerpo(capitulos: list[tuple[int, str]], titulos: dict[int, str]) -> str:
    piezas = []
    for num, texto in capitulos:
        # Sin título en la escaleta el capítulo se queda con su número; el `\capitulo` de la
        # plantilla ya imprime «Capítulo N» encima, así que no queda huérfano.
        titulo = escapar(titulos.get(num, ""))
        # Un solo salto entre la apertura y el primer párrafo, por lo mismo que en `_unir`:
        # `\capitulo` deja un `\noindent` preparado y una línea en blanco lo tiraría a la basura.
        piezas.append(f"\\capitulo{{{num}}}{{{titulo}}}\n{convertir_capitulo(texto)}")
    # No hace falta un \clearpage entre capítulos: `\capitulo` empieza con \cleardoublepage.
    return "\n\n".join(piezas)


def pie_de_portada(raiz: Path) -> str:
    """La línea pequeña bajo la logline.

    Llevaba el nombre de la carpeta de archivo, que en la primera compilación salió impreso en la
    cubierta como `2026-09-18T13-03-10_el-pasajero-del-vacio-del-arbol-principal`. Sirve para
    rastrear la novela, pero un identificador de carpeta en la portada de un libro es ruido. Se queda
    la fecha, que es lo único de ese nombre que le dice algo a un lector.
    """
    sello = raiz.name[:10]
    if len(sello) == 10 and sello[4] == "-" and sello[7] == "-" and sello[:4].isdigit():
        return sello
    return ""


def construir_documento(raiz: Path, plantilla: Path = PLANTILLA_POR_DEFECTO) -> tuple[str, str]:
    """Devuelve (documento .tex completo, título de la novela)."""
    if not plantilla.exists():
        raise ErrorDeConversion(f"no encuentro la plantilla {plantilla}")
    titulo, logline = leer_premisa(raiz)
    cuerpo = construir_cuerpo(leer_capitulos(raiz), leer_escaleta(raiz))
    reemplazos = {
        "{{TITULO}}": escapar(titulo),
        "{{LOGLINE}}": escapar(logline),
        "{{PIE_PORTADA}}": escapar(pie_de_portada(raiz)),
        "{{CUERPO}}": cuerpo,
    }
    doc = _leer_texto(plantilla)
    # El cuerpo ocupa cientos de líneas: si el marcador apareciera dos veces (por ejemplo dentro de
    # un comentario de la plantilla que lo documenta) la segunda copia se saldría del comentario y
    # el .tex no compilaría. Es un fallo fácil de cometer editando la plantilla y difícil de
    # diagnosticar en el log de LaTeX, así que se caza aquí.
    if doc.count("{{CUERPO}}") != 1:
        raise ErrorDeConversion(
            f"la plantilla {plantilla} tiene {doc.count('{{CUERPO}}')} marcadores {{{{CUERPO}}}}; "
            "tiene que haber exactamente uno")
    for marcador, valor in reemplazos.items():
        doc = doc.replace(marcador, valor)
    return doc, titulo


# ---------------------------------------------------------------------------
# Compilación
# ---------------------------------------------------------------------------

def _orden(motor: str, tex: Path) -> list[list[str]]:
    """Las llamadas que hay que hacer con cada motor.

    xelatex y pdflatex van dos veces porque el índice necesita una pasada previa que escriba el
    `.toc`; tectonic y latexmk ya deciden ellos cuántas pasadas hacen falta.
    """
    salida = str(tex.parent)
    if motor == "tectonic":
        return [["tectonic", "--outdir", salida, str(tex)]]
    if motor == "latexmk":
        return [["latexmk", "-pdf", "-interaction=nonstopmode", f"-outdir={salida}", str(tex)]]
    base = [motor, "-interaction=nonstopmode", f"-output-directory={salida}", str(tex)]
    return [base, base]


def compilar(tex: Path) -> Path | None:
    """Intenta producir el PDF. Devuelve su ruta, o None si no había con qué.

    No se instala nada ni se falla por esto: el `.tex` ya está escrito y es el entregable. Si no hay
    motor, se dice cómo conseguir uno y se sigue.
    """
    motor = next((m for m in MOTORES if shutil.which(m)), None)
    if motor is None:
        _avisar("no hay motor LaTeX instalado (se probaron: " + ", ".join(MOTORES) + ")")
        _avisar(f"el .tex está en {tex}; para compilarlo: instala tectonic y ejecuta "
                f"`tectonic \"{tex.name}\"` en {tex.parent}")
        return None
    print(f"compilando con {motor}...", file=sys.stderr)
    for orden in _orden(motor, tex):
        proc = subprocess.run(orden, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", cwd=str(tex.parent))
        if proc.returncode != 0:
            # El log de LaTeX es larguísimo y el error real está en las líneas que empiezan por `!`.
            errores = [l for l in (proc.stdout + proc.stderr).splitlines() if l.startswith("!")]
            _avisar(f"{motor} falló (código {proc.returncode}). "
                    + ("Primeros errores:\n  " + "\n  ".join(errores[:5]) if errores
                       else "Revisa el .log junto al .tex."))
            return None
    pdf = tex.with_suffix(".pdf")
    return pdf if pdf.exists() else None


def _avisar(mensaje: str) -> None:
    print(f"aviso: {mensaje}", file=sys.stderr)


# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Convierte una novela del harness en un libro LaTeX.")
    ap.add_argument("novela", type=Path, help="carpeta de la novela (raíz o 09_archivo/<sello>)")
    ap.add_argument("--salida", type=Path, default=None,
                    help="ruta del .tex (por defecto, ./<titulo>.tex en el directorio actual)")
    ap.add_argument("--plantilla", type=Path, default=PLANTILLA_POR_DEFECTO)
    ap.add_argument("--pdf", action="store_true", help="compilar si hay un motor LaTeX")
    args = ap.parse_args(argv)

    try:
        raiz = args.novela.resolve()
        if not raiz.is_dir():
            raise ErrorDeConversion(f"{args.novela} no es una carpeta")
        doc, titulo = construir_documento(raiz, args.plantilla.resolve())

        salida = args.salida
        if salida is None:
            # Por defecto se escribe en el directorio actual y NO dentro de la novela: las novelas
            # archivadas son material de medición y meterles ficheros nuevos —y los .aux, .log y
            # .toc que deja LaTeX al lado— ensucia lo que otras herramientas leen de ahí.
            salida = Path.cwd() / (_nombre_de_fichero(titulo) + ".tex")
        salida = salida.resolve()
        salida.parent.mkdir(parents=True, exist_ok=True)
        salida.write_text(doc, encoding="utf-8")
        print(salida)

        if args.pdf:
            pdf = compilar(salida)
            if pdf is not None:
                print(pdf)
    except ErrorDeConversion as exc:
        # El usuario de esta herramienta no quiere un traceback: quiere saber qué falta.
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


def _nombre_de_fichero(titulo: str) -> str:
    """Un nombre de fichero seguro a partir del título, para no depender del nombre de carpeta."""
    limpio = re.sub(r"[^\w\s-]", "", titulo, flags=re.UNICODE).strip()
    limpio = re.sub(r"[\s_]+", "-", limpio).lower()
    return limpio or "libro"


if __name__ == "__main__":
    sys.exit(main())
