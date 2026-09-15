# Especificación Funcional — Harness Generador de Novelas de Terror

**Versión:** 1.0
**Documento previo:** `harness-novela-terror.md` (estructura de carpetas y esquemas) — este documento formaliza el comportamiento requerido; no repite decisiones de implementación.
**Lector previsto:** un agente de código que implementará el harness a partir de este documento. Donde este documento sea ambiguo, el agente debe detenerse y pedir aclaración en vez de asumir.

## 1. Alcance

El sistema genera una novela completa de **terror espacial** (space horror — naves, estaciones o colonias aisladas, hostilidad del vacío y de lo desconocido) de 200–500 páginas, mediante un pipeline de 8 fases que produce y consume artefactos de estado estructurados, evitando en todo momento que el texto acumulado del manuscrito entre al contexto de generación.

## 2. Fuera de alcance

- Traducción del manuscrito a otros idiomas.
- Generación de ilustraciones, portada o cualquier elemento visual.
- Maquetación o exportación a formato final (ebook, PDF, DOCX).
- Selección automática entre múltiples borradores generados para un mismo capítulo (esta versión genera un único borrador por capítulo, no hay muestreo ni rechazo).
- Edición interactiva capítulo a capítulo por parte de un humano. La única intervención humana prevista es la revisión disparada por hallazgos de QA (fase 7).
- Subgéneros de terror distintos al terror espacial (el destilado de estilo, fase 0, asume ejemplos de referencia de space horror — no terror gótico, slasher, folk horror, etc., salvo que se cambien los ejemplos de entrada).

## 3. Glosario

Vocabulario cerrado — el agente implementador debe usar estos términos de forma consistente y no introducir sinónimos.

| Término | Definición |
|---|---|
| **Estado persistente** | El conjunto de artefactos que se leen/escriben entre capítulos: guía de estilo, sinopsis, outline, fichas de personajes, biblia del mundo, log de continuidad, resumen rodante. |
| **Manuscrito** | El texto crudo ya generado (`05_manuscrito/cap_*.md`). Crece linealmente y nunca se relee completo. |
| **Resumen rodante** | Resumen comprimido de los últimos 2–3 capítulos. Sustituye al manuscrito completo como contexto retrospectivo. |
| **Log de continuidad** | Lista de hechos atómicos ya establecidos en el manuscrito, cada uno con el capítulo que lo originó. |
| **Agente escritor** | Genera el borrador de un capítulo a partir del contexto ensamblado. |
| **Agente extractor** | Lee un único capítulo recién escrito y produce los cambios (`Δ`) que deben aplicarse al estado persistente. |
| **Agente QA** | Corre de forma periódica (no por capítulo) y detecta contradicciones o repetición estilística. |
| **Corte de QA** | Cada ejecución de la fase 7, disparada por `cadencia_qa`. |

## 4. Actores

| Actor | Tipo | Responsabilidad |
|---|---|---|
| Usuario humano | externo | Provee la idea inicial (fase 1) y resuelve las pausas que dispara QA (fase 7). |
| Agente escritor | interno | Redacta el borrador de un capítulo. Sin acceso de lectura al manuscrito acumulado. |
| Agente extractor | interno | Actualiza el estado persistente a partir de un único capítulo. Sin acceso a capítulos anteriores. |
| Agente QA | interno | Único actor con acceso de lectura a una muestra del manuscrito completo. Corre con cadencia fija. |
| Harness (orquestador) | interno | Ensambla contextos, invoca agentes en el orden correcto, persiste artefactos, hace cumplir las reglas globales de la sección 6. |

## 5. Requisitos funcionales

Formato fijo por requisito: descripción, entradas, salidas, reglas, criterio de aceptación (dado/cuando/entonces).

Los requisitos **RF-CFG-xx** son transversales: no pertenecen a ninguna fase, sino que parametrizan la ejecución completa. El resto sigue la numeración por fase (RF-00 a RF-07).

### Configuración de ejecución

**RF-CFG-01 — Dimensionamiento de la novela**
- Descripción: el usuario debe poder fijar el tamaño de la obra antes de iniciar una tanda, sin tocar código.
- Entradas: `harness.config.json`.
- Parámetros:
  - `total_capitulos` — cuántos capítulos tiene la novela completa. Entero, rango 30–50 (acotado por RF-03.1, que exige que el outline tenga entre 30 y 50 entradas).
  - `palabras_por_capitulo` — longitud objetivo de cada capítulo. Entero positivo. La tolerancia de ±20% la fija RF-05.2.
