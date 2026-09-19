# Spec-X 03 · Una segunda opinión sobre el capítulo, fuera del harness

**Estado:** propuesta, para aprobar antes de tocar código
**Alcance:** el exportador y la configuración de Langfuse. No toca el escritor, ni el extractor, ni el `qa`, ni el bucle, ni las fases.
**Base:** `especificacion-tecnica-harness-novela-terror.md` v1.10, §16 (observabilidad) y RF-07 (QA), RF-09 (exportación)
**Evidencia:** sondas contra la API real de Langfuse 4.38.0 del 2026-09-17 (tabla en §1.3), traza `tanda_2026-09-16T19-30-34`, `07_registro/tanda_2026-09-17T18-29-18/`

---

## 1. El punto de partida

### 1.1 Qué evalúa hoy el harness y qué no

El agente `qa` (`.claude/agents/qa.md`, skill `criterios-qa`) juzga **dos** cosas sobre una
muestra de `cadencia_qa` capítulos: contradicciones contra hechos vigentes del log de
continuidad —citando siempre el `cap_origen`— y repetición de recursos narrativos con
umbral de tres apariciones acumuladas. Puede detener la producción (RF-07.4, EX-02).

No juzga, ni pretende juzgar, **si el capítulo está bien escrito**: no mide tono, no mide
atmósfera, y no comprueba que el capítulo cumpla el encargo de su entrada de escaleta.
Ese hueco es el que esta propuesta cubre, y lo cubre **fuera** del harness.

El exportador publica hoy cinco puntuaciones (§16.4) —`qa_contradicciones`,
`qa_repeticiones`, `qa_pasa`, `desvio_longitud`, `borradores_descartados`—. Todas se
derivan del registro por conteo. Ninguna es un juicio.

### 1.2 Por qué el evaluador no sustituye al `qa`

El `qa` lee la muestra **completa** contra el log **entero**, y por eso puede afirmar que
el capítulo 6 contradice un hecho fijado en el 2. El evaluador de Langfuse, por diseño de
la plataforma, **solo ve la observación que puntúa**: no carga observaciones hermanas ni
hijas de la misma traza. Son instrumentos distintos. El `qa` es el control de producción;
el evaluador es la segunda opinión, en la plataforma, comparable entre tandas y visible
para quien no tiene el repo delante.

De ahí la decisión de qué juzga cada uno: el evaluador puntúa **lo que el `qa` no mira**.

### 1.3 Lo que se verificó contra la API, y lo que rompe

| Hecho | Cómo se comprobó |
|---|---|
| La ingesta v3 **sí guarda, con unos 9 minutos de retraso** | `POST /api/public/ingestion` → `207` con `successes:[{status:201}]`. Releer a los pocos segundos devuelve `n = 0` y hace creer que se perdió; a los 9 minutos la observación está. Corregido el 2026-09-18 tras una primera lectura equivocada. **Ni un 201 ni un cero inmediato prueban nada: hay que esperar.** |
| Pero **la regla no se ejecuta sobre lo ingerido por esa vía** | Sonda `sonda-juez-ingesta-legacy` del 2026-09-18: generación `escritor:cap_99` ingerida por `/api/public/ingestion` con `input`, `output` y `metadata.rol = "escritor"` —cumple el filtro de la regla, creada media hora antes—, con los dos evaluadores en `active`. **21 minutos después, cero scores.** Es lo que documenta el FAQ *«Why is my observation-level evaluator not executing?»*: los evaluadores de observación solo funcionan con datos ingeridos por OTel; la API REST antigua «no produce observaciones en el formato requerido». |
| La ingesta v3 **se apaga** el 2026-11-16 | Descripción del endpoint en `/generated/api/openapi.yml`. Desde esa fecha solo acepta `score-create`. |
| La ingesta **OTel funciona** | `POST /api/public/otel/v1/traces` con `x-langfuse-ingestion-version: 4`, OTLP/JSON armado con `urllib` → `200`. |
| …y persiste **con todo lo que hace falta** | Relectura: `type:GENERATION`, `input`, `output`, `metadata.rol`, `model:"claude-opus-5"`, `usageDetails` con las cuatro cifras y `total`, `costDetails.total`, `latency:180`. |
| Langfuse ya conoce el precio de nuestros modelos | 10 tokens de entrada → `0,00005 $`, es decir 5 $/M: coincide con `config/precios.json`. |
| El evaluador se aplica a **observaciones**, no a trazas | Los evaluadores de traza están deprecados y dejan de producir resultados el 2026-11-16 (docs `llm-as-a-judge`). |
| El proyecto **no tiene conexión LLM** | `GET /api/public/llm-connections` → `{"data":[],"totalItems":0}`. Sin ella el juez no puede ejecutarse. |
| No hay evaluadores ni reglas | `GET /v2/evaluators` y `GET /v2/evaluation-rules` → `{"data":[]}`. |
| La tanda que ya está subida **no sirve de material** | Sus generaciones devuelven `input: None`, `output: None` (se exportó sin `--con-cuerpos`). Pedir `fields=basic,io` sobre ella devuelve `504` en dos intentos de 150 s. |

