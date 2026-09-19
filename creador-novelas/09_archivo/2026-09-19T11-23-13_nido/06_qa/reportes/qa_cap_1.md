# Reporte de QA — corte en el capítulo 1

Muestra leída: `05_manuscrito/cap_1.md`
Log de continuidad cruzado: 14 hechos vigentes (`superado_por: null`), de `cap_origen` 0 y 1.
Registro de recursos de partida: vacío (primer corte).

## Contradicciones

Ninguna.

Comprobaciones hechas contra hechos vigentes del log, todas conformes:

- Reyes actúa como capitana y ordena a la cuadrilla (hecho de `cap_origen` 0). Conforme.
- Okafor conoce el trazado del depósito «de memoria» y es quien nota la anomalía (`cap_origen` 0). Conforme.
- Sol es quien baja a revisar el tanque (`cap_origen` 0). Conforme.
- Ibarra repasa de memoria el protocolo antes de aplicarlo (`cap_origen` 0). Conforme.
- Vance, desde soporte vital, reporta medio punto de humedad relativa por encima de lo normal y en ascenso en los ramales de los sectores tres y cuatro (`cap_origen` 1). Conforme, mismas cifras y mismos sectores.
- El texto niega la fuga por boca de Vance y el narrador no la contradice; el hecho «no se detectó ninguna fuga que explique el exceso de humedad» (`cap_origen` 1) queda intacto.
- Los sensores no registraron ninguna entrada ni variación en las reservas tratadas (`cap_origen` 0, dos hechos). Conforme: la pantalla informa «normalidad perfecta».
- La pared del anillo dos aparece tapizada de cientos de vainas del tamaño de un puño, la mayoría rasgadas desde dentro y vacías (`cap_origen` 1). Conforme, aunque el capítulo las nombra «bolsas» y no «vainas»: es variación léxica, no contradicción.
- Okafor rompe una de las vainas con el guante al comprobar su consistencia (`cap_origen` 1). Conforme.

Voz narrativa: tercera persona limitada, tiempo pasado, es-ES (uso peninsular coherente: «subid»). Sin hallazgo de voz.

## Repeticiones estilísticas

1. **[repeticion]** `cap_origen`: null — Describir por negación: el capítulo establece lo que ocurre enumerando lo que no ocurre. En el capítulo 1: «Nada en los registros de mantenimiento pedía otra cosa», «la superficie del anillo dos no devolvía la luz como debía», «un color que la linterna no terminaba de decidir», «y no dijo nada más», «Ninguna alerta. Ningún registro de entrada. Ninguna variación», «Los sensores no vieron llegar nada», «No hay fuga». Siete apariciones acumuladas, todas en el capítulo 1. El recurso funciona la primera vez y se vuelve previsible al concentrarse tanto en un capítulo corto.

2. **[repeticion]** `cap_origen`: null — La linterna y su haz como instrumento que revela lo que hay: aparece en la bajada de Sol, al acercar el haz a la pared, al describir el color que la luz «no termina de decidir» y al cerrar con Sol barriendo la pared. Cuatro apariciones acumuladas, todas en el capítulo 1. Conviene alternar la fuente de la revelación en capítulos siguientes.

## Registro de recursos

Actualizado en `06_qa/recursos_usados.json`. Quedan por debajo del umbral y sin enumerar aquí: la imagen de la cáscara seca para las vainas (2), el símil de color orgánico ámbar/hueso (1) y la acotación de tono plano o contenido en diálogo (2).

## Resumen

- Contradicciones: 0
- Repeticiones: 2
