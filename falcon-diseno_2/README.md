# El casco frío del Falcon — direcciones de diseño

Herramienta de escritorio web que genera novelas de terror espacial con un equipo de agentes (Orquestador, Escritor, Extractor de hechos, Revisor de calidad). El usuario encarga, vigila y lee; no escribe. El diseño transmite vigilancia, no productividad: la máquina es lenta, cuesta dinero real y puede detenerse con un veredicto en contra.

## Contenido de la carpeta

- `html/` — una maqueta autónoma por dirección. Se abren con doble clic, sin dependencias externas, todo el CSS y el SVG en línea. Cada una tiene un único momento de movimiento que responde a una acción del usuario.
- `lienzo/project/` — las mismas pantallas como mesas de trabajo estáticas del lienzo de Diseño de Claude (`*.dc.html` + `canvas.json`). Son versiones sin interacción; la referencia es siempre `html/`.
- `referencia/` — capturas que guiaron el lenguaje visual de la dirección 1 y la atmósfera de las 2 a 4 (pantalla de carga con plano de nave en alambre; traje de metal oxidado con visor cian). No se ha copiado ninguna forma registrada: la nave, la barra de vida y el plano son dibujos propios.

## Pantallas del producto

1. Entrada — elegir entre novelas en marcha, terminadas o canceladas, o empezar una nueva.
2. Encargo — premisa, número de capítulos, tono, obras de referencia, firma.
3. Producción — qué agente está activo, capítulo actual de 30, registro de eventos, parada del revisor.
4. Lectura — la novela terminada, capítulo a capítulo, con lo que el Extractor fijó al margen.

## Direcciones

### Dirección 1 — Sala de máquinas (Producción) · `html/direccion-1-sala-de-maquinas.html`

Concepto: la producción es un plano en alambre del Falcon sobre un tubo apagado con barrido de líneas. Cada agente es una cubierta que se ilumina cuando trabaja; el ramal seis de inspección se enciende en rojo cuando el Revisor detiene la nave. Título del capítulo en marco con esquinas en escuadra; «Detenido...» con marcas de progreso arriba a la derecha; indicadores en línea (capítulos, gasto, tiempo); veredicto en el marco inferior; registro de a bordo.

Paleta: Pantalla `#0A0D10`, Alambre `#93A6B9`, Costilla `#3B4652`, Texto `#C9D3DC`, Cubierta en marcha `#7BE3B2`, Hechos `#E39BC4`, Inspección `#E0483C`.
Tipografía: una sola grotesca condensada (Arial Narrow / Helvetica Neue) con numerales tabulares; etiquetas con doble barra `//`.
Retícula: cabecera, plano a todo el ancho, tres indicadores, pie de dos columnas (veredicto 1fr, registro 420 px).
Movimiento: «Reanudar bajo mi responsabilidad» apaga el ramal rojo y reenciende puente, redacción y bodega en orden escalonado.

Decisión del cliente: esta pantalla conserva su paleta de pantalla de carga. Sobre ella se han añadido efectos de luz de a bordo: los bloques activos de la nave parpadean (el ramal en parada late en rojo con patrón de emergencia; en marcha, cada cubierta respira a su ritmo), una banda de barrido de tubo recorre la pantalla, un haz rojo cruza en diagonal, el brillo cae a ratos como en un tubo viejo, el plano brilla como holograma y sus etiquetas titilan, los marcos respiran con halo y los puntos de «Detenido...» se escriben uno a uno. Todo se desactiva con `prefers-reduced-motion`.

## Sistema visual compartido por las direcciones 2, 3 y 4 (terror oscuro)

Las tres pantallas comparten una misma atmósfera cinematográfica, definida en el bloque `:root` y las clases `.atm-*` de cada archivo: negro casi absoluto y frío como base, un foco halógeno cálido que cae desde arriba a la izquierda, un sangrado de luz roja de emergencia por el borde derecho, viñeta en los bordes, grano de película (filtro SVG `feTurbulence`) y motas de polvo en suspensión. La interfaz se apoya en líneas finas semitransparentes en lugar de bordes sólidos, y los paneles son vidrio ahumado. Encima se añade un haz de luz volumétrico desde el foco (gradiente cónico), un filo rojo luminoso en el borde derecho, costillas de mamparo muy tenues al fondo, y un texto fantasma enorme en serif itálica, solo contorno, detrás de cada cabecera (el número de orden, el número de capítulo, la palabra «Vestuario»). Los títulos van en serif itálica color halógeno con halo; los botones principales son vidrio con el filo superior iluminado. Además, la luz roja del fondo es un fluido: la capa `.atm-sangre` (mancha roja desplazada por un filtro SVG `feTurbulence` + `feDisplacementMap`) fluye muy despacio por el borde derecho, con un ciclo de 32 s en CSS y otro de 46 s en el ruido del filtro, ambos sin saltos. Es la única animación ambiental; se desactiva por completo con `prefers-reduced-motion` (CSS y SVG) y en las mesas del lienzo aparece congelada. El resto sigue igual: una sola animación por pantalla que responde a una acción.

