# Domain knowledge — Oficio de la novela, con el terror espacial como género dominante

Principios de escritura que determinan si una novela se siente lograda o no, más allá del esquema de datos. No son entidades del modelo (ver [definitions.md](definitions.md)), pero cada uno se apoya en él o lo atraviesa.

Están en cinco capas, de lo más general a lo más específico. Las cuatro primeras son oficio de novela: valen para cualquier libro. La quinta es el género de esta obra, terror espacial, y es la que decide qué se hace con las otras cuatro.

- **Capa 1 — Diseño**: qué historia es esta y qué forma tiene.
- **Capa 2 — Estructura**: cómo se encadenan las unidades para que haya presión.
- **Capa 3 — Personaje**: quién la recorre y por qué cambia.
- **Capa 4 — Prosa**: cómo suena en la página.
- **Capa 5 — Terror espacial**: qué exige el género y qué promete al lector.

El proceso de producción —borradores, tipos de pasada de revisión, lectores beta— es pipeline y vive en [architecture.md](architecture.md). Los criterios de comprobación viven en [validators.md](validators.md).

---

## Capa 1 — Diseño

### 1. Premisa, logline y pregunta dramática
Tres compresiones distintas de la misma historia. La **premisa** es la proposición causal que la obra demuestra con los actos de sus personajes ("el conocimiento que salva es el mismo que destruye"). El **logline** es una frase con protagonista, objetivo y antagonismo. La **pregunta dramática** es la pregunta de sí o no que el primer acto abre y el clímax responde. Si no se pueden escribir, casi nunca es que la historia sea demasiado compleja para resumirse: es que todavía no se sabe de qué trata.
*Se relaciona con:* `Novela`, atributos `premisa`, `logline` y `preguntaDramatica`. Son el criterio con el que se decide qué escenas sobran.

### 2. Modelos estructurales
No hay un molde único, hay descripciones del mismo fenómeno con vocabularios distintos: tres actos, las cuatro partes de Weiland, los siete puntos de Dan Wells, los quince beats de *Save the Cat*, el viaje del héroe de Vogler, los cinco mandamientos del Story Grid de Coyne, la pirámide de Freytag. Conviene elegir uno como lengua de trabajo y conocer las equivalencias, no mezclarlos a mitad de proyecto. `kishōtenketsu` queda como recordatorio de que el conflicto es la convención dominante en Occidente, no una ley de la narración.
*Se relaciona con:* `Acto` y `PuntoDeGiro`, atributo `tipo`.

### 3. Beats canónicos y su posición
Los hitos que casi todos los modelos reconocen, con su lugar aproximado: gancho (0 %), incidente incitador (10-15 %), primer umbral (20-25 %), punto de pellizco (37 %), punto medio (50 %), segundo pellizco (62 %), todo está perdido (75 %), entrada al tercer acto (80 %), crisis y clímax (85-95 %), resolución y desenlace (95-100 %). Las cifras son orientación, no obligación; lo que no es negociable es el orden y la función de cada uno.
*Se relaciona con:* `PuntoDeGiro`, atributos `tipo` y `posicion`.

### 4. El punto medio como bisagra
El 50 % es la única ancla del tramo más largo del libro. Su función es invertir el modo del protagonista: deja de reaccionar y empieza a provocar. Suele venir con falsa victoria o falsa derrota, y con una revelación que reencuadra el conflicto. Un punto medio inerte es la causa más frecuente de abandono del lector.
*Se relaciona con:* `PuntoDeGiro` de tipo "punto medio"; es donde `HiloNarrativo` principal y arco del `Personaje` se tocan explícitamente.

### 5. Hilos como muñecas rusas
Cada hilo abre una pregunta de un tipo: entorno (se entra en un lugar, se sale de él), indagación (se pregunta, se responde), personaje (insatisfacción con uno mismo, reconciliación) o evento (se rompe un orden, se instaura otro). Los hilos se anidan y se cierran en orden inverso al de apertura. La mayoría de los finales insatisfactorios no son clímax débiles: son hilos cerrados en el orden equivocado o nunca cerrados.
*Se relaciona con:* `HiloNarrativo`, atributos `tipo` y `estado`.

