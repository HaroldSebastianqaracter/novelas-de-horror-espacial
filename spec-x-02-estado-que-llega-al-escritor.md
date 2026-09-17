# Spec-X 02 · El escritor puede escribir sobre seis personajes y solo conoce a dos

**Estado:** propuesta, para discutir
**Alcance:** qué estado y qué previsión se le entregan al escritor. No toca el bucle, ni las fases, ni el QA.
**Base:** `especificacion-tecnica-harness-novela-terror.md` v1.9, §11 (estado) y RF-03/RF-04
**Evidencia:** prompt `005_escritor_cap_6.md`, `04_estado/continuidad.json` y el informe `qa_cap_6.md`

---

## 1. El hallazgo

El QA detuvo la novela en el capítulo 6 con dos contradicciones. La primera:

> Las marcas de Irene Montoro cambian de sitio. En el cap. 6 el narrador las ubica en el
> hombro. El hecho vigente las fija en **cuello y antebrazo derecho**.

Parecía un descuido del escritor. No lo es. El prompt con el que se escribió ese
capítulo contiene:

**Hechos de continuidad entregados** — 10, sobre `mundo`, Pedro, Mesa y la bodega.
Ninguno sobre Irene.

**Fichas de personajes entregadas** — dos: Pedro y Mesa.

**Personajes que la regla 2 le permite usar** — seis, Irene entre ellos.

En el estado, mientras tanto, hay **tres hechos vigentes** que dicen dónde están esas
marcas. Ninguno viajó.

**El escritor escribió una escena sobre las marcas de un personaje del que no recibió
ni un dato.** No es que ignorara la continuidad: es que no la tenía. Con ese prompt,
acertar habría sido casualidad.

## 2. La causa

Dos listas que deberían coincidir y no coinciden:

- La **lista de personajes permitidos** sale de las fichas del registro: quién existe en
  la novela.
- La **lista de fichas y hechos entregados** sale de `personajes` de la entrada de
  escaleta: quién estaba previsto en escena.

Cuando la escena se mueve —y se mueve, porque la escaleta es una previsión, no un
guion— el escritor entra en territorio permitido y desamueblado.

El filtro de hechos, además, prioriza `mundo` y los personajes en escena, y los `mundo`
entran siempre. En el capítulo 6, ocho de los diez hechos entregados eran de `mundo` y
de capítulos 0 y 1: contexto de fondo que el escritor ya sabía, ocupando el sitio del
dato que necesitaba.

## 3. La propuesta

### X-02.1 · Quien se puede escribir, se documenta

Si un personaje está en la lista de personajes permitidos, su ficha y sus hechos
vigentes viajan en el prompt. Sin excepción.

Coste: las fichas de los cuatro personajes que faltaban son ~800 tokens sobre los
165.000 que ya mueve el escritor. Medio punto porcentual.

La alternativa —dejar el estado como está y estrechar la lista de permitidos a los
personajes de la escaleta— también cierra el agujero, pero le quita al escritor la
libertad de mover una escena, y esa libertad es la que hace que la novela no parezca
una escaleta rellenada. **Se propone la primera.**

### X-02.2 · Mapa de posiciones

No existe hoy. `mundo.json` describe las locaciones, pero nadie registra dónde queda
cada personaje al cerrar cada capítulo.

```json
{"6": {"Pedro Sánchez": "Bodega de carga",
       "Irene Montoro": "Enfermería (inconsciente desde cap. 3)",
       "Capitana Larrea": "Camarote (muerta desde cap. 3)"}}
```

Lo rellena el extractor, que ya lee el capítulo entero. Son datos, no prosa, así que
—al contrario que un resumen literal— no puede provocar repeticiones de RF-05.5.
Cuesta unos 200 tokens por capítulo.

Ataca la misma familia de fallo que X-02.1: el escritor que coloca a alguien donde no
podía estar.

### X-02.3 · Todos los resúmenes, no los dos últimos

`ventana_resumen_rodante` vale 2: al escritor del capítulo 6 le llegaron los resúmenes
del 4 y del 5, y nada del 1 al 3.

Propuesta: que lleguen **todos**, recortados. Los dos últimos completos, como ahora; los
anteriores en una línea cada uno.

En el capítulo 30 eso son unos 28 resúmenes de una línea: ~1.200 tokens. El arco
completo de la novela por menos del 1 % del contexto.

Esto no es lo mismo que darle los capítulos anteriores en prosa, que es una idea que
esta spec **rechaza** por la razón de §4.

