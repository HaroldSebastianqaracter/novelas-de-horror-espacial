# Documentación de proceso

El razonamiento que llevó a storyMaker a ser como es: qué se decidió construir, qué se descartó, qué cambió tras cada fallo y cómo se comprobó. Es la documentación que pide la entrega del examen; el sistema en sí está descrito en los cuatro documentos de [docs/](../).

| Lo que pide la entrega | Dónde está | Estado |
| --- | --- | --- |
| Spec inicial | [spec-inicial.md](spec-inicial.md) | Escrita |
| Trade-offs | [trade-offs.md](trade-offs.md) | Escrita; se amplía con cada decisión nueva |
| Explainers | [explainers.md](explainers.md) | Los conceptos ya aplicados; los pendientes, marcados |
| Diagramas | [diagramas.md](diagramas.md) | Harness, máquina de estados (la del código y la de TLA+), esquema SQLite y tabla de validadores |
| Registro de iteraciones | [registro-iteraciones.md](registro-iteraciones.md) | Al día hasta el 24 de septiembre de 2026 |
| Red-team log | [red-team-log.md](red-team-log.md) | Formato fijado; casos adversariales pendientes |
| Tabla de evals (cinco briefs, con Claude real) | [evals-tabla.md](evals-tabla.md) | Medida el 24 de septiembre; dos briefs no llegaron a la prosa por el recorte a tres capítulos (explicado) |
| Iteración de tuning (antes y después) | [tuning.md](tuning.md) | Escrita: el prompt del redactor v5 → v6 en la novela de diez capítulos |
| Coste real por novela (para la slide de presupuesto) | [coste.md](coste.md) | Medido en la novela de diez capítulos; precio y escenarios, propuestos |
| Los dos hooks (validación del capítulo y política) | [architecture.md](../architecture.md#los-dos-hooks-del-harness) | Escrito |
| Uso del browser MCP | — | Pendiente (bloque 7 del [plan de entrega](../../specs/storymaker-plan.md)) |
| Skills, subagentes y comandos | [herramientas.md](herramientas.md) | Escrita |
| Resumen de la noche del 23 al 24 de septiembre (trabajo sin el autor) | [noche-23-09.md](noche-23-09.md) | Escrito; la rama `noche-23-09` está sin integrar |

> **Decisión sin entrevistar, 23 de septiembre de 2026.** La documentación de proceso va en una subcarpeta propia y **resume y enlaza, no copia**. Cada decisión ya está justificada en su sitio, en los callouts de `architecture.md`, `definitions.md` y `validators.md`, y en los mensajes de commit de cada fase. Copiarla aquí crearía una segunda versión que se desincroniza con el primer cambio. Se descartó reorganizar `docs/` entero con el formato del examen: `AGENTS.md` fija cuatro tipos de documento que el resto del repo ya cita por su ruta, y moverlos rompería esas referencias. Afecta a `AGENTS.md`, que ahora nombra esta carpeta.