### 6. Promesa, progreso y pago
El principio promete qué clase de historia es y qué pregunta se responderá; el desarrollo tiene que dar sensación medible de avance hacia esa promesa; el final la cumple de un modo a la vez inesperado e inevitable. Es fractal: vale para la novela, el acto, el capítulo y la escena. El lector abandona el libro en la página en que deja de percibir progreso sobre la promesa que le importa.
*Se relaciona con:* `Novela` (promesa global), `HiloNarrativo` (`estado`) y `Siembra` (pagos concretos).

### 7. Tema y argumento moral
El tema no se enuncia, se demuestra: el protagonista sostiene una respuesta a la pregunta central, el oponente sostiene la contraria con la mayor fuerza posible, y el clímax decide. La calidad temática de una novela tiene como techo la calidad del argumento de su antagonista. Un antagonista que solo es malo reduce el tema a una consigna.
*Se relaciona con:* `Tema`, atributos `preguntaCentral` y `verdadTematica`; `Amenaza` que lo encarna; `Personaje` con `rolNarrativo` de oponente.

### 8. Tipos de final y su preparación
Cerrado, trágico, agridulce, con giro, ambiguo, circular, irónico, de cierre parcial. Cada uno se prepara desde el principio: el trágico exige que la mentira del personaje se haya establecido temprano y haya tenido una oportunidad real de ser abandonada; el agridulce exige que deseo y necesidad se hayan declarado incompatibles antes del punto medio; el giro exige que la información haya estado disponible y la desviación haya sido por atención dirigida, no por ocultación. Reglas transversales: el clímax responde la pregunta abierta en el incidente incitador y no otra; el protagonista actúa, nada externo lo salva; nada esencial entra en el último 10 % sin siembra.
*Se relaciona con:* `Novela`, atributo `tipoFinal`.

---

## Capa 2 — Estructura

### 9. Escena y secuela
La escena tiene objetivo, conflicto y resultado; la secuela que la sigue tiene reacción, dilema y decisión, y esa decisión es el objetivo de la escena siguiente. La escena hace que pase algo; la secuela hace que importe. Las novelas con mucha acción y sin alma carecen de secuelas; las novelas lentas las tienen hipertrofiadas. En tramos de tensión alta la secuela se comprime a un párrafo; en los valles se expande.
*Se relaciona con:* `Escena` y `Secuela`, y la relación `Secuela motiva Escena`.

### 10. La escena cambia un valor
Una escena existe si algo está en un polo al empezar y en el contrario al terminar: seguro→expuesto, confiado→sospechoso, vivo→muerto. Es el test más falsable del oficio. Si el lector puede saltarse la escena sin perder nada, debía haber sido una frase.
*Se relaciona con:* `Escena`, atributos `valorInicial` y `valorFinal`.

### 11. Causalidad: "pero" y "por tanto", nunca "y entonces"
Entre dos beats consecutivos debe caber un "por tanto" (consecuencia) o un "pero" (complicación). Si solo cabe un "y entonces", los beats están yuxtapuestos y la trama está muerta. Es la prueba de causalidad más barata que existe y localiza el defecto entre dos escenas concretas en lugar de dejarlo en "la trama está floja".
*Se relaciona con:* `Beat`, atributo `cambio`; cadena `Escena` → `Secuela` → `Escena`.

### 12. Ciclos de intento y fracaso
El protagonista intenta resolver el problema y falla de forma productiva: "no, y además…" (falla y empeora) o "sí, pero…" (consigue el objetivo con un coste que abre uno mayor). Las variantes muertas son "sí, y ya está" (final prematuro) y "no, y nada cambia" (rueda de hámster). Tres ciclos es la cadencia habitual, y el último fracaso es el que provoca el "todo está perdido".
*Se relaciona con:* `Escena` (`resultado`) y `Secuencia` (`objetivoIntermedio`).

### 13. Escalada y agencia
La tensión es función de lo que se pierde si el protagonista fracasa, no de la cantidad de acción. Se escala el alcance, la intimidad o el precio moral, y cada obstáculo debe sentirse peor que el anterior; tres secuestros seguidos no escalan. La trama avanza por decisiones del protagonista: la casualidad puede crear problemas, nunca resolverlos.
*Se relaciona con:* `Escena` (`tension`), `PuntoDeGiro`, `Personaje` (`deseo`).

### 14. Estado de los hilos y entrelazado
Cada hilo está abierto, complicándose, latente o resuelto, y hay que saber en qué estado está en cada punto del manuscrito. Los hilos alternan el primer plano como en una trenza, y los momentos de mayor energía son las **colisiones**: lo que el protagonista gana en un hilo le cuesta algo en otro. La alternancia sin colisión produce dos novelas cortas pegadas.
*Se relaciona con:* `HiloNarrativo`, atributo `estado`; relación `HiloNarrativo involucra Personaje`.