### X-02.4 · El escritor no sabe qué viene después, y eso ya rompió un giro

La escaleta completa existe: 30 entradas con título, objetivo narrativo, personajes,
locación, información nueva y nivel de tensión. Al escritor le llega **solo la suya**.
Ni el título del capítulo siguiente aparece en su prompt. Lo único que mira hacia
adelante es la sinopsis en tres actos, que da el arco pero no lo que toca justo después,
y una regla que le pide «no adelantes giros que la sinopsis reserva para más adelante»
sin decirle cuáles son.

**Dos consecuencias, y la primera ya ocurrió.**

**a) La escaleta filtra los giros por la lista de personajes.** Según la entrada del
capítulo 7, es ahí donde Pedro bautiza a la presencia. El QA lo encontró ocurriendo en
el capítulo 5. La causa está a la vista en la propia escaleta:

| Cap | Personajes en escena | Locación |
|---|---|---|
| 5 | Pedro, *la presencia, ya con su nombre*, Capitana Larrea | Bodega de carga |
| 6 | Pedro, Mesa | Bodega de carga |
| 7 | Pedro, *la presencia*, Mesa — **aquí es donde se le pone el nombre** | Conductos de servicio |

La entidad figura como personaje desde el capítulo 5, con el nombre que se supone que
Pedro le inventa en el 7. El escritor del 5 recibió ese nombre en su lista de personajes
en escena y lo usó. No desobedeció: el giro estaba en su prompt.

Esto no se arregla en el armado del prompt sino en la escaleta: **un personaje cuyo
nombre es en sí mismo un giro no puede aparecer nombrado en entradas anteriores a ese
giro.** Antes de esa entrada se le designa por su función («la presencia»).

**b) Nadie prepara el relevo.** El capítulo 6 transcurre en la bodega de carga; el 7
empieza en los conductos de servicio. El escritor del 6 no lo sabe, así que cierra donde
le parece y el del 7 hereda un salto que tiene que remendar.

Propuesta: entregarle del capítulo siguiente **dos datos y solo dos** — su locación y
una línea de «dónde tiene que quedar la escena». Nunca su `informacion_nueva`, que es
precisamente lo que no debe adelantar. Unos 120 tokens.

Es el complemento de X-02.2: no basta con saber dónde **quedó** cada personaje, hace
falta saber dónde tiene que **quedar**.

## 4. Lo que esta spec rechaza, y por qué

Se estudió entregarle al escritor los capítulos anteriores —el último entero, el
anterior a la mitad, el siguiente a un cuarto— y trozos literales de texto alrededor de
cada evento importante.

**No.** Dos razones medidas:

**a) La peor repetición de la tanda vino exactamente de ahí.** El capítulo 6 repitió
quince palabras seguidas del capítulo 5:

> «La capitana llevaba cuatro días muerta en su camarote con los párpados sin cerrar y»

El escritor no leyó el capítulo 5: no tiene `Read`. Esa frase le llegó **en el contexto**,
en prosa, y la reprodujo palabra por palabra. Entregar prosa literal fabrica ese fallo
en serie, y RF-05.5 lo rechaza cada vez.

**b) La ventana decreciente apunta al lado contrario.** De las 19 repeticiones literales
medidas, solo el 26 % viene del capítulo inmediatamente anterior. El bloque mayor —37 %—
viene de tres capítulos atrás, y un 26 % de cuatro o cinco. Dar el texto completo del
capítulo anterior y un cuarto del de tres atrás reparte el esfuerzo justo al revés de
donde está el problema.

La conclusión es la que atraviesa las tres propuestas: **al escritor se le dan datos
estructurados, nunca prosa de la novela.**

## 5. Cómo se comprueba

1. Contradicciones por corte de QA. Hoy: 2 en el capítulo 6.
2. Que ningún personaje nombrado en un capítulo carezca de ficha en el prompt de ese
   capítulo. Hoy: cuatro de seis.
3. Giros que se disparan antes de su capítulo. Hoy: 1 medido (el bautizo, dos
   capítulos antes).
4. Capítulos que empiezan en una locación distinta de donde cerró el anterior sin
   transición escrita. Hoy: sin medir.
5. Tokens de entrada del escritor. Hoy: ~165.000. Las cuatro propuestas suman ~2.320.

## 6. Qué NO propone

- **No toca INV-01.** El escritor sigue sin `Read` y sin ver el manuscrito.
- **No toca RF-05.5** ni su umbral. Eso es X-01.3 y sigue abierta.
- **No toca el bucle, las fases ni los hooks.** Es estado y armado de prompt.