- Reglas:
  - `total_capitulos` determina cuántas entradas genera la fase 3 y es el criterio de fin de la generación.
  - Ambos parámetros son inmutables durante una tanda: cambiarlos con capítulos ya cerrados invalida la escaleta y las longitudes ya generadas (ver INV-04).
- Criterio de aceptación: dado `harness.config.json` con `total_capitulos = K`, cuando termina la fase 3, entonces `capitulos.json` tiene exactamente K entradas con `num` consecutivo de 1 a K.

**RF-CFG-02 — Tanda parcial: capítulos por ejecución**
- Descripción: el usuario debe poder escribir la novela en tandas, indicando cuántos capítulos generar en una ejecución sin comprometerse a la novela entera.
- Entradas: `harness.config.json` y, opcionalmente, un argumento de línea de comandos.
- Parámetro: `capitulos_por_tanda` — cuántos capítulos generar en esta ejecución. Entero positivo, o ausente/nulo para "seguir hasta `total_capitulos`".
- Reglas:
  - El conteo es **de capítulos cerrados en esta ejecución**, no del número de capítulo. Una tanda de 5 que arranca en el capítulo 11 termina tras cerrar el 15.
  - Al alcanzar el tope, el harness termina de forma **limpia**: no es un error ni una pausa por QA. El manifiesto queda en `en_progreso` y la siguiente ejecución reanuda donde quedó (RF-CFG-04).
  - El tope no altera `total_capitulos` ni la escaleta: es un límite de ejecución, no de obra.
  - Si `capitulos_por_tanda` excede los capítulos que faltan, la ejecución termina al completar la novela y el manifiesto pasa a `completo`.
  - El corte de tanda no adelanta ni omite un corte de QA: si el último capítulo de la tanda es múltiplo de `cadencia_qa`, el QA corre antes de terminar (RF-07.1 no se ve afectado).
- Criterio de aceptación: dado `total_capitulos = 40`, `capitulos_por_tanda = 5` y un manifiesto con `ultimo_capitulo_cerrado = 10`, cuando termina la ejecución, entonces existen `cap_11.md` … `cap_15.md`, no existe `cap_16.md`, el manifiesto indica `ultimo_capitulo_cerrado = 15` y `estado = en_progreso`.

**RF-CFG-03 — Precedencia de la línea de comandos**
- Descripción: el valor de `capitulos_por_tanda` pasado por línea de comandos tiene prioridad sobre el del archivo de configuración.
- Regla: la precedencia aplica **solo** a `capitulos_por_tanda`. `total_capitulos`, `palabras_por_capitulo` y el resto de los parámetros se leen exclusivamente del archivo, porque cambiarlos a mitad de una novela rompe INV-04.
- Criterio de aceptación: dado `capitulos_por_tanda = 10` en el archivo, cuando se invoca la ejecución pasando 3 por línea de comandos, entonces se cierran 3 capítulos y no 10.

**RF-CFG-04 — Reanudación entre tandas**
- Descripción: una ejecución que arranca con capítulos ya cerrados debe continuar desde el siguiente, sin regenerar ninguno.
- Entradas: el manifiesto de ejecución.
- Reglas:
  - El punto de reanudación es `ultimo_capitulo_cerrado + 1`.
  - Si el manifiesto indica que la tanda quedó pausada por QA, la ejecución no reanuda hasta que el usuario marque el reporte como resuelto (RF-07.4). El tope de `capitulos_por_tanda` no sobrescribe esa pausa.
- Criterio de aceptación: dado un manifiesto con `ultimo_capitulo_cerrado = 15` y `estado = en_progreso`, cuando se inicia una nueva ejecución, entonces el primer capítulo generado es el 16 y ningún archivo de `05_manuscrito/` previo se sobrescribe.

### Fase 0 — Destilado de estilo

**RF-00.1 — Extracción de guía de estilo**
- Descripción: el sistema debe producir una guía de estilo a partir de ejemplos de referencia del subgénero de terror espacial.
- Entradas: uno o más textos de ejemplo de terror espacial (naves, estaciones, colonias aisladas — no terror genérico de otro subgénero).
- Salidas: `style_guide.md` (tropos recurrentes del terror espacial —p. ej. aislamiento, fallas de soporte vital, criaturas o presencias que se confunden con el entorno de la nave—, ritmo de tensión/alivio, vocabulario sensorial, longitud de frase típica).
- Criterio de aceptación: dado un conjunto de ejemplos, cuando se ejecuta la fase, entonces `style_guide.md` no contiene ninguna oración copiada literalmente de los ejemplos de entrada.

