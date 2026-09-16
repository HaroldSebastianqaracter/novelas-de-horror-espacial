# Guía de estilo: terror espacial

Excepción documentada (prueba de humo 2026-09-16): generada desde la descripción del subgénero, sin textos de referencia.

Guía para el escritor de esta novela. Describe el estilo del subgénero (terror en naves, estaciones y colonias aisladas) y fija el vocabulario con el que se interpreta el campo `tension` de cada capítulo. Idioma de la obra: español peninsular (es-ES). Narración en tercera persona limitada, tiempo pasado.

## 1. Tropos recurrentes

- **Aislamiento absoluto.** No hay rescate posible en un plazo humano: la distancia, la latencia de las comunicaciones o el silencio de la central convierten cualquier problema local en definitivo. El exterior no es un refugio sino la muerte inmediata.
- **Fallas de soporte vital.** La amenaza más constante es la propia infraestructura: oxígeno que baja, temperatura que sube, reciclado de agua que se ensucia, energía racionada. Los números de los paneles funcionan como personajes: se leen, se releen y se desconfía de ellos.
- **Presencias que se confunden con la nave.** Lo que acecha se manifiesta primero como fallo técnico: un ruido en los conductos, una puerta que se cierra sola, un sensor que registra una masa donde no hay nadie. La duda entre avería y presencia se sostiene el mayor tiempo posible.
- **La tripulación reducida.** Pocos personajes, cada uno con una función técnica que lo define y lo aísla. Las jerarquías se erosionan a medida que el protocolo deja de servir.
- **La rutina como ancla y como trampa.** Turnos, listas de comprobación, mantenimientos programados. La repetición tranquiliza hasta que una desviación mínima revela que algo ha cambiado.
- **El cuerpo como sistema frágil.** Fatiga, hipoxia, insomnio, alucinaciones inducidas por el entorno. La percepción del punto de vista deja de ser fiable y el texto lo aprovecha sin declararlo.
- **La máquina que no explica.** Sistemas automáticos, inteligencias de a bordo o protocolos de cuarentena que actúan con lógica propia. Nunca se les atribuye malicia explícita; basta con que sus prioridades no incluyan a la tripulación.
- **La ausencia como pista.** Un tripulante que no responde, un registro borrado, una cápsula vacía. El horror se construye con lo que falta más que con lo que aparece.

## 2. Ritmo de tensión y alivio (niveles 1 a 5)

El nivel indicado en `capitulos[N].tension` es el punto donde el capítulo debe **terminar**, no su promedio. Dentro del capítulo puede haber picos y descensos, pero la última escena fija el nivel. Vocabulario para interpretar cada nivel:

- **Nivel 1 — Calma vigilada.** Rutina, diálogo funcional, descripción del entorno con detalle técnico. Ninguna anomalía confirmada; a lo sumo un dato menor fuera de rango que nadie considera relevante. Frases largas, ritmo pausado. El lector respira; el personaje también. Se permite humor seco entre tripulantes. Uso: apertura, recuperación tras un pico, escenas de vínculo.
- **Nivel 2 — Inquietud.** Aparece una desviación que sí se registra: un ruido sin origen, una lectura repetida, un compañero que actúa raro. El punto de vista lo racionaliza. El ritmo sigue pausado, pero las descripciones incorporan un elemento que no encaja. El alivio existe, aunque incompleto: la escena termina con una pregunta sin formular.
- **Nivel 3 — Amenaza reconocida.** Los personajes admiten que algo va mal y actúan: diagnósticos, sellado de compartimentos, búsqueda de un desaparecido. Alternancia clara entre acción y pausa. Se acortan las frases en los momentos de decisión. Puede haber un sobresalto resuelto (falsa alarma), pero al cerrar el capítulo el problema sigue abierto y se ha agravado.
- **Nivel 4 — Peligro inmediato.** Pérdida de control sobre el entorno: soporte vital comprometido, un espacio de la nave que ya no es seguro, la presencia que ha actuado de forma inequívoca. Frases cortas, párrafos breves, percepción fragmentada. El diálogo se reduce a órdenes y monosílabos. El alivio, si lo hay, dura un párrafo y sirve para que el siguiente golpe duela más.
- **Nivel 5 — Colapso.** Sin alivio en el último tercio del capítulo. Muerte, encierro, revelación irreversible o pérdida de la identidad del punto de vista. El lenguaje se vuelve sensorial y elíptico; se omiten conectores y explicaciones. El capítulo cierra en el pico o en su silencio inmediato, nunca en un consuelo.