**La consecuencia, dicha entera: las tandas sí llegan a Langfuse, pero llegan en un formato
que el evaluador no puede puntuar.** Es un resultado peor que el de no llegar, porque no se
nota: la traza se ve perfecta en la interfaz, con sus tiempos y su coste, y la pestaña de
scores simplemente se queda vacía sin ningún error que lo explique. Por eso la migración a
OTel (X-03.1) sigue siendo requisito y no comodidad — solo que el motivo no es perder
datos, sino que los evaluadores de observación no corren sobre ellos.

Esto se creyó dos veces por la razón contraria, así que queda anotado como método: en esta
plataforma **ni un `201` ni un cero inmediato son evidencia**. Lo primero porque la
escritura es asíncrona; lo segundo porque la lectura tarda unos nueve minutos en reflejarla.
Toda afirmación sobre si algo llegó exige releer después de esperar.

### 1.4 Un detalle de lectura que no es un error de escritura

`GET /v2/observations` devuelve **52 filas con solo 30 `id` distintos** para la tanda de
septiembre: cada observación aparece repetida. Los `id` repetidos son **idénticos**, así
que el upsert de §16.5 hizo su trabajo y no hay observaciones duplicadas en el proyecto:
es la vía de lectura sobre datos v3 la que devuelve una fila por versión del registro.
No hay doble puntuación ni doble coste. Se anota aquí porque al mirar la tabla de trazas
parece un fallo del exportador, y no lo es. Se vuelve a comprobar sobre la primera tanda
ingerida por OTel (§7, paso 3).

---

## 2. X-03.1 · Las tandas nuevas persisten por OpenTelemetry

El exportador deja de hablar con `/api/public/ingestion` y pasa a **OTLP/HTTP sobre
`POST /api/public/otel/v1/traces`**, con la cabecera `x-langfuse-ingestion-version: 4`.
Sin dependencias nuevas: la sonda que lo demostró está escrita con `urllib` y `json`, que
es lo que el exportador ya usa. Añadir el SDK de Langfuse o los paquetes de OpenTelemetry
se rechaza por la misma razón de siempre: el proyecto no tiene dependencias en esta capa y
la vía manual ya está probada de punta a punta.

Se mantiene **todo** el mapeo de §16.2 —trace, span de capítulo, span de verbo,
generation, event—, porque los verbos son el flujo y sin ellos no se ve en qué paso murió
una tanda. La traducción es directa:

| Objeto de §16.2 | Cómo viaja en OTLP |
|---|---|
| `trace` = la tanda | span raíz, con `langfuse.trace.name` y `langfuse.trace.metadata.*` (los `prompts_hash`, el dimensionamiento, `version_specs`), `langfuse.trace.tags` |
| `span` = capítulo | span hijo del raíz, `langfuse.observation.type = span` |
| `span` anidado = verbo | span hijo del capítulo, con su `startTime` real (`ts - ms`) |
| `generation` = invocación | `langfuse.observation.type = generation`, `langfuse.observation.model.name`, `langfuse.observation.usage_details` (las cuatro cifras, §16.3) |
| `event` = hook, EX-08, EX-10 | span instantáneo con `langfuse.observation.type = event` y su `level` |
| `score` | **no viaja por OTLP**: se publica con `POST /api/public/scores` (§2.2) |

Los instantes dejan de ser un problema de diseño: OTLP transporta `startTimeUnixNano` y
`endTimeUnixNano` explícitos, que es justo lo que §16.8 exigía comprobar y lo que la
biblioteca instalable no daba. La objeción de §16.8 queda resuelta por la vía que esa
misma sección anticipaba.

