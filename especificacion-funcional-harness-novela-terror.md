# Especificación Funcional — Harness Generador de Novelas de Terror

**Versión:** 1.2 — historial de cambios en `git log` sobre este archivo.
**Documento previo:** `harness-novela-terror.md` (estructura de carpetas y esquemas) — este documento formaliza el comportamiento requerido; no repite decisiones de implementación.
**Lector previsto:** un agente de código que implementará el harness a partir de este documento. Donde este documento sea ambiguo, el agente debe detenerse y pedir aclaración en vez de asumir.

## 1. Alcance

El sistema genera una novela completa de **terror espacial** (space horror — naves, estaciones o colonias aisladas, hostilidad del vacío y de lo desconocido) de 200–500 páginas, mediante un pipeline de 8 fases que produce y consume artefactos de estado estructurados, evitando en todo momento que el texto acumulado del manuscrito entre al contexto de generación.

## 2. Fuera de alcance

- Traducción del manuscrito a otros idiomas.
- Generación de ilustraciones, portada o cualquier elemento visual.
- Maquetación o exportación a formato final (ebook, PDF, DOCX). **Sí está en alcance** concatenar los capítulos cerrados con sus títulos en un único `.md` legible (spec técnica §8.2, `ensamblar`): no es exportación, es poder leer lo que se generó.
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
| Harness (orquestador) | interno | Sesión de Claude Code que ejecuta las skills de cada fase: ensambla contextos, invoca los subagentes en el orden correcto y hace cumplir las reglas globales de la sección 6. Delega en un núcleo Python determinista, sin llamadas a modelo, la validación, el filtrado, la persistencia y el manifiesto. |
| Frontend de entrada | interno | Formulario web local con el que el usuario escribe la idea y la configuración antes de la fase 0. No llama a ningún modelo (RF-UI). |

## 5. Requisitos funcionales

Formato fijo por requisito: descripción, entradas, salidas, reglas, criterio de aceptación (dado/cuando/entonces).

Los requisitos **RF-CFG-xx** son transversales: no pertenecen a ninguna fase, sino que parametrizan la ejecución completa. Los **RF-UI-xx** especifican el frontend con el que el usuario escribe esa configuración. El resto sigue la numeración por fase (RF-00 a RF-07).

### Configuración de ejecución

**RF-CFG-01 — Dimensionamiento de la novela**
- Descripción: el usuario debe poder fijar el tamaño de la obra antes de iniciar una tanda, sin tocar código.
- Entradas: `config/novela.json` (spec técnica §11.2).
- Parámetros:
  - `total_capitulos` — cuántos capítulos tiene la novela completa. Entero, rango 30–50 (acotado por RF-03.1, que exige que el outline tenga entre 30 y 50 entradas).
  - `palabras_por_capitulo` — longitud objetivo de cada capítulo. Entero positivo. La tolerancia de ±20% la fija RF-05.2.
- Reglas:
  - `total_capitulos` determina cuántas entradas genera la fase 3 y es el criterio de fin de la generación.
  - Ambos parámetros son inmutables durante una tanda: cambiarlos con capítulos ya cerrados invalida la escaleta y las longitudes ya generadas (ver INV-04).
- Criterio de aceptación: dado `config/novela.json` con `total_capitulos = K`, cuando termina la fase 3, entonces `capitulos.json` tiene exactamente K entradas con `num` consecutivo de 1 a K.

**RF-CFG-02 — Tanda parcial: capítulos por ejecución**
- Descripción: el usuario debe poder escribir la novela en tandas, indicando cuántos capítulos generar en una ejecución sin comprometerse a la novela entera.
- Entradas: `config/ejecucion.json` y, opcionalmente, un argumento de línea de comandos.
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

