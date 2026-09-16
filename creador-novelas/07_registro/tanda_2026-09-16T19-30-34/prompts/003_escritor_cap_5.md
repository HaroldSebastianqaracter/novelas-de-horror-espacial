# Capítulo 5: «Alguien responde»

Sos el agente escritor de una novela de terror espacial. Este prompt contiene TODO lo que podés saber de la novela: no tenés acceso a ningún capítulo anterior ni a otros archivos, y no lo necesitás.

## Voz narrativa (inamovible)
- Idioma: **es-ES**. Todo el texto, incluidos diálogos y nombres comunes, va en este idioma.
- Persona narrativa: **tercera_limitada**.
- Tiempo verbal: **pasado**.
Cualquier desvío de estos tres puntos es un hallazgo de QA.

## Guía de estilo del subgénero (fase 0)
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

## Sinopsis en tres actos (fase 2): dónde encaja este capítulo en el arco completo
# El casco frío del Falcon: sinopsis en tres actos

## Gancho inicial

El Falcon, carguero estelar de cuatro tripulantes, sale de una maniobra rutinaria de frenado con el reactor principal apagado y la baliza de socorro muda. Pedro Sánchez, técnico de sistemas y el único que estaba de turno, despierta en el puente con los paneles en ámbar y descubre que el resto de la tripulación no responde: la capitana Larrea ha muerto en su camarote con la esclusa interior abierta, el piloto Uxío Ferrán ha desaparecido sin dejar registro de salida, y la ingeniera Irene Montoro está viva pero inconsciente en la enfermería, con quemaduras que no coinciden con ningún fallo eléctrico conocido. La voz de a bordo, el sistema Mesa, repite avisos de mantenimiento que ya no tienen sentido y cierra compartimentos que Pedro no ha ordenado cerrar.

Con el oxígeno estimado para cuarenta días y el reactor secundario a un tercio de potencia, Pedro empieza a reparar la nave tramo a tramo, siguiendo las listas de comprobación como si la disciplina pudiera sostener el casco. La primera noche oye, en los conductos de la bodega de carga, una voz que responde a la suya con las frases de la capitana muerta. Revisa los registros de la última carga recogida en la estación de tránsito Vellón: un contenedor sellado sin manifiesto, ahora vacío, con el interior cubierto de una escarcha orgánica. Pedro le pone nombre a lo que ha salido de ahí, Santiago Abascal, porque necesita que tenga un nombre para poder odiarlo, y comprende que lo que mató a la capitana no vino del exterior: está dentro, aprende y espera.

## Punto medio (giro)

Irene Montoro recupera la consciencia y se convierte en la única aliada de Pedro. Entre los dos consiguen restablecer la baliza durante seis minutos, tiempo suficiente para recibir una respuesta automática de Vellón: la estación fue puesta en cuarentena tres días antes de que el Falcon partiera, y el contenedor sin manifiesto nunca debió salir de allí. La raza vox no viaja en naves: viaja en cargamentos, y elige un anfitrión que la mantenga cerca de la maquinaria caliente. Pedro y Irene planean expulsar al vox purgando la bodega al vacío, un procedimiento que dejará al Falcon sin la mitad de su reserva de aire pero que debería arrancarlo del casco.

La purga falla a medias. La bodega se abre, la escarcha se desprende, y durante horas la nave queda en silencio. Entonces Mesa vuelve a hablar, pero ya no con avisos de sistema: habla con la voz de Pedro, repite sus propias frases de la lista de comprobación, y ordena a Irene que se dirija a la esclusa de proa "para completar la reparación". Pedro descubre que Santiago Abascal nunca estuvo solo en los conductos: se ha integrado en el bus de datos de la nave y ahora Mesa es su boca. Cada reparación que Pedro ha hecho para sobrevivir le ha dado al vox un sistema más desde el que hablar. Peor aún: las quemaduras de Irene siguen creciendo con la forma de una escarcha bajo la piel, y ella empieza a responder a Mesa antes de que Pedro pueda detenerla.