**Metadatos de primer nivel.** Un atributo suelto cae en el cajón `metadata.attributes` y
**no se puede filtrar**. Los que la regla necesita van con el prefijo explícito:
`langfuse.observation.metadata.rol`, `.capitulo`, `.intento`, `.agent_id`. Verificado: la
sonda envió `langfuse.observation.metadata.rol` y volvió como `metadata.rol`, filtrable.

### 2.2 Los scores propios, por su endpoint

Las cinco puntuaciones de §16.4 pasan a `POST /api/public/scores`, con el mismo `id`
determinista de `id_puntuacion()` para que reexportar siga sin duplicar. Es el endpoint
que sobrevive al 16 de noviembre. Se leen por `GET /api/public/v3/scores` —`v2/scores`
devuelve `410` en esta organización—.

### 2.3 Idempotencia

Los `id` siguen siendo función de la tanda (`uuid5` sobre el espacio fijo). En OTLP pasan
a ser `traceId` de 32 hex y `spanId` de 16 hex, que es exactamente el formato que
`id_traza()` e `id_observacion()` ya producen. Reexportar la misma tanda sigue
actualizando en lugar de duplicar, tal como exige §16.5.

---

## 3. X-03.2 · Qué lleva cada generación para que el juez tenga con qué trabajar

El juez solo ve la observación que puntúa. **Lo que no esté en el `input` o el `output` de
`escritor:cap_N` no existe para él.** Y hay una trampa concreta: el retorno del escritor
es un resumen de cinco líneas (`cap_7.md · 1.520 palabras · …`), no el capítulo. El texto
está en `05_manuscrito/cap_N.md`.

### 3.1 El nuevo modo `--para-juez`

`--con-cuerpos` sube `prompts/` y `retornos/` enteros y desactiva el filtro de privacidad
completo. No sirve aquí, y no por comodidad: el prompt del escritor contiene
`STYLE_GUIDE`, la guía de estilo destilada de `00_referencias/`, que está fuera del
control de versiones porque son obras con derechos (RF-00.2, §16.6). **Lo que se decidió
no versionar no se manda a un servicio de terceros, ni siquiera para que lo lea un juez.**

Se añade un modo distinto:

```
python -m app exportar-traza <tanda> --para-juez
```

Con él, y **solo** en las generaciones de rol `escritor`:

- `output` = el texto íntegro de `05_manuscrito/cap_N.md`.
- `input` = un objeto JSON que el exportador **reconstruye del estado**, no del prompt:

```json
{
  "capitulo": 7,
  "escaleta": {
    "titulo": "...",
    "objetivo_narrativo": "...",
    "locacion": "...",
    "personajes": ["..."],
    "informacion_nueva": "...",
    "tension": 4
  },
  "hechos_vigentes": [
    { "hecho": "...", "sujeto": "...", "cap_origen": 2 }
  ],
  "personajes": { "...": "ficha breve" },
  "resumen_rodante": "...",
  "parametros": { "idioma": "es", "persona_narrativa": "...", "tiempo_verbal": "...", "palabras_objetivo": 1500 }
}
```

Las fuentes son las mismas que usa `escritor.ensamblar_contexto()`
(`repo.leer_outline_entry`, `cont.filtrar_para_capitulo`, `repo.leer_personajes`,
`repo.leer_resumen_rodante`), **menos `STYLE_GUIDE`**, que nunca se incluye. Se reconstruye
el contexto en vez de recortar el prompt porque un recorte por texto se rompe en silencio
en cuanto cambie la plantilla, y lo que se filtra aquí es material con derechos.

El resto de las generaciones —`extractor:cap_N`, `qa:cap_N`— **siguen sin cuerpos** con
`--para-juez`. No las puntúa nadie y no hay razón para subirlas.

### 3.2 Qué sale del repo y qué no

| Sale con `--para-juez` | No sale nunca |
|---|---|
| El texto de los capítulos de la tanda | `00_referencias/` y cualquier cosa derivada de ahí |
| Escaleta, hechos vigentes, fichas, resumen rodante | `STYLE_GUIDE` y el cuerpo de los prompts |
| Estructura, tiempos, modelos, tokens, conteos | Borradores descartados |
| Los códigos de regla de las validaciones fallidas | El texto de los errores de validación, que cita prosa |