### 15. La trama temática
Una de las subtramas —normalmente relacional— existe para portar el tema: su personaje encarna la verdad que el protagonista niega, y es ahí donde la lección se dramatiza en vez de enunciarse. Se abre poco después del primer umbral y paga justo antes del tercer acto. Resuelve el problema de cómo se entera el protagonista de lo que necesita saber sin que un narrador se lo explique.
*Se relaciona con:* `HiloNarrativo` con relación `dramatiza Tema`.

### 16. Siembra y pago
Tres tiempos: plantar el elemento donde parece natural y secundario, regarlo una vez a media novela para que el lector lo retenga sin sospechar, y pagarlo cuando decide algo. Todo lo que se destaca debe usarse; nada debe resolverse con material no anunciado. Pocas siembras plenamente cargadas pesan más que muchas: demasiada siembra vuelve el pago previsible, demasiada poca lo vuelve arbitrario.
*Se relaciona con:* `Siembra`, atributo `estado`, y sus relaciones `sembradaEn` / `pagadaEn`.

### 17. Arquitectura de capítulo
El capítulo es unidad de lectura, no de historia: su trabajo es administrar el momento en que el lector puede parar y hacer que no quiera. Necesita gancho de apertura y de cierre propios, independientes del gancho general del libro. El cierre suele ser una revelación parcial, una pregunta nueva o un corte justo antes de mostrar algo.
*Se relaciona con:* `Capitulo`, atributos `ganchoApertura` y `ganchoCierre`; `Escena`, atributo `ganchoSalida`.

### 18. Ritmo macro
La tensión es una sierra de dientes crecientes, no una recta: cada pico mayor que el anterior, cada valle menos profundo. Una tensión sostenida al máximo se anestesia. Se regula con la longitud de escena y capítulo (cortos aceleran, largos profundizan), acortando hacia el clímax, y con la proporción entre escena dramatizada y sumario. La uniformidad de longitud es síntoma de ritmo inconsciente.
*Se relaciona con:* `Escena` (`tension`), `Capitulo`, `Secuencia`.

### 19. Síntomas estructurales de fallo
Arranque lento (incidente incitador tarde), pantano del segundo acto (el protagonista deja de tomar decisiones significativas; no hay escalada; el antagonista desaparece), episodismo (cadena de "y entonces"), final apresurado (crisis no dramatizada, subtramas cerradas por sumario). Cada uno tiene una causa estructural localizable, no es falta de inspiración.
*Se relaciona con:* se diagnostica sobre `HiloNarrativo`, `Secuencia` y `PuntoDeGiro`; ver [validators.md](validators.md).

---

## Capa 3 — Personaje

### 20. Deseo frente a necesidad
El deseo es el objetivo externo y consciente que estructura la trama; la necesidad es la carencia interna, normalmente inconsciente, que debe resolver. No coinciden, y a menudo el deseo es la forma en que el personaje evita la necesidad. El deseo genera trama, la necesidad genera tema y arco.
*Se relaciona con:* `Personaje`, atributos `deseo` y `necesidadInterna`.

### 21. La cadena fantasma → herida → mentira → defecto
Cuatro cosas distintas que se confunden con facilidad. El **fantasma** es el suceso del pasado; la **herida** es el dolor que dejó; la **mentira** es la creencia protectora que el personaje construyó sobre ese dolor; el **defecto** es la conducta observable que de ahí se deriva. En la página solo se ve el defecto: fantasma y herida son material de subtexto, no de exposición. El arco es la presión creciente hasta que la mentira se vuelve insostenible.
*Se relaciona con:* `Personaje`, atributos `fantasma`, `herida`, `mentira`, `defecto`; la verdad opuesta está en `Tema.verdadTematica`.

### 22. Tipos de arco
**Positivo**: abandona la mentira y abraza la verdad. **Plano**: ya posee la verdad y no cambia; lo que cambia es el mundo a su alrededor, y la duda es lo que evita que resulte inerte. **Negativo**, en tres subtipos: **desilusión** (supera la mentira pero la verdad es amarga), **caída** (se aferra a la mentira aunque la verdad esté disponible) y **corrupción** (ve la verdad con claridad y la rechaza conscientemente). Distinguirlos evita escribir "personaje que acaba mal" sin decidir qué falla: el conocimiento, la voluntad o la elección.
*Se relaciona con:* `Personaje`, atributos `tipoArco` y `subtipoArco`.