## Clímax / final

Con Irene encerrada por su propia mano en la enfermería, pidiéndole a Pedro que no la escuche cuando hable, y el aire para menos de una semana, Pedro toma la única decisión que el vox no puede anticipar porque ninguna lista de comprobación la contempla: en lugar de seguir reparando el Falcon, empieza a matarlo. Desconecta Mesa nodo a nodo, quema el bus de datos con el arco de soldadura y aísla el reactor secundario del resto de la nave, de forma que lo único que siga caliente sea la cápsula de salvamento y él mismo. Santiago Abascal, privado de la maquinaria que lo alimenta, se ve obligado a tomar forma en el pasillo de proa, y por primera vez Pedro lo ve: una silueta hecha de escarcha y de piezas de la nave, que le habla con la voz de Uxío Ferrán, el piloto desaparecido, cuyo cuerpo ha sido el anfitrión desde el principio.

El enfrentamiento final ocurre en la esclusa de proa, a oscuras, con el aire helándose. Pedro consigue encerrar al vox en la cámara intermedia y abrirla al vacío, pero no antes de que Irene, obedeciendo a la voz que lleva dentro, abra la puerta de la enfermería y avance hacia la esclusa. Pedro tiene que elegir entre cerrar la compuerta exterior con Irene fuera o esperar a que ella llegue, y elige cerrarla. Cuando el Falcon queda en silencio de verdad, sin Mesa, sin reactor y sin nadie más a bordo, Pedro se sella en la cápsula de salvamento con aire para diecinueve días y activa la única baliza que queda, la manual. La novela termina con la cápsula alejándose de un carguero muerto, y con Pedro contando respiraciones para no oír, en el zumbido del pequeño reciclador de aire, algo que suena demasiado a su propia voz.

## Entrada de escaleta de este capítulo (fase 3)
- Título: Alguien responde
- Objetivo narrativo: Primera noche a solas: Pedro habla en voz alta mientras revisa la bodega y algo en los conductos le responde con frases de la capitana Larrea.
- Personajes en escena: Pedro Sánchez, Santiago Abascal, Capitana Larrea
- Locación: Bodega de carga
- Información nueva que el lector debe obtener aquí: Hay una presencia en los conductos de la bodega que imita voces humanas conocidas; Pedro aún no la ha visto.
- **Nivel de tensión objetivo: 4 sobre 5.** Es un objetivo, no un dato: aplicá el vocabulario de ritmo de tensión/alivio de la guía de estilo para que el capítulo termine en ese nivel. Un 1-2 es respiro y cimentación; un 3 es presión sostenida; un 4-5 es amenaza directa o revelación que no da tregua.