El `FiltroPrivacidad` sigue aplicándose **a todo lo demás** igual que hoy: args de verbos,
motivos de hook, mensajes de error. Lo único que se exceptúa es el par
`input`/`output` de las generaciones del escritor, que es precisamente lo que se autoriza
a subir. Sin esa excepción el filtro blanquearía el capítulo contra el manuscrito y el
juez recibiría `[omitido: N caracteres…]`.

`exportar-traza` sin `--para-juez` no cambia de comportamiento: por defecto sigue sin
salir prosa.

### 3.3 Lo que esto obliga a decir en voz alta

Con `--para-juez`, **el texto de la novela sale de la máquina** y viaja a Anthropic a
través de Langfuse. Es una decisión tomada, no un efecto colateral: sin el capítulo
delante no hay juicio posible. Queda escrito aquí para que el grupo lo sepa antes de
correr el comando.

Segundo aviso, menor pero real: reexportar una tanda **después** de haber corregido
capítulos a mano (RF-07.4) sube el texto corregido con los tiempos de la tanda original.
Los `id` deterministas hacen upsert, así que el score del juez se recalcula sobre el texto
nuevo. Es lo deseable, pero conviene saber que la puntuación puede cambiar sin que haya
corrido ninguna tanda.

---

## 4. X-03.3 · El evaluador y su plantilla

Dos evaluadores, no cuatro. En Langfuse **un evaluador produce un solo score**
(`outputDefinition` admite `NUMERIC`, `BOOLEAN` o `CATEGORICAL`, uno por evaluador), así
que cada criterio es un evaluador y una llamada al juez. Se juzga lo que el `qa` no
cubre; continuidad y repetición se dejan donde ya se miden bien.

Ambos: `NUMERIC`, `minValue: 1`, `maxValue: 5`, con `scoreReasoningInstructions` para que
la justificación quede en el comentario del score.

### 4.1 Evaluador `juez-tono` — tono de terror espacial

```
Sos un crítico literario especializado en terror espacial (Alien, Solaris, Blindsight,
Event Horizon). Evaluás UN capítulo de una novela por entregas, en español.

Capítulo a evaluar:
{{capitulo}}

Contexto de producción (escaleta, hechos fijados y estado previo):
{{contexto}}

Puntuá de 1 a 5 el TONO Y LA ATMÓSFERA de terror espacial:

5 — La amenaza se sostiene sin nombrarse; el espacio y la nave son hostiles por su
    física, no por adjetivos. La tensión crece por lo que se oculta.
4 — Atmósfera sólida, con alguna caída a lo explícito o a la frase hecha del género.
3 — Funciona a ratos; alterna atmósfera con exposición plana o con sustos gratuitos.
2 — El terror se enuncia en vez de construirse ("sintió un terror indescriptible").
1 — No hay atmósfera de terror: es ciencia ficción neutra, o el registro es ajeno al género.

No penalices la falta de resolución: es un capítulo de una novela, no un relato cerrado.
No juzgues continuidad ni repeticiones entre capítulos: eso lo mide otro control.
```

`scoreReasoningInstructions`: *Dos o tres frases. Citá el pasaje concreto que sostiene la
nota, y el que más baja el promedio. En español.*

### 4.2 Evaluador `juez-escaleta` — adherencia al encargo del capítulo

```
Evaluás si UN capítulo cumple el encargo que la escaleta le fijó.

Encargo del capítulo (escaleta, personajes previstos, información nueva a revelar):
{{escaleta}}

Capítulo escrito:
{{capitulo}}

Puntuá de 1 a 5 la ADHERENCIA AL ENCARGO:

5 — Cumple el objetivo narrativo, ocurre en la locación fijada, revela la información
    nueva prevista y no adelanta lo que no le tocaba.
4 — Cumple lo esencial; una desviación menor y justificada por la escena.
3 — Cumple el objetivo a medias, o cambia la locación sin transición, o deja la
    información nueva a medio revelar.
2 — Se desvía del objetivo, o revela algo que correspondía a un capítulo posterior.
1 — No cumple el encargo: otra escena, otros personajes, u otro momento de la trama.

Una escena que se mueve a un personaje permitido y no previsto NO es un fallo si el
objetivo narrativo se cumple. Adelantar información nueva del capítulo siguiente SÍ lo es.
```

`scoreReasoningInstructions`: *Dos o tres frases. Nombrá qué parte del encargo se cumplió
y cuál no. En español.*

### 4.3 Mapeo de variables

