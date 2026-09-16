# Reporte de QA — corte en el capítulo 3

Muestra leída: capítulos 1, 2 y 3.
Voz verificada: es-ES, tercera persona limitada, tiempo pasado. Los tres capítulos la respetan.

## Contradicciones

Ninguna. Los tres capítulos son compatibles con los hechos vigentes del log (`superado_por: null`).

Verificaciones hechas y su resultado:
- Reactor principal apagado a las 23:06 y bus de control tras un pasillo que Mesa sella: el capítulo 3 lo mantiene; el pasillo se vuelve a sellar en el capítulo 2 tras la reapertura del capítulo 1, así que la clausura está explicada.
- Capitana Larrea muerta en su camarote, sin causa eléctrica ni descompresión: el capítulo 2 lo establece y ningún capítulo posterior la hace actuar. La orden "Capitana Larrea, confirme" la emite Mesa, no el narrador.
- Esclusa interior del camarote abierta de par en par mientras el sistema la reporta cerrada: el capítulo 2 lo sostiene como contradicción interna del sistema, no del log.
- Irene Montoro inconsciente en la enfermería con quemaduras ramificadas en cuello y antebrazo derecho: el capítulo 3 coincide. El registro del capítulo 1 que la sitúa en ingeniería a las 22:52 es anterior en el tiempo y no la niega.
- Enfermería sellada: el capítulo 3 la abre con el husillo manual de emergencia, es decir, alguien la reabre de forma explicada.
- Reserva de aire de 40 días para cuatro tripulantes y secundario a un tercio (31,4 %): coherente en los capítulos 1 y 3.
- Uxío Ferrán desaparecido sin registro de esclusa ni de cápsula: el capítulo 2 lo confirma sin revelar su condición de anfitrión, que no debe descubrirse hasta el capítulo 26.

Observación sin categoría de hallazgo: en el capítulo 2 Mesa declara "Dos cápsulas", mientras que el log de mundo (`cap_origen: 0`) describe una única cápsula de salvamento de una sola plaza. Como la afirmación es de Mesa, sistema establecido como poco fiable, y no del narrador, no se computa como contradicción; se deja anotada para el corte siguiente por si el narrador llega a confirmar el número.

## Repeticiones (umbral: 3 apariciones acumuladas)

1. `repeticion` — Mesa responde con una evasiva fija ("Sin datos", "Aviso de mantenimiento…") en lugar de contestar. 10 apariciones acumuladas en los capítulos 1, 2 y 3. Es el recurso más desgastado de la muestra.
2. `repeticion` — El zumbido o el armónico de los ventiladores cierra la escena tras el momento de tensión. 7 apariciones en los capítulos 1, 2 y 3 (capítulo 1 al abrir y al cerrar, capítulo 2 tras la frase de Mesa, capítulo 3 con el ciclo de ocho minutos).
3. `repeticion` — Estructura de negación en cascada: "No en X, no en Y: en Z" / "No era X. Era Y.". 6 apariciones en los capítulos 1, 2 y 3 (capítulo 3: "No hay ciclo. No hay nadie que lo haya iniciado").
4. `repeticion` — La lista de comprobación o la tablilla como asidero psicológico declarado, con la hora anotada al lado del dato. 5 apariciones en los capítulos 1, 2 y 3 (capítulo 3: el bloc rígido y el punto de tinta con la hora).
5. `repeticion` — La luz ámbar como color único de la emergencia: paneles en espera y mapa de rutas en el capítulo 1, tiras del pasillo en el capítulo 2, letras del sellado en el capítulo 3. 5 apariciones.
6. `repeticion` — Pedro cuenta (segundos, respiraciones, ventiladores) para sostenerse. 4 apariciones en los capítulos 1, 2 y 3.
7. `repeticion` — El agua del reciclador que "sabe a filtro" como prueba tranquilizadora de continuidad. 3 apariciones, una por capítulo; en los tres casos con la misma función consoladora.
8. `repeticion` — La frase literal "El metal estaba frío". 3 apariciones, capítulos 1, 2 y 3.
9. `repeticion` — Las costillas doloridas "del arnés" como recordatorio físico. 3 apariciones, capítulos 1, 2 y 3.
10. `repeticion` — El olor a "plástico tibio". 3 apariciones, capítulos 1 y 2.

Todos los hallazgos de repetición llevan `cap_origen: null`.

## Recursos por debajo del umbral (para el corte siguiente)

- Olor dulce y vegetal a agua estancada: 2 apariciones (capítulos 2 y 3).
- Escarcha blanca ramificada que no se derrite / dibujo que se ramifica: 2 apariciones (capítulos 2 y 3).
- Mesa devuelve como eco la última frase ajena ("Capitana Larrea, confirme"; "Cuarenta días"): 2 apariciones (capítulos 2 y 3).
- Pedro apoya la frente en el metal y respira contando: 2 apariciones (capítulos 2 y 3).

El registro completo queda en `06_qa/recursos_usados.json`.
