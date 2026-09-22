# Backend

Stack: FastAPI + Python 3.12 + SQLite. Motor de agentes: Claude Code.

Implementa [specs/spec1.md](../../specs/spec1.md); su plan de verificación está en
[specs/spec1-verification.md](../../specs/spec1-verification.md).

## Preparar el entorno

Una sola vez, desde `src\backend` en **cmd**:

```bat
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

El extra `vectores` es opcional: añade el índice de recuperación, y sin él el pipeline corre
igual.

## Probarlo sin gastar nada

Con `NOVELAS_PUERTO=falso` el pipeline entero corre **sin Claude Code**, con agentes de
demostración que devuelven salidas válidas. Son dos ventanas de cmd.

**Ventana 1, el worker.** Es el único que escribe, y aquí vive el orquestador.

```bat
cd src\backend
set NOVELAS_DB_PATH=novela.db
set NOVELAS_PUERTO=falso
.venv\Scripts\python.exe -m worker
```

**Ventana 2, el lanzador.** Crea una novela, la arranca y muestra cómo avanza.

```bat
cd src\backend
set NOVELAS_DB_PATH=novela.db
set NOVELAS_PUERTO=falso
.venv\Scripts\python.exe demo.py
```

Otras cosas que sabe hacer el lanzador:

```bat
.venv\Scripts\python.exe demo.py --ver
.venv\Scripts\python.exe demo.py --leer 1
.venv\Scripts\python.exe demo.py --parar
.venv\Scripts\python.exe demo.py --relanzar 2
```

Sirven, en orden, para mirar lo que ya hay sin crear nada, imprimir un capítulo, detener la
generación y rehacerla desde un capítulo concreto.

**Ventana 3, la API**, si quieres verlo por HTTP. Es opcional.

```bat
cd src\backend
set NOVELAS_DB_PATH=novela.db
.venv\Scripts\python.exe -m main
```

Queda en `http://127.0.0.1:8000`, con la documentación navegable en `/docs` y el contrato en
`/openapi.json`.

## Con Claude Code de verdad

Lo mismo, cambiando una variable. **Cuesta dinero**: ronda medio dólar por llamada de agente,
y una novela de tres capítulos son unas veinte llamadas.

```bat
set NOVELAS_PUERTO=terminal
```

Claude Code tiene que estar instalado y con la sesión iniciada. El backend no gestiona
ninguna credencial ni la pasa al subproceso.

## Variables de entorno

| Variable | Obligatoria | Defecto | Para qué |
| --- | --- | --- | --- |
| `NOVELAS_DB_PATH` | sí | — | Fichero SQLite de la novela |
| `NOVELAS_PUERTO` | no | `terminal` | `terminal` o `falso` |
| `NOVELAS_CLAUDE_BIN` | no | `claude` | Ejecutable de Claude Code |
| `NOVELAS_POLL_SEGUNDOS` | no | `2` | Cada cuánto sondea el worker |
| `NOVELAS_TIMEOUT_AGENTE_SEGUNDOS` | no | `1800` | Máximo por llamada |
| `NOVELAS_VECTORES` | no | `1` | `0` desactiva el índice |

## Cómo está cortado

```text
main.py          el borde HTTP. Solo lee; actuar es encolar una intencion
worker.py        el unico proceso que escribe
demo.py          lanzador de prueba
config.py        unico sitio donde se lee el entorno
compartido/      infraestructura y canon: db, grafo, contexto, puerto, vectores
orquestador/     que fase toca, puertas, politica de fallo, reversion
tareas/          una carpeta por agente, con su esquema, su servicio y su puerta
```

Dos reglas lo sostienen, y las dos están comprobadas en `tests/test_arquitectura.py`:
**una tarea no importa de otra**, y **FastAPI solo aparece en el borde HTTP**.

## Probar

```bat
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m ruff check .
```
