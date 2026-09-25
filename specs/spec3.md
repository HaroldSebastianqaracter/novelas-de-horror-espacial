# SRS — storyMaker: personalización y entrega

Requisitos de lo que el [plan de entrega](storymaker-plan.md) añade al backend para el examen: la personalización, la lectura, la observabilidad, los guardrails y la verificación formal. Una sección por bloque del plan; cada una se escribe al empezar su bloque.

Versión 0.1 · 23 de septiembre de 2026

> **Cómo leer este documento.** Refina [spec1](spec1.md) y [spec2](spec2.md), no las sustituye. Los requisitos nuevos llevan el prefijo `RF3-`. Si uno reemplaza a otro anterior, lo nombra, y el anterior recibe la línea `> Sustituido por spec3, RF3-…`. Los callouts **Decisión entrevistada** y **Decisión de la spec** marcan qué se preguntó al autor y qué se decidió sin él. El plan de verificación está en [spec3-verification.md](spec3-verification.md).

---

## 1. Alcance

| Bloque del plan | Sección | Estado |
| --- | --- | --- |
| 2. Personalización del terror | [3.2](#32-bloque-2--personalización-del-terror) | Escrita |
| 3. Huecos de la story bible | [3.3](#33-bloque-3--huecos-de-la-story-bible) | Escrita |
| 4. Observabilidad con Langfuse | [3.4](#34-bloque-4--observabilidad-con-langfuse) | Escrita |
| 5. Guardrails | [3.5](#35-bloque-5--guardrails) | Escrita |
| 6. Validadores que faltan | [3.6](#36-bloque-6--validadores-que-faltan) | Escrita: nombres, allegados, longitud, elementos del encargo, segunda opinión, votos del juez y la rúbrica de la novela entera |
| 7. Lectura | [3.7](#37-bloque-7--lo-que-la-lectura-web-pide-al-backend) | Escrita: lo que la web pide al backend. La lectura es el frontend ([spec-frontend.md](spec-frontend.md)) |
| 8. Cambio del lector | [3.8](#38-bloque-8--cambio-del-lector) | Escrita |
| 9. Validadores formales | 3.9 | En sus propias specs: [spec-tla.md](spec-tla.md) (TLA+, integrada) y [spec-lean.md](spec-lean.md) (Lean 4, integrada como puerta 6) |
| 10. Infraestructura de evals | [3.10](#310-bloque-10--infraestructura-de-evals) | Escrita: el banco de contraejemplos de la puerta 3, los cinco briefs y la tabla de evals |
| Mejoras tras la primera pasada real | [3.11](#311-lo-que-enseñó-la-primera-pasada-real) | Escrita: 3 de los 6 frentes (extractor, resumen y nombres menores) |

---

## 3.2 Bloque 2 — Personalización del terror

Las novelas siguen siendo de terror espacial. Lo que se personaliza es **para quién** es el terror: el destinatario del regalo es el protagonista, sus rasgos y sus recuerdos entran en la historia, y la intensidad se ajusta a su edad.

> **Decisión entrevistada, 23 de septiembre de 2026.** Cuatro decisiones de producto:
>
> 1. **El destinatario es el protagonista** y el punto de vista principal. Se descartó un personaje principal sin punto de vista (se reconoce menos) y dejarlo a elección del comprador (más casos que probar sin ganar nada claro).
> 2. **Tres niveles de intensidad con edad mínima.** Se descartaron una escala del 1 al 5 (cada número necesitaría una definición comprobable) y dos niveles (dejan fuera al adolescente y al adulto que no quiere violencia explícita).
> 3. **El destinatario nunca muere.** Es un regalo. Se descartó permitirlo con permiso del comprador: añade un caso a validar sin que nadie lo haya pedido.
> 4. **La entrevista es un CLI conversacional.** Se descartó un formulario de una sola pasada (menos entrevista) y un endpoint en la API (la API no invoca al modelo, RF-COD-05).

```mermaid
graph TD
  C["Comprador"] -- "respuestas y texto libre" --> E["entrevista.py<br/>(CLI)"]
  E -- "qué falta y qué se contradice:<br/>código" --> A["analizar(brief)"]
  E -- "entender la respuesta y preguntar:<br/>agente entrevistador" --> P["Puerto a Claude Code"]
  A --> E
  E -- "brief válido, confirmado" --> I["intención crear_novela<br/>(brief + transcripción)"]
  I --> W["Worker: brief, elementos personales,<br/>restricciones derivadas"]
  W --> PL["Planner con el destinatario:<br/>arquitecto, mundo, elenco, escaleta"]
  PL --> G["Puertas 1, 2 y 3<br/>con comprobaciones del brief"]
```

### El brief

**RF3-BRF-01 — Modelo.** El brief es un modelo Pydantic en `compartido/brief.py`, porque lo usan la API, el worker y el entrevistador. Campos:

| Campo | Tipo | Obligatorio | Notas |
| --- | --- | --- | --- |
| `destinatario.nombre` | texto, 1–60 | sí | Se escribe **exactamente** así en toda la novela |
| `destinatario.edad` | entero, 1–110 | sí | Es la edad del lector: la novela es para él |
| `destinatario.pronombres` | `el` · `ella` · `neutro` | sí | Concordancia gramatical del protagonista en castellano |
| `destinatario.rasgos` | lista de elementos personales, 1–8 | sí (al menos uno) | Rasgos de carácter o físicos |
| `recuerdos` | lista de elementos personales, 1–10 | sí (al menos uno) | Anécdotas, lugares, costumbres |
| `allegados` | lista de allegados, 0–6 | no | Personas o mascotas cercanas: `nombre`, `relacion`, `rasgos`, `obligatorio` |
| `ocasion` | `cumpleanos` · `aniversario` · `boda` · `jubilacion` · `navidad` · `otra` | sí | Más `ocasion_detalle` libre si es `otra` |
| `quien_regala` | texto, 1–80 | sí | Firma la dedicatoria |
| `mensaje_dedicatoria` | texto, ≤ 300 | no | Lo que el comprador quiere decir; el arquitecto lo integra |
| `intensidad` | `atmosferico` · `tension` · `intenso` | sí | RF3-BRF-02 |
| `tono` | `sobrio` · `emotivo` · `humor_negro` · `aventura` | sí | |
| `subgenero` | uno de los seis de `compartido/tipos.py::Subgenero` | no | Si falta, lo elige el arquitecto |
| `capitulos` | entero, 3–10 | no, por defecto 10 | Extensión (RF3-ESC-01). Tres como mínimo: la estructura tiene tres actos, y un acto sin capítulos para la puerta 2 |
| `vetados` | lista de textos, 0–30 | no | Palabras o temas que no pueden aparecer; los aplica el guardrail del bloque 5 |
| `texto_libre` | texto, ≤ 4.000 | no | Anécdota o carta pegada por el comprador. **No confiable** (RF3-ENT-05) |

Un **elemento personal** es `{codigo, texto, obligatorio, origen, cita}`. El `codigo` es estable dentro del brief (`RAS1`, `REC1`, `ALL1`…) y es lo que el resto del sistema usa para decir dónde aparece cada elemento. `origen` es `entrevista` o `texto_libre`, y `cita` es el fragmento literal del que se extrajo. Por defecto todo elemento es obligatorio.

**RF3-BRF-02 — Intensidad.** Tres niveles, cada uno con su edad mínima y con lo que admite:

| Nivel | Edad mínima | Admite | No admite |
| --- | --- | --- | --- |
| `atmosferico` | 10 | Inquietud, amenaza sugerida, peligro que se resuelve, pérdidas sin descripción | Muertes en escena, sangre, heridas descritas, crueldad |
| `tension` | 14 | Peligro real, muertes fuera de plano, heridas sin detalle anatómico | Violencia gráfica, tortura, terror corporal explícito |
| `intenso` | 18 | Violencia explícita al servicio de la historia | Contenido sexual, que queda fuera del producto en todos los niveles |

La tabla vive en `compartido/brief.py` y es la única fuente: de ella salen las restricciones de público y de política de contenido (RF3-PER-01) y el texto que reciben el arquitecto y el redactor.

> **Decisión de la spec.** No hay nivel para menores de 10 años: una novela de terror para un niño de 8 no es un producto que el sistema deba ofrecer. El brief con esa edad es una contradicción que no se resuelve bajando la intensidad, y el entrevistador lo dice así.

**RF3-BRF-03 — Análisis determinista.** `analizar(brief_parcial)` devuelve dos listas, **sin llamar a ningún modelo** (picaresca antes que juicio):

- **Faltantes:** los campos obligatorios de RF3-BRF-01 vacíos, en el orden de la tabla.
- **Contradicciones**, cada una con un código y los campos implicados:

| Código | Cuándo | Cómo se resuelve |
| --- | --- | --- |
| `edad_bajo_intensidad` | La edad está por debajo de la mínima de la intensidad elegida | Bajar la intensidad, o corregir la edad; con menos de 10 años no hay resolución |
| `subgenero_exige_intensidad` | `terror_corporal` o `slasher_espacial` con intensidad `atmosferico`: esos subgéneros viven del cuerpo y de las bajas | Otro subgénero, o más intensidad si la edad lo permite |
| `elemento_con_vetado` | Un término de `vetados` aparece, normalizado, en un elemento obligatorio o en el nombre de un allegado obligatorio | Quitar el término de `vetados` o el elemento |

La normalización ignora mayúsculas y acentos, conserva la eñe y trata el plural simple (`-s`, `-es`) como el singular. Es la misma que usará el guardrail del bloque 5, y vive en `compartido/` para que ambos la compartan.

**RF3-BRF-04 — Un brief válido no tiene faltantes ni contradicciones.** `Brief.validar_completo()` lanza un error con las dos listas si alguna no está vacía. Lo aplican la API (RF3-PER-05) y el worker.

### El entrevistador

**RF3-ENT-01 — Qué es.** Un agente nuevo, `entrevistador`, con su skill en `.claude/skills/entrevistador/` y su tarea en `tareas/entrevistador/` (esquemas y servicio). Hace dos cosas y ninguna más: **entender** la respuesta del comprador (convertirla en campos del brief) y **preguntar** por lo siguiente pendiente. Qué falta y qué se contradice lo decide el código (RF3-BRF-03), no el agente.

**RF3-ENT-02 — Bucle.** `src/backend/entrevista.py` es un CLI, como `demo.py`:

1. Si hay texto libre (`--texto-libre fichero`), se procesa primero (RF3-ENT-05).
2. En cada turno el código calcula los pendientes (contradicciones primero, después faltantes) y llama al agente con el brief parcial, los pendientes, los últimos turnos y la última respuesta.
3. El agente devuelve `SalidaEntrevistador = {actualizaciones: [{campo, valor, cita}], pregunta}`.
4. El código aplica cada actualización solo si pasa cuatro filtros, y lo que no los pasa se descarta con su motivo en la transcripción:
   - el campo está permitido;
   - la `cita` son **palabras completas** de la respuesta del comprador (no una letra ni un trozo de palabra);
   - el `valor` está **anclado** en lo que dijo: en los campos de texto, el valor son sus propias palabras; en la edad y los capítulos, el número está en la cita, en cifras o en letras; en los enumerados, la cita nombra el valor o una palabra que lo signifique (tabla `ANCLAS` del servicio);
   - el valor valida contra el brief.

   Así el agente no puede meter un dato que el comprador no dio, ni con una cita real: la cita sola no basta, el valor tiene que salir de ella.
5. En las listas, una actualización puede **añadir** o **quitar** (`operacion`). Quitar es como se resuelve `elemento_con_vetado`, y lo que ya está no se añade dos veces.
6. Sin pendientes, se muestra el resumen y se pide confirmación, también si el encargo se completa en el último turno. Con un «sí», se encola `crear_novela` con el brief y la transcripción.

**RF3-ENT-03 — Límite.** Como máximo 25 turnos. Si se agotan con pendientes, la entrevista termina sin encolar nada y lo dice: un retry con límite, como el resto del harness.

**RF3-ENT-04 — Sin agente, cuando no hace falta.** `entrevista.py --brief fichero.json` valida un brief ya escrito, informa de sus faltantes y contradicciones y, si es válido, lo encola. No invoca al modelo. Es lo que usan el brief de ejemplo, los tests y los cinco briefs de prueba del bloque 10.

**RF3-ENT-05 — Texto libre no confiable.** El texto libre es **dato, nunca instrucción**:

- Entra en el paquete entre delimitadores explícitos y con la indicación de que es contenido del comprador que no se obedece.
- De él solo se pueden extraer `rasgos`, `recuerdos` y `allegados`, con origen `texto_libre`, y entran como **no obligatorios**: son material que la novela puede usar, no algo que la escaleta esté obligada a planificar. La intensidad, los vetados, la extensión, la ocasión y quién regala solo los fija el comprador en la conversación.
- Un elemento extraído que dispara un patrón de inyección se descarta, y el texto pierde cualquier marcador del delimitador antes de entrar en el paquete, para que no pueda cerrarlo por su cuenta.
- Cuando los recuerdos llegan a los agentes del pipeline, van entre comillas y marcados como descripciones del comprador, no como instrucciones.
- Cada elemento extraído lleva una cita que el código comprueba literalmente contra el texto (como en RF3-ENT-02, punto 4).
- Una búsqueda determinista de patrones de inyección («ignora las instrucciones», «a partir de ahora eres», «prompt del sistema», marcadores de rol) añade una **alerta** a la transcripción. El texto sigue tratándose como dato; la alerta es para el red-team log y el audit log del bloque 5.

**RF3-ENT-06 — Un solo escritor.** La entrevista no escribe en la base de datos salvo la fila de la intención, igual que la API (RF-API-02). Invoca al puerto **sin conexión**, así que sus llamadas no van a `llamada_modelo`; su traza viaja en la transcripción dentro de la intención y el worker la guarda (RF3-PER-02).

**RF3-ENT-07 — Puerto falso.** El puerto falso tiene un generador de entrevistador que responde de forma determinista a un guion de respuestas, para probar el bucle sin gastar.

### El brief dentro del pipeline

**RF3-PER-01 — Restricciones derivadas.** Al crear una novela con brief, el worker deriva sus restricciones del brief en lugar de recibirlas: `longitud_objetivo_palabras = capitulos × 1.250`, `longitud_capitulo_palabras = 1000-1500`, `capitulos = N`, `publico` y `politica_contenido` de la tabla de intensidad, `pov_por_defecto = tercera_limitada` y `tiempo_verbal = pasado`. El título queda vacío y lo propone el arquitecto (ya lo hace si falta).

**RF3-PER-02 — Persistencia.** Tres tablas nuevas (migración 004):

| Tabla | Qué guarda |
| --- | --- |
| `brief` | El brief validado, en JSON, uno por novela |
| `elemento_personal` | Un elemento por fila: código, tipo (`rasgo`, `recuerdo`, `allegado`), texto, obligatorio, origen, cita |
| `escena_elemento` | Qué elementos personales planifica la escaleta en cada escena |

Más `entrevista` (la transcripción, con sus alertas y las llamadas al agente) y la columna `novela.dedicatoria`. Son canon: ninguna reversión de capítulos las toca. `escena_elemento` cae con sus escenas cuando se rehace la escaleta.

**RF3-PER-03 — Qué recibe cada agente.**

| Agente | Recibe del brief | Produce |
| --- | --- | --- |
| Arquitecto | Destinatario, ocasión, quién regala, mensaje, intensidad con su tabla, tono, subgénero si viene fijado, vetados | Lo de siempre más `dedicatoria` (≤ 400 caracteres, con el nombre del destinatario escrito exactamente) |
| Mundo | Los recuerdos, como material que la estación puede reflejar | Lo de siempre |
| Elenco | Destinatario (nombre, edad, pronombres, rasgos) y allegados obligatorios | El destinatario como `protagonista` con su nombre exacto, y cada allegado obligatorio como personaje |
| Escaleta | Los elementos personales obligatorios con su código, y el número de capítulos | Cada escena declara los códigos que integra (`elementos`) |
| Redactor | Por escena, los elementos que integra; la intensidad con su tabla; el nombre exacto del destinatario | Lo de siempre |

**RF3-PER-04 — Puertas.** Comprobaciones nuevas, todas deterministas y bloqueantes:

| Puerta | Comprobación | Falla si |
| --- | --- | --- |
| 1 | `destinatario_protagonista` | No hay un personaje con el nombre normalizado del destinatario y rol `protagonista` |
| 1 | `allegado_en_elenco` | Un allegado obligatorio no está en el elenco |
| 1 | `dedicatoria_nombra_al_destinatario` | La dedicatoria no contiene el nombre del destinatario tal cual |
| 1 | `subgenero_del_brief` | El brief fija un subgénero y el arquitecto eligió otro |
| 1 | `subgenero_exige_intensidad` | El brief no fija subgénero y el arquitecto eligió uno que no cabe en la intensidad (terror corporal o slasher en «atmosférico») |
| 2 | `numero_de_capitulos` | La escaleta no tiene exactamente los capítulos del brief |
| 2 | `pov_del_destinatario` | El destinatario es el punto de vista de la mitad de las escenas o menos |
| 2 | `elemento_sin_escena` | Un elemento obligatorio no está planificado en ninguna escena |
| 3 | `destinatario_muere` | La condición del destinatario pasa a `muerto` en el capítulo |

Un código de elemento que la escaleta declara y no existe se ignora y queda en la traza (evento `elemento_desconocido`); si por eso un elemento obligatorio se queda sin escena, lo para `elemento_sin_escena`.

Las comprobaciones del encargo solo corren en novelas con brief: una novela sin personalizar pasa por las puertas exactamente igual que antes.

**Rehacer una parada de estructura vuelve a la fase culpable.** La puerta 1 juzga cosas que no escribe el estructurador: la dedicatoria y el subgénero son del arquitecto, y el protagonista y los allegados, del elenco. `rehacer` mira qué comprobaciones fallaron y borra desde la fase más temprana implicada (arquitecto, elenco o estructura); la planificación se repite desde ahí, y el agente que vuelve a correr recibe el informe de la puerta en su paquete. Sin esto, una dedicatoria mal escrita dejaba la novela en una parada que no se podía resolver.

> **Decisión de la spec.** Que un elemento esté **planificado** en una escena lo declara el escaletador, así que es dato autodeclarado (regla 3 de validators.md). La comprobación de la puerta 2 detecta un olvido del plan, pero no que la prosa lo cumpla. El segundo método, que el elemento aparezca en la prosa comprobado contra la tabla de hechos, es del bloque 6; hasta entonces la fila de verificación lo declara.

**RF3-PER-05 — API.** `crear_novela` acepta `brief` (RF3-BRF-01) y `entrevista`. Un brief con faltantes o contradicciones es `422` con código `brief_incompleto` y las dos listas, en JSON, en `detalle`. Un brief mal formado (un nombre en blanco, dos elementos con el mismo código) también es `422`, y nunca llega al worker. El payload antiguo, sin brief, sigue funcionando para los tests y la demo existentes, y crea una novela sin personalización.

**RF3-PER-07 — Vigencia de las puertas.** Amplía RF2-PIPE-00. Las puertas 1 y 2 añaden a su huella lo que leen del encargo (el brief, el nombre normalizado de los personajes, la dedicatoria, los elementos personales y dónde los planifica la escaleta), pero **solo si la novela tiene brief**. Una novela sin personalizar conserva exactamente la huella de antes, así que ninguna novela ya generada pierde la vigencia de sus puertas al migrar.

**RF3-PER-06 — Demo.** `demo.py --brief fichero.json` crea la novela desde un brief. `ejemplos/brief-ejemplo.json` pasa a ser un brief personalizado completo.

**RF3-ESC-01 — Escala del examen.** Diez capítulos de 1.000 a 1.500 palabras por defecto. La escala sale de RF3-PER-01 y la vigilan comprobaciones que ya existen (presupuesto y longitud por capítulo de la puerta 2) más `numero_de_capitulos`. La longitud **real** de cada capítulo escrito es del bloque 6 (RF3-VAL-02).

### Lo que el bloque 2 deja para después

- Que la prosa respete la intensidad: el guardrail por nivel (bloque 5) y la rúbrica del juez (bloque 6).
- Que cada elemento personal aparezca en la prosa y de forma natural (bloque 6; los allegados, RF3-VAL-03).
- Los nombres escritos exactamente en la prosa (bloque 6, RF3-VAL-01).
- Que las llamadas del entrevistador lleguen a Langfuse (bloque 4); hasta entonces viven en la transcripción.

---

## 3.3 Bloque 3 — Huecos de la story bible

La story bible guardaba dónde se **establece** cada hecho, pero no dónde se **usa**, ni la edad de nadie, ni un tiempo con el que se pueda contar, ni qué leyó el lector. Tres bloques posteriores lo necesitan: el cambio del lector (bloque 8) regenera solo los capítulos que usan el hecho cambiado, Lean (bloque 9) comprueba edades y orden temporal con números, y la lectura (bloque 7) publica versiones con una página de novedades.

> **Decisión entrevistada, 23 de septiembre de 2026.** Cuatro decisiones:
>
> 1. **Dónde se usa un hecho sale de tres fuentes**: lo que el extractor vuelve a afirmar, el conocimiento que los personajes adquieren o usan, y una búsqueda determinista del valor exacto en la prosa. Se descartaron solo el extractor (dato autodeclarado sin segundo método, regla 3 de validators.md) y solo la búsqueda (no ve una paráfrasis). La tabla peca de incluir de más: regenerar un capítulo de sobra cuesta dinero, dejarse uno rompe la continuidad.
> 2. **El protagonista tiene la edad del destinatario.** Se reconoce mejor, y es comprobable contra el brief. Se descartaron que la eligiera el elenco con margen y que la eligiera libremente.
> 3. **Una versión nace cuando la novela se completa** y cada vez que un cambio la vuelve a completar con otro texto. Lo que el harness rehace por dentro (reintentos, paradas) no es una versión: el lector nunca lo vio. Se descartaron versionar también cada parada resuelta y versionar solo a petición del autor.
> 4. **El tiempo se cuenta en días desde el comienzo de la historia**, enteros y negativos antes de él. Se descartaron los años (no distinguen dos sucesos de la misma semana, que en una estación son casi todos) y quedarse en el orden relativo (Lean no podría comprobar una edad).

```mermaid
graph LR
  X["Extractor<br/>(capítulo N)"] -- "hecho nuevo" --> H["hecho<br/>(establece)"]
  X -- "repite un hecho vigente" --> U["hecho_uso<br/>(reafirma, con cita)"]
  P["Prosa del capítulo"] -- "valor exacto: nombre o cifra<br/>(código)" --> U2["hecho_uso<br/>(menciona)"]
  X -- "adquiere o usa" --> C["estado_conocimiento<br/>uso_conocimiento"]
  H & U & U2 & C --> V["vista hecho_escena<br/>hecho → escenas y capítulos"]
  V --> B8["Bloque 8: regenerar<br/>solo lo afectado"]
```

### Dónde se usa cada hecho

**RF3-BIB-01 — Tabla `hecho_uso`.** Una fila por cada escena que usa un hecho sin establecerlo: `hecho_id`, `escena_id`, `via` y `cita`. Es estado: append-only, con escena de origen, y la reversión de un capítulo la borra con el resto de su estado (RF-FALLO-04). Dos vías:

| Vía | Quién la registra | Cuándo |
| --- | --- | --- |
| `reafirma` | El extractor, sin saberlo | Devuelve un hecho con el mismo valor que el vigente. Hasta ahora esa reafirmación se descartaba sin rastro (RF2-PIPE-19): sigue sin crear un hecho nuevo, pero deja su uso con la cita que la fija |
| `menciona` | El código, al registrar el capítulo | El **valor exacto** de un hecho vigente, y todavía no sustituido en ese punto de la historia, aparece en la prosa de la escena, con la comparación de palabras completas de `compartido/texto.py` (la misma del brief y del guardrail). Solo cuentan los hechos cuyo valor es un literal que la prosa repite: categorías `nombre`, `fecha` y `distancia`, o un valor con cifras. Un valor de menos de tres letras sin cifras no se busca |

Una escena no se registra como uso del hecho que ella misma establece, y un mismo hecho se registra como mucho una vez por escena y vía.

**RF3-BIB-02 — Vista `hecho_escena`.** Une las cuatro fuentes en `(novela_id, hecho_id, escena_id, capitulo_numero, via)`, con `via` en `establece`, `reafirma`, `menciona`, `conoce` (un estado de conocimiento) y `usa` (un uso de conocimiento). `lectura.capitulos_de_hecho(hecho_id)` devuelve los capítulos, en orden, que el bloque 8 regenerará.

> **Decisión de la spec.** Cambiar el **nombre** de una entidad (el perro se llama Nala) no es cambiar un hecho: los nombres viven en `personaje`, `lugar` y `objeto`, no en `hecho`. Esos capítulos son los del reparto de la entidad más los que la nombran, y los calcula el bloque 8 con las mismas dos piezas (el reparto de la escaleta y `contiene_termino`). Aquí no se duplica.

**RF3-BIB-03 — Lo que ve la puerta 3.** Dos búsquedas dirigidas de la puerta 3 (RF2-PIPE-17) cuentan ahora `hecho_uso` como registro:

- `nombre_sin_registro` deja de avisar cuando la escena reafirma un hecho de la entidad nombrada. Era un falso aviso: el extractor sí había dicho algo, y se descartaba.
- `cifra_sin_hecho` deja de avisar cuando la escena usa (reafirma o menciona) un hecho de fecha o distancia: la cifra ya está en el canon.

### Edad de los personajes

**RF3-BIB-04 — Edad.** El elenco declara la `edad` de cada personaje, en años enteros de 0 a 1.000 (una inteligencia de a bordo o algo más viejo también la tiene), **el día 0** de la historia. Es obligatoria en la salida del elenco. La columna `personaje.edad` admite nulo solo por las novelas anteriores a este bloque.

**RF3-BIB-05 — Nacimiento.** La vista `personaje_nacimiento` deriva el día de nacimiento: `nacimiento_dia = −(edad × 365) − 182`. El año tiene 365 días, sin bisiestos, y el nacimiento cae a mitad de año para que la edad sea la declarada durante medio año antes y después del día 0: una analepsis de una semana no le quita un año a nadie. La edad en un día `d` es `⌊(d − nacimiento_dia) / 365⌋`. La fórmula vive solo en la vista; Lean (bloque 9) la lee de ahí.

**RF3-BIB-06 — La edad del destinatario.** En una novela con brief, el protagonista tiene exactamente la edad del destinatario. Comprobación nueva de la puerta 1, `edad_del_destinatario`, bloqueante; su rechazo se rehace desde el elenco (la fase culpable, como `destinatario_protagonista`). La huella de la puerta 1 incluye la edad de los personajes solo si la novela tiene brief **y** edades (RF3-PER-07).

Una novela con brief creada antes de este bloque no tiene edades: su elenco no las declaraba. Para ella la comprobación no se aplica y la huella es exactamente la que registró su puerta 1, así que al migrar no pierde la vigencia. Sin esa excepción, la puerta 1 quedaba sin vigencia, una ejecución en `generando` se atascaba al intentar replanificar, y al reevaluarse la puerta rechazaba siempre por una edad nula.

**RF3-BIB-07 — La edad llega a quien escribe.** La ficha de cada personaje en el paquete del redactor incluye su edad, para que la prosa no la contradiga.

### Cronología

**RF3-BIB-08 — Día.** Cada evento lleva `dia`: días enteros desde el comienzo de la historia, que es el día 0, y negativos antes de él.

- El constructor de mundo declara el `dia` de cada evento previo, que tiene que ser 0 o menor. Su `orden_interno` sale de ordenar los previos por día (antes salía del orden de la lista, y un previo mal colocado habría contradicho su propia fecha).
- El extractor declara el `dia` de cada evento dramatizado, igual que su `orden_interno` y con la misma obligación (RF2-PIPE-10). Su paquete le dice el último día registrado.
- `fecha_interna` se queda como texto para la prosa («la tercera noche»); el cálculo usa `dia`.

**RF3-BIB-09 — El día y el orden no se contradicen.** Comprobación nueva de la puerta 3, `dia_contra_orden`, bloqueante: dos eventos con día y orden interno se contradicen si uno va antes en orden y después en días, o si son simultáneos (mismo orden) y caen en días distintos. Cada par sale una vez, y al menos uno de los dos es del capítulo que se evalúa. Es la misma familia que `coherencia_temporal`: dos datos que declara el extractor, comparados entre sí sin preguntar a nadie.

Como `coherencia_temporal`, solo compara eventos **dramatizados fuera de una analepsis**. Los antecedentes del mundo llevan un orden negativo que el extractor no ve, y el orden de un recuerdo respecto a sucesos de capítulos lejanos tampoco lo conoce: compararlos producía choques que el extractor no podía evitar. Esos pares se comprueban por el día en Lean (bloque 9).

**RF3-BIB-10 — Vista `cronologia`.** Un evento por fila, en orden de `dia` y `orden_interno`: evento, día, orden, fecha en texto, descripción, si está dramatizado, capítulo y escena, y lugar. `cronologia_personaje` da los personajes de cada evento: el reparto y el punto de vista de su escena. Un evento previo del mundo no tiene escena, ni lugar, ni personajes.

> **Decisión de la spec.** Los personajes de un evento son los de su escena. Es una aproximación: en una escena larga, alguien del reparto puede no estar en un suceso concreto. La alternativa, que el extractor declarase los participantes de cada evento, añade otro dato autodeclarado sin segundo método. Para las invariantes de Lean (nadie en dos lugares a la vez, nadie actúa antes de nacer) la aproximación peca de estricta, que es el lado seguro.

### Versiones de la novela

**RF3-BIB-11 — Tablas.** `novela_version` (número, motivo, detalle, título, dedicatoria, fecha) y `novela_version_capitulo` (número de capítulo, texto, palabras, `cambiado`). Son canon: ninguna reversión las toca.

> **Decisión de la spec.** La versión **copia** el texto de cada capítulo en lugar de apuntar a `capitulo_compilado`. Rehacer la escaleta borra los capítulos, y con ellos sus compilados, en cascada; una versión que apuntase a ellos perdería su texto justo cuando el lector más la necesita. Diez capítulos de 1.500 palabras por versión no pesan nada.

**RF3-BIB-12 — Cuándo nace.** Al completarse la novela, en la misma transacción que la lleva a `completada` o `completada_con_avisos`, el worker publica una versión **si el texto difiere de la última publicada**: capítulos, título o dedicatoria.

| Situación | Resultado |
| --- | --- |
| Primera vez que se completa | Versión 1, motivo `primera`, todos sus capítulos `cambiado` |
| Se relanza desde un capítulo y se vuelve a completar con otro texto | Versión siguiente, motivo `relanzamiento`, `cambiado` solo en los capítulos cuyo texto difiere |
| Se vuelve a completar con el mismo texto | Ninguna |
| Un cambio del lector (bloque 8) | Versión siguiente, motivo `cambio_lector`, con el cambio en `detalle` |

**RF3-BIB-13 — Novelas anteriores.** La migración publica la versión 1 de cada novela que ya estaba completada, con su texto vigente, para que ninguna novela completada quede sin versión.

**RF3-BIB-14 — Integridad.** Regla nueva de `verificar_integridad`, `version_desfasada`: una novela completada tiene al menos una versión, y la última tiene exactamente sus capítulos vigentes con su texto (ni uno de menos ni uno que ya no exista), su título y su dedicatoria. Otra regla, `uso_antes_del_hecho`: ningún `hecho_uso` precede a la escena que establece su hecho.

### API

**RF3-BIB-15 — Rutas de lectura.** Tres rutas nuevas, de solo lectura como el resto (RF-API-02):

| Ruta | Devuelve |
| --- | --- |
| `GET /novelas/{id}/cronologia` | Los eventos de la vista `cronologia`, con sus personajes |
| `GET /novelas/{id}/hechos/{hecho_id}/usos` | Las filas de `hecho_escena` del hecho, con capítulo, escena, vía y cita |
| `GET /novelas/{id}/versiones` y `GET /novelas/{id}/versiones/{numero}` | Las versiones publicadas; la segunda, con sus capítulos |

### Lo que el bloque 3 deja para después

- Regenerar los capítulos de un hecho cambiado, y la página de novedades (bloque 8).
- Generar el fichero de Lean desde la cronología y las edades (bloque 9).
- La lectura en HTML y PDF de una versión (bloque 7).

---

## 3.4 Bloque 4 — Observabilidad con Langfuse

Cada llamada a un agente ya queda en `llamada_modelo` con su entrada, su salida, sus tokens y el coste que declara Claude Code, y cada puerta deja su veredicto en `resultado_puerta`. Este bloque lleva esos datos a Langfuse, para ver una novela entera, su coste y sus validadores en un solo sitio, y para comparar versiones de las skills cuando llegue la iteración de tuning.

> **Decisión entrevistada, 23 de septiembre de 2026.** Tres decisiones:
>
> 1. **Langfuse Cloud, región UE.** Se descartaron el autoalojado con Docker (hay que levantarlo y mantenerlo, también en la demo) y reutilizar otro proyecto.
> 2. **Se envía todo, con el encargo seudonimizado.** Entradas y salidas de cada llamada, pero el nombre del destinatario, los allegados y quien regala se sustituyen por etiquetas antes de salir de la máquina. Se descartaron enviar solo métricas (en Langfuse no se podría leer qué recibió cada agente) y enviarlo todo tal cual (datos personales reales a un tercero).
> 3. **Envía el worker al cerrar cada unidad de trabajo**, y un comando exporta novelas enteras. Se descartaron enviar solo a mano (hay que acordarse) y enviar cada llamada en directo (mete la red en el camino del pipeline).

> **Lección del primer harness.** Langfuse declaraba menos de la cuarta parte del coste real, porque solo anotaba lo que se le contaba desde fuera (commit `2280640`). Otros dos fallos de entonces: un modelo sin precio que salía gratis (`cf3ba67`) e identificadores que chocaban entre novelas (`b87775d`). Aquí la fuente es la base, el coste es el que declara el puerto llamada a llamada, y los identificadores salen de las filas de la base.

```mermaid
graph LR
  P["Puerto<br/>(cada llamada)"] --> L["llamada_modelo<br/>entrada, salida, tokens, coste"]
  G["Puertas 1 a 5"] --> R["resultado_puerta"]
  E["Entrevista"] --> T["entrevista<br/>(métricas de sus llamadas)"]
  L & R & T --> X["Exportador<br/>(worker, al cerrar una unidad)"]
  X -- "seudonimiza el encargo" --> S["[DESTINATARIO], [ALLEGADO_1]…"]
  S --> LF["Langfuse Cloud (UE)<br/>sesión = novela"]
```

### Configuración

**RF3-OBS-01 — Claves.** `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` y `LANGFUSE_HOST` (por defecto `https://cloud.langfuse.com`, la región UE). Sin las dos claves, el exportador está desactivado y nada más cambia: el pipeline, los tests y la demo corren igual. Con el puerto falso tampoco se exporta, aunque haya claves: una demo o un test no gasta nada y solo ensuciaría el proyecto del autor. Las claves solo viven en `src/backend/.env`, que no se commitea; `.env.example` lleva las variables vacías.

**RF3-OBS-02 — El `.env` se carga solo.** `config.py` lee `src/backend/.env` si existe, antes de leer el entorno. Una variable ya fijada en el entorno del proceso manda sobre la del fichero. Cierra el punto pendiente del bloque 1 del plan.

### Qué se envía

**RF3-OBS-03 — La base es la única fuente.** El exportador lee `llamada_modelo` (solo llamadas terminadas), `resultado_puerta` y `entrevista`, y no depende de nada que el pipeline recuerde en memoria. El coste de cada llamada es el `total_cost_usd` que devolvió Claude Code. Una llamada terminada sin coste se envía con nivel `WARNING` y la marca `coste_desconocido`: parecer gratis es peor que no contarlo.

**RF3-OBS-04 — Estructura.**

| En Langfuse | Qué es | Identificador |
| --- | --- | --- |
| Sesión | La novela entera | `storymaker-novela-<clave>` |
| Traza | Una unidad de trabajo: `entrevista`, `planificacion`, `capitulo-<n>` o `cierre` (la puerta 5), con la fecha de su primera fila en la base | Derivado de la clave y la unidad |
| Generación | Una llamada a un agente, con su rol (planner, writer, editor, extractor o entrevistador), intento, estado, turnos, modelo, tokens, coste y latencia | Derivado de la fila de `llamada_modelo` |
| Span | Una evaluación de puerta, con sus conflictos | Derivado de la fila de `resultado_puerta` |
| Score | Los validadores (RF3-OBS-05) | Derivado de la fila y del nombre del score |

Los identificadores son UUID deterministas (versión 5) de la **clave** de la novela y de la fila de origen: reenviar lo mismo actualiza, no duplica. La clave es el id de la novela más una huella de su fecha de creación, porque cada base (`novela.db`, `novela_real.db`, las temporales) tiene su novela 1, y con el id solo se pisarían. El sobre de cada evento lleva un identificador nuevo en cada envío, para que Langfuse no descarte como repetida una actualización. Las llamadas de la entrevista solo guardan métricas en la transcripción, así que en Langfuse van sin texto.

> **Decisión de la spec.** El plan decía «una traza por novela». Se usa **una sesión por novela y una traza por unidad**: una novela dura horas, cruza reinicios del worker y suma cientos de llamadas, y una sola traza así no se puede leer. La sesión es la vista de la novela entera; la traza, la de un capítulo.

**RF3-OBS-05 — Los validadores como scores.** Por cada evaluación de puerta:

- `puerta_<n>`, booleano: 1 si no falla.
- `puerta_<n>_bloqueantes` y `puerta_<n>_avisos`, numéricos.
- Por cada comprobación que falla o avisa, un score booleano a 0 con su nombre (`continuidad_factual`, `dia_contra_orden`…), para poder filtrar por comprobación.

**RF3-OBS-06 — Las skills como prompts versionados.** Cada skill es un prompt de Langfuse llamado `storymaker-<agente>`. Su versión se identifica por la huella SHA-256 del texto que recibió el agente (etiqueta `sha-<12 primeros>`), que es el `sistema` guardado en la propia llamada. La primera vez que aparece una huella se crea la versión, y cada generación enlaza la suya. Cambiar una skill produce una versión nueva sin que nadie tenga que registrarla.

**RF3-OBS-07 — Seudonimización (RGPD).** Antes de salir de la máquina, todo texto que se envía (entradas, salidas, metadatos y también las **claves** de los diccionarios, porque `nivel_confianza` va por personaje) sustituye los nombres del encargo. La comparación se hace sobre el texto entero **plegado**: sin distinguir mayúsculas, también las matemáticas o de tipo letra («𝐌», «ℳ»); sin ninguna marca diacrítica, en los dos lados (el brief puede decir «Ramon» y la prosa «Ramón», o al revés, y lo mismo con «João», «Dvořák» o «Ştefan»); con las letras sin descomposición que se leen como otra («Łukasz» y «Lukasz», «ø», «ß»); sin los caracteres que no se ven (todos los de formato, que incluyen el guion blando, los anchos cero y las marcas bidi que trae un nombre pegado desde un contacto, y todas las marcas, también las que no combinan, como el CGJ o los selectores de variante), y con los apóstrofos rectos, los tipográficos y las letras modificadoras que Unicode recomienda como apóstrofo («ʼ», U+02BC) como iguales. Un mapa de posiciones lleva cada acierto al texto original, y la salida sale en NFC. Se sustituye como palabra completa: solo otra letra, delante o detrás, hace de un nombre otra palabra («Martina» no es «Marta»); un dígito o un guion bajo, no («Marta2», «marta_ibanez»), y tampoco una letra separada por una frontera suave (un carácter de formato o un relleno quitados, «Marta​Ibáñez», o un símbolo que pliega a letras, «Marta™») o por un paso a mayúscula («regaloParaMarta», «MARTAIbáñez»). El reemplazo cubre las marcas que siguen al nombre, no los caracteres de formato: el cierre de un aislamiento bidi se queda donde estaba. Dos aciertos que se solapan en parte en el texto original se funden en un solo reemplazo. El nombre del brief se trocea por cualquier carácter que no sea letra. Una frontera suave o un paso a mayúscula («MartaIbáñez») pueden separar dos partes o ir dentro de una (un guion blando), así que se toman todas las lecturas: cada tramo entre dos cortes cualesquiera. `quien_regala` es la firma de la dedicatoria y trae puntuación («Andrés, tu hermano», «Tus padres (Lucía y Andrés)»). **Lo que puede no ser un nombre se sustituye igual, pero solo cuando en la prosa empieza en mayúscula**: una partícula («Van», «Del»), lo que acompaña al nombre en la firma (posesivos, parentescos, palabras de dedicatoria) y una parte que solo sale de partir por un corte sin separador visible («mar» de «Mar­ta»). En mayúscula es como la prosa escribe un nombre; en minúscula, «del», «feliz» o «el mar» no se tocan. Escritas en minúscula en el brief, la partícula («María de los Ángeles», salvo que abra el nombre: «van Ferrer») y las palabras de dedicatoria de la firma («tu hermano») no son el nombre, y tampoco el posesivo o la preposición que abre la firma («Tus padres…»). Cualquier otra palabra de la firma escrita en minúscula («un abrazo enorme») casa solo en mayúscula. Un brief tecleado todo en minúscula no distingue el nombre de lo que lo acompaña: ahí la minúscula no descarta ni marca nada. Un nombre de una sola palabra que es dudosa («Van») casa, también entero, solo en mayúscula. Ninguna lista descarta nunca una parte del destinatario ni de un allegado escrita en mayúscula: «Tía», «Prima», «Van» o «Amigo» son nombres y apellidos reales. Un apellido con apóstrofo cuenta entero y por la parte de después («O'Hara» y «Hara»). Dos claves de un diccionario que dan la misma etiqueta no se pisan: la segunda lleva « #2».

| Dato del brief | Etiqueta |
| --- | --- |
| Nombre del destinatario, completo y cada una de sus partes de tres letras o más que no sean partículas («de los» de «María de los Ángeles» no se sustituye suelto) | `[DESTINATARIO]` |
| Nombre de cada allegado, completo y por partes | `[ALLEGADO_1]`, `[ALLEGADO_2]`… |
| Quien regala, completo y por partes | `[QUIEN_REGALA]` |

El mapa de sustitución no sale nunca de la máquina. Una novela sin brief no tiene nada que sustituir.

> **Decisión de la spec.** Seis puntos ciegos quedan aceptados (el sexto, reescrito tras la quinta revisión), con su fila en el plan de verificación (44). Una parte de menos de tres letras («Li», «Bo») no se sustituye suelta: sustituirla tocaría cada sílaba igual de la prosa, y el nombre completo sí se cubre. Dos copias de una misma base comparten la clave de novela y, por tanto, identificadores en Langfuse: la segunda pisa a la primera, que es lo que se quiere al reenviar. Un nombre que también es palabra común («Luz», «Rosa») se sustituye de más, también cuando la prosa habla de la luz: sustituir de más es el lado seguro. Y un nombre escrito con escapes JSON (`\u00e1`) dentro de un texto no se ve: hoy no hay camino que los produzca, porque todo `json.dumps` que alimenta lo enviado usa `ensure_ascii=False` y la salida se parsea antes de seudonimizar; un `json.dumps` nuevo sin ese parámetro abriría la fuga. Dos partes fundidas todo en mayúsculas y sin separador («MARTAIBAÑEZ») tampoco se separan. Y una parte que puede no ser un nombre (una partícula, lo que acompaña a la firma, lo que solo sale de un corte invisible del brief) escrita en minúscula en la prosa no se sustituye suelta; ni, en la firma, un nombre escrito en minúscula que coincide con una palabra de dedicatoria, o uno que la abre y coincide con un posesivo o una preposición («Con»). Se descartaron las listas que excluían del todo: cada una dejaba pasar los nombres reales que coincidían con ella (cuarta y quinta revisión del validador).

> **Decisión de la spec.** Los rasgos y los recuerdos se envían tal cual. Son la materia que hay que poder leer para depurar la personalización, y sin los nombres no identifican a nadie por sí solos. Queda como riesgo aceptado (U3-3): un recuerdo muy concreto («el faro de su abuelo en Cabo de Gata») puede identificar a alguien combinado con otros datos.

### Cuándo se envía

**RF3-OBS-08 — El worker, al cerrar una unidad.** El worker exporta lo nuevo de la novela al terminar la planificación, la escaleta, cada capítulo, al abrir una parada y al completar la novela. Envía dentro de su proceso, con un tiempo máximo por petición. Lo enviado queda en `langfuse_envio` (tabla, fila; migración 009), que solo escribe el worker, y se envía una sola vez. Si Langfuse falla o rechaza parte del lote, se emite el evento `langfuse_fallo` en la traza, no se marca nada de ese lote y se reintenta en el siguiente envío. Un fallo de Langfuse nunca para ni revierte el pipeline. Sí puede retrasarlo un poco: con Langfuse caído, cada envío espera como mucho el tiempo máximo por operación (5 segundos para conectar, 10 para el resto) antes de rendirse. El latido del cerrojo va en su propio hilo y no se ve afectado.

**RF3-OBS-09 — El comando.** `python exportar_langfuse.py --novela <id>` (o `--todas`) exporta una novela entera desde la base, por ejemplo la de la pasada real. Abre la base en solo lectura y no marca nada: como los identificadores son deterministas, repetirlo no duplica. `--comprobar` hace una petición mínima y dice si las claves y el host funcionan.

**RF3-OBS-10 — El modelo de cada llamada.** El puerto guarda también `modelUsage` en los metadatos de la llamada, que es donde Claude Code dice qué modelo contestó y cuánto costó cada uno. La generación lleva ese modelo. Cuando `modelUsage` trae varios, lleva el de mayor `costUSD`: Claude Code usa además un modelo pequeño (Haiku) para una tarea interna mínima, y etiquetar con el primero de la lista hacía que toda la novela apareciera en Langfuse como Haiku. El coste de la generación sigue siendo el total de la llamada (RF3-OBS-03), no el del modelo elegido.

### Lo que el bloque 4 deja para después

- Enviar el audit log del policy engine (bloque 5) y las evals (bloque 10) como scores y datasets.
- Comparar versiones de prompts en la iteración de tuning, que es donde se usa lo que este bloque registra.
- El diagnóstico del coste del extractor (spec3, RF3-PAS-01) se lee en estas trazas: turnos y coste por llamada.

---

## 3.5 Bloque 5 — Guardrails

Una novela regalo tiene dos listas de lo que no puede salir: lo que su intensidad no admite (RF3-BRF-02) y lo que el comprador vetó en la entrevista (`vetados`). Hasta aquí las dos llegaban al redactor como instrucción, y nada comprobaba la prosa. Este bloque es la comprobación: determinista, por palabras, con el capítulo de vuelta al redactor y un registro de cada decisión.

**RF3-GRD-01 — Los términos vetados, en SQLite.** La tabla `termino_vetado` (migración 010) guarda un término por fila:
- `novela_id` vacío para los **globales**, o el de una novela para los suyos;
- `hasta_nivel`, en los globales: el término se veta en las novelas de esa intensidad y de las más suaves (`atmosferico` < `tension` < `intenso`); `intenso` lo veta en todas;
- `excepciones`: expresiones en JSON dentro de las cuales el término no cuenta («a sangre fría» para «sangre»).

La migración siembra una lista global prudente: el contenido sexual en todos los niveles, la sangre y los cadáveres hasta `atmosferico`, y la tortura, la mutilación y las vísceras hasta `tension`. Cada forma flexionada que importa es su propia fila (infinitivo, imperfecto, **pretérito**, que es el tiempo de la narración, gerundio y participios), porque la búsqueda solo trata el plural simple. Los usos corrientes van como excepciones: «se le heló la sangre», «análisis de sangre», «la misma sangre», «el sexo del embrión», «esta espera es una tortura». Dos grafías del mismo término cuentan una vez, y gana la más estricta: primero la del brief, luego la de la novela y al final la global. Así, el veto del brief nunca hereda las excepciones de la lista global: si el comprador vetó «sangre», «a sangre fría» también para. Al redactor le llega la lista que aplica a su novela, para que no la descubra fallando. Los `vetados` del brief se aplican siempre, en todos los niveles, sin copiarlos a la tabla: el brief ya está en SQLite (RF3-PER-02). Una novela sin brief no tiene intensidad, y solo le aplican los globales de `intenso`.

**RF3-GRD-02 — La búsqueda.** `compartido/politica.py` busca cada término en la prosa como **secuencia de palabras completas**, con la normalización de `compartido/texto.py` (sin mayúsculas ni tildes, con la eñe, y el plural simple como el singular), la misma del análisis del brief (RF3-BRF-03). Una palabra incluye sus marcas combinantes, así que un texto o un término en NFD casa igual que en NFC. Nunca por subcadena: «sangre» no está en «sangrienta» si nadie lo pone en la lista, y «tripa» no está en «tripulación». Antes de partir, se quitan los caracteres invisibles de formato (categoría Unicode Cf), y cada hallazgo guarda su posición sobre el **texto original**: el término, la forma que casó, el fragmento de alrededor y las posiciones de inicio y fin.

**RF3-GRD-03 — El capítulo vuelve al redactor.** La parte mecánica de la puerta 4 falla con `termino_vetado` si hay algún hallazgo. La descripción lleva cada forma con su fragmento y pide reescribir esos pasajes sin la palabra ni lo que nombra. El capítulo vuelve al redactor como con cualquier fallo de la mecánica, y al agotar los intentos (`MAX_INTENTOS_CAPITULO`) la novela para con el informe de oficio, que lleva los hallazgos. Nunca se sustituye nada en silencio.

**RF3-GRD-04 — Registro de decisiones.** Cada hallazgo deja una fila en `decision_politica` (migración 010): novela, capítulo, intento, término, origen (global, novela o brief), forma, fragmento, inicio y fin, la **acción** (`reintentar` si quedan intentos, `parar` si no), la **huella de la política** (sha-256 de los términos aplicados con sus excepciones y de la versión de la normalización) y la huella del texto. Es append-only y ninguna reversión la borra: es el registro de lo que el sistema decidió. La fila se escribe **en la misma transacción** que lo que se hace: `reintentar` con la reversión del capítulo, `parar` con la apertura de la parada. Si el worker cae antes, no queda una acción que no ocurrió. A Langfuse llega con la puerta 4: la comprobación `termino_vetado` como score, y en los metadatos del span cada hallazgo y la huella de la política, todo seudonimizado (RF3-OBS-05 y RF3-OBS-07). La acción (`reintentar` o `parar`) queda solo en SQLite: se decide después de evaluar la puerta.

> **Decisión sin entrevistar.** Las decisiones de producto de este bloque se tomaron sin el autor, con el criterio más prudente, y quedan para su revisión:
> - **Qué hay en la lista global.** Solo palabras que casi nunca tienen otro sentido. Se quedaron fuera «muerte», «herida» o «violación», que el nivel admite en algunos usos («violación del protocolo») y cuyo veto pararía capítulos legítimos. Lo que no se puede decidir por palabras (una muerte en escena, la crueldad) sigue siendo del redactor, por instrucción, y del juez.
> - **Palabras y no temas.** Un veto como «ahogamiento» funciona; uno como «la pérdida de un hijo» solo casa si la prosa usa esas palabras. Los temas son del juez de personalización del bloque 6.
> - **La flexión se escribe, no se deduce.** Se descartó el stemming, que junta palabras distintas («casa» y «caso»), y la expansión automática, que en castellano necesita un diccionario. Por eso la lista siembra las formas que importan.
> - **Se reescribe el capítulo entero y no el párrafo.** El pipeline ya sabe devolver el capítulo con el fallo y la evidencia, y reescribir solo un párrafo exigiría otro agente y otra vuelta por la extracción. Coste aceptado: una reescritura completa por una palabra.
> - **Puntos ciegos.** Una forma que no está en la lista (las que llevan el pronombre pegado, como «torturarlo»), un sinónimo, una perífrasis, y un carácter invisible que no sea de formato dentro de una palabra. La prosa la escribe nuestro propio redactor, no un adversario, así que no se trata el leetspeak.

## 3.6 Bloque 6 — Validadores que faltan

Tres errores de la prosa que el lector de un regalo ve y que ninguna puerta miraba: su nombre mal escrito, un allegado que la escaleta prometió y no sale, y un capítulo de longitud impropia. Los tres son deterministas y van en la parte mecánica de la puerta 4 (RF-PIPE-13), que corre antes del juez y, si falla, devuelve el capítulo al redactor con la descripción del fallo. Si falla tres veces, para.

**RF3-VAL-01 — Los nombres del canon, escritos exactamente.** La comprobación `nombre_mal_escrito` falla si una palabra de la prosa con mayúscula es una palabra de un nombre del canon (personaje, lugar, objeto o facción, de tres letras o más y con mayúscula en el canon) salvo por las tildes o la eñe: «Sebastian» por «Sebastián», «Nunez» por «Núñez». Las mayúsculas no cuentan («NÚÑEZ» está bien escrito), y una palabra en minúscula no es un nombre. **Al empezar frase o diálogo** (tras un punto, «…», dos puntos, un salto de línea, comillas, raya, guion o asterisco) va con mayúscula cualquier palabra, y «Cortes profundos» o «Más tarde» coinciden con los apellidos «Cortés» y «Mas» salvo por la tilde: ahí sale el aviso `nombre_por_revisar`, que no devuelve el capítulo. **Salvo el nombre del destinatario y de sus allegados**, el error más visible de un regalo: si esa palabra no sale nunca en minúscula en el capítulo, no es una palabra corriente, y también devuelve el capítulo. Tras dos puntos o punto y coma va minúscula, así que una mayúscula ahí es un nombre propio, salvo cuando los dos puntos abren una cita o un diálogo («Le dijo: —Tomas el primer turno»), que llevan mayúscula y cuentan como inicio de frase. Una forma que devuelve el capítulo cuenta todas sus apariciones, también las del principio de frase. La descripción dice cada forma mal escrita, cuántas veces sale y cómo se escribe; si el canon tiene dos grafías de esa palabra, las dos.

**RF3-VAL-02 — La longitud real.** El aviso `longitud_real` sale si el capítulo escrito tiene menos o más palabras que el rango `longitud_capitulo_palabras` de la novela. Va al informe y al juez como los demás avisos de la mecánica.

**RF3-VAL-03 — Los allegados planificados, en la prosa.** En una novela con brief, la comprobación `allegado_ausente` falla si la escaleta planificó un allegado en una escena del capítulo y la prosa del capítulo no lo nombra. Basta con una palabra de su nombre de tres letras o más, escrita con mayúscula, porque el redactor lo llama por el nombre de pila. Las partículas («de», «del», «los», «San») no nombran a nadie, y la mayúscula evita que «la luz» cuente como «Luz». La redacción de demostración nombra a los allegados que la escaleta le pide, para que la demo con brief siga pasando.

> **Decisión sin entrevistar.** El nombre y el allegado devuelven el capítulo, y la longitud solo avisa. El nombre mal escrito del destinatario es el error más visible de un regalo, y el allegado que falta es una promesa del encargo incumplida; los dos se corrigen con una reescritura dirigida. La longitud, en cambio, no la percibe el lector como un error, el modelo no cuenta palabras, y reescribir un capítulo entero por eso arriesga meter errores de continuidad nuevos, que es lo contrario del objetivo del autor. Se descartó bloquear la longitud con un margen (por ejemplo, un 20 %) por lo mismo. El validador de 469d64d encontró que un umbral de longitud al empezar frase daba falsos positivos que le pedían al redactor meter una falta («Cortes» se escribe «Cortés»); por eso ahí es un aviso y no una vuelta. Se descartó una lista cerrada de palabras corrientes: sin diccionario no se puede cerrar. Puntos ciegos: un nombre mal escrito que solo aparece al empezar frase (queda como aviso), un nombre escrito con otra letra («Sevastián»), un allegado nombrado solo al empezar frase con una palabra corriente («Luz entró» cuenta) y los rasgos y recuerdos del encargo, que no se pueden buscar por palabras y quedan para el juez de personalización del bloque 6.

### Cada elemento del encargo, en la novela

El enunciado pide que cada elemento personalizado obligatorio aparezca en al menos un capítulo, comprobado contra la story bible. Hasta ahora solo se comprobaba que la escaleta lo planificara (puerta 2, `elemento_sin_escena`) y, para los allegados, que la prosa escribiera su nombre (RF3-VAL-02). Nada miraba si la prosa integraba de verdad un rasgo o un recuerdo.

**RF3-ELE-01 — El extractor registra lo que la prosa integra.** El paquete del extractor lleva los elementos del encargo que la escaleta puso en el capítulo, con su código y su escena. El extractor devuelve en `elementos` cada uno que la prosa integra, con la escena y una cita literal de ella. Entra solo si el código es del encargo y la cita está en la escena (comparación normalizada); lo demás es un descarte con su motivo. Se guarda en `elemento_integrado` (migración 013), estado append-only con escena de origen que se revierte con el capítulo.

**RF3-ELE-02 — La puerta 4 devuelve el capítulo.** Un rasgo o un recuerdo obligatorio que la escaleta puso en el capítulo y que la prosa no integra devuelve el capítulo al redactor (`elemento_sin_integrar`), con el código, el texto y la escena. Los allegados siguen por su nombre (RF3-VAL-02), y un elemento no obligatorio (los que salen del texto libre) no devuelve nada. La corrección del lector (RF3-CAM-09) no aplica esta comprobación: no vuelve a extraer, así que leería la extracción del texto aprobado, o ninguna en una novela anterior a la migración 013.

**RF3-ELE-03 — La puerta 5 avisa de lo que falta en toda la novela.** Un rasgo o un recuerdo obligatorio que ningún capítulo completado integra es el aviso `elemento_obligatorio_ausente` (la puerta 5 no bloquea, RF2-PIPE-15).

> **Decisión sin entrevistar.** Se comprueba contra lo que registra el extractor, con cita verificable, y no buscando el texto del recuerdo en la prosa: un recuerdo bien integrado se cuenta con otras palabras, y buscar el literal pararía casi todos. Se hizo bloqueante por capítulo, como el allegado, porque un elemento del regalo que falta es el fallo que el comprador ve primero; el riesgo es que el extractor no lo reconozca y el capítulo vuelva sin motivo, y ese coste es un intento más. Se descartó que la comprobación la hiciera solo el juez: es probabilístico, y esto se puede comprobar contra la base.

### La segunda opinión en la parada

**RF3-JUE-01 — El revisor de continuidad opina, y la parada sigue abierta.** Cuando la puerta 3 para un capítulo, el pipeline **abre la parada** y después invoca al agente `continuidad`, que tenía skill y esquema pero nadie llamaba. Recibe los conflictos bloqueantes, con sus datos y con su número en la lista entera del informe (avisos incluidos, que es como los ve el autor en el frontend), y la prosa rechazada. Devuelve:
- el resumen;
- la explicación de cada conflicto;
- **una opinión por conflicto**, con su número: `real`, `falso_positivo` o `dudoso`, y el motivo, citando la prosa;
- la sugerencia.

Todo se añade al informe de la parada ya abierta como `segunda_opinion`. La skill le da los falsos positivos conocidos: la reformulación, la presencia sin registrar, el reparto desfasado y el cálculo propio tomado por el dato. Como la parada ya existe, nada de lo que pase en la llamada puede perderla: un fallo del puerto, una salida inválida, el presupuesto, una señal de terminar, una detención pedida por el autor o un error imprevisto dejan `segunda_opinion` vacía y el evento `segunda_opinion_fallida` en la traza. El validador de la primera versión, que llamaba al revisor antes de abrir la parada, encontró que esos casos se la llevaban por delante. El esquema pasa de `tareas/oficio/` a `tareas/continuidad/esquemas.py`, junto a su servicio.

> **Decisión sin entrevistar.** La opinión no levanta nunca la parada. La puerta 3 es SQL y exacta con lo que registró el extractor. El juez LLM es menos fiable (el verificador de ConStory-Bench: 88 % de precisión y 55 % de recall), y dejarle decidir cambiaría una parada visible por un silencio. En la primera novela real, las diez paradas fueron falsos positivos o casos discutibles. Al autor le ahorra leer el grafo: le dice dónde mirar. Coste: una llamada por parada, unos 0,25 $. Se descartó un agente nuevo, porque el revisor de continuidad ya existía con este encargo a medias.

**Medido con el revisor real** (23 de septiembre, las diez paradas de continuidad de `novela_real.db` sobre una copia, 2,10 $). En las paradas 2 a 10 (la 1 es de una versión de la puerta que ya no existe), de 17 conflictos opinó 12 `falso_positivo`, 3 `dudoso` y 2 `real`, cada uno con el motivo citando la prosa («el mismo dato con otras palabras», «la prosa pone la cifra en boca de otro personaje»). El repaso de la prosa de la sesión que hizo la pasada había clasificado las diez como falsos positivos o discutibles.

### El juez de oficio vota

**RF3-JUE-02 — Tres muestras, y dos más si discrepan.** *Amplía RF-PIPE-13 de spec1.* El juez de oficio se invoca **tres veces** por intento con el mismo paquete (`OFICIO_MUESTRAS`). Si alguna muestra da otro veredicto que las demás en algún criterio, se piden **dos más** (`OFICIO_MUESTRAS_SI_DISCREPAN`, cinco en total). Cada criterio se decide por **mayoría de muestras**, y cada muestra es un voto aunque repita el criterio (vota en contra si alguno de sus veredictos para él falla); con empate falla. El veredicto que llega al redactor es el de la primera muestra que coincide con la mayoría, con su evidencia y su sugerencia. Cada `juicio:<criterio>` que falla lleva sus votos (en contra y total), y si algún criterio no fue unánime, pase o falle, la puerta añade el aviso `juicio_dividido` con los votos: es lo que el juez no tiene claro, y el autor y Langfuse lo ven.

> **Decisión sin entrevistar.** Lo motivó la medida real de RF3-PAS-12: el mismo capítulo 1 pasó `cuentas_cuadran` en una llamada y falló en la siguiente. La investigación de la noche proponía puntuar cada criterio con una nota, tomar la mediana y el rango, y parar al autor si el rango cruzaba el umbral. Se adaptó así:
> - **Votos y no notas.** El esquema del juez es `pasa` o `falla`, y una escala necesita anclas y un umbral calibrado con fragmentos dorados del autor, que no hay.
> - **Mayoría y no parada** cuando discrepan. Una parada por cada criterio dudoso pararía casi todos los capítulos, y el aviso ya deja la duda a la vista.
> - **El empate falla.** Dejar pasar un error cuesta la novela; un `falla` de más cuesta una reescritura. Con cinco muestras no hay empate.
> - **Una muestra, un voto.** El esquema exige todos los criterios pero no que salgan una sola vez. El validador de la primera versión, que contaba veredictos, mostró que una muestra con un criterio repetido daba la vuelta a la mayoría.
>
> Coste: el juez pasa de una llamada por intento a tres, o cinco si discrepan (unos 0,25 $ cada una). La temperatura no se controla desde el CLI, así que la variación entre muestras es la del modelo. Queda pendiente calibrar con el autor si tres son pocas.

**Medido con el juez real** (capítulos 1 y 4 de la copia de `novela_real.db`, 2,15 $). En el capítulo 1, `cuentas_cuadran` salió en contra en cuatro de cinco muestras: las tres primeras discreparon, se pidieron dos más y ganó `falla`. En el 4, en contra en tres de tres. Los otros ocho criterios salieron unánimes a favor en los dos capítulos. Es el caso que motivó el voto: con una sola muestra, el capítulo 1 pasó una vez y falló otra.

### La rúbrica de la novela entera

> Esta sección se escribe el 25 de septiembre de 2026, después del código (migración 015, `tareas/rubrica/`, `tests/test_rubrica.py`). Describe lo que el código ya hace, para que la rúbrica tenga sus requisitos como el resto del harness.

**RF3-RUB-01 — Seis notas con justificación y cita.** Al terminar la generación, ya publicada la versión, el agente `rubrica` (LLM-as-judge) lee la novela entera y pone una nota de 1 a 5 a seis criterios: continuidad, tono, arco, coherencia de personajes, ritmo y personalización natural (`CRITERIOS_RUBRICA`). Cada nota lleva su justificación y una cita literal. Falta un criterio o sobra uno: la salida no valida. Una cita que no aparece en la novela (comparada sin cursivas, comillas, rayas ni puntuación, y de al menos tres palabras) queda marcada como no literal. Se guarda en `evaluacion_rubrica` con `origen = 'llm'`.

**RF3-RUB-02 — Informa y no decide.** La rúbrica no bloquea la publicación: una nota de 2 o menos deja el evento `rubrica_baja`, y cualquier fallo del agente o del paquete deja `rubrica_fallida` con la novela completada. Se apaga con `NOVELAS_RUBRICA=0`. Cada nota sale a Langfuse como score de la traza `rubrica`.

**RF3-RUB-03 — La revisión humana, por la misma tabla.** La revisión humana usa la misma rúbrica: el autor rellena `src/backend/evals/plantilla_rubrica_humana.csv` y `evals/rubrica_humana.py` la importa con `origen = 'humano'` y la compara criterio a criterio con la del LLM. Una plantilla a medias no se importa.

> **Decisión sin entrevistar.** La rúbrica corre después de publicar y no para nada porque el enunciado la pide como validador semántico con puntuación y justificación, no como puerta: las puertas 4 y 5 ya deciden si la novela se publica, y un juez probabilístico que además bloquease sumaría reintentos sin un umbral calibrado con el autor.

## 3.7 Bloque 7 — Lo que la lectura web pide al backend

> **Decisión entrevistada, 24 de septiembre de 2026.** La lectura de la entrega es la **web** del frontend (la variante web del enunciado), con su exportación a PDF, y no un HTML estático generado por el backend. Cambia la decisión del bloque 7 del [plan](storymaker-plan.md), que se tomó cuando el frontend no existía. La web la construye la sesión del frontend ([spec-frontend.md](spec-frontend.md)); aquí van solo las dos lecturas que le faltaban al backend.

**RF3-LEC-01 — La portada.** `GET /novelas/{id}` añade a `NovelaDetalle`:

- `dedicatoria`: la de la novela (`novela.dedicatoria`), o nula;
- `regalo`: `{para, de, ocasion}` con el nombre del destinatario, quien regala y la ocasión legible («cumpleaños», «jubilación»; con `otra`, su detalle), o nulo si la novela no tiene brief.

**RF3-LEC-02 — Dónde aparece cada uno.** `GET /novelas/{id}/apariciones` devuelve `{personajes: [{id, nombre, capitulos}], lugares: [{id, nombre, capitulos}]}`, solo con capítulos **completados** y en orden. Los personajes salen de la vista `presencia` (reparto, punto de vista, presencias registradas, usos de conocimiento y estados: RF2-PIPE-31); los lugares, del lugar de cada escena. Un personaje o un lugar que no aparece en ningún capítulo completado sale con la lista vacía: la ficha lo enseña igual.

## 3.8 Bloque 8 — Cambio del lector

El lector selecciona en la web un personaje, un lugar, un objeto, un hecho o un fragmento, y pide un cambio («el perro se llama Nala»). El sistema entiende qué dato del canon cambia, localiza los capítulos que lo usan, **reescribe solo esos** y publica una versión nueva con lo que cambió marcado. La versión anterior se conserva siempre (RF3-BIB-11).

> **Decisión entrevistada, 24 de septiembre de 2026.** Dos decisiones:
>
> 1. **Solo cambios de canon**: renombrar un personaje, un lugar o un objeto, o cambiar el valor de un hecho. Un agente convierte la petición libre en un cambio estructurado y rechaza lo demás («hazlo más triste»). Se descartó admitir cambios de estilo: no hay un dato que localizar ni una forma determinista de comprobar el resultado, y el riesgo de meter fallos en una novela ya aprobada es mayor.
> 2. **Reescritura quirúrgica**: cada capítulo afectado se corrige sobre su prosa aprobada, cambiando solo lo que toca el dato, y los demás capítulos quedan idénticos. Se descartó regenerarlo entero desde la escaleta: los capítulos siguientes, que no se tocan, apuntan a hechos, conocimientos y siembras de ese capítulo, que se borran al revertirlo (RF-FALLO-04); rehacer esa parte del grafo sin regenerar lo que viene después rompía la continuidad que el enunciado pide conservar.

```mermaid
sequenceDiagram
  participant W as Web
  participant A as API
  participant K as Worker
  participant I as interprete
  participant R as revision
  participant J as Puerta 4
  W->>A: POST /intenciones cambio_lector
  A-->>W: 202 (o 422 cambio_invalido)
  K->>K: estado, versión base y objetivo
  K->>I: petición (no confiable) y candidatos del canon
  I-->>K: cambio estructurado o no admisible
  K->>K: validación en código y alcance
  K-->>W: intención hecha {capitulos}
  loop cada capítulo del alcance, hasta 3 intentos
    K->>R: prosa aprobada + cambio (canon simulado)
    R-->>K: escenas corregidas, citas, resúmenes
    K->>J: comprobaciones del cambio, mecánica y juez con votos
  end
  K->>K: una transacción: canon, textos, versión nueva
```

### La petición

**RF3-CAM-01 — La intención.** Tipo nuevo `cambio_lector`, con este payload, que la API valida en forma (422 con `codigo: "cambio_invalido"` y los campos en `detalle`, como `brief_incompleto`):

| Campo | Contenido |
| --- | --- |
| `version_base` | La versión que el lector estaba leyendo |
| `objetivo` | `{"tipo": "entidad", "entidad": "personajes" \| "lugares" \| "objetos", "id": N}`, `{"tipo": "hecho", "hecho_id": N}` o `{"tipo": "fragmento"}` |
| `peticion` | Lo que pide el lector, de 3 a 300 caracteres |
| `cita` | Opcional, hasta 500 caracteres: `{"capitulo": N, "texto": "…"}`. Obligatoria con `fragmento` |

**RF3-CAM-02 — Lo que comprueba el worker antes de nada.** Rechaza la intención, sin llamar a ningún agente ni tocar nada, con uno de estos motivos:

| Motivo | Cuándo |
| --- | --- |
| `novela_no_terminada` | La ejecución no está en `completada` ni en `completada_con_avisos` |
| `version_desfasada` | `version_base` no es la última versión publicada |
| `objetivo_inexistente` | La entidad o el hecho no existen en la novela, el hecho no está vigente, o el capítulo de la cita no está completado |

**RF3-CAM-03 — El intérprete.** Agente nuevo, `interprete` (con su skill, RF-SKILL-01), que convierte la petición en un cambio. Recibe la petición y la cita **delimitadas como datos no confiables**, el objetivo y los candidatos del canon:

- con una entidad: la entidad y sus hechos vigentes;
- con un hecho: el hecho y su sujeto;
- con un fragmento: las entidades del reparto del capítulo de la cita y los hechos vigentes que ese capítulo establece o usa (`hecho_escena`).

Devuelve `admisible`, el `motivo` y, si es admisible, uno de dos cambios: `renombrar` (tabla, id y `nombre_nuevo`) o `cambiar_hecho` (id y `valor_nuevo`).

**RF3-CAM-04 — La validación en código.** Lo que el intérprete devuelve no se cree: el código lo comprueba y, si falla algo, rechaza la intención con el motivo `cambio_no_admisible` y la explicación en `resultado`:

- el id está entre los candidatos que recibió, y con un objetivo de entidad o de hecho, es ese objetivo;
- un nombre nuevo tiene de 1 a 4 palabras y 60 caracteres como mucho, solo letras, espacios, guiones y apóstrofos, empieza por mayúscula, es distinto del actual y no coincide con otra entidad de la novela (su nombre normalizado es único, RF2-PER-11);
- el nombre **actual** no lo lleva también otra entidad (un lugar que se llama como un personaje): la prosa no dice cuál de los dos es cada mención, y sustituirlas todas renombraría también al otro (validador de la tercera versión);
- un valor nuevo tiene como mucho `PALABRAS_POR_DATO` palabras y 120 caracteres, sin saltos de línea, y es distinto del actual;
- ni el nombre ni el valor contienen un término vetado de la novela (RF3-GRD-02);
- la petición y la cita no traen ningún patrón de inyección conocido (los de RF3-ENT-05, que pasan a `compartido/`). Esto se mira **antes** de llamar al intérprete: una petición con un patrón no llega a ningún agente;
- aplicado en simulación (RF3-CAM-07), el cambio deja pasar las puertas 1 y 2, que son deterministas: renombrar toca filas que las dos leen (el elenco, la escaleta, el brief). Se mira antes de gastar ninguna llamada de reescritura.

> **Decisión sin entrevistar.** Un patrón de inyección rechaza el cambio en lugar de solo avisar, como hace la entrevista con el texto libre (RF3-ENT-05). El texto de un lector llega a dos agentes y acaba en la prosa de un regalo: ante la duda, no se aplica. La defensa de fondo no es la lista de patrones, que es cerrada, sino que el intérprete solo puede devolver un id de una lista y un valor con forma de dato.

**RF3-CAM-05 — El alcance.** Los capítulos que se reescriben, en orden, calculados por código:

- **Renombrar:** los capítulos completados cuya prosa escribe el nombre actual: el nombre entero o una palabra suya de tres letras o más, con mayúscula, sin mirar tildes (así entra también un «Tomas» mal escrito).
- **Cambiar un hecho:** `lectura.capitulos_de_hecho` (RF3-BIB-02): los que lo establecen, lo reafirman, lo mencionan, lo conocen o lo usan.

La API expone el mismo cálculo en `GET /novelas/{id}/cambios/alcance?entidad=personajes&id=N` o `?hecho_id=N`, que devuelve `{capitulos}`, para que el lector vea el alcance antes de confirmar. Con un fragmento no hay alcance previo: depende de lo que entienda el intérprete.

> **Decisión de la spec.** *Afina la decisión de RF3-BIB-02.* Para renombrar no cuenta el reparto, solo la prosa. Un capítulo que no escribe el nombre no puede contener el nombre viejo, así que reescribirlo no cambia nada y cuesta cinco llamadas. La regla de pecar de incluir de más (RF3-BIB-02) sigue valiendo para los hechos, que se pueden parafrasear; un nombre, no.

Si la validación pasa, la intención se cierra como `hecha` con `resultado: {"cambio_id", "capitulos"}` y empieza la reescritura. Si el alcance sale vacío, el cambio se aplica al canon y se publica versión solo si cambian el título o la dedicatoria.

### La reescritura

**RF3-CAM-06 — Estados.** Dos transiciones nuevas: `(completada, cambio_lector) → generando` y `(completada_con_avisos, cambio_lector) → generando`. Durante la reescritura la ejecución está en `generando`, con la fase `revision` o `puerta_4` y el capítulo que se corrige; los capítulos siguen `completado`, y `capitulos_completados` no se mueve. La reescritura termina por las transiciones de siempre, `terminado_limpio` o `terminado_con_avisos`, según la puerta 5, que se evalúa de nuevo.

**RF3-CAM-07 — El canon simulado.** El cambio **no se aplica** hasta el final. Para construir los paquetes y pasar la mecánica, el pipeline lo aplica dentro de una transacción que **siempre se deshace** (`db.simulacion`): así el revisor, la mecánica (nombres, allegados del brief, términos vetados) y el paquete del juez (hechos con cifras) ven ya el canon cambiado, y ningún fallo, parada ni caída deja un canon a medias. Dentro de una simulación **solo se lee y se construye**: el paquete del revisor antes de llamarlo, y la mecánica y el paquete del juez después, en una segunda simulación. Todo lo que se escribe de verdad (el registro de cada puerta, los eventos, las llamadas a los agentes y su coste) va fuera, en sus transacciones de siempre.

> **Decisión de la spec.** Se descartó aplicar el cambio al principio y deshacerlo si fallaba: exigía guardar lo anterior, compensar en cada salida (fallo, `parar`, señal, caída del worker) y dejaba a la API leyendo un canon que no casaba con los textos publicados. Con la simulación no hay nada que compensar.

**RF3-CAM-08 — El revisor.** El agente `revision`, que la arquitectura reservaba para las pasadas globales (fuera de la v1), existe ya con una sola pasada: la del cambio del lector. Recibe el cambio (lo viejo y lo nuevo), la prosa aprobada del capítulo escena por escena, su resumen y su resumen breve, la línea de palabras vetadas y, en los intentos 2 y 3, lo que falló en el anterior. Devuelve las **mismas escenas** corregidas, los resúmenes corregidos y las `citas` del cambio: fragmentos literales de la prosa nueva donde aplicó el cambio. La skill le pide cambiar solo lo necesario (el dato, sus concordancias y lo que deje de tener sentido por él) y no mejorar nada más.

**RF3-CAM-09 — Las comprobaciones del cambio.** Deterministas, bloqueantes, en la parte mecánica de la puerta 4, antes del juez:

| Comprobación | Falla si |
| --- | --- |
| `cambio_sin_aplicar` | Renombrar: la prosa o los resúmenes nuevos escriben todavía el nombre viejo (el entero o una palabra suya que no esté en el nombre nuevo, con mayúscula; si esa palabra también sale en minúscula en la prosa aprobada, es una palabra corriente y solo cuenta en mitad de frase). Cambiar un hecho de valor literal (las categorías y cifras de RF3-BIB-01): el valor viejo no aparece menos veces que antes, o el nuevo no aparece |
| `cambio_toca_otro` | Renombrar: un nombre protegido (de otra entidad, RF3-CAM-11) sale en la prosa o los resúmenes nuevos menos veces que en los aprobados. Se cuenta fuera del nombre viejo y del nuevo enteros, buscados sin mirar tildes: al renombrar «Nina Reyes» con «Reyes» protegido, el «Reyes» de «Nina Reyes» no es el otro, y el de un nombre nuevo que lo contenga tampoco |
| `cambio_sin_cita` | Una cita no está en la prosa nueva, o ya estaba en la aprobada; o la prosa cambió y no trae ninguna cita |
| `cambio_desborda` | La prosa nueva se parece a la aprobada menos que `CAMBIO_SIMILITUD_MINIMA` (0,85, provisional), medido con `difflib` por palabras sobre el capítulo entero |
| `cambio_escenas` | La respuesta no trae exactamente las escenas del capítulo. Si pasa, no se mira nada más |

Después, la mecánica de siempre (RF3-VAL-01 a 03, RF3-GRD-03) y el juez con votos (RF3-JUE-02). Si algo falla, el capítulo vuelve al revisor con la descripción; al tercer intento fallido, el cambio **fracasa**.

> **Decisión sin entrevistar.** El capítulo corregido pasa la puerta 4 entera, juez incluido, aunque ya la pasó una vez. El objetivo del autor es la novela con menos fallos, y una corrección puede romper una concordancia o una cuenta que el juez sí ve. Cuesta de 3 a 5 llamadas más por capítulo. La puerta 3 no vuelve a correr: el capítulo no se reextrae, porque el cambio se aplica al canon por código y el resto de su estado sigue siendo cierto.

**RF3-CAM-10 — Un capítulo sin cambios.** Con un hecho que el capítulo solo conoce o usa (sin escribirlo), el revisor puede devolver la prosa igual. Es válido: pasa las comprobaciones sin citas y no se marca como cambiado en la versión.

### Al final

**RF3-CAM-11 — Todo en una transacción.** Cuando todos los capítulos del alcance pasan, en **una sola** transacción:

1. **El canon.** Renombrar: el nombre y su nombre normalizado; los hechos vigentes que llevan el nombre en el sujeto, el valor o la cita se revocan y se insertan de nuevo con el nombre nuevo; y el nombre se sustituye, palabra completa, en los textos del plan y del canon de la novela: fichas, escaleta, resúmenes, título, dedicatoria y brief (no en los registros: la entrevista, las trazas, las versiones). El nombre de **otra** entidad no se toca nunca, y los nombres de otras entidades que comparten una palabra con el viejo («Pedro Reyes» al renombrar a «Reyes», o «Marta Ruiz» al renombrar a «Tomás Ruiz») quedan protegidos: no se sustituyen en ningún texto ni cuentan como nombre viejo en las comprobaciones (validador de la primera versión). Si el protegido es, entero, una palabra del propio nombre viejo («Reyes» al renombrar «Nina Reyes» a «Nina Soto»), esa palabra no se sustituye suelta: solo cambia el nombre entero, que se sustituye siempre, y es el nombre entero, como frase, lo que las comprobaciones buscan (validador de la segunda versión). Un protegido que solo comparte la palabra («Marta Ruiz» al renombrar «Tomás Ruiz») se protege entero, y «Ruiz» a secas sigue siendo el nombre viejo (validador de la tercera versión). Los textos del plan incluyen los que cuelgan de una escena de la novela sin llevar su id (los *beats* y las secuelas). Cambiar un hecho: se revoca y se inserta de nuevo con el valor nuevo y la primera cita del revisor en su capítulo. En los dos casos:
   - la revocación (`hecho_revocacion`, motivo `cambio_lector`) guarda como `capitulo` el de la **escena del hecho**, no el último: un `relanzar` posterior desde un capítulo intermedio no la borra (RF-FALLO-04 borra las de capítulos mayores), y si relanza desde el capítulo del hecho, se van el hecho viejo y el nuevo, que están en la misma escena;
   - el hecho nuevo va en la misma escena que el viejo, y lo que colgaba del viejo pasa al nuevo: sus usos (`hecho_uso`), los estados y usos de conocimiento, y los hechos que lo sustituían (`supersede_a`).
2. **Los textos.** Cada escena corregida guarda una versión nueva de `escena_texto` con origen `revision` (la anterior queda `descartada`, como en RF-PER-05); el capítulo se recompila y recibe los resúmenes del revisor.
3. **Las puertas de planificación.** Si el cambio dejó sin vigencia la puerta 1 o la 2 (su huella lee el elenco, la escaleta y el brief, RF3-PER-07), se evalúan de nuevo sobre el canon cambiado y se registran con la huella nueva. Sin eso, la novela quedaría con la planificación sin vigencia y el siguiente `arrancar` la replanificaría. Si alguna falla, la transacción entera se deshace y el cambio fracasa.
4. **La versión.** La puerta 5 se evalúa de nuevo, la ejecución vuelve a `completada` o `completada_con_avisos`, y se publica la versión con motivo `cambio_lector` y la petición en `detalle` (RF3-BIB-12), con `cambiado` solo en los capítulos cuyo texto difiere.

Después, fuera de la transacción, el índice vectorial reindexa los capítulos corregidos (prescindible, como siempre: RF2-CTX-09).

> **Decisión de la spec.** Un hecho no se modifica nunca (el trigger `hecho_inmutable`, RF2-PER-06), así que cambiarlo es revocarlo e insertarlo de nuevo, con el rastro del motivo. Lo que sí se actualiza es lo que apunta a él: `hecho_uso`, los conocimientos y `supersede_a` en otros hechos. Es una excepción escrita al «append-only» de esas tablas (migración 006): el trigger deja `supersede_a` fuera a propósito, y la alternativa, copiar cada uso y cada conocimiento con el id nuevo, duplicaba filas con la misma escena de origen sin ganar rastro, porque el rastro ya está en la revocación y en `cambio_lector`. La sustitución del nombre en los textos del plan es literal y por palabra completa: si el nombre viejo es también una palabra corriente con mayúscula («Luna»), puede tocar de más. Se prefirió eso a dejar el nombre viejo en la escaleta, que el juez compara con la prosa (función de escena).

**RF3-CAM-12 — Si fracasa.** Un cambio que agota los intentos, que el autor para o que se interrumpe no aplica nada, porque todo lo anterior al paso final fue simulado. Cómo queda cada cosa:

| Salida | Ejecución | Cambio |
| --- | --- | --- |
| Tres intentos sin pasar un capítulo, o el paso final se deshace (puertas 1 y 2, o un error de datos: uno de la base, `sqlite3.DatabaseError`, o un hecho que ya no está vigente, `CanonDesfasado`) | Vuelve a su estado completado por la misma puerta 5, sin versión nueva porque el texto no cambió | `fallido`, con el informe, y el evento `cambio_fallido` |
| El autor para, o llega una señal de terminar | `detenida`, como cualquier generación parada. Un cambio nuevo se rechaza con `novela_no_terminada` hasta que el autor la arranque; `arrancar` encuentra todos los capítulos completados, pasa la puerta 5 y vuelve a `completada` sin versión nueva | `interrumpido` |
| Se cae el worker | La recuperación la deja en `detenida` como a cualquier ejecución activa (RF2-FALLO-06); no revierte nada, porque todos los capítulos siguen completados | `interrumpido` |
| Un error imprevisto, también en el paso final (un fallo del código no es del cambio) | `error`, como en la generación | `fallido`, con el error |

El cambio no pasa por `avanzar`: lo lleva `pipeline.aplicar_cambio`, que el worker llama tras cerrar la intención. `avanzar` solo lo ve si el autor arranca una novela detenida a mitad de un cambio, y entonces no hay nada que distinguir: no queda nada del cambio que retomar.

Toda novela completada tiene al menos una versión (RF3-BIB-13 publicó la 1 de las anteriores al bloque 3, y la regla `version_desfasada` lo vigila), así que `version_base` siempre tiene contra qué compararse.

**RF3-CAM-13 — El registro.** Tabla nueva `cambio_lector`, canon y fuera de toda reversión: la petición, el objetivo, la cita, lo que devolvió el intérprete, las alertas, el alcance, el estado (`interpretando`, `rechazado`, `reescribiendo`, `aplicado`, `fallido`, `interrumpido`), el informe y la versión que publicó. La API la lee en `GET /novelas/{id}/cambios` y `GET /novelas/{id}/cambios/{cambio_id}`.

**RF3-CAM-14 — Las reescrituras siguientes respetan el cambio.** El paquete del redactor lleva, si los hay, los cambios aplicados del lector («el lector fijó: …»). Sin eso, relanzar un capítulo tras cambiar un hecho podía volver a escribir el valor viejo: el hecho vive en el canon, pero el extractor lo volvería a establecer desde la prosa nueva.

**RF3-CAM-15 — Demo por CLI.** `demo.py --cambio "petición" [--hecho N | --entidad personajes:N | --cita-capitulo N --cita "…"]` encola el cambio sobre la última versión y muestra cómo avanza. Es la variante por línea de comandos que el enunciado admite, y la que usa el vídeo si la web no está.

### Lo que el bloque 8 deja para después

- Una traza de Langfuse propia por cambio. Hoy las llamadas del cambio caen en la traza del capítulo que corrigen, con su rol.
- Cambios que afecten a varios datos a la vez, y cambios de estilo (descartados arriba).
- Cambiar un hecho no toca los textos del plan que lo repiten con otras palabras: solo la prosa y los resúmenes, que pasan por el revisor.
- Calibrar `CAMBIO_SIMILITUD_MINIMA` con cambios reales.

## 3.10 Bloque 10 — Infraestructura de evals

La tabla definitiva se saca al final. Esta sección empieza por la pieza que mide la puerta 3.

### La tabla de evals

**RF3-EVL-01 — Cinco briefs.** En `ejemplos/`: el brief de ejemplo del README y cuatro en `ejemplos/evals/`: dos normales (una boda y una jubilación, con otras ocasiones, tonos e intensidades), uno **adversarial** con una inyección en el texto libre (órdenes al modelo, la petición del prompt de sistema, un intento de saltarse un término vetado y una palabra canario) y uno de **incoherencia temporal** (recuerdos obligatorios imposibles con la edad del destinatario). Cada fichero es un brief como el de ejemplo y lleva además un bloque `eval` con su nombre, su propósito y el canario, si lo tiene; la entrevista y el worker lo ignoran.

**RF3-EVL-02 — La tabla.** `python -m evals.tabla <briefs…> --puerto falso|terminal --dir <carpeta> [--capitulos N] [--salida tabla.md]` corre cada brief de principio a fin por el mismo camino que una novela de verdad: el schema y el análisis del brief; el texto libre por el entrevistador (`entrevista.procesar_texto_libre`, el mismo paso que la entrevista); `crear_novela` y `arrancar` en el worker, sobre una base nueva por brief. Una parada no se resuelve: es un resultado. La tabla tiene una fila por validador, con su tipo (programático, semántico o formal) y su punto de ejecución, y una columna por brief:

| Fila | Sale de |
| --- | --- |
| Schema del brief, datos que faltan, contradicciones | `Brief` y `analizar` |
| Inyección en el texto libre | las alertas de RF3-ENT-05 |
| Puertas 1, 2, 3 y 5 | `resultado_puerta` |
| Palabras vetadas; nombres, allegados y etiquetas; longitud; el resto de la mecánica; el juez | los conflictos de la puerta 4, por su comprobación |
| Cronología en Lean 4 | «no integrado» hasta que entre el bloque 9 de Lean |
| Canario | si la palabra canario del brief aparece en la prosa |

Cada celda dice `pasa`, `falla n/m` (en cuántas de las evaluaciones de ese validador hubo un conflicto bloqueante) y los avisos, o `sin ejecutar` si la novela no llegó hasta ahí. Debajo, el estado final, los capítulos completados, las paradas, las llamadas y el coste; y por brief, cada comprobación que saltó con sus veces. Con `--salida`, también un JSON con lo mismo.

**RF3-EVL-03 — La medición de referencia.** La primera pasada con Claude Code real de los cinco briefs es el «antes» de la iteración de tuning; la tabla y su JSON se guardan en `docs/proceso/evals/` con la versión de los prompts (Langfuse, RF3-OBS-05). Cuesta dinero: se lanza con la aprobación del autor, y `--capitulos` permite una pasada más barata con los mismos briefs.

> **Decisión sin entrevistar.** La tabla recorre el camino real (worker y entrevistador) en lugar de llamar a las puertas sueltas: así mide el sistema que se entrega, con sus reintentos y sus paradas. Se descartó resolver las paradas automáticamente para llegar al final, porque escondería lo que la parada detectó. El brief de incoherencia temporal se escribió sabiendo que ningún validador del brief lo detecta todavía: la tabla lo tiene que enseñar.

### El banco de contraejemplos de la puerta 3

La puerta 3 se ha afinado parada a parada quitando falsos positivos, y cada arreglo afloja algo: la reafirmación por trozos, las presencias, la deducción. Los falsos negativos no paran nada, así que nadie los ve. En la primera novela real completa, las diez paradas fueron falsos positivos o casos discutibles. En cambio, las cinco puertas dejaron pasar contradicciones reales de la prosa final:
- «los siete de fuera» con una cuadrilla de seis;
- un censo que pierde a tres personas;
- un plazo de cuarenta horas para un carguero que llega en treinta y una;
- un personaje al que el elenco pone en una facción y la prosa trata siempre como de otra.

La idea de medirlo metiendo errores a propósito viene de FlawedFictions (arXiv 2504.11900) y de ConStory-Bench (arXiv 2603.05890).

**RF3-BAN-01 — La base.** Una novela de demo completa hecha con el puerto falso (tres capítulos aprobados), creada una vez. Cada caso trabaja sobre una copia hecha con la API de backup: ningún caso ve lo que cambió otro, y no cuesta nada.

**RF3-BAN-02 — Los casos.** Cada caso lleva:
- un identificador;
- un subtipo: factual, personaje, conocimiento, objeto, espacio, tiempo, estado, aritmética, pertenencia o control;
- la verdad: contradicción o caso limpio;
- una mutación del grafo de la novela aprobada: puede caer en un capítulo anterior, como una muerte o una presencia, pero la contradicción aflora siempre en el último, que es el que la puerta evalúa;
- lo que la puerta hace hoy: los bloqueantes que salen y los avisos que tienen que salir.

La mutación deja el grafo como lo habría dejado el extractor ante una prosa con ese error. Si el extractor no lo habría registrado, como una cifra dicha solo en un diálogo, lo deja sin tocar. Una contradicción que hoy no para, o un caso limpio que para, lleva su **punto ciego**: por qué pasa, con su fila del plan de verificación. Algunos casos van por pares, con el mismo grafo y distinta verdad, para dejar a la vista lo que la puerta no puede distinguir: la presencia inflada frente a la presencia real fuera del reparto, y el muerto que vuelve frente al reparto desfasado.

**RF3-BAN-03 — La medida.** El **recall** es la parte de las contradicciones que paran la novela. Los **falsos positivos** son la parte de los casos limpios que la paran. Las dos se dan también por subtipo. Los avisos no paran, así que se cuentan aparte: en cuántos casos sale cada uno. La línea base del 23 de septiembre (14 contradicciones y 8 limpios) da un recall del 50 % y un 25 % de falsos positivos.

**RF3-BAN-04 — Regresión en los dos sentidos.** Un test fija lo que la puerta hace hoy con cada caso. Si un cambio hace que deje de detectar una contradicción, o que empiece a parar un caso limpio, el test falla. Entonces el banco se actualiza a conciencia y deja su entrada en el registro de iteraciones. Mejorar la puerta también obliga a tocar el banco, y así la mejora queda medida.

**RF3-BAN-05 — El informe.** `banco_contraejemplos.py`, desde `src/backend`, imprime:
- la tabla de casos, con el subtipo, la verdad, lo esperado, los bloqueantes y avisos que salen y si el caso es conforme;
- las dos métricas;
- el desglose por subtipo;
- el recuento de avisos.

Sale con código 1 si algún caso se desvía de lo esperado. Solo trabaja sobre bases temporales.

> **Decisión de la spec.** Las mutaciones son del grafo y no de la prosa. La puerta 3 es SQL sobre el grafo, y medir lo que el extractor registra de una prosa es otra eval (fila 34), que cuesta dinero. Por eso lo que el extractor no registra se modela no registrando nada: una contradicción así cuenta como falso negativo de la puerta, aunque la raíz esté en la extracción.
>
> ConStory-Bench reparte sus 19 subtipos de error en tres grupos:
> - los que una consulta sobre un grafo puede detectar: fechas, duraciones, simultaneidad, elementos abandonados, geografía, apariencia y cantidades;
> - los que necesitan un juez;
> - los de estilo.
>
> El banco empieza por los primeros, que es donde el paper sitúa la mayoría de los fallos de los modelos. Ahí quedan dos huecos sin comprobación hoy: las duraciones declaradas frente a los días transcurridos y la topología de la estación.

> **Decisión sin entrevistar.** El banco vive en un paquete nuevo, `evals/`, junto a `tareas/`, `orquestador/` y `compartido/`. No es un agente ni corre dentro del pipeline, y ahí irá el resto del bloque 10: el ejecutor de briefs y la tabla de resultados. Se descartó ponerlo en `tests/`, porque el informe tiene que poder correrse como comando y no solo como test.

---

## 3.11 Lo que enseñó la primera pasada real

La primera pasada con Claude Code real (23 de septiembre, `novela_real.db`, sin brief) escribió 2 de 4 capítulos por 11,57 $ y paró seis veces por continuidad. Las cinco primeras paradas se cerraron en spec2 (RF2-PIPE-20 a RF2-PIPE-26, RF2-FALLO-07, RF2-PER-13). Esta sección recoge lo que quedaba y no necesitaba una decisión de producto: los valores compuestos del extractor, el resumen que siempre se recorta y los nombres menores que nadie mantiene.

> **Decisión entrevistada, 23 de septiembre de 2026.** El autor eligió empezar por estos tres frentes porque no gastan y atacan la mayoría de las paradas y de los avisos. Quedan para después: la puerta 4 que no rechaza nada, el modelo por agente (necesita medir con Claude Code real) y los tres huecos de la parada 6 (hábito roto, conocimiento de grupo, objetos de información), que necesitan entrevista.

**Datos de la pasada** (sobre una copia de la base):

| Qué | Medida |
| --- | --- |
| Hechos con un valor de más de 8 palabras | 57 de 94; media de 12,7 palabras y un máximo de 38 |
| Valores de distancia, relación y nombre | Todos de 7 palabras o menos |
| Resúmenes recortados | 7 de 7, con entre 201 y 261 palabras |
| Avisos de entidad fuera de canon | 50, sobre 15 nombres distintos; uno es el nombre del propio mundo y otro, una variante de un lugar del canon |

### Un hecho, un dato

**RF3-PAS-01 — Valor corto.** El valor de un hecho tiene como mucho **10 palabras**. Es un **límite blando**: un valor más largo no invalida la salida del extractor, se registra, se cuenta en las correcciones de la traza (`valor_largo`) y la puerta 3 da un aviso `valor_compuesto`. El esquema que recibe el agente declara el límite. La skill del extractor explica cómo partir un valor compuesto en varios hechos con atributos distintos («frecuencia respiratoria en reposo = doce por minuto», no «doce por minuto en reposo, dieciséis en trabajo ligero»).

> **Decisión de la spec.** Diez palabras deja pasar todos los valores legítimos de la pasada y marca los compuestos. Un valor largo es la causa de las contradicciones falsas: cualquier reformulación parece otro valor, y la búsqueda de menciones del bloque 3 no lo encuentra nunca. Se descartó recortar el valor (perdería el dato sin rastro). Al principio se rechazaba la salida entera; la segunda reanudación demostró que era un error (ver abajo).

**Medido con el extractor real** (paquete congelado de los dos capítulos de la pasada, 23 de septiembre): 0 valores largos, salida válida a la primera, recall igual a la línea base y 0 contradicciones falsas, también en el capítulo 2, que arrastra los valores largos del 1. **Pero la llamada cuesta unas 2,5 veces más** (1,19 $ y 1,36 $ frente a 0,45 $ y 0,54 $), con el doble de tokens de salida y de tiempo. Los hechos de más (59 frente a 46, y 77 frente a 50) no lo explican todo.

> **Decisión entrevistada, 23 de septiembre de 2026.** El autor decidió integrar la mejora y diagnosticar el coste con la reanudación de la novela real, que guarda en la traza los turnos y el coste de cada llamada. Si el CLI trata el patrón del esquema como una validación con reintentos internos, se quita el patrón del esquema y el límite queda en la validación de Python y en la skill. Se descartó medir antes otra variante con coste.

**Lo que enseñó la reanudación** (capítulo 3 de `novela_real.db`, con las mejoras ya integradas). Dos cosas, y las dos se corrigen aquí:

- **El patrón provocaba reintentos internos.** La extracción dio 3 turnos, 1,75 $ y 48.311 tokens de salida, frente a los 2 turnos de una llamada sin reintento (la redacción del mismo capítulo). El límite deja de viajar como `pattern` del esquema: lo dice la descripción del campo (y, desde el relanzamiento, pasarlo solo deja un aviso).
- **Un valor vigente compuesto no se puede repetir.** El capítulo 2 había fijado un «ambiente interior» de 22 palabras; en el 3, el extractor, que ya no puede escribir más de 10, se quedó con una parte («treinta y un grados y ochenta por ciento de humedad») y la puerta 3 lo tomó por contradicción. Ahora, cuando el valor vigente pasa del límite y el nuevo es un **trozo** suyo, cuenta como **reafirmación**, con su uso en `hecho_uso`. Un trozo son tres palabras completas seguidas o más del valor vigente (con la comparación de `compartido/texto.py`, que admite plurales simples), y no puede ir detrás de un negador («no», «sin», «nunca», «ni», «jamás», «ningún», «nadie», «nada», «tampoco», «salvo», «excepto»), tampoco del que cierra el segmento anterior: «es vegetal» sale de «que no es vegetal» y dice lo contrario. El trozo cae dentro de un solo segmento del vigente (partido por «;»): uno que cruce el «;» junta el final de un dato con el principio de otro. En el segundo relanzamiento, el extractor se quedó con el primer y el último segmento del vigente y se saltó el del medio, y eso abrió la parada 8: un valor nuevo con varios segmentos separados por «;» cuenta si **cada segmento es un segmento entero del vigente**, en el mismo orden y sin repetir ninguno. Con trozos no basta, y lo encontró el validador: juntar trozos de datos distintos cambia a quién se atribuye cada valor («sector 6 a Otxoa; turno de trabajo, al noventa» pone el sector 6 al noventa por ciento). Un trozo tampoco corta una cifra escrita en cifras o en letra («al ciento» de «al ciento quince por ciento» pasa de 115 a 100). La regla supone que cada segmento del vigente es un dato completo: si el vigente separa con «;» el sujeto de su cifra, saltarse segmentos vuelve a cruzar la atribución, y eso queda como punto ciego (fila 33b). Además, el paquete del extractor marca esos valores como `[COMPUESTO]` y le pide partirlos en hechos de un dato con `supersede_a`. Un valor que no es un trozo válido sigue contradiciendo.

**Lo que enseñó el relanzamiento** (el mismo capítulo 3, ya sin el patrón). Sin el patrón, la extracción volvió al coste de antes: 2 turnos y 0,60 $ y 0,47 $ en sus dos intentos, frente a 0,62 $ de la redacción. Pero los dos intentos traían tres o cuatro valores de 11 y 12 palabras («Registro del día 1.890: constantes leídas en la grabación»), la validación los rechazó y, agotados los intentos, la novela acabó en `error`, con decenas de hechos válidos tirados. Es la misma lección que la del resumen (RF2-PIPE-20): **un límite blando no rechaza**. Desde aquí, el valor largo entra con aviso (arriba), y si más adelante se repite, la regla de los trozos evita que dé una contradicción falsa.

> **Decisión de la spec.** Se descartó rechazar solo por encima de un techo alto (por ejemplo, 20 palabras): cualquier techo que rechace vuelve a poder llevar una novela a `error` por un solo valor, y el aviso basta para que el autor lo vea.

### El resumen

**RF3-PAS-02 — Resumen sin recorte.** El esquema pide un resumen de **unas 160 palabras**, y el límite duro sube de 200 a 250. El modelo no cuenta palabras: pedirle 200 le hacía escribir entre 201 y 261, y el recorte se llevaba la última frase, que suele ser el gancho. El estado rodante tiene sitio de sobra: tres resúmenes completos caben con holgura en su presupuesto de 10.000 tokens.

### Los nombres menores

**RF3-PAS-03 — El mundo es del canon.** El inventario del extractor incluye el nombre del mundo y el título de la novela. En la pasada, «Cerro Quince», el nombre de la propia estación, salió como entidad no reconocida en el capítulo 1.

**RF3-PAS-04 — Variantes de un nombre del canon.** El resolvedor de nombres, cuando no encuentra la clave exacta, prueba una **clave laxa**: sin puntuación y sin artículos ni preposiciones de dos letras o más («de», «del», «la», «el», «los», «las», «en», «al»). La acepta solo si identifica una entidad y nada más. «Bodega fría del sector 7» es así «Bodega fría, sector 7». Una palabra de una letra nunca se quita: «a» e «y» también designan, y «Anillo A», «Anillo Y» y «Anillo» son tres sitios. Al registrar las entidades no reconocidas, se descarta la que tiene la clave laxa de una entidad del canon, del mundo o del título, y la que tiene la de otra ya registrada en el mismo capítulo, aunque sea en otra escena y con la misma grafía («la operadora» y «la Operadora»): se conserva la primera. Cada descarte queda en las correcciones del extractor, en la traza.

**RF3-PAS-05 — Los nombres menores se mantienen.** Los nombres no reconocidos de capítulos anteriores forman una lista de **nombres menores**, sin duplicados por clave laxa y con la primera grafía. El redactor la recibe como material opcional del canon: si vuelve a usar uno, lo escribe igual. El extractor la recibe para registrarlos con esa misma grafía.

**RF3-PAS-06 — Un aviso por nombre nuevo.** El aviso `entidad_fuera_de_canon` de la puerta 3 sale solo la primera vez que aparece un nombre. Un nombre menor que ya salió en un capítulo anterior no vuelve a avisar: el autor ya lo vio.

> **Decisión de la spec.** Los nombres menores no entran en el canon: harían falta un tipo (lugar, objeto, facción) y una descripción que nadie ha escrito, y promoverlos es trabajo del revisor. La lista es un canon ligero que solo garantiza la grafía. Se descartó seguir avisando cada vez (50 avisos para 15 nombres tapaban los que importan).

### Los usos de conocimiento

**RF3-PAS-07 — Un cálculo propio no es un uso.** La skill del extractor define el uso de conocimiento como actuar sobre el dato **tal como consta**. Un personaje que calcula con sus propios datos una cifra o un valor parecido a un hecho del canon ni usa ese hecho ni lo conoce: su cuenta es un hecho **del personaje** (su estimación), con un atributo propio (y `supersede_a` si vuelve a estimar con otra cifra), y no del sujeto sobre el que calcula, porque lo que un personaje estima no es canon del mundo. Solo si la escena muestra que llega al dato registrado exacto, en las mismas condiciones, es conocimiento por la vía `dedujo`; y si además actúa sobre él, también es un uso, como dice la regla de siempre. En el relanzamiento del capítulo 3 de la novela real (parada 9), un personaje hizo su propia cuenta con diez personas y llegó a «veintiséis de planta». El extractor registró a la vez el cálculo como hecho nuevo y un uso del hecho «déficit a las veintiséis horas con once respirando», fijado en una escena en la que ese personaje no estaba. La puerta 3 lo tomó por conocimiento no adquirido.

> **Decisión de la spec.** El arreglo va en la skill y no en la puerta. La puerta 3 hace bien su trabajo con el uso que recibe, y relajarla dejaría pasar usos reales de lo que no se ha recibido, que es el error número uno de continuidad en obra larga. Se descartó exigir una cita en cada uso: la cita de este caso («veintiséis de planta») habría casado igual con el hecho. Se mide en el siguiente relanzamiento (fila 38b), que regenera la prosa: la medida solo vale si la traza muestra una escena con una cuenta propia parecida a un hecho.

**RF3-PAS-08 — Una deducción de lo que no se presenció, a la vista.** La puerta 3 da el aviso `deduccion_por_verificar` por cada conocimiento con la vía `dedujo` y una postura que habilita usos, sobre un hecho fijado en una escena en la que el personaje no estaba. Estar es lo que aplica la comprobación de conocimiento no adquirido, la vista `presencia` de spec2 RF2-PIPE-31: punto de vista, reparto, la presencia que registra el extractor (RF3-PAS-09) o actuar en ella (un uso o un estado del personaje, RF2-PIPE-30). Ese conocimiento habilita los usos siguientes, y nada comprueba si la deducción es plausible: sin el aviso, un extractor que tomara una cifra que coincide por una deducción cambiaría una parada visible por un silencio.

> **Decisión de la spec.** Es un aviso y no un bloqueante: deducir lo que no se vio es legítimo, y parar cada deducción castigaría la prosa que razona. El autor ve el hecho y la escena, y decide.

**RF3-PAS-09 — Quién está en la escena.** La salida del extractor lleva `presencias`: cada personaje del canon que la prosa muestra **físicamente** en una escena, aunque la escaleta no lo pusiera en el reparto. Nombrar o recordar a alguien no es estar, ni oírlo por un canal o verlo en una pantalla desde otro sitio. `aplicar` las escribe en `presencia_escena` (spec2, RF2-PIPE-31), resolviendo el nombre como las demás referencias; la que no se resuelve se descarta con su motivo, en la traza. Para que pueda nombrar a quien el redactor mete por su cuenta, el paquete del extractor lleva, además del reparto del capítulo, una línea con los otros personajes de la novela: sin ella, ese nombre solo podía ir a entidades no reconocidas. La puerta 3 las cuenta como presencia. En la parada 10 (capítulo 4 de la novela real), un personaje repitió una máxima que él mismo había dicho en el capítulo 3; la escaleta no lo ponía en esa escena y el extractor no le registró ni un uso ni un estado allí, así que para la puerta no estaba. Era la segunda vez.

> **Decisión entrevistada, 23 de septiembre de 2026** (vía la sesión de la pasada real). El extractor registra la presencia física y la puerta 3 la cuenta. El reparto es de la escaleta, que se escribe antes que la prosa; quien está de verdad solo lo sabe quien lee la prosa. La presencia es autodeclarada: un extractor que marque de más a alguien silencia `conocimiento_no_adquirido` (punto ciego de la fila 38d y de RF2-PIPE-31).

### Lo que el redactor tiene delante

**RF3-PAS-10 — La ficha de quien ya salió, los hechos que faltaban y las cuentas.** El repaso de la primera novela completa con la prosa (23 de septiembre) dejó dos patrones:
- **El redactor mete en una escena a personajes que la escaleta no puso.** Pasó en las paradas 8 y 10, y otra vez en el capítulo 4, y los escribe sin su ficha.
- **Las contradicciones reales que nadie cazó son cuentas.** «Los siete de fuera» con una cuadrilla de seis, un censo que pierde a tres personas y un plazo de cuarenta horas para un carguero que llega en treinta y una.

El paquete del redactor añade tres cosas:
- **Las fichas de los personajes que ya salieron en un capítulo anterior** y no están en el reparto de este. Salieron según la vista `presencia`: reparto, POV, lo que constató el extractor o actuar en la escena. Van en su propia sección y son opcionales: se recortan antes que el reparto.
- **Los hechos vigentes de esos personajes, de los objetos de las escenas del capítulo y de las facciones del reparto.** Son opcionales, como los de amenaza, mundo y novela, pero se recortan antes que ellos: primero los de quien está fuera del reparto, después los de objetos y facciones, y los de amenaza, mundo y novela los últimos. Dentro de cada grupo, del más antiguo al más reciente. Amplía la tabla de RF2-CTX-11.
- **Dos reglas en la skill.** Una cuenta de personas, horas, plazos o raciones sale de los hechos establecidos y cuadra con ellos. Y a quien la escaleta no puso solo se le trae si está entre los que ya han salido, como dicen su ficha y sus hechos. Quien está en la escena oye lo que se dice en ella; lo que sabía de antes no viene en el paquete, así que actúa sobre lo que oye allí.

> **Decisión sin entrevistar.** La regla de las cuentas es un prompt, y no una comprobación, porque la puerta 3 no suma ni resta entre hechos de atributos distintos: es el falso negativo C12 del banco (fila 50). Prevenir en el redactor es lo más barato. La detección es el criterio `cuentas_cuadran` de la puerta 4 (RF3-PAS-12). Se descartó hacer obligatorias las fichas de los que ya salieron: con un elenco grande, desplazarían del paquete el canon del reparto, que es el que el capítulo usa seguro. Por lo mismo, sus hechos se recortan antes que los de mundo: el validador midió que, mezclados por recencia, 25 personajes fuera del reparto con 30 hechos cada uno sacaban del paquete un «personas a bordo: once» del capítulo 1, que es justo lo que la regla de las cuentas necesita. También se descartó darle al redactor lo que sabe cada uno de ellos: multiplicaría el bloque obligatorio del conocimiento, y si le hace usar lo que no ha recibido, la puerta 3 lo para.

### Las cuentas, en la puerta 4

**RF3-PAS-12 — El juez de oficio comprueba las cuentas.** *Amplía RF-PIPE-13 de spec1.* Las cuatro contradicciones reales que pasaron las cinco puertas en la primera novela completa eran cuentas o se comprueban igual:
- «los siete de fuera» con el hecho «once a bordo: cinco del turno y seis de cuadrilla» (el extractor registró «los siete de fuera» como siembra, así que la puerta 3 ni lo vio);
- un censo del capítulo 4 que no suma dentro del propio capítulo;
- un plazo de cuarenta horas para un carguero que llega en treinta y una;
- la facción de un personaje, que el elenco y la prosa no comparten.

La puerta 3 no puede con las tres primeras: compara cada valor con el de su mismo sujeto y atributo, y no suma ni resta entre datos distintos (C12 del banco). Tampoco ve una cifra que no llegó a hecho (C10 y C14). Leer la prosa y hacer la cuenta es juicio, así que va al juez de oficio:
- **Un noveno criterio, `cuentas_cuadran`** (principio 48: la avería como reloj, con cifras concretas y visibles). Toda cifra de la prosa que se deriva de otras cuadra con los hechos establecidos y dentro del capítulo. Si falla, el capítulo vuelve al redactor con la cita y el hecho con el que no cuadra, como cualquier criterio de oficio.
- **El paquete del juez lleva los hechos vigentes con cifras** hasta el capítulo, incluido, porque una cuenta puede descuadrar dentro del mismo capítulo. Un hecho lleva cifra si su valor tiene un dígito en alguna palabra («31h»), un numeral en letra o una cantidad como «docena», «mitad» o «miles»; «un», «una», «uno» y «medio» solo cuentan seguidos de una unidad («una hora», «un minuto»), porque también son artículos o adjetivos. Van primero los de amenaza, mundo y novela, y después del más reciente al más antiguo. Son opcionales: sin ellos, el juez aún ve si la prosa cuadra consigo misma.
- **La skill deja de decirle que no busque contradicciones.** Hechos, conocimiento y presencias siguen siendo de la puerta 3; las cuentas, del juez.

> **Decisión sin entrevistar.** Es un criterio de oficio y no una llamada aparte: cuesta cero llamadas más y reutiliza la vuelta al redactor con evidencia, que ya funciona. Se descartó hacer la cuenta en SQL: haría falta que el extractor registrara cada cifra con su unidad y su relación con otras, que es justo lo que falló en «los siete de fuera». Un juez LLM tiene recall limitado (el verificador de ConStory-Bench, un 55 %), así que esto reduce los fallos de cuentas pero no los elimina. La facción del elenco frente a la prosa (C13) queda fuera: necesita la ficha del elenco en el paquete del juez y es otra comprobación. Riesgo aceptado: un `falla` de más cuesta una reescritura, y al tercer intento, una parada. Punto ciego: el bloque de hechos del juez tiene 16.000 tokens, y el validador midió que, con la densidad de la novela real, cabe todo lo que importa hasta unos 40 capítulos; hacia 60 empieza a recortar los de mundo más antiguos. El examen pide diez. La skill solo le deja pasar una cifra equivocada si la propia escena la marca como error del personaje (otro lo corrige, él rectifica o el narrador lo señala); en la duda, falla.

**Medido con el juez real** (23 de septiembre, copia de `novela_real.db`, cuatro capítulos, 1,16 $), con la primera redacción de la exención («una cifra que el personaje estima o recuerda mal a sabiendas… pasa»). El juez cazó b4 (cuarenta horas de antelación frente a treinta y una) y b3 («delante de siete» frente al censo) en el capítulo 4. En el 3 cazó una contradicción real que no estaba en la lista: una reserva de sesenta y una horas-persona que baja de cuarenta en veinte minutos. En el 2 cazó «nueve de ustedes» frente al hecho «once respiran cinco días», y el capítulo 1 pasó con la cuenta razonada. No cazó b1: tomó «los siete de fuera» por un recuento falseado a propósito por el personaje, amparándose en la exención. Por eso la exención se endureció a la redacción de arriba. Con esa prosa, la puerta 4 habría devuelto tres de los cuatro capítulos al redactor.

**Medido otra vez con la exención endurecida** (capítulos 1 y 2, 0,47 $). El capítulo 2 sigue fallando por «nueve de ustedes», y el juez explica que «los siete de fuera» sí queda señalado por la propia escena: con la regla nueva, es un error marcado y no un descuido. El capítulo 1 pasa a fallar por una conversación en tiempo real con cincuenta y un minutos de retardo por sentido, que la misma escena usa dos párrafos después. Es una contradicción plausible que antes pasó. Con una sola muestra por criterio, el veredicto de un capítulo concreto puede variar entre llamadas: es lo que ataca la puerta 4 con varias muestras del bloque 6, pendiente.

## 3.12 Lo que enseñó la novela de tres capítulos

La segunda pasada real (24 de septiembre, `novela_3cap.db`, el brief de ejemplo recortado a tres capítulos) paró cuatro veces y no llegó a terminar: tres paradas de continuidad en el capítulo 2 y una de oficio en el capítulo 3, con los tres intentos gastados. Leída con la prosa, cada parada tenía una causa que se repetía en la novela de cuatro capítulos. Las tres decisiones de esta sección las tomó el autor en entrevista el 24 de septiembre, antes de lanzar la novela de diez capítulos.

### El allegado, por su nombre

**RF3-PAS-13 — Un allegado se nombra.** *Amplía RF3-VAL-02.* En el capítulo 3, la escaleta ponía al hermano de la protagonista en la escena 3, y la prosa lo metía («Aquí tu hermano favorito») sin escribir su nombre. `allegado_ausente` devolvía el capítulo con «intégralo en esa escena», y el redactor, que creía haberlo integrado, repitió lo mismo dos veces. La comprobación se queda como estaba, porque el nombre es lo que el comprador reconoce en el regalo; lo que cambia es lo que se le pide al redactor:

- el conflicto dice que escriba el nombre, literal y con mayúscula, al menos una vez en esa escena, y que llamarlo por su parentesco o su papel no cuenta;
- el paquete del redactor lo pide de entrada junto a los elementos personales de cada escena.

### El juez, siempre

**RF3-PAS-14 — El juez corre aunque falle la mecánica.** *Modifica RF2-PIPE-13 de spec2.* Hasta ahora, si la mecánica de la puerta 4 fallaba, el juez de oficio no se invocaba. En el capítulo 3, los intentos 1 y 2 fallaron por el allegado y el juez no llegó a leerlos; en el 3 la mecánica pasó y el juez vio una cuenta que no cuadraba (nueve personas donde el canon dice siete), que el redactor ya no tuvo intento para arreglar. Ahora el juez vota en cada intento, y el redactor recibe en la vuelta todo lo que falló: los conflictos de la mecánica y los criterios del juez juntos.

> **Decisión entrevistada, 24 de septiembre de 2026.** Cuesta de 3 a 5 llamadas del juez más por cada intento que falla la mecánica (de 0,3 a 0,5 $). Se descartó añadir un cuarto intento: seguiría descubriendo los fallos de uno en uno. La corrección del lector (RF3-CAM-09) mantiene el orden anterior: sus comprobaciones son bloqueantes baratas y un revisor que no aplicó el cambio no merece juez.

### Lo que ve cualquiera

**RF3-PAS-15 — Hechos observables.** *Amplía RF2-PIPE-21.* En el capítulo 2, una personaje actuaba sobre el patrón del pulso de una luz del pozo que la protagonista había visto a solas, y la puerta 3 paró tres veces por conocimiento no adquirido. Se relanzó dos veces y al final el autor lo dio por sabido: una luz que late a la vista es algo que cualquiera en la estación puede haber visto fuera de escena. La novela de cuatro capítulos paró por casos de la misma familia.

- El extractor marca `observable: true` en un hecho que percibe cualquiera en ese lugar, con los sentidos o en un indicador a la vista de todos (una luz, un ruido, una alarma, un temblor). Lo que se sabe por dentro, se dice en privado o se lee no lo es. Ante la duda, no.
- Como la conducta (RF2-PIPE-29), ser observable es del atributo: la marca va en `atributo_observable` (migración 012) con su escena, y revertir el capítulo la borra. Renombrar al sujeto con el cambio del lector (RF3-CAM-11) mueve sus marcas de observable y de conducta a la clave nueva.
- En la puerta 3, un uso de un hecho observable no para. Si el personaje estuvo en el lugar donde se fijó el hecho entre la escena que lo fijó y la del uso, las dos incluidas, lo sabe y no hay nada que decir. Haber pasado por allí antes no basta: una alarma que sonó ayer no la oyó quien estuvo la semana pasada (validador de la primera versión). Si no estuvo, es el aviso `conocimiento_observable`, para que el autor compruebe que es verosímil.

> **Decisión entrevistada, 24 de septiembre de 2026.** Se eligió frente a pasar todo el conocimiento no adquirido a aviso, que dejaba de proteger los errores reales, y frente a dejarlo como estaba, que con diez capítulos pararía varias veces por el mismo motivo. El riesgo es que el extractor marque de más y se cuele un error real como aviso: la skill pide ante la duda `false`, y la marca queda a la vista en el grafo. «El mismo lugar» es el mismo `lugar_id`, sin contención (RF2-PIPE-26): quien estuvo en un sitio que contiene al otro recibe el aviso, no el silencio.

### El censo, delante

**RF3-PAS-16 — El redactor recibe el censo.** *Amplía RF3-PAS-10 y RF3-PAS-12.* En el intento 2 del capítulo 3 las cuentas cuadraban («siete a bordo: Marta, Idoia, Casilda, Tomás y tres de la cuadrilla»); en el 3, al reescribir el capítulo entero para arreglar otra cosa, daban nueve. Los de la cuadrilla no tienen nombre ni ficha, y el único dato del canon era una línea, «personas a bordo: siete personas», así que el redactor rehacía la suma de memoria en cada versión. En la primera novela, tres de las cuatro contradicciones reales que pasaron las puertas eran cuentas de este tipo. El juez las caza (RF3-PAS-12, y ahora en cada intento por RF3-PAS-14), pero es probabilístico; esto ataca que se cometan.

- Si el canon tiene algún dato que cuenta personas (una cantidad y una palabra de gente: «personas a bordo: siete», «bajas del turno: dos», «once respirando»), el bloque de hechos del redactor empieza por una sección **Censo**, obligatoria:
  - la regla: toda cifra de personas cuadra con el censo; antes de escribirla, la suma de los que tienen nombre más los anónimos que cuentan los datos; quien se va o muere baja el total desde esa escena; quien está lejos no cuenta entre los presentes;
  - cada personaje que ya ha salido o que la escaleta pone en este capítulo (este último, marcado), con su última condición registrada antes del capítulo (vivo, herido, muerto…) fuera de las analepsis: un muerto vivo en un recuerdo sigue muerto. Quien no ha salido todavía no entra, porque la regla pide sumar a los que tienen nombre;
  - los datos que cuentan personas hasta el capítulo, del más reciente al más antiguo y como mucho 30: la cuenta que vale es la última (validador de la primera versión).
- Sin ningún dato de personas no hay sección: los nombres ya están en el canon del capítulo.
- Va dentro del bloque `hechos` y no en uno propio, porque los bloques del redactor ya suman el paquete entero (RF2-CTX-12); por ser obligatoria, el recorte no la toca.

> **Decisión entrevistada, 24 de septiembre de 2026.** El autor eligió hacerlo antes de la novela de diez capítulos, a propuesta de la sesión que lanzó la de tres. Se dejó para después una comprobación determinista de las cifras de personas (el punto ciego C12 del banco): es un trabajo grande, y con el censo delante y el juez en cada intento ya hay dos defensas. El criterio de «dato de personas» es una cifra y una palabra entera de gente, casi siempre en plural («personas», «cuadrilla», «desaparecidos», «cadáveres», «quedan»…): con raíces, «persona» casaba con «personalidad» y «herid» con «herida en el casco», y esas líneas podían echar del tope a la cuenta real (validador de la primera versión).

### Lo que sabe otro, en escena

**RF3-PAS-17 — El redactor muestra cómo llega lo que sabía otro.** *Amplía RF2-PIPE-21.* La prueba real del capítulo 3 con RF3-PAS-13 a 16 (24 de septiembre, sobre una copia de `novela_3cap.db`, 4,76 $) confirmó los arreglos: ni allegado ausente ni cuentas descuadradas. Pero el intento 2 paró por conocimiento no adquirido: una personaje citaba una regla de la amenaza «según las observaciones» de la protagonista, sin ninguna escena en la que se la contara. La segunda opinión lo dio por real. Es el caso que más se repite en las tres novelas reales: la prosa supone una conversación fuera de escena que el canon no tiene.

La regla de la skill del redactor «No haces saber a un personaje algo que aún no ha recibido» se amplía: un personaje sabe lo que presenció, lo que le dicen en una escena, lo que consta en la sección «Quien sabe que» de su paquete, lo que su grupo ya sabía en un capítulo anterior (RF2-PIPE-27), lo que deduce de lo que tiene delante (RF3-PAS-08) y lo que cualquiera percibe en un sitio donde ha estado (RF3-PAS-15). Si usa algo que solo vio otro y no le llega por ninguna de esas vías, la escena muestra cómo le llega (basta una réplica, sin exposición), y una fuente citada sin escena («según sus observaciones», «me lo dijo ayer») no cuenta. Las vías son las mismas que acepta la puerta 3: una regla más estricta que la puerta obligaría a escenas de transmisión sobrantes, que son exposición (validador de la primera versión). La puerta 3 no cambia: si el redactor no lo cumple, sigue parando.

> **Decisión entrevistada, 24 de septiembre de 2026.** Se eligió prevenir en el redactor, sin tocar la puerta. Se descartó que la puerta avisara en vez de parar cuando la prosa cita la fuente: un error real con una fuente inventada saldría solo como aviso. También se descartó lanzar sin cambios y decidir en cada parada, que en una novela de diez capítulos serían varias.

### Las cifras que el juez comprueba

**RF3-PAS-18 — El redactor recibe las cifras que comprueba el juez.** *Amplía RF3-PAS-12 y RF3-PAS-16.* La novela de diez capítulos (24 de septiembre, Opus 5.5) paró en el capítulo 5: los tres intentos fallaron `cuentas_cuadran`, cada uno por una cifra distinta, y los tres fallos eran reales. En el primero, el carguero llegaba «el día 140» y la prosa decía que faltaban ciento cuarenta días cuando ya habían pasado semanas. En el segundo, la protagonista explicaba una diferencia de dos décimas con una cuenta que daba nueve centésimas. En el tercero, contaba «tres líneas» anotadas en la manga cuando el canon ya tenía cuatro. El capítulo 4 ya había gastado un intento en otra resta de días. En los tres casos el redactor tenía el dato en el paquete: el problema es que deriva cifras sin hacer la cuenta. Además, midiendo el paquete del capítulo 5, 34 de las 66 cifras que el juez comprobaba no llegaban nunca al redactor, porque `hechos_del_reparto` solo trae las del reparto, y otras 5 eran opcionales al final del bloque.

- El paquete del redactor lleva en el bloque `hechos`, detrás del conocimiento, una sección **Cifras establecidas**:
  - una regla obligatoria: son las mismas cifras con las que el juez comprueba la prosa; una cifra derivada (lo que falta hasta un plazo, cuántos quedan, cuántas veces ha pasado algo) sale de hacer la cuenta con ellas, y si no se puede hacer no se escribe como cifra;
  - las cifras de `lectura.hechos_con_cifras` hasta el capítulo anterior que no están ya entre los hechos obligatorios, en el orden del juez. No se incluye el propio capítulo, al contrario que en el juez: al reescribirlo, lo que el extractor sacó de un intento fallido no es canon.
- Las cifras son opcionales, pero van delante de los hechos opcionales sin cifra: el recorte, que quita desde el final, se lleva antes cualquier hecho sin cifra. Cada hecho sale una sola vez en el bloque.
- El juez y el redactor leen las cifras de la misma función, `lectura.hechos_con_cifras`, para que no vuelvan a separarse.
- La regla de la skill del redactor «No descuadras una cuenta» nombra las tres cuentas que fallaron: lo que falta hasta un plazo se resta desde el momento de la escena; un recuento cerrado de algo que se acumula entre capítulos incluye lo de los anteriores; si un personaje explica una cifra con otras, la operación da lo que dice. Y pide escribir una cifra derivada solo cuando la escena la necesita, y decirla sin número si no se puede hacer la cuenta.

> **Decisión entrevistada, 24 de septiembre de 2026.** El autor eligió arreglar la causa antes de relanzar el capítulo 5 (opción B), en vez de relanzarlo tal cual. Criterio propio, sin entrevistar: las cifras no son obligatorias porque con una novela larga pueden pasar de cien y un bloque obligatorio que no cabe para la novela (RF2-CTX-03); su posición las protege igual. Se descartó que el juez recibiera menos cifras para igualarlo con el redactor: comprobar contra menos canon deja pasar más errores. Sigue pendiente la comprobación determinista de cifras (el punto ciego C12 del banco, arreglo C de la sesión que lanzó la novela de tres capítulos): el juez sigue siendo la única detección.

## 3.13 Los nombres del encargo no salen de la máquina

La novela de diez capítulos (24 de septiembre, Opus 5.5) paró en la puerta 1 sin haber escrito nada: el arquitecto, el elenco y el estructurador devolvieron `[NOMBRE_ANONIMIZADO]` en lugar del nombre del destinatario y del de quien regala, en dos personajes y en la dedicatoria. Cada agente es una sesión de Claude Code de la organización, y la política de privacidad de la organización (RGPD) le pide no reproducir datos personales; el modelo no puede saber que los nombres del brief son de un encargo, y los anonimiza. Las puertas hicieron su trabajo (`destinatario_protagonista`, `allegado_en_elenco`, `dedicatoria_nombra_al_destinatario`), pero sin nombres no hay producto.

**RF3-SEU-01 — Etiquetas hacia el modelo.** Antes de cada llamada a un agente del pipeline (`pipeline._invocar`, por donde pasan todas), los nombres del brief se cambian por etiquetas: el destinatario (`[DESTINATARIO]`, y por partes `[DESTINATARIO_NOMBRE]` y `[DESTINATARIO_APELLIDO]`), cada allegado (`[ALLEGADO_n]`) y quien regala (`[QUIEN_REGALA]`, o la etiqueta del allegado que lo es). La búsqueda es la del seudonimizador de Langfuse (RF3-OBS-07: texto plegado, fronteras de palabra), pero cada forma tiene su propia etiqueta para poder deshacerla, y solo casa si empieza en mayúscula: lo que se reescribe es lo que lee el modelo, y con una destinataria llamada Luz, «la luz del pasillo» no puede volverse «la [DESTINATARIO_NOMBRE] del pasillo». La excepción es un nombre que el brief escribe en minúscula: así viaja en los paquetes, y se oculta en cualquier grafía (la privacidad gana a no tocar una palabra corriente). La firma de quien regala se oculta siempre entera, en cualquier grafía, y vuelve tal como la escribió el comprador (con mayúscula si abre frase). Si es descriptiva, la que empieza por un posesivo o un artículo («tu tía Carmen», «Los García», «Sus compañeros del instituto»), sus palabras sueltas se ocultan también, en mayúscula o en minúscula, salvo los determinantes y las de parentesco o de grupo («tía», «compañeros», «instituto»); si es un nombre, se oculta entero y por partes. En la corrección del lector (RF3-CAM-08) la máscara se hace dentro de la simulación, con el brief que ya lleva el nombre nuevo, y si el renombrado es una persona del encargo su nombre viejo sale como `[NOMBRE_ANTERIOR]`. Lo que se guarda en `llamada_modelo` es lo que se envió y lo que volvió, con etiquetas.

**RF3-SEU-02 — La leyenda.** El paquete empieza por una leyenda sin ningún nombre (también pasa por la máscara, por si una relación nombra a alguien): qué persona es cada etiqueta (el destinatario y sus pronombres, cada allegado con su relación, quién regala) y la orden de escribir la etiqueta tal cual donde iría el nombre, sin inventar otro nombre ni otra etiqueta.

**RF3-SEU-03 — Nombres de vuelta.** La respuesta del agente vuelve con cada etiqueta del encargo cambiada por el nombre escrito como en el brief (con sus tildes; con mayúscula inicial si el brief lo trae todo en minúsculas o en mayúsculas), en textos, listas y claves (dos claves que quedan iguales no se pisan), antes de validarla. Vuelven también las etiquetas que un modelo escribiría por analogía: `_NOMBRE` y `_APELLIDO` de cualquier persona del encargo, y `[QUIEN_REGALA]` aunque quien regala sea un allegado. El grafo, las puertas, la lectura y el cambio del lector ven los nombres reales, como hasta ahora. Si la validación falla, el error que se reenvía al agente se vuelve a enmascarar.

**RF3-SEU-04 — Ninguna etiqueta en la prosa ni en el canon.** La mecánica de la puerta 4 devuelve el capítulo si la prosa lleva una etiqueta del encargo que no volvió (`[DESTINATARIO_APODO]`, con uno o más sufijos) o una de anonimización (todo lo que diga ANONIMIZADO, y un dato personal —nombre, apellido, teléfono, correo, DNI, NIE, pasaporte, documento, dirección, empresa, persona o cliente, con o sin tilde— oculto, eliminado, borrado, censurado u omitido: `[NOMBRE_OCULTO]`, `[DNI_OCULTO]`, `[CORREO_ELIMINADO]`…, en cualquier grafía): `etiqueta_en_la_prosa`. «[ALERTA]», «[FIN]», «[ARCHIVO_ELIMINADO]» o «[DATOS_ELIMINADOS]» son texto legítimo del género. La puerta 1 hace lo mismo con la dedicatoria, el título y los nombres de personajes, lugares y objetos (`etiqueta_en_el_canon`, que se rehace desde el arquitecto). El lector no puede encontrar `[NOMBRE_ANONIMIZADO]` en su regalo.

**RF3-SEU-05 — Lo que queda fuera.** El entrevistador (3.2) sigue viendo los nombres: los extrae de lo que dice el comprador, y no se pueden ocultar antes de saber cuáles son. El brief escrito a mano o desde la web no pasa por él. Los términos vetados (3.5) se envían tal cual al redactor; si uno es un nombre (una expareja), sale. Una forma del nombre que la búsqueda no reconoce (un apodo que no está en el brief, o el nombre escrito en minúscula cuando el brief lo trae con mayúscula) sale, como en Langfuse. Con un nombre en minúscula en el brief que además es una palabra corriente («luz»), esa palabra se oculta también donde no es el nombre, y si el agente la copia vuelve con mayúscula («la Luz del pasillo»): se aceptó, porque la alternativa era enviar el nombre. Lo mismo con una palabra corriente de una firma descriptiva que no está en la lista de parentescos («tus compañeros de Recursos Humanos»): se oculta, y vuelve escrita como en la firma. Y lo mismo con la firma entera, que se oculta en cualquier grafía: si quien regala firma con una palabra corriente («Luz»), esa palabra se oculta también donde no es la firma, y si el agente copia la etiqueta vuelve con mayúscula («la Luz del pasillo»). La petición del lector llega al intérprete tal cual, con el nombre nuevo que pide: es quien lo descubre, como el entrevistador. Si dos personas del encargo comparten nombre de pila, ese nombre suelto sale con la etiqueta de la primera (vuelve bien escrito, pero el modelo no sabe cuál de las dos es). Si dos nombres enteros se solapan en el texto («Ana Luz» y «Luz Marina» en «Ana Luz Marina»), el tramo común se duplica al volver.

> **Decisión entrevistada, 24 de septiembre de 2026.** El autor eligió la seudonimización desde el diseño frente a pedir al administrador de la organización que ajustara la política. Los datos personales del encargo dejan de llegar al modelo, que es lo que pide la minimización del RGPD, y el diseño no depende de cómo cada modelo aplique la política. Se descartó cambiar de modelo para esquivarla. El coste: el agente escribe etiquetas en lugar de nombres, y la prosa depende de que las respete; la puerta 4 lo comprueba.

