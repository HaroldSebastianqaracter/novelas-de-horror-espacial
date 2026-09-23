# La noche del 23 al 24 de septiembre

Trabajo sin el autor en la rama `noche-23-09` (worktree `../novelasv2-noche`, sale de `pruebas` en `134e453`). **Nada se ha integrado en `pruebas`**: lo decide el autor. Manda el objetivo que fijó: **que el generador saque una novela con los menores fallos posibles.** El plan de partida está en [storymaker-plan.md](../../specs/storymaker-plan.md), «Plan de la noche del 23 al 24».

## En una frase

Ahora la puerta 4 caza lo que las cinco puertas dejaron pasar en la primera novela real: las cuentas que no cuadran (medido con el juez real sobre esa novela), los nombres mal escritos, los allegados que faltan y las palabras vetadas. Cada parada de continuidad llega con una segunda opinión, y el juez vota para no depender de una sola llamada.

## Lo hecho

Cada paso se cerró con la spec en el mismo commit, `/verificar` en verde (601 tests al final, ruff y pyright limpios), un `validador-de-codigo` y sus correcciones.

| Paso | Qué evita o caza en la prosa | Commits | Spec |
| --- | --- | --- | --- |
| Banco de contraejemplos de la puerta 3 | Mide los falsos negativos, que antes no veía nadie: recall del 50 % (7 de 14) y falsos positivos del 25 % (2 de 8) | `786c4b0`, `88be175` | [spec3, 3.10](../../specs/spec3.md) |
| Ficha para el redactor | Que traiga a una escena a quien la escaleta no puso sin saber cómo es, y que descuadre las cuentas: recibe las fichas de quien ya salió, los hechos de objetos y facciones, y la regla de las cuentas. Los de mundo se recortan los últimos | `e810d8f`, `a277d54` | spec3, RF3-PAS-10 |
| Juez de cuentas en la puerta 4 | Las cifras que no cuadran con el canon o dentro del capítulo: noveno criterio de oficio, `cuentas_cuadran`, con los hechos con cifras en su paquete | `a65c01d`, `97ceafd` | spec3, RF3-PAS-12 |
| Validadores deterministas de la prosa | El nombre del destinatario o de otro personaje sin su tilde; un allegado planificado que la prosa no nombra (los dos devuelven el capítulo); la longitud real (aviso) | `469d64d`, `bfb95a3` | spec3, 3.6 |
| Guardrails | Lo que la intensidad no admite y lo que el comprador vetó: términos en SQLite, búsqueda por palabras completas, capítulo de vuelta al redactor y registro de cada decisión (también en Langfuse) | `66542ef`, `8330dcf`, `1cd2630` | spec3, 3.5 |
| Segunda opinión en la parada | Que el autor tenga que leer el grafo para saber si una parada es real: el revisor de continuidad, que nunca se invocaba, opina por conflicto y no levanta la parada | `9cc7972` | spec3, RF3-JUE-01 |
| El juez vota | Que el veredicto dependa de la llamada: tres muestras, dos más si discrepan, mayoría por criterio | `5da56ac` | spec3, RF3-JUE-02 |
| Correcciones finales | Lo que encontraron los últimos validadores (ver abajo) | `f5deddc`, `a5d0355`, `778bc6a` | — |

**Lo que corrigieron los validadores** (no todo fue a la primera):
- el veto del brief heredaba las excepciones de la lista global;
- al empezar frase, el nombre del destinatario mal escrito había dejado de devolver el capítulo;
- con la segunda opinión antes de abrir la parada, un error se llevaba la parada por delante;
- el voto contaba veredictos y no muestras;
- los hechos nuevos del redactor desplazaban del paquete el censo.

Todo está en el [registro de iteraciones](registro-iteraciones.md), entradas 30 a 37.

## Medidas con Claude Code real

El autor autorizó lanzar trozos para comprobar que los cambios funcionan. Todo se hizo sobre una **copia** de `novela_real.db` hecha con la API de backup; la base del autor no se abrió para escribir. Coste total: **unos 5,90 $**.

| Qué | Resultado |
| --- | --- |
| Juez de cuentas, cuatro capítulos (1,16 $) | Caza b4 (40 h de antelación frente a un carguero que llega en 31) y b3 (el censo) en el capítulo 4. Caza también una contradicción real que no estaba en la lista: una reserva de 61 horas-persona que baja de 40 en veinte minutos (capítulo 3). No caza b1: toma «los siete de fuera» por un recuento falseado a propósito |
| Exención endurecida, capítulos 1 y 2 (0,47 $) | Con la regla nueva, el juez explica que la propia escena marca «los siete de fuera». El capítulo 1 pasa a fallar por una conversación en tiempo real con 51 minutos de retardo por sentido |
| Voto, capítulos 1 y 4 (2,15 $) | Capítulo 1: `cuentas_cuadran` en contra en 4 de 5 muestras (discreparon y se pidieron dos más). Capítulo 4: 3 de 3. Los otros ocho criterios, unánimes a favor |
| Segunda opinión, diez paradas (2,10 $) | En las paradas 2 a 10: 12 falsos positivos, 3 dudosos y 2 reales de 17 conflictos, con el motivo citando la prosa. Coincide con el repaso de 1d (todas falsos positivos o discutibles) |
| Mecánica del bloque 6 sobre la prosa real | 0 falsos positivos de nombres en unas 10.000 palabras |