Reglas de ritmo:
- Nunca dos capítulos consecutivos con la misma textura de frase; aunque compartan nivel, se varía la escena (acción frente a espera, diálogo frente a soledad).
- Un descenso de nivel entre capítulos no borra la amenaza: se muestra a los personajes gestionando las consecuencias, no olvidándolas.
- El alivio se construye con lo cotidiano (comida, una tarea manual, una conversación banal), nunca con explicaciones tranquilizadoras que el lector sepa falsas.

## 3. Vocabulario sensorial

- **Sonido.** Es el sentido dominante: zumbido de ventiladores, crujidos de dilatación del casco, chasquidos en los conductos, el silencio cuando un sistema se apaga. Se distingue entre el ruido de fondo habitual y su alteración. Los sonidos se nombran por su origen técnico presunto antes que por su cualidad emocional.
- **Luz.** Iluminación artificial, parpadeos, luces de emergencia rojas o ámbar, pantallas como única fuente en una sala apagada. La oscuridad del espacio no es negra sino ausencia con puntos fijos. Las sombras se describen por lo que ocultan.
- **Olfato.** Aire reciclado, ozono de los equipos, sudor viejo, plástico caliente, un olor orgánico donde no debería haberlo. El olor es el primer aviso de una avería y de una presencia.
- **Tacto y cuerpo.** Frío de superficies metálicas, vibración del suelo, presión en los oídos al cambiar la atmósfera, pesadez o ligereza según la gravedad. Se registra el cuerpo del punto de vista sin nombrar la emoción: manos que no obedecen, respiración contada.
- **Gusto.** Escaso y siempre desagradable: agua con sabor a filtro, ración pastosa, sangre en la boca.
- **Léxico técnico.** Se usa con naturalidad y sin glosar: esclusa, mamparo, compartimento, presurización, telemetría, ciclo de sueño, baliza, diagnóstico. El personaje lo conoce; el lector lo deduce del contexto.

## 4. Longitud y cadencia de frase

- Frase base de 15 a 25 palabras, con subordinación moderada. En los niveles 1 y 2 se admiten frases de hasta 40 palabras que acumulan detalle técnico o espacial.
- En los niveles 4 y 5 predominan frases de 3 a 10 palabras, con párrafos de una o dos líneas y fragmentos sin verbo.
- Los párrafos descriptivos no superan las seis líneas; se alternan con párrafos de una sola frase que marcan el cambio de percepción.
- El diálogo es breve, con acotaciones mínimas (dijo, preguntó) o sin ellas. Los personajes hablan como técnicos: precisión, elipsis, jerga compartida, sin discursos.
- Se usa la puntuación estándar del español (raya de diálogo, comillas angulares para citas escritas). Se evitan los puntos suspensivos como recurso de suspense; el silencio se marca con un párrafo corto.
- El pasado narrativo se mantiene estable; el presente solo aparece en diálogos y en registros o mensajes transcritos.

## 5. Qué evitar

- Explicar el origen de la presencia antes del acto final. La ambigüedad entre avería, locura y entidad es el motor del subgénero.
- Adjetivos emocionales aplicados al entorno (un pasillo siniestro, una oscuridad aterradora). El miedo lo aporta el detalle concreto, no el calificativo.
- Introspección larga del punto de vista. La emoción se muestra en la conducta y en el cuerpo; un párrafo de pensamiento como máximo por escena.
- Personajes que ignoran el protocolo sin motivo. Las malas decisiones deben nacer de la fatiga, de la falta de información o de un protocolo que ya no aplica.
- Tecnología que resuelve el problema por sí sola. Cada recurso técnico que ayuda debe cobrar un precio o fallar parcialmente.
- Repetir el mismo tipo de sobresalto (puerta que se cierra, sombra en el pasillo) en capítulos consecutivos.
- Nombres, marcas o referencias a obras reales del género. Todo lo que aparece pertenece al mundo de la novela.
- Comienzos de capítulo con resumen de lo anterior. Se entra en escena; el resumen lo lleva el estado, no la prosa.
- Cerrar un capítulo de nivel 4 o 5 con un personaje que se duerme o con una frase de consuelo.