**RF-00.2 — Prohibición de embebido de texto crudo**
- Descripción: los ejemplos de referencia no deben pasarse completos a ningún prompt posterior a esta fase.
- Regla: ningún artefacto de estado de fases 1–7 puede contener el texto literal de los ejemplos de entrada.
- Criterio de aceptación: dado el estado persistente completo tras cualquier fase, cuando se busca una subcadena de más de 30 caracteres de los ejemplos originales, entonces no se encuentra ninguna coincidencia.

### Fase 1 — Concepto

**RF-01.1 — Generación de premisa**
- Descripción: a partir de una idea del usuario, el sistema produce título, logline y premisa de un párrafo.
- Entradas: idea del usuario (texto libre, puede ser tan corta como una frase).
- Salidas: `premisa.md` con tres campos obligatorios: título, logline, premisa.
- Criterio de aceptación: dado cualquier input no vacío del usuario, cuando se ejecuta la fase, entonces los tres campos están presentes y ninguno queda vacío.

### Fase 2 — Sinopsis en tres actos

**RF-02.1 — Generación de sinopsis**
- Descripción: a partir de la premisa, generar gancho inicial, punto medio (giro) y clímax/final.
- Entradas: `premisa.md`.
- Salidas: `tres_actos.md` con las tres secciones nombradas explícitamente.
- Criterio de aceptación: dado `premisa.md` válido, cuando se genera la sinopsis, entonces cada una de las tres secciones tiene al menos un párrafo y el clímax/final no contradice el gancho inicial (ningún personaje mencionado en el final aparece por primera vez sin mención previa en gancho o punto medio).

**RF-02.2 — Inyección obligatoria en fases posteriores**
- Descripción: toda fase desde 3 en adelante debe recibir `tres_actos.md` (completo o resumido) como parte de su contexto.
- Criterio de aceptación: dado el prompt ensamblado para cualquier fase ≥ 3, cuando se inspecciona su contenido, entonces contiene una referencia identificable a la sinopsis de tres actos.

### Fase 3 — Escaleta de capítulos

**RF-03.1 — Generación de outline**
- Descripción: generar entre 30 y 50 entradas de outline a partir de la sinopsis.
- Entradas: `tres_actos.md`, `premisa.md`.
- Salidas: `capitulos.json`, array de objetos con los campos: `num`, `objetivo_narrativo`, `personajes`, `locacion`, `informacion_nueva`, `tension` (entero 1–5).
- Criterio de aceptación: dado `tres_actos.md`, cuando se genera el outline, entonces `capitulos.json` valida contra el esquema (todos los campos presentes, `num` consecutivo desde 1, sin huecos, `tension` entre 1 y 5).

**RF-03.2 — Coherencia de progresión narrativa**
- Descripción: el nivel de tensión no debe ser estrictamente decreciente a lo largo del outline (el terror no se puede ir apagando de forma monótona antes del clímax).
- Criterio de aceptación: dado `capitulos.json` completo, cuando se grafica `tension` contra `num`, entonces el valor máximo de `tension` ocurre en el tercio final del outline.

### Fase 4 — Bases de estado

**RF-04.1 — Inicialización de fichas de personajes**
- Descripción: crear `personajes.json` con una entrada por personaje mencionado en el outline.
- Entradas: `capitulos.json`.
- Salidas: `personajes.json` — ver esquema en `harness-novela-terror.md` §3.
- Criterio de aceptación: dado `capitulos.json`, cuando se inicializan las fichas, entonces todo personaje que aparece en el campo `personajes` de al menos una entrada de outline tiene una ficha correspondiente.

**RF-04.2 — Inicialización de biblia del mundo**
- Descripción: crear `mundo.json` con reglas del universo, objetos relevantes y línea de tiempo, a partir de la sinopsis y el outline.
- Criterio de aceptación: dado `tres_actos.md` y `capitulos.json`, cuando se inicializa, entonces `mundo.json` no está vacío y cada locación mencionada en el outline aparece referenciada.

**RF-04.3 — Inicialización de log de continuidad**
- Descripción: crear `continuidad.json` vacío o con hechos iniciales derivados de la premisa (ej. reglas del mundo que ya son "hechos" desde el capítulo 1).
- Criterio de aceptación: dado el estado inicial, cuando se crea `continuidad.json`, entonces cada entrada, si existe, tiene los campos `hecho` y `cap_origen`.

### Fase 5 — Generación capítulo a capítulo

