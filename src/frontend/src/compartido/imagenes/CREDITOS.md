# Imágenes de la web: procedencia y tratamiento

Requisitos en [spec-frontend](../../../../../specs/spec-frontend.md), sección 3.14 (RF-FE-IMG). Ninguna imagen lleva texto, logotipos ni caras reconocibles.

## Portadas (estilo B: papel A5, hueco para el título y foto en duotono de tinta con un acento de rojo óxido)

| Fichero | Subgénero | Origen | Tratamiento |
| --- | --- | --- | --- |
| `portada-generica` | Sin subgénero | Generada por el autor con Gemini (una llave con un hilo rojo) | Recorte a A5 |
| `portada-supervivencia` | `supervivencia` | NASA, [S84-27031](https://images.nasa.gov/details/S84-27031): paseo espacial con la MMU sobre la Tierra (STS 41-B) | Duotono, sin acento |
| `portada-horror_cosmico` | `horror_cosmico` | NASA, [art002e016318](https://images.nasa.gov/details/art002e016318): «Orion and the Eclipse» (Artemis II) | Duotono; el anillo de diamante del eclipse, en rojo |
| `portada-slasher_espacial` | `slasher_espacial` | NASA, [KSC-03pd1886](https://images.nasa.gov/details/KSC-03pd1886): interior del módulo de fabricación italiana en el centro de procesado | Rótulos de dirección («To JEM», «To PMA2»…) y placa «CLOSED» borrados, y un suavizado leve contra la letra diminuta; duotono; la luz del fondo del pasillo, en rojo |
| `portada-terror_corporal` | `terror_corporal` | NASA, [iss065e282008](https://images.nasa.gov/details/iss065e282008): trajes EMU en la esclusa de la ISS | Recorte que deja fuera la etiqueta «3015» y el cartel de la pared; insignia de misión, código de barras y etiquetas «EV1» borrados; el visor, en rojo |
| `portada-ia_hostil` | `ia_hostil` | NASA, [NHQ202410240004](https://images.nasa.gov/details/NHQ202410240004): Robonaut 2 en el NASM | Duotono; el visor, en rojo |
| `portada-infeccion` | `infeccion` | NASA, [jsc2026e034367](https://images.nasa.gov/details/jsc2026e034367): placa de cultivo | Recorte por encima de la rotulación a mano; las colonias, en rojo |

Los borrados se hacen por difusión (la zona se rellena con el promedio de sus vecinos) y con el detalle fino de la tela o el panel de al lado, para que no quede un parche liso.

Cada portada va en dos tamaños: `-web` (874 × 1240) para la pantalla y la completa (1748 × 2480, A5 a 300 ppp) para la vista de impresión y el PDF.

## Planos (estilo A: trazo cianotipo `#2B4C7E` sobre blanco, que se funde con el papel de cada pantalla por `multiply`)

| Fichero | Dónde | Origen | Tratamiento |
| --- | --- | --- | --- |
| `plano-nave` | Cabecera de «Personajes y lugares» | NASA, [S73-24316](https://images.nasa.gov/details/S73-24316): corte del taller orbital de Skylab | Girado, trazo extraído por bordes y pasado a cianotipo |
| `cabecera-consola` | Cabecera del tablero general | Generada por el autor con Gemini | Recorte de la fila superior a 4:1 |

## Dibujos SVG (trazo `currentColor`, pintados por máscara CSS)

| Fichero | Dónde | Origen |
| --- | --- | --- |
| `parada.svg` | Cabecera de la alerta de parada | Redibujado a mano: el que generó Gemini se leía como un altavoz silenciado a 40 px |
| `vacio-tablero.svg` | Tablero sin novelas | Generado por el autor con Gemini, sin retocar salvo los comentarios |
| `sin-senal.svg` | Ruta desconocida | Generado por el autor con Gemini, sin retocar salvo los comentarios |
| `crear-novela.svg` | Alta de novela, en pantalla estrecha | Generado por el autor con Gemini, sin retocar salvo los comentarios |

## Sobre las imágenes de la NASA

El material de la NASA no tiene, en general, derechos de autor ([NASA Images and Media Usage Guidelines](https://www.nasa.gov/nasa-brand-center/images-and-media/)). Las condiciones que se respetan aquí: no se usa el logotipo ni la insignia de la NASA, ninguna imagen da a entender que la NASA respalda el producto, y no aparece ninguna persona reconocible.