**RF-CFG-05 — Voz narrativa**
- Descripción: el usuario debe poder fijar idioma, persona narrativa y tiempo verbal antes de la fase 0. Son decisiones que atraviesan toda la obra y que ningún agente debe poder cambiar a mitad de camino.
- Entradas: configuración.
- Parámetros:
  - `idioma` — código de idioma en el que se escribe la novela (p. ej. `es-ES`). Afecta todas las fases: la guía de estilo, la sinopsis, la escaleta y el manuscrito se producen en este idioma.
  - `persona_narrativa` — `primera` | `tercera_limitada` | `tercera_omnisciente`.
  - `tiempo_verbal` — `presente` | `pasado`.
- Reglas:
  - Los tres parámetros se inyectan en el contexto del agente escritor en cada capítulo (RF-05.1) y en el del agente QA (RF-07.1).
  - Son inmutables durante una tanda, por la misma razón que `total_capitulos` (INV-04).
- Criterio de aceptación: dado `persona_narrativa = tercera_limitada` y `tiempo_verbal = pasado`, cuando se audita el prompt ensamblado de cualquier capítulo, entonces contiene ambas restricciones de forma explícita; y un corte de QA que detecte un capítulo escrito en otra persona o tiempo lo reporta como hallazgo.

**RF-CFG-06 — Presupuesto de ejecución**
- Descripción: el usuario debe poder acotar cuánto está dispuesto a gastar en una tanda, para que una configuración mal calibrada no consuma la cuota entera.
- Parámetros:
  - `max_llamadas_por_tanda` — tope de invocaciones al modelo en una ejecución. Ausente o nulo = sin tope.
  - `registrar_uso` — booleano. Si está activo, cada invocación registra rol, modelo, tokens de entrada y de salida.
- Reglas: alcanzar `max_llamadas_por_tanda` termina la tanda de forma limpia, igual que `capitulos_por_tanda` (RF-CFG-02), nunca a mitad de un capítulo: el corte se evalúa solo entre capítulos, para no dejar un capítulo escrito sin su extracción.
- Criterio de aceptación: dado `max_llamadas_por_tanda = 10` y un capítulo que consume 2 llamadas, cuando se ejecuta la tanda, entonces se cierran 5 capítulos y el manifiesto queda en `en_progreso`.

### Frontend de entrada

**RF-UI-01 — Formulario local de requisitos**
- Descripción: el usuario debe poder escribir la idea de la novela y todos los parámetros de configuración desde un formulario web local, sin editar JSON a mano.
- Entradas: lo que el usuario teclea; opcionalmente, rutas locales a los ejemplos de referencia de la fase 0.
- Salidas: `01_concepto/idea.md`, `config/novela.json`, `config/ejecucion.json`; si se indicaron ejemplos, copia de estos a `00_referencias/`.
- Reglas:
  - El frontend **no invoca ningún modelo ni lee el manuscrito**: su única función es producir entradas válidas. Se lanza con `python -m harness ui` y escucha solo en la máquina local (spec técnica §15).
  - Valida con el mismo esquema de configuración que usa el harness antes de escribir. Una configuración fuera de rango se rechaza en pantalla con el motivo; nunca llega al disco.
- Criterio de aceptación: dado un formulario completado, cuando el usuario guarda, entonces los tres archivos existen, `config/novela.json` y `config/ejecucion.json` validan contra el esquema (EX-05 no puede dispararse con archivos escritos por el frontend), e `idea.md` contiene exactamente el texto escrito.

**RF-UI-02 — Bloqueo de parámetros inmutables**
- Descripción: con capítulos ya cerrados, el formulario impide cambiar los parámetros protegidos por INV-04, igual que RF-CFG-03 lo impide por línea de comandos.
- Criterio de aceptación: dado un manifiesto con `ultimo_capitulo_cerrado > 0`, cuando se abre el formulario, entonces los campos que escriben en `config/novela.json` aparecen deshabilitados mostrando el motivo, y la idea y los campos de `config/ejecucion.json` siguen editables.

### Fase 0 — Destilado de estilo

