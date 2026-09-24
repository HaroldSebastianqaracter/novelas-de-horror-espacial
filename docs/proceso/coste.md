# Coste real por novela

Los números de la slide de presupuesto. **Lo medido** sale de la novela de diez capítulos del 24 de septiembre de 2026 (brief de ejemplo, Opus 5.5, copia de solo lectura `novela_10cap_final.db`). Es el `total_cost_usd` que devuelve Claude Code en cada llamada, el mismo que el worker envía a Langfuse como coste de cada generación. **Lo propuesto** (precio, infraestructura, horas y volúmenes) es una estimación razonada que el autor tiene que revisar antes de presentarla: va marcado.

## Lo medido

| Concepto | Valor |
| --- | --- |
| Coste total de la novela | **41,47 $** |
| Llamadas al modelo | 97 |
| Tokens de entrada / salida | 1,29 M / 1,30 M |
| Duración | 3 h 50 min (13:54 a 17:44 UTC), con una parada de 15 min en el capítulo 5 |
| Mayor llamada | 90.764 tokens entre entrada y salida (redacción del capítulo 7), por debajo del techo de 100.000 |

**Por rol:**

| Rol | Llamadas | Coste | Tiempo |
| --- | --- | --- | --- |
| Planner (arquitecto, mundo, elenco, estructura, escaleta) | 5 | 2,33 $ | 18 min |
| Writer (redacción) | 16 | 12,79 $ | 67 min |
| Extractor (story bible) | 16 | 12,13 $ | 66 min |
| Editor (juez de oficio, 3 a 5 votos por intento) | 60 | 14,22 $ | 64 min |

**Por capítulo:**

| | Coste |
| --- | --- |
| Capítulo aprobado a la primera (1, 2, 3, 6 y 9) | 1,54 $ a 4,00 $; media **2,35 $** |
| Intentos rechazados, en total (capítulos 4, 5 y 8) | 14,31 $ (el 35 % del total) |
| Planificación | 2,33 $ |

**Lo que costaría la misma novela sin reintentos:** 2,33 $ + 10 × 2,35 $ ≈ **26 $**. La diferencia con los 41,47 $ reales son los reintentos. La [iteración de tuning](tuning.md) ya los redujo: los rechazos pasaron del 44 % al 14 % de los intentos en la segunda mitad.

## Lo propuesto (a revisar por el autor)

> Todo lo de esta sección son supuestos, no medidas. Tipo de cambio supuesto: **1 $ = 0,92 €**.

**Coste unitario por novela:**

| Partida | Supuesto | €/novela |
| --- | --- | --- |
| Tokens de la generación | 35 $, entre el ideal (26 $) y el medido (41 $) | 32,20 |
| Revisiones del lector | 3 incluidas en el precio; cada una regenera de media unos 2 capítulos, ≈ 5 $ | +13,80 (3 × 4,60) |
| Infraestructura | Servidor, almacenamiento, Langfuse Cloud y PDF, repartidos entre el volumen medio | 1,50 |
| Operación | Soporte y revisión humana de muestreo, aprox. 10 min por novela | 5,00 |
| **Coste unitario** | | **≈ 52,50 €** |

**Precio de venta:** **149 €** por novela, con 3 revisiones incluidas. Es un regalo premium, hecho a medida, con un tiempo de entrega de horas y no de semanas; un libro personalizado de plantilla cuesta entre 30 y 50 €. Margen bruto por novela: 149 − 52,50 ≈ **96,50 € (65 %)**.

**Coste del proyecto de desarrollo** (tarifa supuesta de 60 €/h):

| Fase | Horas | Coste |
| --- | --- | --- |
| Diseño (ontología, specs, arquitectura, validadores) | 80 | 4.800 € |
| Desarrollo (harness, story bible, agentes, API, web) | 220 | 13.200 € |
| Validación (evals, Lean, TLA+, pasadas reales, revisión humana) | 100 | 6.000 € |
| Despliegue (infraestructura, observabilidad, puesta en marcha) | 40 | 2.400 € |
| **Total** | **440** | **26.400 €** |

**Escenarios de volumen** (costes fijos supuestos: 1.500 €/mes de infraestructura base, mantenimiento y atención al cliente):

| Novelas/mes | Ingresos | Coste variable | Fijos | Margen mensual | Recuperar el desarrollo |
| --- | --- | --- | --- | --- | --- |
| 50 | 7.450 € | 2.625 € | 1.500 € | **3.325 €** | 8 meses |
| 200 | 29.800 € | 10.500 € | 1.500 € | **17.800 €** | 1,5 meses |
| 1.000 | 149.000 € | 52.500 € | 1.500 € | **95.000 €** | menos de 1 mes |

**Sensibilidad:**

| Escenario | Coste unitario | Margen por novela |
| --- | --- | --- |
| Base | 52,50 € | 96,50 € (65 %) |
| Tokens +50 % (tokens y revisiones × 1,5) | 75,50 € | 73,50 € (49 %) |
| El cliente pide 6 revisiones (3 más de las incluidas) | 66,30 € | 82,70 € (56 %), o 149 € + 3 × 9,90 € si se cobran aparte |
| Los dos a la vez | 96,20 € | 52,80 € (35 %) |

Hasta con los dos riesgos a la vez el margen sigue siendo positivo. La palanca más fuerte es el tuning: cada punto de reintentos que se quita baja el coste de tokens sin tocar el precio.

## Pendiente

- Contrastar el coste medido con el panel de Langfuse (sesión de la novela) y hacer la captura para la presentación.
- Añadir el coste de las cuatro evals reales cuando terminen: dan cuatro medidas más del coste de la planificación y de un capítulo.