### 23. El carácter se revela en la elección bajo presión
Lo observable —oficio, ropa, tics, forma de hablar— es la máscara. El carácter verdadero solo aparece en las decisiones bajo presión, y cuanto mayor la presión más profunda la revelación. Una elección sin riesgo no significa nada. El personaje memorable además se contradice: la tensión entre fachada y fondo es lo que produce dimensión; la coherencia total produce tipos.
*Se relaciona con:* se escribe dentro de `Escena` (`conflicto`, `resultado`); se prueba en el `PuntoDeGiro` de tipo crisis.

### 24. Red de personajes
Los personajes no se diseñan de uno en uno sino como sistema: cada uno se define por comparación con el protagonista y con los demás, y cada uno es una variación del tema. Un elenco hinchado no falla por número sino por duplicación de función. Pruebas: si dos personajes pueden fundirse sin perder nada, se funden; si al tapar las acotaciones no se distingue quién habla, son redundantes en voz; si dos defienden la misma posición ante el problema moral, uno es decorado.
*Se relaciona con:* `Personaje` (`rolNarrativo`), relaciones `seOponeA` / `aliadoCon`, y `Faccion`.

### 25. Voz de personaje
El idiolecto es la huella verbal de cada uno: léxico, sintaxis, muletillas, silencios, lo que no sabe decir. Es también indicador de estado: la emoción acorta las frases, la racionalidad las alarga. El diálogo no es conversación, es acción verbal: cada réplica es una táctica para conseguir algo, y lo dicho rara vez coincide con lo pretendido.
*Se relaciona con:* `Personaje`, atributo `idiolecto`; el subtexto suele apoyarse en `secreto`.

### 26. Quién sabe qué, y desde cuándo
Lo que cada personaje sabe, cree o ignora cambia escena a escena y por vías rastreables: lo presenció, se lo contaron, lo dedujo, le mintieron. Es simultáneamente la palanca de tensión más potente y el mayor riesgo de coherencia. La distribución del conocimiento define tres regímenes: **misterio** (el lector sabe menos que los personajes: curiosidad), **suspense** (saben lo mismo: identificación) e **ironía dramática** (el lector sabe más: temor y espera). Toda revelación es un cambio de estado que hay que propagar: quién más lo sabe ahora, qué conductas anteriores quedan invalidadas.
*Se relaciona con:* `EstadoDeConocimiento`, atributos `postura` y `via`; `Hecho`.

### 27. Trasfondo
El autor necesita saber mucho más trasfondo del que la novela muestra. Se entrega bajo demanda: solo cuando una conducta presente resulta inexplicable y crea la pregunta que el trasfondo responde. Entregarlo de golpe al principio no funciona porque el lector no concede crédito a información sobre personajes que aún no le importan. Mejor en conflicto, dicho por alguien que lo usa como arma, que en reflexión serena.
*Se relaciona con:* `Personaje` (`fantasma`, `herida`, `secreto`) y `Evento` no dramatizado.

---

## Capa 4 — Prosa

### 28. Punto de vista
Quién ve y quién sabe, no solo quién habla. Primera persona (intimidad inmediata, a cambio de que todo pase por esa conciencia), tercera limitada (el estándar de la novela contemporánea), omnisciente (escala e ironía estructural, exige voz propia con autoridad), objetiva o cámara (solo lo observable: la escuela más severa de mostrar en vez de contar). El sistema se establece en las primeras páginas y el lector lo aprende: romperlo sin motivo se percibe como ruptura de contrato. Cambiar de conciencia dentro de una escena sin marca ni transición es el error clásico.
*Se relaciona con:* `Novela`, atributo `povPorDefecto`; `Escena`, atributo `pov`.

### 29. Distancia psíquica
Dentro de un mismo punto de vista se puede estar a vista de pájaro o dentro del pulso del personaje. Es un continuo de cinco niveles, del panorama impersonal ("Era invierno de 2213. Una mujer cruzó la cubierta.") al pensamiento sin mediación ("Frío. El zumbido otra vez, más cerca del casco de lo que debería."). El movimiento por la escala debe ser gradual y motivado: se entra lejos para situar, se acerca al subir la tensión, se retira al cerrar. La mayoría de escenas planas no están mal escritas: están escritas enteras a una sola distancia.
*Se relaciona con:* `EstiloNarrativo`, atributo `distanciaPsiquica`.