| Evaluador | Variable | `source` | `jsonPath` |
|---|---|---|---|
| `juez-tono` | `capitulo` | `output` | — |
| `juez-tono` | `contexto` | `input` | — |
| `juez-escaleta` | `capitulo` | `output` | — |
| `juez-escaleta` | `escaleta` | `input` | `$.escaleta` |

Las fuentes válidas son `input`, `output`, `metadata`, `tool_calls`, `expected_output` y
`experiment_item_metadata`; `jsonPath` es opcional y debe empezar por `$`. Cada variable
de la plantilla se mapea **exactamente una vez** o la API devuelve error de validación.
Si `jsonPath` sobre `input` no se acepta —está documentado como «más útil con
`metadata`»—, la alternativa es mapear `escaleta` al `input` entero: el prompt sigue
funcionando, con algo más de contexto del necesario.

### 4.4 El modelo juez

Conexión LLM del proyecto: **OpenRouter**, que el harness ya usa para sus tres agentes
(`config/proveedores.json`, spec técnica §3.1), con un **modelo de la capa gratuita**.

Langfuse no tiene adaptador propio de OpenRouter: se da de alta como gateway compatible
con OpenAI. En Project Settings → LLM Connections → `Add new LLM API key`:

| Campo | Valor |
|---|---|
| Provider | `OpenAI` |
| API key | la clave de OpenRouter (la misma que ya usa el harness) |
| Advanced Settings → Base URL | `https://openrouter.ai/api/v1` |
| Custom model names | el identificador exacto del modelo gratuito elegido |

**El modelo tiene que admitir *tool calling* en formato OpenAI.** No es un detalle: Langfuse
pide la nota mediante una llamada a función (`tools: [{"type":"function", …}]`), y un modelo
que no la soporte devuelve error y el evaluador queda en `paused`. De los 444 modelos del
catálogo de OpenRouter, 24 son gratuitos y **20 de esos admiten `tools`** (consultado el
2026-09-17 en `GET https://openrouter.ai/api/v1/models`, filtrando
`pricing.prompt == 0 && pricing.completion == 0` y `"tools" in supported_parameters`). La
elección concreta se valida en el panel de prueba del evaluador antes de crear la regla.

Sigue cumpliéndose lo que hacía de esto una segunda opinión: el juez es de otra familia
que el escritor (`claude-opus-5`), no un autorretrato.

La clave se introduce **en la interfaz de Langfuse**. No va al repo, ni a `config/`, ni a
`.claude/settings.json`, ni a los tests, ni al chat.

**Tres límites de la capa gratuita que hay que aceptar por escrito:**

1. **Privacidad.** Los modelos gratuitos de OpenRouter suelen exigir tener activado el
   registro de prompts en los ajustes de privacidad de la cuenta, y el proveedor puede
   usarlos para entrenar. Con `--para-juez`, lo que viaja es el texto de la novela. Es
   aceptable para un trabajo de clase sobre material propio; no lo sería para material de
   `00_referencias/`, que por eso no sale nunca (§3.2).
2. **Estabilidad.** El catálogo gratuito rota: un modelo puede desaparecer o cambiar de
   versión sin aviso. Si el juez cambia, **las notas dejan de ser comparables entre
   tandas**, que es justo para lo que sirven. El modelo usado se anota junto a los
   resultados, y un cambio de juez se trata como un corte en la serie, no como una
   variación de calidad.
3. **Cuotas.** La capa gratuita limita peticiones por minuto y por día. Con dos
   evaluadores y seis capítulos son 12 llamadas por novela: sobra. Si la novela crece,
   esto es lo primero que se rompe, y la salida es bajar `sampling` o pagar el juez.

---

## 5. X-03.4 · La regla y su filtro

Una sola regla, con los dos evaluadores asignados.

```json
{
  "name": "capitulos del escritor",
  "enabled": true,
  "sampling": 1,
  "filter": [
    { "type": "stringOptions", "column": "type",     "operator": "any of", "value": ["GENERATION"] },
    { "type": "stringObject",  "column": "metadata", "key": "rol", "operator": "=", "value": "escritor" }
  ],
  "evaluatorAssignments": [
    { "evaluatorId": "<id de juez-tono>" },
    { "evaluatorId": "<id de juez-escaleta>" }
  ]
}
```

