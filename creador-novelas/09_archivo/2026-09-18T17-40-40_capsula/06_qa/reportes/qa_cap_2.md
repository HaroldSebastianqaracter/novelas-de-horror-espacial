# Reporte de QA — corte en el capítulo 2

Muestra leída: `05_manuscrito/cap_2.md`.
Voz verificada: es-ES, tercera limitada, pasado. Conforme (sin hallazgo de voz).

## Hallazgos

### 1. Contradicción — `cap_origen: 0`
El capítulo 2 establece como cierto, por narrador y no por boca de un personaje, que Mkhari
encuentra "entre la bodega y la sala de máquinas un tramo de pasillo de servicio", dos metros y
medio de mamparo con juntas idénticas a las suyas, y que los planos no lo recogen.
Hecho vigente contradicho (`cap_origen` 0, `superado_por: null`): "Entre la bodega y la sala de
máquinas no hay ningún pasillo de servicio: los planos de a bordo no registran ninguno."
El hecho de origen niega la existencia del tramo, no solo su documentación; el capítulo lo afirma
como espacio físico existente. La contradicción se señala, no se corrige.

### 2. Repetición — `cap_origen: null`
Recurso: definición por acumulación de negaciones y ausencias ("No era X", "sin A, sin B, sin C").
Apariciones acumuladas: 8 (capítulos 1 y 2). En esta muestra: "Fenn lo apoyó sin convicción",
"una voz sin dueño", "sin incidencias", "con el sello intacto y sin una marca nueva en el casco",
más el cierre "No la habían rescatado. La habían recibido.".

### 3. Repetición — `cap_origen: null`
Recurso: párrafo de una sola frase breve, aislado, como pivote o remate de escena.
Apariciones acumuladas: 4 (capítulo 2). En esta muestra: "Sacar la cápsula.", "Y sucedían.",
"Cinco nombres, los suyos.", "No la habían rescatado. La habían recibido.".

### 4. Repetición — `cap_origen: null`
Recurso: dato técnico de precisión exacta usado como vehículo del horror.
Apariciones acumuladas: 4 (capítulo 2). En esta muestra: "dos metros y medio", "en el minuto
exacto... y del modo exacto", "el canal llevaba once minutos cerrado", "corrigió rumbo tres veces
en cuarenta horas".

## Recursos por debajo del umbral o sin aparición en este corte
No se enumeran como hallazgo, pero siguen contabilizados en `06_qa/recursos_usados.json`:
símil con fórmula "como/de quien + oración" (4, cap. 1, sin aparición en el corte); la nave como
cuerpo que sufre (2, cap. 1, sin aparición); el dinero del salvamento como primera reacción de
Beas (1, cap. 1, sin aparición); el personaje que verifica y luego deja de verificar (1, cap. 2).

## Resumen
- Contradicciones: 1
- Repeticiones: 3
- `tiene_contradicciones`: true