### 30. Estilo indirecto libre
El pensamiento del personaje vertido en la tercera persona y el tiempo del narrador, pero con su léxico y su entonación, sin verbo introductorio ni comillas. Permite usar lenguaje de escritor y lenguaje de personaje en la misma frase, e instala una intimidad irónica: el lector está dentro y a la vez ve desde fuera. Es el recurso central de la novela moderna y la forma natural de sostener los niveles cercanos de distancia psíquica.
*Se relaciona con:* `EstiloNarrativo`; escribe el `estadoPsicologico` de `EstadoPersonaje`.

### 31. Mostrar y contar
No significa no resumir nunca. Se dramatiza lo que cambia algo —decisión, revelación, conflicto, pérdida— y se resume lo que solo conecta o contextualiza; el sumario es lo que da relieve a lo que sí se dramatiza. Lo que no se hace es nombrar la emoción: "sintió terror" es más débil que la mano temblando al no poder abrir una escotilla. El vicio más frecuente no es contar, es mostrar y después, por desconfianza, contar lo mismo.
*Se relaciona con:* técnica para escribir `EstadoPersonaje` dentro de una `Escena` en vez de declararlo.

### 32. Palabras filtro y distanciamiento
Verbos de percepción que se interponen entre el lector y el hecho: vio, oyó, sintió, notó, se dio cuenta. En punto de vista limitado son tautológicos —si estamos dentro de alguien, todo lo narrado ya lo percibe él— y añaden un centímetro de distancia cada vez. Solo son correctos cuando el acto de percibir es el acontecimiento ("solo entonces vio la sangre"). Misma familia: "empezó a", "pudo ver", las nominalizaciones y los sujetos abstractos.
*Se relaciona con:* `EstiloNarrativo`, atributo `ticsProhibidos`.

### 33. Diálogo
Tres funciones a la vez: caracteriza, genera subtexto y avanza el conflicto. Toda conversación es una negociación con algo en juego, y ninguna réplica responde exactamente a la anterior. "Dijo" es una palabra invisible y casi siempre la correcta: si hace falta "espetó" para que la réplica suene dura, la réplica no es dura. Las acotaciones de acción sustituyen a la atribución y dan cuerpo, ritmo y caracterización. El error mayor es la exposición encubierta: dos personajes contándose lo que ambos ya saben.
*Se relaciona con:* ocurre dentro de `Escena`; el subtexto se apoya en `Personaje.secreto` y en `EstadoDeConocimiento`.

### 34. Descripción
Tres detalles elegidos valen más que treinta enumerados: la especificidad produce realidad, no la cantidad. En punto de vista limitado la descripción nunca es neutra —lo que el personaje nota y con qué palabras lo nota es caracterización—, lo que resuelve a la vez qué describir y cómo evitar que la descripción detenga la escena. Se distribuye en fragmentos breves dentro de la acción, no en bloques al entrar en un escenario: el párrafo-bloque es lo primero que el lector se salta.
*Se relaciona con:* `Lugar`, atributo `descripcion`; `EstiloNarrativo`, atributo `densidadSensorial`.

### 35. Interioridad
Lo que ocurre dentro del personaje es la razón por la que se leen novelas y no solo se ven películas. La emoción se construye en cadena —estímulo, reacción física involuntaria, percepción alterada, pensamiento, acción— en lugar de sustituirse por una etiqueta. La deliberación visible es lo que convierte una decisión argumental en carácter. Y la contención importa: el acceso total y constante a la mente aplana el misterio.
*Se relaciona con:* `EstadoPersonaje`, atributo `estadoPsicologico`.

### 36. Microoficio
La prosa es sonido aunque se lea en silencio. Se alterna la longitud de frase —la corta tras varias largas cae como un golpe—, se coloca la palabra clave al final, que es la posición fuerte, y se usa la puntuación como valores de pausa y no como adorno. El párrafo es unidad de respiración y su forma en la página comunica ritmo antes de que se lea una palabra. El blanco entre secciones es el signo de puntuación más grande que tiene un novelista: permite saltar lo que no importa sin escribir transiciones de relleno.
*Se relaciona con:* `EstiloNarrativo`, atributos `ritmoProsa` y `convencionesFormato`.