Paleta común: Abismo `#06070A`, Acero `#0E1116`, Acero alto `#161B22`, Hilo `rgba(214,218,216,.14)`, Niebla (texto) `#D6DAD8`, Niebla baja `#8A9399`, Halógeno `#E8D9B5`, Emergencia `#B3261E`, Fósforo (lo que fija la máquina) `#A8D8C8`.
Tipografía común: serif antigua (Iowan Old Style / Palatino / Georgia) en itálica para títulos y para lo que escribe la persona; Helvetica / Arial para la interfaz.

### Dirección 2 — Orden de trabajo (Encargo) · `html/direccion-2-orden-de-trabajo.html`

Concepto: encargar una novela es firmar una orden de trabajo que no admite correcciones. El impreso está bajo un flexo en una sala a oscuras: lo que la máquina imprime en gris niebla, lo que el usuario rellena en serif «a mano» color hueso, con la luz halógena cayendo sobre la cabecera y una pinza metálica de tablilla sujetando la hoja por arriba. Los capítulos se cuentan con palotes tachados de cinco en cinco; el tono se marca con aspas; los cuatro agentes firman en una tabla de personal, y solo el Revisor tiene una potestad en rojo: detener la producción. Coste, tiempo y puntos de parada, anotados a lápiz en el margen.

Paleta: la común de terror oscuro (véase arriba); el tampón «Recibido» y las marcas del revisor en rojo de emergencia con halo.
Tipografía: Helvetica / Arial 13–14 px para lo impreso; Georgia / Iowan Old Style 17 px para lo escrito por la persona; firmas en trazos SVG.
Retícula: hoja de ~860 px con etiquetas en columna de 168 px; margen de anotaciones de 300 px.
Movimiento: al firmar cae el tampón «Recibido» y la hoja se bloquea.

### Dirección 3 — Lectura en la oscuridad (Lectura) · `html/direccion-3-luz-de-emergencia.html`

Concepto: la lectura ocurre en la oscuridad; un foco cálido cae sobre la columna de texto y el resto de la pantalla queda en sombra, con la luz roja del ramal seis sangrando por la derecha. El título del capítulo en serif itálica color halógeno; costillar de capítulos en hilos finos, el actual encendido en halógeno y la pausa del revisor en rojo. La capital del primer párrafo es una letra grande en halógeno, la cabecera cierra con una regla que termina en un piloto rojo, y la frase escrita en el mamparo va centrada con un charco de luz roja detrás. El margen del Extractor es un panel de vidrio ahumado; sus hechos van en fósforo apagado y el conflicto en rojo. Columna de texto de 66 caracteres; margen con los hechos fijados (`//Vlk`, `//El cortador`...) y el conflicto en rojo.

Paleta: la común de terror oscuro.
Tipografía: serif antigua (Iowan Old Style / Palatino / Georgia) 20 px para el cuerpo; grotesca condensada 12,5–14 px para interfaz y marginalia.
Retícula: costillar 120 px | texto 66ch | margen fluido ≥ 240 px; cabecera fija con marco centrado.
Movimiento: «Resaltar los hechos fijados en el texto» ilumina en fósforo apagado las frases que el Extractor tomó como hechos y en rojo la que entra en conflicto con el capítulo 6.

### Dirección 4 — Barra de vida (Entrada) · `html/direccion-4-barra-de-vida.html`

Concepto: cada novela es un traje colgado en un vestuario a oscuras, colgado de un riel de acero con su gancho, con un cono de luz sobre cada percha y un reflejo en el suelo, y su barra de vida: un tubo vertical de acero con un segmento por capítulo. Los cerrados brillan en fósforo apagado, los pendientes están apagados, el segmento donde el Revisor detuvo la novela es rojo y las marcas rojas del tubo señalan las auditorías cada cuatro capítulos. La longitud del tubo depende del número de capítulos. El quinto traje es nuevo: treinta segmentos apagados y un campo de premisa.

Paleta: la común de terror oscuro.
Tipografía: serif itálica para el título y los nombres de las novelas; Helvetica / Arial para el resto.
Retícula: cinco columnas iguales alineadas por la base; en cada una, barra de 64 px + datos.
Movimiento: «Conectar el traje» encienda el primer segmento y el borde de la carcasa; el botón pasa a abrir la orden de trabajo.

## Contenido real y contenido ilustrativo

Real (del encargo): la novela «El casco frío del Falcon», 30 capítulos, 6 cerrados; premisa; referencias de tono; agentes; el estado de ejemplo (revisor detenido en el capítulo 6, dos contradicciones y quince repeticiones); el fragmento del capítulo 4 «Lo que quedó despierto».

Ilustrativo (inventado para que las maquetas no tengan huecos, sustituir por datos reales): títulos de los capítulos 5 y 6, el detalle de las dos contradicciones, costes y tiempos, las horas del registro, y las otras tres novelas de la pantalla de entrada («La cuota de oxígeno», «Salmos para la tripulación de relevo», «Turno de noche en la cubierta de fundición»).

## Restricciones que cumplen las maquetas

Responsive hasta 1280 px; foco de teclado visible (`:focus-visible`); `prefers-reduced-motion` respetado; un único movimiento orquestado por dirección; sin etiquetas en mayúsculas sostenidas, sin cadenas de metadatos con puntos medios, sin monoespaciada para datos, sin marcadores numerados decorativos, sin tarjetas idénticas, sin flechas al final de botones, sin fondo crema con terracota. Las tipografías son pilas de sistema porque no se permitían dependencias externas; al fijar una dirección conviene elegir la fuente web definitiva.
