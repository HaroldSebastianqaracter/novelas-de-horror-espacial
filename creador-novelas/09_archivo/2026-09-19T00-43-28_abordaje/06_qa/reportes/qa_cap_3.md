# Reporte de QA — corte del capítulo 3

Muestra leída: capítulos 1, 2 y 3.
Registro de recursos de partida: vacío (primer corte).

## Contradicciones (3)

1. **[contradiccion · cap_origen: 0]** Voz narrativa fuera de la configurada (es-ES).
   El diálogo de los capítulos 1 y 3 usa imperativos voseantes y pronombre de segunda persona rioplatense: cap. 1 "Confirmá tu puesto"; cap. 3 "Sostenela", "salí por el pozo", "Despresurizá"/"Si las despresurizo" en el mismo intercambio. La configuración de idioma es es-ES y la voz se fija antes del capítulo 1, de modo que el registro dialectal mezclado contradice la voz establecida. La tercera persona limitada y el tiempo pasado sí se respetan en los tres capítulos.

2. **[contradiccion · cap_origen: 1]** Bakó tratado como muerto sin que ninguna muerte esté registrada.
   El hecho vigente del log (cap_origen 1) dice que Bakó "fue atacado por la presencia en el pasillo de carga y golpeado contra el mamparo, quedando incapacitado". El capítulo 2 lo da por muerto en la narración, no en boca de un personaje: "Eran cuatro de pie y uno abajo que ya no respiraba de esa manera", y la cuenta de aire de cinco cuerpos solo cuadra si Bakó no respira (cuatro tripulantes en pie más la presencia). El capítulo 3 lo confirma al cerrar con "dos muertos". Incapacitado y muerto no son el mismo estado y ningún hecho del log registra el paso de uno a otro.

3. **[contradiccion · cap_origen: 3]** Circunstancias de la muerte de Sadhu incompatibles con el hecho registrado.
   El hecho vigente (cap_origen 3) establece que "Sadhu muere sellado en la Cubierta de máquinas del Amanecer Tardío cuando Ilesanmi cierra las bandas de comunicación tras descubrir que él tecleaba la esclusa". El capítulo 3 narra otra cosa como cierta: Sadhu —mujer en todo el texto, "una cifra que ella sabía leer de memoria" en el cap. 2— muere sosteniendo a mano la secuencia de despresurización por orden de Vinter, y la línea se corta sola ("La línea se cerró con un chasquido seco"); Ilesanmi no cierra ninguna banda, al contrario, las **abre** después de esa muerte ("volvió a abrir las tres bandas"). Además, quien afirma que la esclusa se tecleó desde máquinas es la propia Sadhu en diálogo, mientras el hecho vigente de cap_origen 2 atribuye el ciclo a Bakó desde la consola de carga: la línea de Sadhu queda como afirmación de personaje, no como hecho narrado.

## Repeticiones estilísticas (5)

1. **[repeticion]** Estructura de negación/corrección "No X. (Sino) Y." — 4 apariciones, capítulos 2 y 3: cap. 2 "no llegó de proa. Llegó de popa"; cap. 3 "No con voz. Con una cadena de tonos", "No habían acorralado a un animal. Habían escoltado a un huésped", "se cerró con un chasquido seco, no con un grito".

2. **[repeticion]** Atenuación por "sin + infinitivo" para describir gestos y órdenes — 6 apariciones, capítulos 1, 2 y 3: cap. 1 "firmó el parte sin leerlo entero", "dijo, sin dramatismo"; cap. 2 "dijo Vinter, sin subir la voz"; cap. 3 "dio la orden sin levantar la voz", "se hubiera desprendido sin prisa". El tic marca casi todas las intervenciones de Vinter.

3. **[repeticion]** Símil hipotético con "como si" / "como quien" — 3 apariciones, capítulos 1, 2 y 3: cap. 1 "ocupando el espacio entre los contenedores como si lo hubiera medido antes"; cap. 2 "Lo dijo despacio, como quien lee una avería"; cap. 3 "como si algo enorme se hubiera desprendido sin prisa".

4. **[repeticion]** Cierre de escena con sentencia breve del narrador que glosa lo anterior — 3 apariciones, capítulos 1, 2 y 3: cap. 1 "Kerr lo sabía mejor que ninguno"; cap. 2 "Solo ocupaba lo que ellos le iban dejando"; cap. 3 "Eso fue lo peor: que no hiciera nada".

5. **[repeticion]** Tríada asindética de sustantivos técnicos como golpe de ritmo — 3 apariciones, capítulos 1, 2 y 3: cap. 1 "Hora, clave, consola"; cap. 2 "figuraba con su hora, su clave y su origen"; cap. 3 "bombas, pozo central, puente".

## Recursos registrados por debajo del umbral

- El silencio que pesa más que el ruido — 2 apariciones (caps. 1 y 3).
- Los sensores que "no leen calor" / "leen vacío en todas las bandas" — 2 apariciones (caps. 1 y 3).
- La apertura ritual de las tres bandas de emergencia "por academia" — 2 apariciones (caps. 1 y 3).

Detalle acumulado en `06_qa/recursos_usados.json`.
