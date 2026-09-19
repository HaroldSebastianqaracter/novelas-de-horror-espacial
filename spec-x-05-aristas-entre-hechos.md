# Spec-X 05 — Aristas entre hechos, y un filtro que puntúa

**Estado:** especificado, sin implementar.

## El problema

El filtro que arma el prompt del escritor mira **el sujeto de cada hecho y nada más**:

```python
elif h.sujeto in personajes or h.sujeto == entrada.locacion:
    seleccion.append(h)
```

Así que un hecho sobre Volkov que deja a Ruiz aislada **no llega** al capítulo donde actúa Ruiz. El
escritor no puede preguntar ni leer capítulos anteriores: lo que el filtro no le da, no existe para
él, y escribe a ciegas sobre ello.

El segundo problema es el contrario. Los hechos de categoría `mundo` entran **siempre**, son el 40 %
del total y crecen monótonamente: en el capítulo 30 serían unos 50 hechos ≈ 1.800 tokens ocupando
sitio sin competir por él.

## Lo que NO es el problema

Medido sobre 385 hechos reales de 16 novelas: media de 138 caracteres por hecho, y una novela de 30
capítulos son unos **138 hechos ≈ 5.400 tokens** sobre un presupuesto de 12.000. **Cabe entero.**

Por eso esto no es un grafo con motor de consulta: es una lista corta mal ordenada y mal filtrada.
Ver el informe de investigación del 18/09; GraphRAG y compañía existen para corpus que no caben.

## Los cambios

**1. Un campo en el hecho** (`app/schemas/continuidad.py`)

```python
relacionados: list[str] = []
```

Con valor por defecto, así que los hechos que ya existen siguen validando. Aditivo, no migración.

**2. El extractor lo rellena** (`formato-delta`, `ESQUEMA_DELTA`)

Es el único que lee el capítulo entero, así que sabe a quién toca cada hecho. Se le pide con el
ejemplo explícito: si Volkov sella la esclusa y eso deja a Ruiz aislada, el hecho es de Volkov y
`relacionados` lleva a Ruiz. **Cero llamadas extra**: ya está leyendo el capítulo y ya escribe el
delta. Con X-04 encendido lo rellena el escritor, igual.

**3. Un salto de vecindad en el filtro** (`app/state/continuidad.py`, `filtrar_para_capitulo`)

```python
elif set(h.relacionados) & personajes:
    seleccion.append(h)
```

**4. `mundo` deja de entrar siempre, y el filtro puntúa**

```
score = 3·(sujeto en escena) + 2·(sujeto es la locación) + 1·(relacionado con alguien en escena)
        + peso_categoria + recencia(N − cap_origen)
```

Los de `cap_origen = 0` --el canon del preludio-- entran siempre: son las reglas del mundo que no
cambian. El resto compite. Se corta por presupuesto de tokens y **se ordena la salida por
`cap_origen` ascendente** antes de renderizar, para que el escritor lea una cronología y no un
ranking.

## Pruebas

- Un hecho cuyo sujeto no está en escena pero cuyo `relacionados` sí: hoy no entra, mañana sí.
- Un hecho de `mundo` de un capítulo lejano deja de entrar cuando el presupuesto aprieta, y uno de
  `cap_origen = 0` no.
- Los hechos sin el campo (los 385 que ya existen) siguen validando y siguen entrando por sujeto.
- La salida sale ordenada por capítulo, no por puntuación.

## Por qué los dos juntos

Viven en la misma función. Hacerlos por separado son dos pruebas del mismo filtro y dos novelas de
medición; juntos, una.

## Cómo se mide

`contradicciones` por novela, que es lo que el filtro protege, y `escritor_tokens_salida`. La prueba
de fuego no son 3 capítulos sino **una novela larga**: con 3 capítulos el filtro actual no falla
nunca, porque casi todo entra. Esto se nota a partir del capítulo 10.