Los ficheros de las medidas (paquetes, informes JSON y scripts) quedaron en el scratchpad de la sesión, en `eval_cuentas/`, y no en el repo.

## Lo que chocó con el objetivo

**Que la muerte y la ubicuidad leyeran la prosa y no el reparto (RF3-PAS-11) se implementó y se revirtió** (`9a8d864`, revertido en `f452fe3`). Quitaba el falso positivo L08 del banco: un muerto que sigue en el reparto de la escaleta y la prosa ya no trae. El validador lo rechazó por dos razones:
- revocaba una decisión que el autor ya había tomado en la pasada real ([spec2, RF2-PIPE-31](../../specs/spec2.md): «un cadáver está físicamente en la escena»);
- la fila 38d mide que el extractor se queda corto con las presencias, así que perdía detecciones reales.

**Propuesta para el autor:** dejarlo como está. La segunda opinión ya le enseña al autor este caso como falso positivo (está en la lista de la skill). Si se quiere quitar la parada, hace falta una medida de la precisión del extractor en más capítulos (fila 38d), y no una decisión de noche.

Nada más chocó. Dos decisiones se tomaron **a favor de menos paradas** a costa de algo de recall, y conviene que el autor las mire: el nombre mal escrito al empezar frase es solo un aviso (salvo el del destinatario y sus allegados), y la longitud real es un aviso y no un bloqueo.

## Decisiones sin entrevistar

Todas llevan su callout `> **Decisión sin entrevistar.**` con las alternativas descartadas:

- **RF3-PAS-10:** las fichas de quien ya salió son opcionales, y sus hechos se recortan antes que los de mundo.
- **RF3-PAS-12:** las cuentas son un criterio de oficio y no una llamada aparte, y no se hacen en SQL. Añade la excepción en [validators.md](../validators.md).
- **3.5, guardrails:**
  - qué entra en la lista global y qué no;
  - palabras y no temas;
  - flexión escrita, sin stemming;
  - reescribir el capítulo entero y no el párrafo.
- **3.6, validadores de la prosa:** el nombre y el allegado devuelven el capítulo, y la longitud solo avisa.
- **RF3-JUE-01:** la opinión nunca levanta la parada (excepción en validators.md).
- **RF3-JUE-02:** votos y no notas; mayoría y no parada cuando discrepan; el empate falla.

## Lo que falta

- **Integrar en `pruebas`:** lo decide el autor. La migración nueva es la **010**: si otra sesión ha creado otra 010 en `pruebas`, hay que renumerar la de guardrails antes de integrar.
- **La 010 se editó en su sitio durante la noche**, antes de integrarse en ningún lado. Solo afecta a bases migradas con `66542ef` (las temporales de los tests y la copia del scratchpad), no a las del autor.
- **Bloque 6, juez de personalización:** que los rasgos y recuerdos del encargo se integren con naturalidad (U3-2) y que la prosa respete la intensidad más allá de las palabras.
- **La puerta 4 no ve la facción del elenco frente a la prosa** (b2, C13 del banco).
- **El frontend enseña `segunda_opinion` como JSON crudo** en la ficha de la parada. Es cosa de la sesión del frontend.
- **Calibrar con el autor** si tres muestras del juez son pocas, y la lista global de términos.

## Aviso operativo

El validador de `9cc7972` dejó colgados dos procesos pytest de un mutante suyo en bucle: los **PID 19220 y 9652**, lanzados a las 23:42 desde `scratchpad\val9cc-hijo`. Solo tocan bases temporales. El clasificador de permisos le denegó pararlos, y no los he parado yo en su lugar: esa decisión es del autor. Se paran por esos PID exactos, nunca por patrón, y después se puede borrar la carpeta.

## Hashes

`0f639c5` (plan), `786c4b0`, `e810d8f`, `88be175`, `9a8d864`, `a277d54`, `a65c01d`, `f452fe3`, `469d64d`, `97ceafd`, `66542ef`, `bfb95a3`, `9cc7972`, `8330dcf`, `5da56ac`, `1cd2630`, `f5deddc`, `a5d0355`, `778bc6a`.