**RF-05.1 — Ensamblado de contexto por capítulo**
- Descripción: el sistema debe construir el contexto del agente escritor a partir del estado persistente, sin incluir el manuscrito completo.
- Entradas: `style_guide.md`, `tres_actos.md`, `capitulos[N]`, `resumen_rodante.md`, `personajes.json`, `continuidad.json`.
- Salidas: prompt ensamblado para el agente escritor.
- Regla: el prompt nunca debe contener el texto de `cap_1.md` … `cap_(N-1).md`.
- Criterio de aceptación: dado un capítulo N > 3, cuando se ensambla el contexto, entonces (a) no contiene ninguna subcadena de más de 20 caracteres proveniente de `cap_(N-1).md` o anterior, y (b) su tamaño no excede `max_tokens_contexto_escritor`.

**RF-05.2 — Generación del borrador**
- Descripción: el agente escritor produce el texto del capítulo N a partir del contexto ensamblado.
- Salidas: borrador en texto plano/markdown, longitud objetivo `palabras_por_capitulo` (± 20%).
- Criterio de aceptación: dado el contexto de RF-05.1, cuando el agente escritor genera el capítulo, entonces el borrador cubre el `objetivo_narrativo` de `capitulos[N]` (verificable por el agente extractor en la fase siguiente) y no introduce personajes ausentes tanto del outline como de `personajes.json`.

**RF-05.3 — Restricción de acceso del agente escritor**
- Descripción: el agente escritor no tiene, bajo ninguna circunstancia, acceso de lectura a `05_manuscrito/`.
- Criterio de aceptación: dada cualquier ejecución de RF-05.2, cuando se audita el conjunto de archivos leídos por el agente escritor, entonces ninguno pertenece a `05_manuscrito/`.

**RF-05.4 — Persistencia del borrador**
- Descripción: el borrador generado se guarda como `cap_{N}.md` antes de invocar la fase de extracción.
- Criterio de aceptación: dado un borrador generado, cuando termina RF-05.2, entonces existe el archivo `05_manuscrito/cap_{N}.md` antes de que se invoque RF-06.1.

### Fase 6 — Extracción post-capítulo

**RF-06.1 — Extracción de cambios de estado**
- Descripción: un agente separado lee únicamente `cap_{N}.md` y produce los deltas de estado.
- Entradas: `cap_{N}.md` (y solo ese archivo del manuscrito).
- Salidas: objeto `delta` con `personajes`, `hechos_nuevos`, `resumen_corto` (3–5 líneas).
- Criterio de aceptación: dado `cap_{N}.md`, cuando se ejecuta la extracción, entonces el agente extractor no recibe en su contexto ningún otro archivo de `05_manuscrito/`.

**RF-06.2 — Actualización de fichas de personajes**
- Descripción: aplicar `delta.personajes` sobre `personajes.json`, actualizando solo los campos afectados por el capítulo N.
- Criterio de aceptación: dado un delta con cambios para un personaje existente, cuando se aplica, entonces `personajes.json` refleja el nuevo estado y actualiza `ultima_aparicion` a N.

**RF-06.3 — Actualización del log de continuidad**
- Descripción: agregar `delta.hechos_nuevos` a `continuidad.json`, cada uno con `cap_origen = N`.
- Regla: `continuidad.json` es append-only — ningún hecho existente se borra o modifica, solo se agregan nuevos.
- Criterio de aceptación: dado un delta con hechos nuevos, cuando se aplica, entonces el tamaño de `continuidad.json` solo puede crecer, nunca decrecer, y todo hecho previo permanece idéntico.

**RF-06.4 — Actualización del resumen rodante**
- Descripción: incorporar `delta.resumen_corto` a `resumen_rodante.md`, descartando el capítulo más antiguo si se excede `ventana_resumen_rodante`.
- Criterio de aceptación: dado `resumen_rodante.md` con la ventana ya llena, cuando se agrega un nuevo resumen, entonces el número de capítulos cubiertos en el archivo nunca excede `ventana_resumen_rodante`.

### Fase 7 — Control de continuidad (QA)

**RF-07.1 — Ejecución periódica**
- Descripción: cada `cadencia_qa` capítulos, ejecutar un chequeo de continuidad y estilo.
- Entradas: `continuidad.json` completo, muestra de `05_manuscrito/` (los últimos `cadencia_qa` capítulos), `06_qa/recursos_usados.json`.
- Criterio de aceptación: dado N múltiplo de `cadencia_qa`, cuando termina RF-06 para ese capítulo, entonces se dispara automáticamente un corte de QA antes de iniciar el capítulo N+1.

**RF-07.2 — Detección de contradicciones**
- Descripción: comparar el texto de la muestra contra `continuidad.json` y reportar cualquier afirmación que contradiga un hecho registrado.
- Salidas: `06_qa/reportes/qa_cap_{N}.md` con lista de hallazgos, cada uno citando el `cap_origen` del hecho contradicho.
- Criterio de aceptación: dado un hecho en `continuidad.json` con `cap_origen = k`, cuando un capítulo posterior en la muestra lo contradice explícitamente, entonces el reporte de QA lo incluye citando `k`.