**Por qué el filtro va por `metadata.rol` y no por el nombre.** La columna `name` solo
admite el operador `any of` / `none of` sobre una lista cerrada de valores exactos: no
existe «empieza por». Filtrar por nombre obligaría a enumerar `escritor:cap_1`,
`escritor:cap_2`… y a editar la regla en cada capítulo nuevo. El exportador ya emite
`metadata.rol = "escritor"` en cada generación (`observabilidad.py`, cuerpo de la
generación), y con X-03.1 ese campo viaja como metadato de primer nivel, filtrable. El
filtro no depende de cuántos capítulos tenga la novela.

`sampling: 1` —se puntúan todos los capítulos—. Con novelas de seis capítulos y este
coste, muestrear solo introduciría huecos en la comparación entre tandas. Si un día la
novela se alarga a decenas de capítulos, esto es lo primero que se baja.

**Un capítulo reintentado se puntúa una vez.** El escritor se invoca una sola vez por
capítulo; los reintentos de validación ocurren dentro de esa invocación (Spec-X 01 §2), así
que hay una generación `escritor:cap_N` por capítulo y un score por evaluador. Si alguna
vez hubiera dos invocaciones para el mismo capítulo, la regla puntúa las dos: es correcto
—son dos textos distintos— y `metadata.intento` permite distinguirlas.

---

## 6. X-03.5 · Qué cuesta

**Con un modelo de la capa gratuita de OpenRouter, el juicio cuesta 0 $.** No hay factura
que estimar, y en Langfuse el coste de estas evaluaciones aparecerá como cero o vacío,
porque `config/precios.json` no tiene tarifa para el modelo juez y OpenRouter no cobra por
él. No es un error del panel.

Lo que sí conviene tener medido es **qué costaría si hubiera que pagarlo**, porque la capa
gratuita puede desaparecer y porque el tamaño del juicio es el mismo en cualquier caso. El
juez lee el capítulo (~1.500 palabras ≈ 2.300 tokens) más el contexto reconstruido
(escaleta, hechos, fichas, resumen ≈ 1.500 tokens) y escribe la nota con su justificación
(~350 tokens). Con las tarifas de `config/precios.json` para
`claude-haiku-4-5-20251001` (1,00 $/M entrada · 5,00 $/M salida), que es el plan B:

| Concepto | Tokens | Coste |
|---|---:|---:|
| `juez-tono`, entrada | 3.800 | 0,0038 $ |
| `juez-tono`, salida | 350 | 0,0018 $ |
| `juez-escaleta`, entrada | 1.900 | 0,0019 $ |
| `juez-escaleta`, salida | 350 | 0,0018 $ |
| **Por capítulo** | | **≈ 0,0093 $** |
| Por novela de 6 capítulos | | ≈ 0,056 $ |

Para comparar: la tanda de tres capítulos de septiembre costó **2,56 $**. El juicio de sus
tres capítulos habría costado **0,028 $** de pagarse: un **1,1 %**. Es decir, que el plan B
tampoco es caro, y el día que la capa gratuita falle no hay que rediseñar nada, solo cambiar
la conexión LLM en Langfuse.

La cifra oficial de Langfuse para una evaluación es 0,01–0,10 $; la nuestra queda en el
extremo bajo porque el capítulo es corto y la respuesta del juez también.

**Plan Hobby.** 50.000 unidades/mes, 30 días de acceso a los datos, 2 usuarios, 1.000
req/min de ingesta. Cada traza, cada observación y **cada score** es una unidad: la tanda
de septiembre gastó ~60 unidades, y los dos scores por capítulo suman 2 más. Con este
volumen el plan sobra por dos órdenes de magnitud. Lo que sí aprieta es la **retención de
30 días**: una tanda deja de ser consultable un mes después de exportarla, y `07_registro/`
sigue siendo la fuente de verdad (§16.1). LLM-as-a-judge, batch evaluation y scores
personalizados están incluidos en Hobby; lo que está limitado es una sola cola de
anotación, que no usamos.

---

## 7. Cómo se verifica sobre lo que ya existe

La tanda de septiembre **no sirve de material**: sus generaciones no llevan cuerpos y
pedir `fields=io` sobre ella devuelve `504`. La verificación se hace así, en este orden:

1. **Reexportar `tanda_2026-09-16T19-30-34` por OTLP con `--para-juez`.** Sus `id` son
   deterministas, así que hace upsert sobre lo que ya está. Comprobación: relectura con
   `GET /v2/observations?fields=basic,io,metadata,model,usage` devuelve `input` y `output`
   no nulos en las tres generaciones `escritor:cap_4|5|6`, y `metadata.rol = "escritor"`.
