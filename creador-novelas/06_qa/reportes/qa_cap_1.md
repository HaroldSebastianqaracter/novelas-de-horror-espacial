# Reporte de QA — corte en el capítulo 1

Muestra: `05_manuscrito/cap_1.md`
Voz verificada: es-ES, tercera limitada, pasado — conforme.

## Hallazgos

### 1. Contradicción (cap_origen: 0)
El narrador afirma como cierto que la caligrafía del libro es «la misma mano tranquila que las once mil noches anteriores». Once mil noches son unos treinta años de registros, mientras que el hecho vigente de `cap_origen` 0 establece que el libro de guardias lleva **once años** de turnos anotados sin un solo hueco (unas cuatro mil noches) y que la colonia fue evacuada hace once años. No es un personaje equivocándose: es la voz narrativa la que fija la cifra.

### 2. Repetición (cap_origen: null)
Personificación cortés o doméstica de lo mecánico: «temperatura de habitación ocupada», «un chasquido educado», «la misma mano tranquila». 3 apariciones acumuladas, todas en el capítulo 1.

### 3. Repetición (cap_origen: null)
Estructura de negación «sin + sustantivo» para describir perfección o ausencia: «sin pedirles nada», «el soporte vital sin una caída», «sin un solo trazo dudoso». 3 apariciones acumuladas, todas en el capítulo 1.

### 4. Repetición (cap_origen: null)
Repetición léxica dentro de la misma frase como remate: «Ferrán entró primero, porque le tocaba entrar primero», «decía Ferrán, decía Vlach, decía Ospina», «Trabajaron cuatro horas y fue un alivio trabajar». 3 apariciones acumuladas, todas en el capítulo 1.

## Verificaciones sin hallazgo
- Compuerta sellada que se abre con la palma de Vlach: conforme al hecho de `cap_origen` 1; no es puerta abierta sin explicación.
- Mamparos inferiores cerrándose solos a las 21:12 sin intervención: conforme a `cap_origen` 1.
- Soporte vital, luz de emergencia y comida sin caducar tras once años: conforme a `cap_origen` 0.
- Nombres de los tres supervivientes en fechas futuras: conforme a `cap_origen` 0 y 1.
- Brazo entablillado de Ferrán y su fijación con el transmisor: conforme a `cap_origen` 0.
- La hipótesis de Ferrán en voz alta («aquello era un temporizador») y la de Vlach («alguien vive aquí») son juicios de personaje, no afirmaciones del narrador: no cuentan como contradicción.

Contradicciones: 1 · Repeticiones: 3