### 37. Exposición
La exposición no es opcional, lo que se decide es cómo servirla. Se da cada dato en el momento más tardío en que el lector todavía puede entender la escena, y preferiblemente dentro de una acción que lo haga relevante; si un dato no se necesita nunca, se elimina por interesante que sea. El mundo se siembra en detalles de paso, léxico cotidiano y conducta asumida, dejando que el lector reconstruya las reglas: el mundo que deduce le pertenece, el que le explican no.
*Se relaciona con:* `Mundo` y `SistemaTecnologico`; la información no volcada sigue siendo canon aunque no aparezca.

### 38. Errores frecuentes
El adverbio que sostiene un verbo débil o repite lo obvio. El tic inconsciente: el mismo gesto en todos los personajes, la misma construcción, el mismo signo. El cliché, que no es feo sino inerte: pasa por el lector sin producir imagen. La sobreescritura, que en lugar de intensidad produce la sospecha de que no hay nada debajo. Y explicar el chiste: añadir tras un gesto la frase que dice lo mismo en abstracto, que le retira al lector la mitad del placer de leer.
*Se relaciona con:* `EstiloNarrativo`, atributo `ticsProhibidos`; ver [validators.md](validators.md).

---

## Capa 5 — Terror espacial

### 39. Terror, horror y repulsión
Tres intensidades distintas y no intercambiables. El **terror** es el miedo anticipatorio, lo que el lector imagina antes de ver: es la diferencia entre oler la muerte y tropezar con el cadáver. El **horror** es la confrontación efectiva con lo anómalo, cuando la imaginación deja de trabajar. La **repulsión** es el reflejo de arcada ante lo visceral. La jerarquía es clara: se busca aterrorizar; si no se puede, horrorizar; el asco es el recurso de emergencia declarado. Un texto que vive en terror sostiene trescientas páginas; uno que vive en horror se agota, y cada horror consumido gasta el crédito que la anticipación había acumulado.
*Se relaciona con:* `Amenaza`, atributo `nivelRevelacion`; `Escena`, atributo `tension`.

### 40. Pavor sostenido
La ansiedad difusa y sin objeto localizado que precede y sobrevive al susto. Es la variable de estado de la novela de terror, y se construye en las escenas **lentas**: la tensión sube cuando el ritmo baja, porque la acción rápida produce adrenalina y la escena lenta produce ansiedad. Es lo contrario de la intuición que lleva a rellenar el segundo acto con persecuciones.
*Se relaciona con:* atraviesa `Escena` y `Secuela`; interactúa con el ritmo macro (principio 18).

### 41. Suspense frente a sorpresa
Si la bomba estalla sin aviso hay quince segundos de sorpresa; si el lector ha visto colocarla y hay un reloj a la vista, hay quince minutos de suspense. Siempre que se pueda, informar al lector: darle lo que los personajes no tienen —el sello del módulo está comprometido y la tripulación no lo sabe— y dejarlo cocer. La excepción es cuando la sorpresa es el clímax.
*Se relaciona con:* `EstadoDeConocimiento`: es la asimetría deliberada entre lo que sabe el lector y lo que sabe el `Personaje`.

### 42. Lo siniestro y lo que se mueve mal
Lo que aterra no es lo ajeno sino lo familiar que ha dejado de comportarse como tal: la casa que ya no es hogar, el compañero cuya cara sigue siendo la suya. Muy cerca de lo humano pero sin alcanzarlo, la afinidad se desploma en repulsión, y el movimiento profundiza el efecto. En prosa esto se escribe describiendo **comportamiento**, no apariencia: el parpadeo que llega tarde, la respiración que no varía, la sonrisa que dura un segundo de más.
*Se relaciona con:* `Amenaza` (`naturaleza`); `Lugar` (`presenciaActual`); `Personaje` comprometido.

### 43. La anomalía necesita una línea base
Hay que establecer primero una normalidad detallada y aburrida —turnos, comidas, rutinas de mantenimiento, el ruido habitual del casco— para que una desviación mínima sea legible como amenaza. Sin línea base no hay anomalía. Por eso la primera parte de una novela de terror debe parecer que no es de terror.
*Se relaciona con:* `Acto` I, `Lugar` (`sistemasCriticos`), `Hecho` (lo que queda establecido como normal).