2. **Batch evaluation sobre esa misma tanda**, antes de activar la regla: en la tabla de
   trazas, filtrar, seleccionar las filas, Actions → Evaluate, elegir el evaluador. Exige
   el toggle «Langfuse v4 preview» activado en el evaluador. Así se ven las dos notas y
   sus justificaciones sobre tres capítulos que ya conocemos, y se puede ajustar la
   rúbrica sin esperar a una tanda nueva.
3. **Contraste con lo que ya sabemos de esos capítulos.** El `qa` detuvo el capítulo 6 con
   dos contradicciones y ocho repeticiones. Si `juez-escaleta` puntúa el 6 por encima del
   4 y del 5 sin matices, la rúbrica está mal calibrada o el contexto no le llega. Es la
   prueba de que el juez está midiendo algo y no devolviendo un 4 educado. De paso, la
   relectura confirma si la duplicación de filas de §1.4 desaparece sobre datos ingeridos
   por OTel.
4. **Activar la regla** y correr una tanda nueva de tres capítulos. Comprobación:
   `GET /api/public/v3/scores` devuelve `juez-tono` y `juez-escaleta` para cada
   `escritor:cap_N`, con su comentario, junto a los scores propios de §16.4.

---

## 8. Qué NO propone

- **No toca el escritor, el extractor ni el `qa`.** Ni sus prompts, ni sus skills, ni sus
  hooks. Lo único que cambia dentro del harness es qué envía el exportador.
- **No toca INV-01 ni INV-08.** El escritor sigue sin ver el manuscrito y el orquestador
  tampoco. El exportador lo lee, como ya lo lee hoy para construir el filtro de
  privacidad, y corre **después** de la tanda, fuera de ella (§16.1).
- **No sustituye al `qa`.** El evaluador no pausa nada, no bloquea nada y no escribe en
  `06_qa/`. Una nota de 2 en tono no detiene la producción: informa.
- **No mide continuidad ni repetición.** Se descartó: el `qa` las mide con el log entero
  delante y la muestra completa, y el juez solo ve un capítulo. Duplicarlo con menos
  información daría una segunda opinión peor, no otra opinión.
- **No añade dependencias.** OTLP/HTTP con `urllib`, como el exportador actual.
- **No mete ninguna clave en el repo.** Las de Langfuse siguen en el entorno
  (`LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST` o `LANGFUSE_BASE_URL`,
  §16.7); la del modelo juez vive solo en la interfaz de Langfuse.

---

## 9. Lo que queda abierto

- **El 16 de noviembre de 2026** se apaga la ingesta v3 y dejan de funcionar los
  evaluadores de traza. X-03.1 nos deja del lado correcto de esa fecha, pero conviene
  anotarla: cualquier cosa que se construya sobre `/api/public/ingestion` de aquí en
  adelante nace muerta.
- **Calibración de la rúbrica.** Dos evaluadores con escalas de cinco puntos escritas de
  una sentada. El paso 3 de §7 es lo que las corrige; hasta entonces las notas son
  indicativas.
- **Alertas.** Langfuse permite un aviso por umbral de score o de coste sobre un
  evaluador. Se deja fuera de esta spec: primero que las notas signifiquen algo.

---

## 10. Cambios en el código, si se aprueba

1. `app/observabilidad.py`: emisor OTLP (spans, atributos `langfuse.*`, tiempos en
   nanosegundos) en lugar de `ClienteHTTP` sobre `/api/public/ingestion`.
2. `app/observabilidad.py`: publicación de las cinco puntuaciones por
   `POST /api/public/scores`.
3. `app/observabilidad.py`: construcción del `input` del juez desde el estado, y modo
   `--para-juez` con su excepción acotada al par `input`/`output` del escritor.
4. `app/cli.py`: la bandera `--para-juez` junto a `--con-cuerpos`.
5. `tests/`: pruebas del armado OTLP (tipos de observación, atributos de primer nivel,
   tiempos), del contexto del juez (que incluye escaleta y hechos, que **no** incluye
   `STYLE_GUIDE`), y de que sin `--para-juez` no sale prosa. Hoy la suite recoge 200.
6. Documento aparte, paso a paso y con los campos exactos, de la configuración manual en
   la interfaz de Langfuse: conexión LLM, los dos evaluadores y la regla, para que el
   resto del grupo la repita.