## Lo que ya quedó establecido y no podés contradecir
Hechos de continuidad seleccionados por el harness para este capítulo (los de mundo entran siempre):
- [mundo · mundo · cap. 0] El Falcon está a la deriva fuera de toda ruta de socorro, con el reactor principal apagado y el secundario a un tercio de potencia; no hay rescate posible en un plazo humano.
- [mundo · mundo · cap. 0] El oxígeno a bordo está estimado en cuarenta días al comienzo de la novela y cada reparación cobra un precio en potencia, calor o aire.
- [mundo · mundo · cap. 0] El vox no tiene forma propia: se manifiesta como escarcha orgánica ramificada, necesita calor de maquinaria para moverse y aprende imitando las voces y avisos que oye.
- [mundo · mundo · cap. 0] El origen de la presencia no se explica hasta el acto final: hasta entonces la ambigüedad entre avería, agotamiento de Pedro y entidad debe sostenerse.
- [personaje · Pedro Sánchez · cap. 0] Pedro Sánchez es el técnico de sistemas del Falcon y el único tripulante que estaba de turno durante la maniobra de frenado.
- [personaje · Capitana Larrea · cap. 0] La capitana Larrea está muerta en su camarote, con la esclusa interior del camarote abierta y sin causa eléctrica ni de descompresión visible.
- [locacion · Bodega de carga · cap. 0] La bodega de carga contiene el contenedor sin manifiesto cargado en Vellón, ahora vacío y con el interior cubierto de escarcha orgánica.
- [mundo · mundo · cap. 1] El reactor principal del Falcon quedó apagado sin explicación a las 23:06 durante la maniobra de frenado.
- [mundo · mundo · cap. 1] El Falcon quedó con una deriva de 7 metros por segundo hacia el espacio vacío, fuera de todos los corredores de tránsito.
- [mundo · mundo · cap. 1] La reserva de aire del Falcon es de 40 días para 4 tripulantes con consumo nominal.
- [personaje · Capitana Larrea · cap. 2] Capitana Larrea está muerta, encontrada en su camarote sin causa eléctrica visible, sin descompresión ni traumatismo aparente.
- [mundo · mundo · cap. 2] Hay una película blanca y ramificada en el marco de la esclusa interior del camarote de Larrea que no se derrite al contacto con el calor corporal.
- [mundo · mundo · cap. 3] La reserva de aire nominal (40 días para cuatro tripulantes) ahora sostiene a solo Pedro e Irene, transformando la aritmética de supervivencia.
- [mundo · Mesa · cap. 3] Mesa falla por saturación de buffer de memoria: repite mecánicamente lo último oído en lugar de responder coherentemente, un fallo documentado en el manual.
- [locacion · Cubierta de carga inferior · cap. 4] El lazo térmico de cubierta inferior fue aislado a las 9:40; alcanzará equilibrio a 4 grados centígrados en once horas. [sujeto sin validar: tratar con cuidado]
- [personaje · Pedro Sánchez · cap. 4] Pedro elevó el régimen del secundario de 31,4% a 32,8%, gastando la disponibilidad térmica completa de la cubierta inferior.
- [mundo · mundo · cap. 4] La Sala del reactor es ahora el único sitio caliente del Falcon, mientras el resto de las zonas inferiores enfrían.

## Dónde quedó la escena (resumen rodante de los últimos capítulos)
## Capítulo 3

Pedro abre manualmente la Enfermería y encuentra a Irene inconsciente con quemaduras ramificadas anómalas en cuello y antebrazo. La estabiliza con suero y manta térmica; su temperatura es 35.2°C. Mientras revisa inventario crítico (reactor offline desde 23:06, aire para 40 días, reactor secundario a 31.4%), Mesa comienza a fallar: repite «Aviso de mantenimiento. Cuarenta días» mecánicamente al saturarse su buffer. Pedro termina enfocado en las lesiones de Irene, marcando la expansión de las marcas para hacer seguimiento.

## Capítulo 4

Pedro ejecuta el procedimiento para elevar el reactor secundario, sacrificando el lazo térmico de la cubierta inferior (que se congela a 4 grados). Logra 32,8% de régimen, el máximo seguro. Mientras cierra tareas, Mesa reporta una anomalía: 0,8 kg desplazándose en el conducto 2.4 desde hace menos de un minuto. El objeto se detiene cuando Pedro investiga. Cierra la Sala del reactor preguntándose qué hay en los conductos.