**RF-07.3 — Detección de repetición estilística**
- Descripción: comparar recursos narrativos (metáforas, estructuras de frase recurrentes) de la muestra contra `06_qa/recursos_usados.json` y señalar repeticiones.
- Criterio de aceptación: dado un recurso ya registrado como usado 3 o más veces, cuando reaparece en la muestra, entonces el reporte de QA lo señala explícitamente.

**RF-07.4 — Pausa ante hallazgos**
- Descripción: si el reporte contiene al menos una contradicción, el harness detiene el avance a capítulos siguientes hasta revisión humana.
- Criterio de aceptación: dado un reporte con `tiene_contradicciones = true`, cuando el harness lo recibe, entonces no se invoca RF-05.1 para el siguiente capítulo hasta que el usuario humano marque el reporte como resuelto.

## 6. Reglas globales / invariantes

Aplican a todo el sistema, no a una fase específica. Ningún requisito de la sección 5 puede implementarse de forma que las viole.

- **INV-01**: el agente escritor nunca recibe, en ningún prompt, el texto completo de un capítulo ya cerrado.
- **INV-02**: el agente extractor nunca recibe más de un capítulo por invocación.
- **INV-03**: todo hecho en `continuidad.json` lleva `cap_origen`; no existen hechos sin trazabilidad a su capítulo de origen.
- **INV-04**: los esquemas de los artefactos de estado (sección 3 de `harness-novela-terror.md`) no cambian durante la ejecución de una tanda completa de generación.
- **INV-05**: el agente QA es el único actor con permiso de lectura sobre más de un archivo de `05_manuscrito/` a la vez.
- **INV-06**: `capitulos_por_tanda` no afecta el contenido de ningún artefacto de estado. Una novela generada en ocho tandas de cinco capítulos debe ser indistinguible de la misma novela generada en una tanda de cuarenta — el tope solo decide cuándo se detiene la ejecución, nunca qué se escribe.
- **INV-07**: ningún capítulo ya cerrado se regenera. Reanudar una tanda siempre avanza; nunca reescribe.

## 7. Casos de excepción esperados

Comportamiento a nivel funcional — no se especifica mecanismo de implementación (eso corresponde a la especificación técnica).

| Caso | Disparador | Comportamiento requerido |
|---|---|---|
| **EX-01** | Un artefacto de estado (`personajes.json`, `continuidad.json`, etc.) no valida contra su esquema tras una extracción. | El harness detiene el loop antes de iniciar el siguiente capítulo y marca el capítulo N como pendiente de revisión. No se continúa con datos inválidos. |
| **EX-02** | El corte de QA reporta al menos una contradicción (RF-07.4). | El harness pausa el avance y espera resolución humana; no reintenta ni omite el hallazgo automáticamente. |
| **EX-03** | Falta la entrada de outline para el capítulo N, o está incompleta. | El harness no invoca al agente escritor para ese capítulo; reporta el faltante antes de gastar una generación. |
| **EX-04** | El contexto ensamblado (RF-05.1) excede `max_tokens_contexto_escritor`. | El harness recorta primero `resumen_rodante.md`; nunca recorta `continuidad.json` ni `personajes.json`. Si tras recortar el resumen rodante a su mínimo aún excede el límite, se detiene y reporta el problema — no trunca el log de continuidad. |
| **EX-05** | Un parámetro de RF-CFG-01 o RF-CFG-02 está fuera de rango (`total_capitulos` fuera de 30–50, `palabras_por_capitulo` ≤ 0, `capitulos_por_tanda` ≤ 0). | El harness no inicia la ejecución y reporta qué parámetro es inválido. La validación ocurre antes de cualquier llamada al modelo, para no gastar generaciones con una configuración que igual va a fallar. |
| **EX-06** | `total_capitulos` cambió respecto del valor con el que se generó la escaleta, y ya hay capítulos cerrados. | El harness no reanuda y reporta la discrepancia. Cambiar el tamaño de la obra a mitad de camino invalida la escaleta (INV-04); resolverlo es decisión del usuario, no del harness. |

## 8. Definición de "hecho" (Definition of Done) de esta especificación

Esta especificación funcional se considera completa e implementable cuando, para cada requisito de la sección 5, existe un criterio de aceptación verificable de forma automática o por inspección directa del artefacto de estado correspondiente — sin necesidad de juicio subjetivo sobre la calidad narrativa del texto generado (esa evaluación queda fuera de esta especificación funcional).
