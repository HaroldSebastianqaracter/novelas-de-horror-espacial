# Reporte de QA — corte en el capítulo 3

Muestra leída: `05_manuscrito/cap_3.md`
Voz verificada: es-ES, tercera limitada, pasado. Conforme (sin hallazgo de voz).

## Contradicciones

Ninguna. El capítulo respeta los hechos vigentes del log:

- El venteo se fuerza desde el panel auxiliar del pasillo porque Brune cerró la sala de máquinas desde dentro, uso compatible con el hecho de `cap_origen` 0 (el compartimento puede cerrarse desde dentro) y con los mandos del venteo alojados allí.
- Otte habla con la enfermería por el canal mientras el mamparo sigue sellado (`cap_origen` 0 y 1): nadie reabre el compartimento.
- Las muertes de Ivo y Siem y la despresurización de la enfermería concuerdan con los hechos de `cap_origen` 3; los tres supervivientes (Harel, Brune, Otte) son exactamente los que el log deja vivos.
- Lo que Brune afirma sobre el reciclador es habla de personaje, no narración; no se evalúa como contradicción.

## Repeticiones estilísticas

1. **repeticion** — `cap_origen`: null — Estructura "no fue X, fue Y" / "no X, sino Y": reaparece tres veces en el capítulo 3 (la réplica de Brune sobre la paciencia, la conclusión del pasillo de babor sobre el origen de la infección y el cierre sobre extenderse). Acumula 6 apariciones en los capítulos 1, 2 y 3.
2. **repeticion** — `cap_origen`: null — Cierre de escena con una medición anotada: el capítulo 3 vuelve a terminar con Otte anotando la medición del día en su diario clínico. Acumula 4 apariciones en los capítulos 1, 2 y 3.
3. **repeticion** — `cap_origen`: null — Anáfora de negación encadenada: el párrafo del venteo apila negaciones sucesivas (no había empezado en la nave, ninguno había hecho nada, no mintió ni una vez). Acumula 3 apariciones en los capítulos 1 y 3.

Recursos por debajo del umbral o sin aparición en esta muestra quedan registrados en `06_qa/recursos_usados.json` con su conteo intacto.

## Resumen

- Contradicciones: 0
- Repeticiones: 3
