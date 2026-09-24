# Guion del vídeo de demo

Material de trabajo para grabar el vídeo. No es un entregable: bórralo o déjalo fuera del README de esta carpeta cuando el vídeo esté hecho. Duración objetivo: **4 a 6 minutos**. Graba la pantalla con la voz encima (Loom u OBS) y enseña **solo los nombres ficticios del brief de ejemplo**.

## Antes de grabar

1. **La novela:** usa una **copia** de `src/backend/novela_10cap_final.db`, nunca el original. a1 prepara la suya (`novela_10cap_pdf.db`).
2. **Tres terminales**, desde `src/backend` con `.venv\Scripts\python.exe`:
   - la API: `$env:NOVELAS_DB_PATH="<copia>.db"; .venv\Scripts\python.exe main.py` (queda en `http://127.0.0.1:8000`);
   - el worker, con la misma base (`worker.py`, y `NOVELAS_PUERTO=terminal` para el cambio real);
   - la web: en `src/frontend`, `npm run dev`.
3. **El cambio del lector cuesta dinero** (entre 5 y 10 $, según los capítulos que toque) y tarda unos minutos por capítulo. Lánzalo una vez antes y graba el resultado, o graba el lanzamiento y corta la espera.
4. Deja abiertos en otras pestañas: Langfuse (la sesión de la novela), `ejemplos/novela-ejemplo.pdf` y la tabla de evals.

## Escenas

| # | Tiempo | Qué enseñas | Qué dices (idea) |
| --- | --- | --- | --- |
| 1 | 0:00-0:30 | La web: la **portada con la dedicatoria** | «Esto es una novela de 10 capítulos generada para un regalo. La dedicatoria y el protagonista salen del encargo del comprador.» |
| 2 | 0:30-1:00 | El **índice** navegable; entra en un capítulo | «Cada capítulo ha pasado cinco puertas de control antes de aceptarse.» |
| 3 | 1:00-1:40 | La **ficha de personajes y lugares**; pulsa un enlace y salta al capítulo donde aparece | «La ficha no la escribe un modelo: se genera desde la story bible en SQLite.» |
| 4 | 1:40-3:20 | **El cambio del lector:** selecciona un hecho en el texto y pide el cambio (por ejemplo, el nombre de la perra) | «El sistema busca en la story bible qué capítulos usan ese hecho y regenera solo esos, sin romper la continuidad.» |
| 5 | 3:20-4:00 | La nueva versión: los **capítulos marcados como cambiados**, y la **versión anterior conservada** | «Los capítulos que no usaban el hecho no se tocan, y la versión anterior sigue disponible.» Es la evidencia obligatoria: que se vea claro. |
| 6 | 4:00-4:40 | **Langfuse:** la sesión de la novela, una traza con sus spans por rol, tokens y coste, y los scores de las puertas | «Cada llamada queda trazada con su coste; la novela entera costó 41 $, medidos aquí.» |
| 7 | 4:40-5:10 | La **tabla de evals** y, de pasada, el PDF de ejemplo | «Cinco briefs, uno adversarial y otro con una incoherencia temporal, y qué validador cazó cada cosa.» |
| 8 | 5:10-5:30 | Cierre | Una frase con la decisión de diseño más importante: el canon vive en código (SQLite y puertas) y no en la memoria del modelo. |

## Si algo falla al grabar

- **El cambio del lector para** (por continuidad o por el juez): es el sistema funcionando. Enséñalo, di qué puerta lo paró y por qué, y usa la toma buena para la escena 5.
- **La web no carga la novela:** comprueba que la API usa la misma copia que el worker (`NOVELAS_DB_PATH`).