### 44. Las reglas de la amenaza
La amenaza necesita capacidades, límites y condiciones de activación estables, conocidas por el autor desde el principio y descubiertas por los personajes a lo largo del relato. Sin reglas consistentes no hay suspense, porque el lector no puede calcular el peligro de una situación, y sin cálculo no hay anticipación. Romper una regla ya establecida se lee como trampa del autor, no como giro.
*Se relaciona con:* `Amenaza`, atributo `reglas`; `SistemaTecnologico` para el mismo principio en lo técnico.

### 45. Revelación fraccionada
La amenaza se entrega por incrementos: rastro, efecto, vislumbre parcial, encuentro, confrontación. Cada peldaño cierra una pregunta menor y abre una mayor, y siempre queda una zona sin explicar. Si el lector lo sabe todo el miedo se evapora; si no sabe nada, se desconecta. La revelación es el punto de no retorno del terror al horror: una vez gastada, la novela tiene que compensar con otra fuente de tensión —paranoia interna, escasez, cuenta atrás.
*Se relaciona con:* `Amenaza`, atributo `nivelRevelacion`; `Escena` donde `seManifiestaEn`.

### 46. Claustrofobia y agorafobia cósmica
La firma del subgénero es tener las dos a la vez: dentro no se puede huir, fuera no hay a dónde. La nave hereda todas las técnicas de la casa encantada —una geografía que el lector debe aprender, pasillos que se vuelven hostiles, sistemas que responden mal— y añade que no hay puerta al exterior. Mirar por la escotilla y saber que no hay nada en años luz presiona de una manera; el pasillo estrecho presiona de otra. Alternarlas evita la fatiga de una sola nota.
*Se relaciona con:* `Lugar`, atributo `tipo`; `Mundo`, atributo `reglasFisicas`.

### 47. Aislamiento e imposibilidad de rescate
No hay autoridad a la que llamar, y si la hay el retardo de señal la vuelve inútil. Esto elimina la salvación externa y obliga a que toda solución salga de recursos ya presentados: es la condición que legitima el escalado de bajas y la que hace del desenlace un asunto interno del grupo.
*Se relaciona con:* `Mundo`, `Faccion` (la tripulación), `PuntoDeGiro` de clímax.

### 48. La avería como reloj
Respirar, calentarse, orientarse y comunicarse dependen de máquinas que pueden fallar, ser saboteadas o ser el antagonista. La degradación progresiva del soporte vital, la energía o la estructura, con cifras concretas y visibles, es exactamente el reloj a la vista del suspense, y funciona incluso en escenas sin amenaza activa. Da además un criterio objetivo de escalada que impide que el segundo acto se disperse.
*Se relaciona con:* `Lugar`, atributo `sistemasCriticos`; `SistemaTecnologico`, atributos `limites` y `costes`.

### 49. Lo sensorial y el silencio
En novela hay cinco canales donde el cine tiene dos, y renunciar a tres es renunciar a la ventaja del medio. El sonido no se propaga en el vacío: fuera del casco no hay ruido por potente que sea el suceso, y dentro cada sonido estructural se amplifica; el paseo exterior y el pasillo son dos registros de terror distintos. El silencio, tras sostener una cama de tensión, crea un vacío al que el sistema nervioso no puede agarrarse. El olor es el sentido con más acceso directo a la memoria y a la repugnancia; la temperatura y la oscuridad están infrautilizadas.
*Se relaciona con:* `EstiloNarrativo`, atributo `densidadSensorial`; `Lugar`, atributo `descripcion`.

### 50. El grupo se fragmenta y desconfía
Un grupo cohesionado es difícil de amenazar, así que la primera tarea estructural de la amenaza es dividirlo —por logística, por desacuerdo o por sospecha—, y esa división tiene que estar motivada, no ser estupidez. La paranoia es el único motor que mantiene tensión máxima **sin que la amenaza aparezca en escena**, y por eso resuelve el problema del segundo acto. El personaje comprometido —infectado, sustituido, o cumpliendo una orden oculta— convierte cada escena de diálogo en suspense si el lector lo sabe, o en sorpresa si no.
*Se relaciona con:* `EstadoPersonaje` (`nivelConfianza`), `EstadoDeConocimiento`, `Personaje` (`secreto`, `rolNarrativo` de falso aliado).

### 51. Escalado de bajas
El orden de las muertes va restando **capacidades** al grupo, no solo ánimo: primero el prescindible, luego el especialista cuya función se echará de menos, luego la figura de autoridad, luego el aliado emocional del protagonista. Si cada baja no empeora lo que el grupo puede hacer, el recuento es decorativo.
*Se relaciona con:* `Personaje` (`rol`), `Faccion` (`recursos`), `EstadoPersonaje` (`saludFisica`).

