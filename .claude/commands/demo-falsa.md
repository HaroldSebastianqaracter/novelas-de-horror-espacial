---
description: Corre el pipeline entero con el puerto falso sobre una base temporal y resume lo que pasó
argument-hint: "[capitulos a mirar, opcional]"
---

Corre una novela de principio a fin **sin Claude Code**, con los agentes de demostración, para ver el pipeline funcionar sin gastar nada.

1. Crea un directorio temporal fuera del repo y usa como base `NOVELAS_DB_PATH=<temporal>\novela.db`. **Nunca** `src/backend/novela.db`: es la del autor y suele tener su propio worker encima.
2. Con `NOVELAS_PUERTO=falso` y desde `src/backend`, lanza el worker en segundo plano (`.venv\Scripts\python.exe -m worker`) y **guarda su pid**.
3. En otra orden, `.venv\Scripts\python.exe demo.py --segundos 300`, que crea la novela, la arranca y muestra cómo avanza.
4. Cuando la ejecución termine (`completada`, `completada_con_avisos`, `parada` o `error`), detén **solo** el worker del pid que guardaste y su proceso hijo.

Devuelve: el estado final de la ejecución, los capítulos completados, el veredicto de cada puerta (de `resultado_puerta`) y, si hubo parada o error, su informe resumido. Si el autor pasó capítulos como argumento ($ARGUMENTS), muestra su texto con `demo.py --leer N`.
