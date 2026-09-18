# Spec-X 04 — El escritor emite su propio delta

**Estado:** especificado, sin implementar. Se implementa cuando termine la corrida de base.

## Por qué

El extractor se lleva **12 de los 18 minutos** de una novela. Emite entre 6.000 y 11.000 tokens de
salida para dejar un archivo de 1.200, y lo hace para extraer cuatro hechos de un capítulo de 420
palabras que el escritor acaba de escribir.

El escritor ya tenía todo el contexto. Pedirle el delta junto con el capítulo elimina una invocación
de agente entera por capítulo. Si sale, **una novela pasa de ~18 minutos a ~8**.

Es la palanca de velocidad más grande que hay, por delante de apagarle el razonamiento al extractor.

## Lo que se pierde, y es lo que hay que medir

Hoy el extractor lee **lo que se escribió**. El escritor declararía **lo que quiso escribir**. Si se
desvió de su plan --y se desvía--, el log de continuidad pasaría a describir el guion en vez de la
novela, y ese log es lo único que viaja al capítulo siguiente.

Ese es el riesgo entero, y ya sabemos verlo: `contradicciones` y `correcciones` están en la tabla.

## Lo que NO cambia

El paso de información entre capítulos. Nunca fue de agente a agente:

```
escritor cap N → delta → aplicar-delta → 04_estado/ → prompt del escritor cap N+1
```

Cambia quién escribe el delta. No cambia qué lleva dentro, ni quién lo lee después, ni el canal.
`aplicar-delta`, `continuidad.json`, `resumen_rodante.md` y `recursos_narrativos.json` quedan igual.

## Cambios

| pieza | cambio |
|---|---|
| `config/ejecucion.json` | nueva clave `escritor_emite_delta` (bool). Con `false` todo sigue como hoy |
| `config/prompts/escritor.md` | añade el registro de sujetos, el tope de hechos y el formato del delta |
| `app/agents/escritor.py` | el contexto inyecta el registro de sujetos y `max_hechos_por_capitulo` |
| `app/validacion.py` | verbo único `validar-capitulo N --con-delta`, que valida las dos cosas |
| `app/hooks.py` H-06 | el escritor podrá escribir también `04_estado/deltas/delta_cap_N.json` |
| `app/hooks.py` H-11 | sigue permitiendo **un solo** comando; cambia cuál, según la config |
| caída al extractor | si el escritor agota tres intentos con su delta, se invoca al extractor para ese capítulo |
| `.claude/agents/escritor.md` | gana la skill `formato-delta`; sube `maxTurns` de 8 a 10 |
| `.claude/skills/escribir-tanda/SKILL.md` | desaparece la invocación al extractor |
| `app/orchestrator/loop.py` | `registrar-escritor` aplica el delta que ya está en disco |

## Lo que se queda como está

**El agente extractor no se borra.** `/resolver-qa` lo sigue usando: cuando el escritor rehace un
capítulo por una contradicción, quien lo reextrae tiene que ser alguien que lea el texto, no quien lo
acaba de redactar. Es justo el caso donde la independencia más vale.

**INV-01 intacto.** El escritor sigue sin leer el manuscrito: escribe su capítulo y describe lo que
acaba de escribir, que está en su propio contexto.

**INV-02 queda sin efecto en este camino.** Decía que el extractor no recibe memoria narrativa para
que no invente continuidad. Si el delta lo escribe el escritor, que sí la tiene, el invariante deja
de aplicarse aquí --y hay que decirlo en la spec técnica en vez de dejarlo pasar en silencio--.

## Medición

Con dos agentes en vez de tres, la tabla no cambia de forma: `extractor_invocaciones` pasa a 0 y eso
hace el cambio visible solo.

| columna | qué esperamos |
|---|---|
| `minutos` | de ~18,5 a ~8-10 |
| `extractor_segundos` | 0 |
| `escritor_tokens_salida` | +1.200 por capítulo; si sube mucho más, el escritor deliberó de más |
| `contradicciones` | **el guardarraíl**; si sube, la mejora no cuenta |
| `correcciones` | si sube, el sistema se está arreglando a sí mismo más veces |

En Langfuse: dos generaciones por capítulo en vez de tres.

## Plan

Vuelta 1 del loop, por delante de apagar el razonamiento del extractor. Tres novelas con
`escritor_emite_delta: true`, mismas premisas, contra las tres de base.


## Decisiones tomadas

**H-11 no se abre.** Se añade `validar-capitulo N --con-delta`, que valida las dos cosas en una sola
llamada, y la valla sigue permitiendo exactamente un comando: solo cambia cuál, según la config. Era
la primera vez que H-11 iba a aceptar más de una cosa, y esa puerta no se cierra sola.

**Un delta que no valida no cuesta la novela.** El escritor lo corrige hasta tres veces, como hace
hoy el extractor. Agotados los tres, se invoca al extractor para ese capítulo y la novela sigue: ese
capítulo pierde la ventaja de velocidad, pero dieciocho minutos de trabajo no se tiran por un JSON
mal cerrado. La caída queda anotada, para saber cada cuánto ocurre.
