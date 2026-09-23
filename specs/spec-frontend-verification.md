# Verificación — Frontend v1

Plan de verificación de [spec-frontend.md](spec-frontend.md). Métodos y etiquetas según [docs/validators.md](../docs/validators.md).

Actualizado el 23 de septiembre de 2026. Las rutas de evidencia son relativas a `src/frontend/`.

## Cómo leer la tabla

Igual que [spec3-verification.md](spec3-verification.md):

- **Punto ciego:** lo que el método no ve aunque pase.
- **¿Solitario?:** si la propiedad descansa en un solo método.
- **Estado:** `implementado`, `pendiente` o `fallando`.

Aquí no hay datos autodeclarados por un agente: el frontend solo pinta lo que dice la API, así que la regla 3 no aplica.

| # | Propiedad | Requisito | Método | Tag | Punto ciego | ¿Solitario? | Evidencia | Estado |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Los tipos generados coinciden con el snapshot del contrato | RF-FE-API-01 | `npm run tipos` y `git diff --exit-code` sobre el fichero generado | `A` | Lo que la API devuelve y no declara (el `payload` sin esquema, el cuerpo del `422`) | No: la fila 2 cubre los huecos | `npm run tipos:comprobar` | implementado |
| 2 | Los ficheros de deuda (`brief.ts`, `reglas.ts`) coinciden con su fuente en Python | RF-FE-API-04 | Test que compara `reglas.ts` (uniones, resoluciones y conjuntos de estados) y los límites de `brief.ts` con un JSON exportado desde `compartido/tipos.py`, `orquestador/estados.py` y `compartido/brief.py` | `T` | Solo compara lo que se exporta; una regla nueva en Python que no se exporte pasa sin avisar | **Sí**: se retira cuando la API publique lo que falta (sección 5) | `src/compartido/api/deuda.test.ts` | pendiente |
| 3 | Cada uno de los nueve estados cae en su columna, y una novela sin ejecución en «En espera» | RF-FE-TAB-01 | Test unitario parametrizado sobre la función de agrupación | `T` | Un estado nuevo en el backend: la API lo tipa como `string`, así que ni el test ni el compilador lo ven. Se pinta tal cual, con aviso (RF-FE-API-04) | Sí, hasta que la API declare los enumerados; entonces un `switch` exhaustivo lo refuerza | `src/funcionalidades/ejecucion/columnas.test.ts` | implementado |
| 4 | Soltar una tarjeta no la cambia de columna hasta que la ejecución lo confirma, y un rechazo la deja donde estaba con su motivo | RF-FE-TAB-03, RF-FE-DAT-05 | Test de integración con MSW por el menú (intención pendiente, después hecha o rechazada) + test unitario de qué pide soltar en cada columna | `T` | El arrastre de dnd-kit no se ejecuta en jsdom: que soltar llame a esa lógica solo se ha comprobado a mano con Playwright (23-09-2026) | No: la fila 11 lo mira a mano | `src/funcionalidades/ejecucion/intenciones.test.tsx`, `acciones.test.ts` | implementado |
| 5 | Solo se ofrecen las intenciones válidas para el estado y las acciones válidas para el tipo de parada | RF-FE-TAB-03, RF-FE-NOV-01, RF-FE-PAR-02 | Test parametrizado estado × acción y tipo × acción | `T` | Lo que valida el worker además del estado (puertas vigentes para `relanzar`); eso llega como rechazo | No: el rechazo del worker es la segunda barrera | `src/funcionalidades/ejecucion/acciones.test.ts` (estado × acción del tablero), `AlertaParada.test.tsx` (tipo de parada × acción, confirmación en dos pasos y avisos de RF-FE-PAR-04) | implementado |
| 6 | Un evento SSE invalida y no escribe; al reconectar se reconsulta todo | RF-FE-DAT-02, RF-FE-DAT-04 | Test de integración: SSE simulado que se corta, y comprobación de las consultas relanzadas y del `Last-Event-ID` al reconectar, más tests del lector de `text/event-stream` | `T` | Suspensiones largas del equipo y proxies que cortan el stream en silencio. Que el SSE real atraviese el proxy de Vite solo se ha comprobado con mocks | No: el sondeo de RF-FE-DAT-03 cubre el silencio | `src/compartido/api/eventos.test.tsx` | implementado |
| 7 | Un `422 brief_incompleto` lleva al paso de cada campo señalado y lo marca con el mensaje del servidor | RF-FE-BRF-04 | Test de integración con MSW, con un faltante y una contradicción reales (edad frente a intensidad) | `T` | Un código de campo nuevo en el backend que el formulario no sepa ubicar: cae en un aviso general del paso 5 | Sí | `src/funcionalidades/novela/CrearNovela.test.tsx` | implementado |
| 8 | El formulario nunca envía `texto_libre`, `codigo` ni `cita` | RF-FE-BRF-02, RF-FE-BRF-03 | Test de `aBrief` sobre el JSON que se envía, más el cuerpo real del `POST` en el flujo completo | `T` | — | Sí | `src/funcionalidades/novela/CrearNovela.test.tsx` | implementado |
| 9 | Ninguna pantalla tiene violaciones de accesibilidad automáticas | RF-FE-VIS-03 | axe en cada test de pantalla | `T` | Lo que axe no mide: orden de foco con sentido y claridad de los anuncios | No: la fila 11 | `src/pruebas/accesibilidad.ts`, llamado desde el test de cada pantalla (las seis pantallas y los cinco pasos del brief) | implementado |
| 10 | Ningún componente escribe un color literal | RF-FE-VIS-01 | Regla de lint (búsqueda de `#hex`, `rgb(` y `hsl(` fuera de `tokens.css`) | `A` | Colores metidos en SVG o en Three.js | Sí | `eslint.config.js` | pendiente |
| 11 | Las pantallas reproducen la propuesta B, se manejan por teclado y el arrastre se entiende | Decisión 2, RF-FE-TAB-05, RF-FE-VIS-04 | Revisión con el navegador contra el prototipo, en escritorio, a 768 px y en móvil | `I` | Juicio de una persona; no se repite solo | Sí | Capturas en la entrada del registro de iteraciones | pendiente |
| 12 | El flujo completo funciona contra el backend real: crear desde el brief de ejemplo, arrancar, ver avanzar y parar | 3.2 a 3.8 | Demostración con el backend y el puerto falso (`demo.py`) | `D` | El coste y el ritmo real de Claude Code, que el puerto falso no reproduce | Sí | Entrada del registro de iteraciones | pendiente |
| 13 | La pieza Three.js no degrada el formulario en equipos lentos | RF-FE-BRF-06 | — | `U` | Riesgo aceptado: es decorativa, perezosa y se desactiva con `prefers-reduced-motion`. No compensa medir rendimiento | — | — | — |