### 52. Subgéneros y qué pide cada uno
**Terror corporal**: el cuerpo propio como escenario; lo que aterra es la disolución de la frontera dentro/fuera, no la sangre. **Infección**: un umbral —un mordisco, una espora— convierte al compañero en amenaza futura y da un reloj biológico por personaje. **Horror cósmico**: lo incomprensible y la insignificancia humana; el horror no es que la amenaza nos odie, es que no repare en nosotros, y el conflicto se desplaza al interior de la tripulación y a qué se puede llegar a saber. **Slasher espacial**: recuento de bajas, lugar aislado, supervivencia individual. **IA hostil**: la amenaza no ataca, **niega**; su calma lógica hace que parezca inevitable en lugar de malvada. **Supervivencia**: la escasez sustituye al monstruo en el ochenta por ciento del relato en que no hay monstruo. Conviene elegir uno como dominante desde el inicio porque cada uno pide un tipo de final distinto.
*Se relaciona con:* `Novela`, atributo `subgeneroDominante`, que condiciona `tipoFinal`.

### 53. Diseño del monstruo: intersticial y metafórico
Una amenaza aterra por dos razones acumuladas. Es **impura** porque está entre dos categorías que el lector da por separadas: vivo y muerto, yo y otro, animado e inanimado, tripulante y cosa. Y es **cuerpo de una ansiedad concreta**: el monstruo más eficaz no viene de fuera, viene de algo que el grupo ya había decidido no mirar. Antes de describirla hay que poder responder de qué es la encarnación; de ahí salen además sus reglas, que dejan de ser arbitrarias.
*Se relaciona con:* `Amenaza` (`naturaleza`, `origen`) y su relación `encarna Tema`.

### 54. Finales del género
**Cerrado**: la amenaza se destruye y se explica; el final limpio decepciona porque sugiere que el mundo vuelve a ser el de antes, lo que contradice la premisa del género —que la normalidad era una ilusión—, así que debe cobrar un precio permanente. **Abierto**: la amenaza persiste; perdura porque lo que el lector imagina supera a lo descrito. **Ambiguo**: no se resuelve la naturaleza de lo ocurrido; funciona solo si la ambigüedad es la pregunta central de la obra, si no se lee como indecisión. **Victoria pírrica**: se sobrevive con una pérdida que anula el sentido de la victoria; es el final por defecto del terror espacial porque encaja con la imposibilidad de rescate.
*Se relaciona con:* `Novela`, atributo `tipoFinal`.

### 55. Tropos y su subversión
El grupo que se separa sin motivo, el que investiga el ruido solo y desarmado, el escéptico que niega hasta morir, la comunicación que falla justo entonces, el científico que quiere estudiar a la amenaza, el superviviente que carga el patógeno. La subversión consciente ya es a su vez un cliché; la opción más robusta suele ser **ejecutar el tropo con causalidad impecable**: el grupo se separa porque el soporte vital obliga a registrar tres cubiertas en veinte minutos, no por descuido. Otras vías: cambiar el reparto (trabajadores con turnos y disputas salariales en lugar de héroes militares) o conceder la información que el género suele negar y demostrar que no sirve de nada.
*Se relaciona con:* `Escena` (`conflicto`) y `Personaje` (`deseo` que motiva la conducta).

---

## Cómo se conectan entre sí

La capa de diseño se decide primero y condiciona todo lo demás: la premisa elige los personajes, y el subgénero dominante decide el tipo de final. La capa estructural organiza cómo se agrupan actos, capítulos y escenas, y es donde vive la causalidad. La capa de personaje atraviesa las dos: el arco no es un hilo aparte, se demuestra en las decisiones que la estructura obliga a tomar. La capa de prosa se aplica dentro de cada escena y no puede salvar un problema de las anteriores —una escena sin conflicto no se arregla escribiéndola mejor.

La capa de género es la que fija las prioridades cuando dos principios chocan. En terror espacial el caso más frecuente es este: el ritmo general pide acelerar, y el pavor pide frenar. Manda el pavor. El segundo caso: la claridad pide explicar la amenaza, y el miedo pide no hacerlo. Manda la revelación fraccionada, con la restricción de que las reglas ya establecidas no se rompen nunca.
