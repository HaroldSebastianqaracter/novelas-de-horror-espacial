# Reporte de QA — corte en el capítulo 1

Muestra leída: `05_manuscrito/cap_1.md`
Log de continuidad cruzado: 19 hechos vigentes (`superado_por: null`), `cap_origen` 0 y 1.
Registro de recursos de partida: vacío (primer corte).

## Voz narrativa

- Idioma es-ES, tercera persona limitada, tiempo pasado: el capítulo los respeta. La narración va en pasado (`dijo`, `anotó`, `empezó`, `siguió`) y en tercera limitada, sin saltos a primera ni a presente fuera del diálogo. No hay hallazgo de voz (`cap_origen` 0).

## Contradicciones

Ninguna.

Verificaciones hechas contra hechos vigentes del log, todas conformes:

- Dotación de cinco operarios (`cap_origen` 0): en escena aparecen exactamente Ivet Karam, Domas Feller, Renke, Sol Abadie y Tobi Wren.
- Relevo dentro de seis días (`cap_origen` 0): Tobi cuenta «seis» al abrir y lo repite antes del cierre.
- Once días de noche cerrada y ciento ochenta bajo cero al otro lado del casco (`cap_origen` 0): ambos datos se citan sin alterarse.
- Cuatro horas desde el corte de calefacción hasta igualar la temperatura exterior (`cap_origen` 0): es el cálculo que hace Domas Feller, y es él quien lo hace, como corresponde al técnico térmico.
- Fuera del núcleo habitable se trabaja con traje (`cap_origen` 0): la ronda al módulo C se hace con traje y con guante térmico.
- Renke es quien abre las rejillas (`cap_origen` 0) y es mordido en el dorso de la mano a través del guante, con corte por alicate (`cap_origen` 1): coincide con la escena.
- Ivet Karam lleva el registro de turno y decide sobre el calor (`cap_origen` 0): anota la hora, ordena abrir y ordena la retirada al núcleo.
- Sol Abadie lleva enfermería y comunicaciones (`cap_origen` 0): asiste a Renke.
- La cabeza seccionada sigue mordiendo varios minutos y el cuerpo separado se encoge inerte con el frío (`cap_origen` 1): el texto lo muestra así.
- Las criaturas siguen el calor, no a las personas (`cap_origen` 1): lo enuncia Sol como lectura de la escena y el narrador no lo desmiente.

Nota de criterio: la réplica de Domas «Dilatación» es una hipótesis equivocada de un personaje dentro de la ficción y el propio texto la desmiente acto seguido; no es contradicción del log.

## Repeticiones

Ninguna alcanza el umbral de 3 apariciones acumuladas en este corte.

Recursos registrados por debajo del umbral, para el corte siguiente (ver `06_qa/recursos_usados.json`):

- El arrastre de los conductos comparado con grava empujada — 2 apariciones (cap. 1).
- Párrafo de una sola frase corta usado como golpe de tensión — 2 apariciones (cap. 1).
- Estructura «No fue X. Fue Y.» — 1 aparición (cap. 1).
- Repetición triple de una palabra para marcar monotonía («rutina, rutina, rutina») — 1 aparición (cap. 1).
- El frío como agente que apaga o desactiva un cuerpo — 1 aparición (cap. 1).
- El silencio de los demás como respuesta significativa — 2 apariciones (cap. 1).

## Resumen

- `tiene_contradicciones`: false
- contradicciones: 0
- repeticiones: 0
