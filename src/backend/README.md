# Backend

Stack: FastAPI + Python 3.12 + SQLite. Motor de agentes: Claude Code.

Implementa [specs/spec1.md](../../specs/spec1.md), refinada por [specs/spec2.md](../../specs/spec2.md); sus planes de verificación están en
[specs/spec1-verification.md](../../specs/spec1-verification.md) y [specs/spec2-verification.md](../../specs/spec2-verification.md).

## Preparar el entorno

**Todos los comandos de este README se ejecutan desde `src\backend`.** Es la causa número uno
de que fallen: lanzados desde otro sitio, `pip install -e .` no encuentra el proyecto y
`python -m worker` no encuentra el módulo.

Una sola vez, en **cmd**:

```bat
cd /d "C:\Users\<tu-usuario>\Desktop\Nueva carpeta\novelasv2\src\backend"
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
cd /d "...\novelasv2\src\backend"
set NOVELAS_DB_PATH=novela.db
set NOVELAS_PUERTO=falso
.venv\Scripts\python.exe -m worker
```

**Ventana 2, el lanzador.** Crea una novela, la arranca y muestra cómo avanza.

```bat
cd /d "...\novelasv2\src\backend"
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

Y el cambio del lector sobre una novela completada (spec3, 3.8), que la web pide desde la
propia página:

```bat
.venv\Scripts\python.exe demo.py --cambio "Que se llame «Kira»" --entidad personajes:4
.venv\Scripts\python.exe demo.py --cambio "La esclusa queda a «cuarenta metros»" --hecho 11
```

**Ventana 3, la API**, si quieres verlo por HTTP. Es opcional.

```bat
cd /d "...\novelasv2\src\backend"
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
| `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` | no | — | Claves de Langfuse; sin ellas no se envía nada |
| `LANGFUSE_HOST` | no | `https://cloud.langfuse.com` | Región UE de Langfuse Cloud |

Todas se pueden poner en `src/backend/.env` (copia de `.env.example`, no se commitea), que se
carga solo al arrancar; una variable fijada en la consola manda sobre la del fichero.

## Langfuse

Con las claves en `.env`, el worker envía cada novela a Langfuse al cerrar cada unidad de
trabajo, con los nombres del encargo seudonimizados (spec3, 3.4). Para comprobar las claves o
exportar una novela escrita antes:

```bat
.venv\Scripts\python.exe exportar_langfuse.py --comprobar
.venv\Scripts\python.exe exportar_langfuse.py --novela 1
```

El comando abre la base en solo lectura: se puede lanzar con el worker en marcha.

## Cómo está cortado

```text
main.py          el borde HTTP. Solo lee; actuar es encolar una intencion
worker.py        el unico proceso que escribe
demo.py          lanzador de prueba
exportar_langfuse.py  exporta novelas enteras a Langfuse, en solo lectura
config.py        unico sitio donde se lee el entorno (y el .env)
compartido/      infraestructura y canon: db, grafo, contexto, puerto, vectores
orquestador/     que fase toca, puertas, politica de fallo, reversion
tareas/          una carpeta por agente, con su esquema, su servicio y su puerta
```

Dos reglas lo sostienen, y las dos están comprobadas en `tests/test_arquitectura.py`:
**una tarea no importa de otra**, y **FastAPI solo aparece en el borde HTTP**.

## Verificar

Tres comandos, y los tres tienen que salir limpios antes de cada commit. No hay CI: esto es
lo que la sustituye.

```bat
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m pyright
```

`pyright` va en modo estricto sobre todo el backend salvo los tests. Tres extras que no corren
por defecto:

```bat
rem El golden set de recuperacion, con el modelo de embeddings real (tiene que estar en la cache).
.venv\Scripts\python.exe -m pytest -q -m modelo

rem Las evals del extractor contra el capitulo anotado, con Claude Code de verdad: cuesta
rem dinero, asi que solo con la aprobacion del autor.
.venv\Scripts\python.exe -m pytest -q -s -m agente

rem Regenerar el snapshot del contrato OpenAPI tras un cambio de la API hecho a proposito.
rem Revisa el diff de tests\openapi.json antes de commitear.
set NOVELAS_ACTUALIZAR_OPENAPI=1
.venv\Scripts\python.exe -m pytest -q tests\test_api.py -k contrato
```
