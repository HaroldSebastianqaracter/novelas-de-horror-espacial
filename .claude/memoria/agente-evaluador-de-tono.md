---
name: agente-evaluador-de-tono
description: "Idea guardada: agente evaluador que puntúa el tono de cada capítulo y marca para revisión los que se salen de una banda de varianza"
metadata:
  type: project
---

Idea que el usuario pidió apuntar el 22 de septiembre de 2026, **sin implementar todavía**: un **agente evaluador del tono** que da un **score por capítulo** contra las reglas ya fijadas, con **límites de varianza** dentro de los que el score tiene que caer. Lo que se sale de la banda (el usuario propuso ±10 % como ejemplo) **se revisa**. La razón que dio: es la única forma de medir la capacidad probabilística de los modelos.

**Why:** es el «segundo método sobre el texto» que [docs/validators.md](docs/validators.md) declara obligatorio cuando el dato lo escribe el agente evaluado. Hoy `Escena.tension` la declara el escaletador y nadie comprueba que la prosa la cumpla. De rebote ataca U3 (curva de tensión en lectura continua), hoy declarado inverificable en `specs/spec1-verification.md`.

**How to apply:** no tocar `docs/`, `specs/` ni `src/` por esto hasta que el usuario lo pida. Tres correcciones al planteamiento original que ya quedaron acordadas en la conversación:

- **Contra el plan, no contra la media.** Una banda plana sobre la media global pide que la novela no tenga arco. Lo que se mide es el **residuo** entre la `tension` declarada en la escaleta y el tono observado en la prosa. El signo del residuo distingue dos fallos: inflado vs. plano.
- **La banda se deriva, no se decide.** Primero se mide el **ruido del juez** (mismo capítulo, N pasadas); la banda sale de esa dispersión, en **puntos absolutos** sobre una escala ordinal 1-5 con descriptores anclados a un capítulo de referencia real, no en % sobre 0-100. Un ±10 % cae por debajo de la resolución del juez. La dispersión del juez consigo mismo se guarda como señal propia: ambigüedad del capítulo.
- **Score descomponible con evidencia.** Tres o cuatro sub-dimensiones (densidad sensorial, distancia psíquica, carga léxica, ritmo de frase) con cita obligatoria del texto y agregación por código. Por picaresca, las que tienen proxy determinista (longitud de frase, léxico sensorial) las cuenta el código y no el juez.

Decisiones de encaje: **skill nueva junto a `oficio`, no dentro** (oficio emite veredictos por criterio; esto emite un escalar con banda). En v1 **avisa, no para**, hasta tener su eval. Es un **validador solitario** y su punto ciego ya está identificado: un juez calibrado sobre el estilo de la obra no detecta que el estilo de la obra sea malo, solo que un capítulo se salga de él.

**Primer paso acordado si se retoma:** medir el ruido del juez sobre un capítulo real antes de escribir spec. Si el juez no es reproducible consigo mismo, hay que ir a comparación por pares contra ancla en vez de a score absoluto.

Arrastra cambios en los cuatro documentos: `definitions.md` (no hay entidad para «medición de un capítulo»), `validators.md`, `architecture.md` y `specs/spec1-verification.md`. Ver [[huecos-de-diseno-con-criterio-propio]] y [[frontend-tablero-tipo-jira]], la otra idea guardada sin implementar.