**RF-00.1 — Extracción de guía de estilo**
- Descripción: el sistema debe producir una guía de estilo a partir de ejemplos de referencia del subgénero de terror espacial.
- Entradas: uno o más textos de ejemplo de terror espacial (naves, estaciones, colonias aisladas — no terror genérico de otro subgénero).
- Salidas: `style_guide.md` (tropos recurrentes del terror espacial —p. ej. aislamiento, fallas de soporte vital, criaturas o presencias que se confunden con el entorno de la nave—, ritmo de tensión/alivio, vocabulario sensorial, longitud de frase típica).
- Criterio de aceptación: dado un conjunto de ejemplos, cuando se ejecuta la fase, entonces `style_guide.md` no contiene ninguna oración copiada literalmente de los ejemplos de entrada.

**RF-00.2 — Prohibición de embebido de texto crudo**
- Descripción: los ejemplos de referencia no deben pasarse completos a ningún prompt posterior a esta fase.
- Reglas:
  - Ningún artefacto de estado de fases 1–7 puede contener el texto literal de los ejemplos de entrada.
  - Los ejemplos se conservan en `00_referencias/`, **fuera del estado persistente y fuera del control de versiones**. Fuera del estado, porque no son memoria de la novela y ningún agente posterior a la fase 0 debe poder leerlos. Fuera de git, porque si son obras publicadas no pertenecen a un repositorio. Se conservan igual porque el criterio de aceptación de abajo es inverificable sin ellos.
- Criterio de aceptación: dado el estado persistente completo tras cualquier fase, cuando se busca una subcadena de más de 30 caracteres de los ejemplos originales, entonces no se encuentra ninguna coincidencia. Si `00_referencias/` no existe en la máquina donde corre la verificación, el resultado se reporta como **no ejecutable**, nunca como aprobado.

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
- Salidas: `capitulos.json`, array de objetos con los campos: `num`, `titulo`, `objetivo_narrativo`, `personajes`, `locacion`, `informacion_nueva`, `tension` (entero 1–5).
- Regla: los títulos se generan **aquí, no en el escritor**. La fase 3 ve los 40 capítulos a la vez y puede darles un estilo consistente y evitar repeticiones; cada instancia del escritor, en cambio, inventaría el suyo sin saber cómo son los otros 39 — el mismo problema que todo el harness existe para evitar.
- Criterio de aceptación: dado `tres_actos.md`, cuando se genera el outline, entonces `capitulos.json` valida contra el esquema (todos los campos presentes, `num` consecutivo desde 1, sin huecos, `tension` entre 1 y 5, ningún `titulo` vacío ni repetido).

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
- Criterio de aceptación: dado el estado inicial, cuando se crea `continuidad.json`, entonces cada entrada, si existe, tiene los campos `sujeto`, `categoria`, `hecho` y `cap_origen`.
- Nota: los hechos derivados de la premisa suelen ser reglas del universo sin protagonista (cómo funciona el soporte vital, qué hay afuera). Esos llevan `categoria = "mundo"`, que es la categoría que RF-05.1 inyecta siempre sin filtrar.

### Fase 5 — Generación capítulo a capítulo

**RF-05.1 — Ensamblado de contexto por capítulo**
- Descripción: el sistema debe construir el contexto del agente escritor a partir del estado persistente, sin incluir el manuscrito completo.
- Entradas: `style_guide.md`, `tres_actos.md`, `capitulos[N]`, `resumen_rodante.md`, `personajes.json`, `continuidad.json`, y los parámetros de voz narrativa (RF-CFG-05).
- Salidas: prompt ensamblado para el agente escritor.
- Reglas:
  - El prompt nunca debe contener el texto de `cap_1.md` … `cap_(N-1).md`.
  - `continuidad.json` no se inyecta completo: se **filtra por relevancia** usando la entrada de outline del capítulo N. Entran los hechos cuyo `sujeto` sea uno de los `capitulos[N].personajes`, o la `capitulos[N].locacion`.
  - Entran **siempre**, sin filtrar, los hechos de `categoria = "mundo"` y los hechos con `sujeto_validado = false` (RF-06.1). Un fallo de clasificación nunca debe traducirse en omisión: el filtro puede incluir de más, nunca de menos.
  - Los hechos con `superado_por` distinto de nulo no se inyectan (RF-07.6).
  - `capitulos[N].tension` se inyecta como **objetivo explícito** del capítulo, no solo como dato. El vocabulario para interpretarlo ya está en el contexto: `style_guide.md` describe el ritmo de tensión/alivio del subgénero (RF-00.1). Sin esta regla, RF-03.2 valida una curva de tensión que nadie ejecuta.
  - El filtro no borra ni modifica `continuidad.json`: es una selección de lectura. El archivo en disco sigue siendo íntegro y append-only (INV-03).
