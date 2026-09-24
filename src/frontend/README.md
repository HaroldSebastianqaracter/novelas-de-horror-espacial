# Frontend

Stack: React + Three.js.

La v1 está construida con mocks; falta probarla contra el backend real (fila 12 de la verificación). Requisitos en [specs/spec-frontend.md](../../specs/spec-frontend.md) y verificación en [specs/spec-frontend-verification.md](../../specs/spec-frontend-verification.md). La arquitectura está en [docs/architecture.md](../../docs/architecture.md#arquitectura-del-frontend).

La v1 es un tablero al estilo Jira: una tarjeta por novela y, dentro de cada novela, sus capítulos. Tiene además la alerta de parada, un lector de capítulos y el alta de una novela desde un brief. La referencia visual es el prototipo de la propuesta B, «papel técnico», en [prototipo-b/](prototipo-b/): se abre con doble clic en `index.html`, no depende del build y no se toca. Desde el 24 de septiembre es también **la lectura de la entrega** (bloque 7 del plan): portada, índice, ficha de personajes y lugares, versiones con sus novedades, el cambio del lector y el PDF, en `/novelas/:id/lectura`.

## Arrancar

Con Node 24:

```sh
npm install
npm run dev:mocks   # sin backend: MSW sirve la API con datos ficticios
npm run dev         # contra el backend en 127.0.0.1:8000, a través del proxy /api
```

Para probar contra una API en otro puerto sin tocar la tuya (por ejemplo una con el puerto falso y una base temporal), `NOVELAS_API` cambia el destino del proxy. En PowerShell:

```powershell
$env:NOVELAS_API = "http://127.0.0.1:8001"; npm run dev
```

La API se levanta en ese puerto con `.venv\Scripts\python.exe -m uvicorn main:app --port 8001` desde `src/backend`, porque `python -m main` la deja fija en el 8000.

Con los mocks, la novela 6 («Deriva en el anillo Tántalo») está completada y tiene dos versiones: es la que enseña la lectura en `/novelas/6/lectura`. Para probar el cambio del lector hay que parar antes la novela 3, que se está generando, porque el worker hace una cosa a la vez. Una petición con «triste» se rechaza como no admisible, y una con «fracas» falla sin versión nueva.

| Script | Qué hace |
| --- | --- |
| `npm run tipos` | Regenera `src/compartido/api/esquema.gen.ts` desde `../backend/tests/openapi.json`. Hay que hacerlo cada vez que cambie el contrato |
| `npm run tipos:comprobar` | Regenera los tipos y falla si difieren de lo commiteado |
| `npm run comprobar` | Comprobación de tipos |
| `npm test` | Tests (Vitest, siempre contra MSW) |
| `npm run build` | Build de producción en `dist/` |
| `npm run pdf -- <url> <salida.pdf>` | Exporta a PDF la vista de impresión de una novela (`/novelas/:id/lectura/imprimir`) con Playwright. Necesita el servidor de desarrollo en marcha |

## Ideas guardadas

Ideas de producto todavía sin decidir ni especificar. Se apuntan aquí para no perderlas; ninguna es un compromiso. Cuando una se adopte, sale de esta lista y entra en su spec de `specs/`, y lo que afecte a la arquitectura se lleva a `docs/` con la entrevista que exige [AGENTS.md](../../AGENTS.md).

### Mutabilidad de atributos en la puerta 3 (backend)

*Apuntada el 23 de septiembre de 2026.*

Hoy la puerta 3 no sabe qué cambios son legítimos. Para ella, todo cambio de valor en el mismo sujeto y atributo es una contradicción, salvo que el hecho nuevo traiga `supersede_a`, y ese campo lo rellena el **extractor**, que es un agente. Es un dato autodeclarado, la regla 3 de [docs/validators.md](../../docs/validators.md): si el extractor marca `supersede_a` en un cambio de color de ojos, la contradicción pasa blanqueada. El campo `categoria` existe, pero la puerta no lo usa.

La propuesta es clasificarlo en código y no preguntárselo a un modelo, en tres capas:

1. **Mutabilidad por atributo**, en un catálogo que fijamos nosotros:

   | Mutabilidad | Ejemplos | Regla de la puerta 3 |
   | --- | --- | --- |
   | Inmutable | color de ojos, nombre, fecha de nacimiento, altura | Todo cambio es conflicto, aunque venga con `supersede_a` |
   | Irreversible | vivo/muerto, extremidades, ceguera | Solo avanza en un sentido (capa 2) |
   | Cambia con causa | heridas, pelo, ropa, ubicación, posesión | Se admite con `supersede_a` y con la causa en el texto (capa 3) |
   | Libre | ánimo, cansancio, hambre | Ni se compara |

2. **Transiciones permitidas** para los irreversibles: sano → herido → amputado, herido → sano, vivo → muerto. Lo que no está en la tabla, como amputado → sano o muerto → vivo, es conflicto siempre.
3. **La causa tiene que estar en la prosa.** El hecho que sustituye a otro trae la `cita` del momento del cambio («la llamarada le abrasó el antebrazo»), y el código comprueba **literalmente** que esa cita aparece en el texto de la escena. Es el segundo método que mira el texto.

Tres cosas a resolver antes de adoptarla:

- **El terror espacial rompe las reglas a propósito.** Si la amenaza suplanta a alguien, unos ojos que cambian de color pueden ser la revelación. El cambio de un inmutable abre parada, y el informe incluye las reglas de `amenaza.reglas` para que decida el autor; nunca pasa en silencio.
- **Quién rellena el catálogo.** Una base fija en la ontología; los atributos nuevos entran como «cambia con causa» por defecto, que es lo prudente; el autor los reclasifica desde una parada.
- **Cuándo.** Encaja encima de la fase 5 de [specs/spec2-plan.md](../../specs/spec2-plan.md), que ya introduce las claves normalizadas y la supersesión transitiva, así que se retoma cuando esa fase esté hecha. Arrastra cambios en [docs/definitions.md](../../docs/definitions.md) (el `Hecho` gana la mutabilidad de su atributo), en validators.md (el punto ciego de «Continuidad factual») y en la skill `extraccion`, que tiene que citar el momento del cambio.

Encaja en `src/backend/tareas/continuidad/puerta.py` y en `src/backend/tareas/extraccion/`.

### Mejoras del RAG (backend)

*Apuntada el 23 de septiembre de 2026.*

El índice vectorial solo alimenta un bloque del paquete del redactor, «cómo se describió esto antes», y por diseño ninguna puerta depende de él. Hoy funciona, pero aporta poco y nadie ha medido si recupera bien: la base de pruebas cayó en silencio al modelo de respaldo (`potion-multilingual`, 256 dimensiones) en lugar del preferido (`multilingual-e5-small`).

La **fase 7 de [specs/spec2-plan.md](../../specs/spec2-plan.md)** ya cubre cinco problemas: el filtro por lugar se aplica después del KNN global, el cambio de modelo o dimensión pasa sin avisar, los fallos del índice se tragan, la purga solo se hace en `relanzar`, y no hay golden set de recuperación. Aquí va lo que el plan **no** cubre, ordenado de más barato a más caro:

1. **Excluir el capítulo anterior.** `recuperar` filtra por `capitulo < N` y así incluye el N-1, cuyo texto ya va entero en el bloque «capítulo anterior». El filtro pasa a ser `capitulo < N - 1`. Es una línea y libera tokens del bloque para prosa que el redactor no tiene.
2. **Una consulta por escena, como pide RF-CTX-07.** Hoy se hace una sola consulta que concatena objetivo, conflicto y lugar de todas las escenas del capítulo, y eso diluye cada una. La spec pide una consulta por escena, con hasta 3 fragmentos por escena y 8 por capítulo, y el filtro por lugar **u objeto o amenaza** compartidos. `Indice.recuperar` ya acepta `objetos` y nadie se los pasa: `_recuperar` en `orquestador/pipeline.py` solo manda `lugares`.
3. **Entregar pasajes, no escenas enteras.** Se piden 8 escenas completas (unos 1.400 tokens cada una) para un bloque de 4.000, así que sobreviven 2 o 3, y una escena larga sola puede no caber. La propuesta mantiene el índice **por escena**, como decidió la arquitectura, pero al entregar reordena los párrafos de cada escena recuperada contra la consulta y manda solo los uno o dos más cercanos, con su referencia (capítulo, escena, lugar). Caben los 8 fragmentos y cada uno es lo pertinente. Punto ciego: el párrafo más parecido a la consulta no tiene por qué ser el que fija la descripción que importa.
4. **`vec_hecho`: usarlo o quitarlo.** Se calculan y se guardan embeddings de cada hecho y ninguna consulta los lee. Su uso previsto es el desempate por similitud de RF-CTX-08, que el plan deja como riesgo aceptado. Hasta que ese desempate se adopte, lo coherente con la picaresca es **no indexar hechos** y ahorrarse el cómputo; se vuelve a activar el día que haya algo que lo consulte.
5. **Detector de repetición (aviso).** architecture.md lista como uso legítimo del índice detectar repetición de imágenes, gestos y fórmulas a lo largo de la obra, «un problema real de la prosa generada», y nadie lo ha construido. Al cerrar un capítulo, cada escena nueva se compara con las anteriores y, por encima de un umbral de similitud, se emite un **aviso** en la parte mecánica de la puerta 4, con la escena parecida citada. Solo avisa, nunca para: así no cruza la línea de «recuperar, nunca verificar». Punto ciego: la repetición deliberada. Un `Motivo` declarado por el arquitecto se repite a propósito, así que los pasajes que lo contienen quedan fuera de la comparación, y el umbral se calibra sobre un capítulo real antes de activarlo.
6. **Rastro de lo recuperado.** Un evento de traza por capítulo con los fragmentos entregados (escena, capítulo y distancia) y los descartados por presupuesto. Hoy solo queda en la entrada completa de `llamada_modelo`, mezclado con el resto del paquete. Sin este rastro, el golden set de la fase 7 mide el índice aislado, pero no se puede auditar qué recibió de verdad el redactor en cada capítulo.

Tres cosas a resolver antes de adoptarla:

- **Cuándo.** Los puntos 1, 2 y 4 caben dentro de la fase 7 y conviene meterlos cuando esa fase empiece, no antes, para no pisar al agente que aplica el plan. El 3, el 5 y el 6 son trabajo propio.
- **Medir antes de afinar.** Ninguna de estas mejoras se puede dar por buena sin el golden set de la fase 7 (consultas con su escena esperada y recall@k con el modelo real). El orden sensato es: golden set, medir el estado actual, aplicar 1 a 3 y volver a medir.
- **El umbral del detector de repetición** sale de medir, no de decidirlo: pasar el detector sobre un manuscrito real, mirar a mano qué marca y fijar el umbral donde los avisos empiezan a ser útiles.

Encaja en `src/backend/compartido/vectores/indice.py`, en `_recuperar` y `_indexar` de `src/backend/orquestador/pipeline.py` y, el detector, en `src/backend/tareas/oficio/puerta.py`.
