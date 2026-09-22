# Backend

Stack: FastAPI + Python 3.12 + SQLite. Motor de agentes: Claude Code.

Implementa [specs/spec1.md](../../specs/spec1.md).

## Arrancar

Son **dos comandos**, no uno: así se reinicia la API sin matar una generación en curso, que
puede durar horas.

```bash
python -m venv .venv && ./.venv/Scripts/python.exe -m pip install -e ".[dev,vectores]"

export NOVELAS_DB_PATH=./novela.db
./.venv/Scripts/python.exe -m worker    # el único que escribe; aquí vive el orquestador
./.venv/Scripts/python.exe -m main      # el borde HTTP; solo lee
```

Con `NOVELAS_PUERTO=falso` el pipeline entero corre sin Claude Code instalado y sin gastar
nada. Es lo que usan los tests.

## Cómo está cortado

```text
main.py          el borde HTTP. Solo lee; actuar es encolar una intención
worker.py        el único proceso que escribe
config.py        único sitio donde se lee el entorno
compartido/      infraestructura y canon: db, grafo, contexto, puerto, vectores
orquestador/     qué fase toca, puertas, política de fallo, reversión
tareas/          una carpeta por agente, con su esquema, su servicio y su puerta
```

Dos reglas lo sostienen, y las dos están comprobadas en `tests/test_arquitectura.py`:
**una tarea no importa de otra**, y **FastAPI solo aparece en el borde HTTP**.

## Probar

```bash
./.venv/Scripts/python.exe -m pytest -q
./.venv/Scripts/python.exe -m ruff check .
```
