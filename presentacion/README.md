# /presentacion — SpaceMaker · storyMaker

Propuesta de SpaceMaker a **Faro Regalos, S.L.** (cliente ficticio) para el examen de Harness Engineering.
Exposición: 10 minutos · 25 de septiembre de 2026.

**Idioma:** castellano, con los términos técnicos en inglés (harness, validators, LLM-as-judge, guardrails, evals, tuning, trace, score, checkpoint, prompt).

## Contenido

| Fichero | Qué es |
|---|---|
| `storymaker-deck.pptx` | El deck en formato editable (PowerPoint), 15 diapositivas principales + 9 de anexos (A1–A7), con notas del orador |
| `storymaker-deck.pdf` | El deck completo en PDF (24 páginas) |
| `notas-del-orador.md` | Guion de cada diapositiva, con los tiempos |
| `anexo-tla-spec.pdf` | A1 · Especificación TLA+ comentada (2 páginas) |
| `anexo-evals-tabla.pdf` | A2 · Tabla de evals completa (2 páginas) |
| `anexo-sqlite-esquema.pdf` | A3 · Esquema SQLite de la story bible |
| `anexo-red-team.pdf` | A4 · Red-team log |
| `anexo-modelos.pdf` | A5 · Opus 5.5 frente a Sonnet 5 |
| `anexo-langfuse.pdf` | A6 · Langfuse y validación con browser MCP |
| `anexo-rubrica.pdf` | A7 · Rúbrica del LLM frente a revisión humana |
| `README.md` | Este fichero |

## Estructura del deck y tiempos

| # | Diapositiva | Bloque | Tiempo |
|---|---|---|---|
| 1 | Portada | Propuesta | 0:20 |
| 2 | Problema y cliente | El producto | 0:40 |
| 3 | Configuración | El producto | 0:40 |
| 4 | Lectura y corrección | El producto | 0:40 |
| 5 | Arquitectura del harness | El harness | 1:00 |
| 6 | Contexto, memoria y hooks | El harness | 0:45 |
| 7 | Los 4 tipos de validators | Validación | 0:50 |
| 8 | Tabla de evals | Validación | 0:50 |
| 9 | Validadores formales | Validación | 0:45 |
| 10 | Tuning y observabilidad | Operación | 0:40 |
| 11 | Guardrails | Operación | 0:30 |
| 12 | Coste por novela | Negocio | 0:40 |
| 13 | Proyecto, volumen y sensibilidad | Negocio | 0:45 |
| 14 | Demo y cierre | Cierre | 0:45 |
| 15 | Contraportada | Contacto | 0:10 |
| | **Total** | | **10:00** |
| 16–17 | A1 · TLA+ (1/2 y 2/2) | Anexos | respaldo |
| 18–19 | A2 · Evals completas (1/2 y 2/2) | Anexos | respaldo |
| 20–24 | A3 SQLite · A4 Red-team · A5 Modelos · A6 Langfuse · A7 Rúbrica | Anexos | respaldo |

## Identidad

- Fondo `#16141B`, superficies `#211E28`, acento naranja `#E0975A`, lavanda `#5B5078`, texto `#ECEAF0`, texto secundario `#A9A4B5`, alerta `#C0392B` (solo en bordes de «riesgo»).
- Títulos en Fraunces con una palabra clave en cursiva naranja; cuerpo y datos en Manrope.
- Logo: wordmark «SpaceMaker» con la «a» de «Space» convertida en alien; versión reducida (el alien en un círculo) en el pie.

## Capturas usadas

- Diap. 4: `docs/proceso/browser-mcp/01-portada.png` y `04-indice-version-2.png`
- Diap. 10 y A6: `docs/proceso/langfuse/langfuse-traza-capitulo-8.png` (trace real del capítulo 8: span de cada rol con latencia y coste, scores de las puertas 3 y 4, rechazo y reintento)
- A6: `docs/proceso/langfuse/langfuse-prompt-versiones.png` (prompt del redactor versionado en Langfuse; #5 → #6 es el tuning)
- A6: `docs/proceso/browser-mcp/02-ficha.png`
- Diap. 14: `docs/proceso/browser-mcp/06-comparacion-capitulo-1.png`

## Vídeo de la demo

[Enlace al vídeo: pendiente]

## Estado de esta carpeta (25-09-2026)

- `storymaker-deck.pptx` es la versión definitiva, con las capturas de Langfuse de la diapositiva 10 y A6.
- `storymaker-deck.pdf` y los anexos se generaron fuera del deck con fuentes sustitutas (Lora y Poppins) y todavía no llevan esas capturas, que están en el `.pptx` y en `docs/proceso/langfuse/`. Se sustituyen por el PDF exportado del deck.
- A7: la revisión humana se añade al terminarla (`src/backend/evals/plantilla_rubrica_humana.csv`).
