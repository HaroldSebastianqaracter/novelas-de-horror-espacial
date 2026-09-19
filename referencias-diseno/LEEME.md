# Referencias de diseño para la consola

## Qué hay aquí

`corte-nave.html` — referencia estructural dibujada a propósito para este proyecto.
Se abre en el navegador. **No es el diseño final**: es un esqueleto que enseña la
anatomía que el intento anterior no entendió.

Lo que demuestra, y que es justo lo que falló antes:

- El casco es una **silueta continua e irregular** que envuelve todo. No un rectángulo.
- Los compartimentos son **celdas dentro del casco que comparten pared**. No tarjetas
  flotando separadas.
- Hay **pasillos dibujados** entre compartimentos, con compuertas marcadas.
- Está dibujado en **SVG con trazos de 1px**, no con `div` y `border-radius`.
- El compartimento activo se ilumina **por dentro**, y esa luz **mancha la pared
  compartida y el pasillo**. No es un borde de color.
- Las etiquetas van con **línea guía**, y hay cotas, escala y numeración de cuadernas
  por los bordes.
- La sangre ocupa **menos del 5%** del lienzo. Un solo foco.

## Cómo usarla

Abrí el archivo, hacé una captura, y adjuntala junto al prompt con esta instrucción:

```
Adjunto corte-nave.png como referencia ESTRUCTURAL, no estética.

Tomá de ella exactamente esto:
 · que el casco sea una silueta continua e irregular, no un rectángulo
 · que los compartimentos compartan pared dentro del casco, en vez de flotar
   como tarjetas separadas
 · que esté dibujado en SVG con trazos finos, como un plano de ingeniería
 · que la luz del compartimento activo llene su interior y se derrame sobre la
   pared compartida y el pasillo
 · las anotaciones con línea guía, las cotas de escala y la numeración de bordes

NO la tomes como acabado: está deliberadamente cruda. Quiero tu versión con
mucha más finura de dibujo, más detalle de chapas y refuerzos, mejor jerarquía
tipográfica y una atmósfera más trabajada (viñeta, grano, caída de brillo hacia
las esquinas). La estructura es esta; el acabado es cosa tuya.
```

Y adjuntá también la captura del intento anterior:

```
Adjunto contraejemplo.png: esto es lo que salió y está mal. Tarjetas grises con
esquinas redondeadas, azul pizarra dominante, tres rectángulos iguales flotando
en fila. No quiero nada de eso.
```

## Si añadís imágenes de terceros

Fotogramas, arte conceptual, planos publicados: guardadlos aquí pero **no los
subáis a git**, por el mismo motivo que `00_referencias/` está ignorado. Son
material ajeno y no pertenecen al repositorio.

Y etiquetad qué se toma de cada una. Un montón de imágenes sin instrucción se
promedia; una imagen con instrucción se obedece.
