# Iteración de tuning: las cuentas del redactor

Una iteración documentada con resultados antes y después, como pide la entrega (sección 5, *Evaluación del sistema*). Sale de la novela de diez capítulos del 24 de septiembre de 2026 (brief de ejemplo, Opus 5.5). El cambio es RF3-PAS-18 de [spec3](../../specs/spec3.md), commit `82289a2`, y su entrada es la 65 del [registro de iteraciones](registro-iteraciones.md).

## El problema

El juez de oficio de la puerta 4 rechaza un capítulo si una cifra derivada no cuadra con el canon (criterio `cuentas_cuadran`, RF3-PAS-12). La novela gastó intentos en eso una y otra vez, y el capítulo 5 **paró** tras tres rechazos, cada uno por una cuenta distinta y real:

1. el carguero llega «el día 140» y la prosa decía que faltaban ciento cuarenta días, cuando ya habían pasado semanas;
2. la protagonista explicaba una diferencia de dos décimas de CO₂ con una cuenta que daba nueve centésimas;
3. contaba «tres líneas» anotadas en la manga cuando el canon ya tenía cuatro, de capítulos anteriores.

Diagnóstico, medido sobre el paquete real del capítulo 5:

- en los tres casos el dato **estaba** en el paquete del redactor: el fallo era derivar la cifra sin hacer la cuenta;
- además, **34 de las 66 cifras** con las que el juez comprobaba la prosa no llegaban nunca al redactor (`hechos_del_reparto` solo trae las del reparto), y otras 5 eran opcionales al final del bloque, las primeras en caer al recortar.

## El cambio

- El paquete del redactor lleva la sección **Cifras establecidas**: las mismas cifras que comprueba el juez, leídas de la misma función (`lectura.hechos_con_cifras`), delante de los hechos sin cifra para que el recorte no las toque.
- La regla «No descuadras una cuenta» de la skill del redactor nombra las tres cuentas que fallaron (resta desde el momento de la escena, recuentos acumulados entre capítulos, operaciones que dan lo que dicen) y pide decir la cifra sin número si no se puede hacer la cuenta.

Es un cambio de **prompt y de contexto**, no de puertas: el juez sigue igual, así que antes y después se mide con el mismo instrumento.

## La versión del prompt en Langfuse

Cada skill se registra en Langfuse como prompt versionado por la huella de su texto (RF3-OBS-06), y cada generación enlaza la versión que la produjo:

| Prompt | Antes | Después |
| --- | --- | --- |
| `storymaker-redaccion` | **versión 5** (`sha-7af505b6c97b`), llamadas 6 a 52 | **versión 6** (`sha-b6f493f4d707`), desde la llamada 57 |
| `storymaker-oficio` (el juez) | versión 2 | versión 2, sin cambios |

## Resultados

Mismo brief, misma novela, mismo juez. «Antes» son los capítulos 1 a 5 con el redactor v5; «después», el capítulo 5 relanzado y los capítulos 6 a 10 con el v6.

| Métrica (puerta 4) | Antes (v5) | Después (v6) |
| --- | --- | --- |
| Capítulos intentados | 5 | 6 |
| Intentos de redacción | 9 | 7 |
| Intentos por capítulo aprobado | 1,5 (6 para 4 capítulos), y uno sin aprobar | **1,17** (7 para 6) |
| Capítulos aprobados a la primera | 3 de 5 | **5 de 6** |
| Intentos rechazados por `cuentas_cuadran` | **4 de 9 (44 %)** | **1 de 7 (14 %)** |
| Paradas | 1 (capítulo 5) | **0** |
| Coste de los intentos rechazados | **11,44 $** (capítulo 4, intentos 1 y 2: 4,77 $; capítulo 5, los tres intentos: 6,67 $) | **2,87 $** (capítulo 8, intento 1) |

El capítulo 5, que había parado tras tres intentos, **pasó a la primera** con el v6, por unanimidad del juez.

## Lo que este resultado no demuestra

- **Muestra pequeña y sin control:** 16 intentos, capítulos distintos antes y después, y un canon que crece con la novela, lo que en principio hace la segunda mitad *más* difícil, no más fácil.
- **El juez es probabilístico:** un mismo capítulo puede pasar o fallar las cuentas en llamadas distintas (RF3-PAS-12). Se mitiga con votos, pero no desaparece.
- **Hubo otro cambio a la vez:** el worker relanzado corría también las correcciones de seudonimización y de elementos obligatorios, que no tocan las cuentas.
- **El único rechazo posterior fue otra vez una cuenta** (capítulo 8: la pendiente multiplicada por 1,3), junto con dos criterios de estilo. El v6 reduce el problema, pero no lo elimina: la comprobación determinista de cifras (el punto ciego C12 del banco) sigue pendiente.

Los números salen de `resultado_puerta` y `llamada_modelo` de la copia de solo lectura `novela_10cap_final.db`; el coste es el `total_cost_usd` que devuelve Claude Code en cada llamada, el mismo que llega a Langfuse.