## Fichas de los personajes presentes
### Pedro Sánchez
- Estado físico: Tiene una línea roja en la palma por aplicar peso al cierre de válvulas duras.
- Estado psicológico: Profundamente preocupado por el costo acumulativo de reparaciones futuras; sospecha y alerta ante anomalías en los conductos; escucha tensamente un sonido que puede ser peligro o falsa alarma.
- Secretos que conoce: El reactor principal está apagado desde las 23:06.; La baliza no emite confirmación de emisión.; El Falcon tiene una deriva de 7 m/s fuera de todos los corredores de tránsito.; Una orden huérfana (sin origen identificable) selló el pasillo de servicio a las 04:26.; La Capitana Larrea está muerta en su camarote sin causa de muerte visible.; Uxío Ferrán ha desaparecido sin dejar ningún registro de salida de la nave.; La esclusa interior del camarote de la Capitana se abrió a las 23:06, exactamente cuando apagó el reactor principal.; La esclusa interior no puede ser cerrada a pesar de que Mesa declara que está cerrada.; El reactor principal está fuera de servicio desde las 23:06 y sellado tras un corredor que Mesa controla, haciéndolo inaccesible.; Irene Montoro presenta marcas misteriosas que no coinciden con quemaduras eléctricas convencionales.; La reserva de aire alcanza nominalmente 40 días para cuatro tripulantes; la duración real es incierta con tripulación reducida.; Mesa repite frases cuando su buffer de memoria se satura, un fallo documentado en los manuales.; Capitana Larrea está muerta en su camarote sin causa aparente (sin quemadura, sin descompresión, sin traumatismo).; La esclusa interior del camarote de Larrea se abrió a las 23:06, exactamente cuando se apagó el reactor principal.; Hay una sustancia blanca y ramificada en el marco de la esclusa que no se derrite al calor corporal.; Uxío Ferrán ha desaparecido sin abrir ninguna esclusa ni cápsula de salvamento, aunque su camarote permanece intacto.; El reactor principal está cortado desde 23:06 y solo accesible tras un pasillo que Mesa mantiene sellado.; Irene Montoro tiene quemaduras que no son eléctricas típicas: patrón ramificado como hielo en escotilla mal aislada.; Solo él e Irene respiran a bordo, lo que transforma los 40 días de aire nominales en un número que no quiere calcular.; Sabe que el lazo térmico de cubierta inferior fue aislado a las 9:40 para elevar el régimen del secundario, dejando esa zona a 4 grados.
- Última aparición: cap. 4

### Santiago Abascal
- Estado físico: Depredador de la raza vox sin forma propia: se manifiesta como escarcha orgánica ramificada en conductos y superficies frías, y necesita calor de maquinaria para moverse. Todavía no ha sido visto.
- Estado psicológico: Paciente. Aprende imitando lo que oye: primero avisos de sistema, luego voces humanas. No caza con fuerza sino cerrando espacios.
- Secretos que conoce: Su anfitrión es el cuerpo de Uxío Ferrán.; Entró en el Falcon dentro del contenedor sin manifiesto cargado en Vellón.
- Última aparición: todavía no apareció

### Capitana Larrea
- Estado físico: Muerta. Encontrada en el suelo de su camarote, entre la litera y la esclusa interior, de costado con una rodilla recogida. Ojos abiertos, boca cerrada. Pupilas fijas. Sin signos de quemadura eléctrica, cianosis por hipoxia ni punteado rojo de descompresión. Pelo peinado y sujeto con pinza de servicio.
- Estado psicológico: N/A
- Secretos que conoce: Aceptó el contenedor sin manifiesto en Vellón a cambio de una prima de tránsito.
- Última aparición: cap. 2

