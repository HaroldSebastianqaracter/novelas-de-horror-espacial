---
description: Pasa tests, ruff y pyright del backend y resume el resultado exacto
---

Ejecuta la verificación del backend, que es lo que sustituye a una CI en este proyecto. Desde `src/backend`, y en este orden:

```bat
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m pyright
```

Ejecuta los tres aunque falle el primero: el resumen tiene que decir el estado de todos.

Devuelve una tabla con una fila por comando y su resultado literal (por ejemplo, `213 passed, 3 deselected`, `All checks passed!`, `0 errors`). Si algo falla, debajo de la tabla van los fallos con `fichero:línea` y el mensaje, sin arreglar nada: arreglarlo es otro paso.

Los extras `-m modelo` y `-m agente` no corren aquí. El segundo cuesta dinero y solo se lanza con aprobación del autor.