- Criterio de aceptación: dado un capítulo N > 3, cuando se ensambla el contexto, entonces (a) no contiene ninguna subcadena de más de 20 caracteres proveniente de `cap_(N-1).md` o anterior, (b) su tamaño no excede `max_tokens_contexto_escritor`, (c) contiene todos los hechos de `categoria = "mundo"` no superados, y (d) no contiene ningún hecho cuyo `sujeto` sea un personaje ausente de `capitulos[N].personajes`, salvo que su sujeto no haya validado.

**RF-05.2 — Generación del borrador**
- Descripción: el agente escritor produce el texto del capítulo N a partir del contexto ensamblado.
- Salidas: borrador en texto plano/markdown, longitud objetivo `palabras_por_capitulo` (± 20%).
- Reglas ante un borrador fuera de especificación — son dos fallos distintos y se tratan distinto:
  - **Longitud fuera de ±20%** (EX-07): se regenera **una vez**, pasando el desvío como feedback explícito ("el borrador tiene 1.900 palabras; el objetivo es 3.000 ±20%"). Si el segundo intento también falla, se acepta con aviso en el manifiesto. Es un defecto de forma, no de continuidad; no justifica detener la tanda.
  - **Personaje no previsto** (EX-08): se detecta en la fase siguiente, cuando RF-06.1 valida las claves de `delta.personajes` contra el registro de sujetos — un personaje inventado aparece como `sujeto_validado = false` en `personajes`. Se regenera el capítulo. Si el segundo intento también introduce un personaje no previsto, el harness se detiene: dos fallos seguidos indican una entrada de outline mal planteada, no mala suerte, y seguir gastando generaciones sobre un plan roto contradice el mismo principio de EX-03.
  - Regenerar un capítulo en esta fase **no viola INV-07**: el invariante protege capítulos *cerrados*, y un capítulo se cierra recién tras aplicar su extracción. Hasta entonces `cap_N.md` es un borrador reemplazable.
- Criterio de aceptación: dado el contexto de RF-05.1, cuando el agente escritor genera el capítulo, entonces el borrador cubre el `objetivo_narrativo` de `capitulos[N]` (verificable por el agente extractor en la fase siguiente) y no introduce personajes ausentes tanto del outline como de `personajes.json`; y dado un borrador que incumple una de las dos reglas, cuando termina el reintento, entonces existe exactamente un `cap_N.md` en disco y el manifiesto registra cuántos intentos consumió.

**RF-05.3 — Restricción de acceso del agente escritor**
- Descripción: el agente escritor no tiene, bajo ninguna circunstancia, acceso de lectura a `05_manuscrito/`.
- Criterio de aceptación: dada cualquier ejecución de RF-05.2, cuando se audita el conjunto de archivos leídos por el agente escritor, entonces ninguno pertenece a `05_manuscrito/`.

**RF-05.4 — Persistencia del borrador**
- Descripción: el borrador generado se guarda como `cap_{N}.md` antes de invocar la fase de extracción.
- Criterio de aceptación: dado un borrador generado, cuando termina RF-05.2, entonces existe el archivo `05_manuscrito/cap_{N}.md` antes de que se invoque RF-06.1.

