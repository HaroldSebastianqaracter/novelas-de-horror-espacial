# Reporte de QA — corte en el capítulo 1

Muestra leída: `05_manuscrito/cap_1.md`
Log de continuidad cruzado: 15 hechos vigentes (`cap_origen` 0 y 1)
Registro de recursos de partida: vacío (primer corte)

## Resumen

- Contradicciones: 1
- Repeticiones: 0
- `tiene_contradicciones`: true

## Hallazgos

### 1. Contradicción — `cap_origen: 0`

**Variante de idioma distinta de la configurada.** La voz de la novela fija `idioma: es-ES`, pero el diálogo del capítulo 1 está escrito en voseo rioplatense (es-AR) de forma sostenida: tres formas verbales voseantes en boca de Yara Bosch y de la capitana Okafor, con imperativos voseados y presente voseante. La narración sí respeta el registro peninsular neutro, de modo que el capítulo alterna dos variantes. Persona narrativa (tercera limitada) y tiempo verbal (pasado) sí se cumplen en todo el capítulo.

## Verificaciones sin hallazgo

- **Continuidad de personajes.** Selene Vargas actúa como única médica a bordo; Inés Okafor decide sobre el confinamiento como capitana; Tomás Reyes informa sobre el sistema de aire como ingeniero responsable; Yara Bosch y Lior Castell aparecen con sus roles y con sus protuberancias móviles. Todo coincide con los hechos de `cap_origen` 0 y 1.
- **Continuidad de locaciones.** La enfermería figura con el único instrumental de la nave; el reciclador se describe como circuito único que abastece proa a popa y se ubica camino de la sala de máquinas. Coincide con `cap_origen` 0 y 1.
- **Continuidad de mundo.** El manual médico no registra casos de masas móviles; la nave está a tres semanas de auxilio; no existe línea de aislamiento total documentada. Coincide con `cap_origen` 0.
- **Orden de confinamiento.** Camarotes cerrados, comida por esclusa y válvulas cerradas: coincide con el hecho de `cap_origen` 1; la imposibilidad de aislar el aire no lo contradice, lo agrava.
- **Repeticiones.** Dos recursos registrados por debajo del umbral de 3 apariciones acumuladas; ninguno alcanza hallazgo en este corte. Quedan anotados en `06_qa/recursos_usados.json` para el corte siguiente.