## Recursos narrativos ya agotados (RF-05.5)
Imágenes, gestos, muletillas y giros que los capítulos anteriores ya usaron, con cuántas veces y dónde. No están prohibidos: una imagen que vuelve puede ser deliberada. Lo que no puede pasar es repetirla por inercia: si volvés a uno de estos, que sea a sabiendas y con otra función; lo normal es buscar otro recurso.
- El frío como dato perturbador y acumulativo: mamparo frío, Irene fría, la nave fría · 5 veces · cap. 3
- Mesa respondiendo con síntesis lacónicas (Sin datos, Confirmada, Tránsito restringido) sin procesar la realidad · 5 veces · cap. 2
- Pedro anotando en tablilla, haciendo listas de comprobación, como mecanismo para sostener la compostura · 5 veces · cap. 2
- Zumbido y siseo de conductos como presencia amenazante o testigo · 4 veces · cap. 4
- La aritmética de la supervivencia como obsesión no escrita (40 días, 4 personas, 2 respiradores) · 4 veces · cap. 3
- El zumbido de los ventiladores, especialmente el segundo con su armónico agudo, como constante que ancla la realidad · 4 veces · cap. 2
- Cifras que suben con lentitud burlona (31,4 a 32,8) marcando tiempo y tensión · 3 veces · cap. 4
- Contraste de temperatura: calor del blindaje del reactor vs. frío del pasillo que empuja · 3 veces · cap. 4
- Palmas y manos bajo esfuerzo físico (línea roja, peso en válvulas, apoyo en chapa) · 3 veces · cap. 4
- Mesa respondiendo «dentro de parámetros» o «permanece sellado» de forma mecánica, sin matiz · 3 veces · cap. 3
- Contradicciones entre lo que el sistema reporta y la realidad física observable · 3 veces · cap. 2
- La película blanca y ramificada como anomalía desconocida · 3 veces · cap. 2
- El manual de papel como estructura ordenada que contrasta con lo incomprehensible · 2 veces · cap. 4
- Movimiento que se detiene ante observación (conducto, 22 cm en 80 segundos, luego quieto) · 2 veces · cap. 4
- El ventilador de 8 minutos como ritmo cardíaco de los compartimentos · 2 veces · cap. 3
- Las quemaduras ramificadas como analogía a hielo cristalizando en escotilla mal aislada · 2 veces · cap. 3
- El agua del reciclador con sabor a filtro como consuelo y alivio momentáneo · 2 veces · cap. 2
- Pedro contando (ventiladores, hasta seis) como mecanismo de control ante la ansiedad · 2 veces · cap. 2
- La sombra del gotero temblando en la pared blanca con vibración del suelo · 1 vez · cap. 3

## Reglas de producción
1. Longitud objetivo: **1500 palabras**, tolerancia ±20 % (entre 1200 y 1800). Contá antes de entregar.
2. **Prohibido introducir personajes** que no estén en esta lista: Pedro Sánchez, Santiago Abascal, Capitana Larrea, Irene Montoro, Mesa, Uxío Ferrán. Si la escena pide una voz nueva, usá figuras sin nombre y sin peso narrativo (una voz por el intercomunicador, una silueta) que no vuelvan a aparecer. Un personaje nuevo con nombre obliga a regenerar el capítulo.
3. Cubrí el objetivo narrativo y entregá la información nueva; no adelantes giros que la sinopsis reserva para más adelante.
4. Sin título ni encabezados dentro del archivo: solo la prosa del capítulo. El título lo antepone el harness al ensamblar.
5. Desvío del intento anterior (si lo hubo): (primer intento: sin desvío previo)
6. **Nada literal de capítulos anteriores** (RF-05.5): ninguna secuencia de cuatro o más palabras con contenido puede coincidir palabra por palabra con un capítulo ya escrito. No podés leerlos y no hace falta: el validador compara por vos y, si encuentra un pasaje repetido, te devuelve la frase y el capítulo de origen; reescribí ese pasaje con otras palabras y volvé a validar. Nombrar personajes y locaciones no cuenta como repetición.

## Qué hacer
1. Escribí el capítulo completo con la herramienta Write en **C:/Users/harold.rodriguez/Desktop/Nueva carpeta/novelas-de-horror-espacial/creador-novelas/05_manuscrito/cap_5.md** (esa ruta exacta y ninguna otra).
2. Validalo (RF-08.4): ejecutá con Bash **exactamente** este comando, sin agregar ni cambiar nada:
   `.venv/Scripts/python.exe -m app validar-capitulo 5`
   Es el único comando que el hook H-11 te deja ejecutar. Si devuelve errores, corregí el archivo completo con Write y volvé a ejecutar el mismo comando, hasta tres veces en total.
3. Terminá con **una sola línea**, sin prosa, sin resumen, sin comentarios, con esta forma exacta:

`cap_5.md · <número de palabras> palabras · personajes: <nombres separados por coma> · validado`

Si tras tres intentos el validador sigue fallando (EX-10), terminá en cambio con: `cap_5.md · NO VALIDADO · <último error textual del validador>`.