### Fase 6 — Extracción post-capítulo

**RF-06.1 — Extracción de cambios de estado**
- Descripción: un agente separado lee únicamente `cap_{N}.md` y produce los deltas de estado.
- Entradas: `cap_{N}.md` (y solo ese archivo del manuscrito), más el **registro de sujetos conocidos**: las claves de `personajes.json`, las locaciones de `mundo.json`, y el valor literal `mundo`.
- Salidas: objeto `delta` con `personajes`, `hechos_nuevos`, `resumen_corto` (3–5 líneas).
- Reglas:
  - El registro de sujetos es un **vocabulario, no memoria**: la lista de nombres, sin los hechos ni los estados asociados. El extractor sigue sin ver el log de continuidad, el resumen rodante ni ningún capítulo anterior (INV-02).
  - Cada hecho de `hechos_nuevos` lleva `sujeto` y `categoria`. El `sujeto` debe pertenecer al registro; si el capítulo establece un hecho sobre una entidad ausente del registro, el extractor lo emite igual y el harness le fija `sujeto_validado = false` en vez de descartarlo. Ese marcado es lo que hace que RF-05.1 lo inyecte siempre.
  - Las claves de `delta.personajes` también deben pertenecer al registro. Sin esta regla, el extractor puede devolver `"el capitán"` donde `personajes.json` tiene `"Kovacs"` y crear una ficha duplicada que nadie detecta.
- Criterio de aceptación: dado `cap_{N}.md`, cuando se ejecuta la extracción, entonces (a) el agente extractor no recibe en su contexto ningún otro archivo de `05_manuscrito/`, (b) no recibe `continuidad.json` ni `resumen_rodante.md`, y (c) todo hecho emitido tiene `sujeto` y `categoria`.

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
- Regla: "marcar como resuelto" es una **operación del harness**, no una edición manual del manifiesto. El usuario la invoca declarando qué capítulos corrigió (mecanismo en la spec técnica §8.2). Si resolver fuera editar `manifest.json` a mano, RF-07.6 nunca se ejecutaría: el texto quedaría corregido y el log de continuidad seguiría describiendo la versión anterior.
- Criterio de aceptación: dado un reporte con `tiene_contradicciones = true`, cuando el harness lo recibe, entonces no se invoca RF-05.1 para el siguiente capítulo hasta que el usuario humano marque el reporte como resuelto; y dado un `manifest.json` editado a mano de `pausado_por_qa` a `en_progreso` sin pasar por la operación de resolución, cuando arranca la siguiente tanda, entonces el harness detecta que el reporte sigue sin resolver y no reanuda.

**RF-07.5 — Registro de recursos narrativos**
- Descripción: el agente QA debe **escribir** `06_qa/recursos_usados.json` al terminar cada corte, acumulando los recursos narrativos detectados en la muestra con su conteo de apariciones.
- Entradas: la muestra del corte actual, `06_qa/recursos_usados.json` tal como quedó del corte anterior.
- Salidas: `06_qa/recursos_usados.json` actualizado — lista de objetos con `recurso` (descripción del recurso), `veces` (entero) y `caps` (capítulos donde apareció).
- Reglas: es el único artefacto que escribe el agente QA. Sin este requisito, RF-07.3 no tiene fuente de datos y su criterio de aceptación es inalcanzable — nada registraría los conteos contra los que comparar.
- Criterio de aceptación: dado un primer corte de QA sobre capítulos 1–8 donde una metáfora aparece 2 veces, cuando termina el corte, entonces `recursos_usados.json` contiene esa entrada con `veces = 2`; y si reaparece una vez en el corte de 9–16, el conteo pasa a 3 y RF-07.3 la señala.

