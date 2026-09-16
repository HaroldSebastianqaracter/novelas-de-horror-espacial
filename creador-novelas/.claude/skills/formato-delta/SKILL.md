---
name: formato-delta
description: Esquema DeltaExtraccion con un ejemplo correcto y uno con los errores típicos anotados, para el agente extractor (spec técnica §11.8, §4).
user-invocable: false
---

# Formato del DeltaExtraccion

El delta es exactamente un objeto JSON con cuatro claves: `personajes`, `hechos_nuevos`, `resumen_corto` y `recursos_narrativos` (RF-05.5). Lo escribís en disco con Write, sin texto alrededor, sin bloque de código; el mensaje final es solo la línea de confirmación.

## Ejemplo correcto
Registro de sujetos recibido: personajes `Kovacs`, `Ilse`; locaciones `Puente`, `Bodega 4`; y `mundo`. Capítulo 7.

```json
{
  "personajes": {
    "Kovacs": {
      "estado_fisico": "Brazo izquierdo fracturado e inmovilizado con cinta de presión.",
      "estado_psicologico": "Contenido en apariencia; evita mirar la escotilla de la bodega.",
      "secretos_que_conoce": ["Sabe que el registro de apertura de la Bodega 4 fue borrado a mano."],
      "ultima_aparicion": 7
    }
  },
  "hechos_nuevos": [
    { "sujeto": "Kovacs", "categoria": "personaje", "hecho": "Kovacs se fracturó el brazo izquierdo al cerrar la escotilla de la Bodega 4.", "cap_origen": 7 },
    { "sujeto": "Bodega 4", "categoria": "locacion", "hecho": "La Bodega 4 quedó sellada desde el puente y su atmósfera fue venteada.", "cap_origen": 7 },
    { "sujeto": "mundo", "categoria": "mundo", "hecho": "El sistema de soporte vital reserva oxígeno para 41 días con la tripulación actual.", "cap_origen": 7 }
  ],
  "resumen_corto": "Kovacs e Ilse sellan la Bodega 4 desde el puente tras oír golpes rítmicos en el casco interior.\nKovacs se fractura el brazo en la maniobra y oculta que alguien borró el registro de apertura.\nLa escena termina con ambos en el puente, la bodega venteada y 41 días de oxígeno.",
  "recursos_narrativos": [
    { "recurso": "golpes rítmicos en el casco interior como señal de amenaza", "veces": 3 },
    { "recurso": "Kovacs evita mirar la escotilla (gesto de negación)", "veces": 2 },
    { "recurso": "el zumbido de los ventiladores como coda tras la tensión", "veces": 2 },
    { "recurso": "estructura «No era X. Era Y.»", "veces": 1 }
  ]
}
```

Por qué está bien: cada `sujeto` es un nombre del registro o `mundo`; cada hecho es una oración atómica y nueva; `personajes` trae solo a quien cambió (Ilse aparece pero no cambia, así que no va); el resumen tiene 3 líneas y dice dónde quedó la escena; `recursos_narrativos` describe recursos de prosa reconocibles en otro capítulo, con sus veces en este, y no cuenta para el tope de hechos.

## Ejemplo con los errores típicos (NO hacer esto)

```json
{
  "personajes": {
    "el capitán": { "...": "ERROR 1: la clave no está en el registro; el registro dice Kovacs. Crea una ficha duplicada (EX-08)." },
    "Ilse": { "...": "ERROR 2: Ilse aparece pero no cambia de estado; no va en personajes." }
  },
  "hechos_nuevos": [
    { "sujeto": "Kovacs", "categoria": "personaje", "hecho": "Kovacs es el capitán de la nave.", "cap_origen": 7 },
    { "sujeto": "la bodega", "categoria": "locacion", "hecho": "La bodega quedó sellada y venteada, y Kovacs se rompió el brazo cerrándola.", "cap_origen": 7 },
    { "sujeto": "mundo", "categoria": "mundo", "hecho": "Hay algo afuera.", "cap_origen": 3 }
  ],
  "resumen_corto": "En este capítulo, que empieza con Kovacs revisando... (doce líneas de recuento)"
}
```

- ERROR 3: "Kovacs es el capitán" no es nuevo, es reiteración de algo ya establecido. Solo lo que el capítulo establece por primera vez.
- ERROR 4: "la bodega" no es el nombre canónico (`Bodega 4`); y el hecho junta dos hechos (sellado + fractura) que deben ir separados y con sujetos distintos.
- ERROR 5: "Hay algo afuera" no es verificable; y `cap_origen` debe ser el capítulo actual (el harness lo corrige, pero no lo mientas).
- ERROR 6: el resumen excede las 5 líneas y recuenta en vez de decir dónde quedó la escena.
- ERROR 7 (no visible en el JSON): devolver el JSON envuelto en explicaciones o con el texto del capítulo. El mensaje final es solo el objeto.

## Prioridad cuando hay más hechos que el tope
Irreversibles primero (muertes, pérdidas, sellados, destrucción); después conocimientos adquiridos (quién sabe qué); después estados físicos y psicológicos. Lo que no entre en el tope se queda en el resumen corto.