**RF-07.6 — Reextracción tras corrección humana**
- Descripción: cuando el usuario corrige capítulos a raíz de un reporte de QA, el estado persistente derivado de esos capítulos debe regenerarse antes de reanudar.
- Entradas: la lista de capítulos que el usuario declara haber modificado al invocar la operación de resolución (RF-07.4). El harness no puede adivinar cuáles tocó; por eso la lista es obligatoria y una resolución sin capítulos declarados se interpreta como "revisé y no cambié nada".
- Reglas:
  - Para cada capítulo modificado se vuelve a ejecutar la extracción (RF-06.1) sobre su texto corregido.
  - Los hechos de `continuidad.json` cuyo `cap_origen` esté en esa lista se marcan como **superados** y se agregan los nuevos. Es la única operación que altera hechos existentes, y no los borra: los marca. `continuidad.json` sigue siendo append-only en el sentido de INV-03 — ningún registro desaparece ni pierde su trazabilidad.
  - `personajes.json` se recalcula para los personajes afectados; `resumen_rodante.md` se regenera si alguno de los capítulos modificados cae dentro de la ventana.
- Criterio de aceptación: dado un reporte que llevó al usuario a corregir `cap_30.md`, cuando marca el reporte como resuelto declarando ese capítulo, entonces los hechos con `cap_origen = 30` quedan marcados como superados, existen los hechos nuevos extraídos del texto corregido, y recién entonces el manifiesto vuelve a `en_progreso`.
- Nota: sin este requisito, corregir el texto deja el log de continuidad describiendo una versión del capítulo que ya no existe, y el siguiente corte de QA volvería a reportar la misma contradicción.

## 6. Reglas globales / invariantes

Aplican a todo el sistema, no a una fase específica. Ningún requisito de la sección 5 puede implementarse de forma que las viole.

- **INV-01**: el agente escritor nunca recibe, en ningún prompt, el texto completo de un capítulo ya cerrado.
- **INV-02**: el agente extractor nunca recibe más de un capítulo por invocación.
- **INV-03**: todo hecho en `continuidad.json` lleva `cap_origen`; no existen hechos sin trazabilidad a su capítulo de origen.
- **INV-04**: los esquemas de los artefactos de estado (sección 3 de `harness-novela-terror.md`) no cambian durante la ejecución de una tanda completa de generación.
- **INV-05**: el agente QA es el único actor con permiso de lectura sobre más de un archivo de `05_manuscrito/` a la vez.
- **INV-06**: `capitulos_por_tanda` no afecta el contenido de ningún artefacto de estado. Una novela generada en ocho tandas de cinco capítulos debe ser indistinguible de la misma novela generada en una tanda de cuarenta — el tope solo decide cuándo se detiene la ejecución, nunca qué se escribe.
- **INV-07**: ningún capítulo ya **cerrado** se regenera. Reanudar una tanda siempre avanza; nunca reescribe. Un capítulo se cierra tras aplicar su extracción (RF-06.3); antes de eso es un borrador y los reintentos de RF-05.2 pueden reemplazarlo.

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
| **EX-07** | El borrador del capítulo N queda fuera de `palabras_por_capitulo` ±20% (RF-05.2). | Un reintento con el desvío como feedback. Si el segundo también falla, se acepta con aviso en el manifiesto y la tanda continúa. Defecto de forma: no amerita detener nada. |
| **EX-08** | La extracción del capítulo N devuelve en `delta.personajes` una clave ausente del registro de sujetos — el borrador introdujo un personaje no previsto (RF-05.2, RF-06.1). | Se descarta el borrador y se regenera el capítulo. Si el segundo intento repite el fallo, el harness se detiene y reporta la entrada de outline como sospechosa: dos fallos seguidos señalan un plan mal planteado, y seguir generando sobre él contradice el principio de EX-03. |

## 8. Definición de "hecho" (Definition of Done) de esta especificación

Esta especificación funcional se considera completa e implementable cuando, para cada requisito de la sección 5, existe un criterio de aceptación verificable de forma automática o por inspección directa del artefacto de estado correspondiente — sin necesidad de juicio subjetivo sobre la calidad narrativa del texto generado (esa evaluación queda fuera de esta especificación funcional).
