# El casco frío del Falcon — direcciones de diseño

Herramienta de escritorio web que genera novelas de terror espacial con un equipo de agentes (Orquestador, Escritor, Extractor de hechos, Revisor de calidad). El usuario encarga, vigila y lee; no escribe. El diseño transmite vigilancia, no productividad: la máquina es lenta, cuesta dinero real y puede detenerse con un veredicto en contra.

## Contenido de la carpeta

- `html/` — una maqueta autónoma por dirección. Se abren con doble clic, sin dependencias externas, todo el CSS y el SVG en línea. Cada una tiene un único momento de movimiento que responde a una acción del usuario.
- `lienzo/project/` — las mismas pantallas como mesas de trabajo estáticas del lienzo de Diseño de Claude (`*.dc.html` + `canvas.json`). Son versiones sin interacción; la referencia es siempre `html/`.
- `referencia/` — capturas que guiaron el lenguaje visual de las direcciones 1, 3 y 4 (pantalla de carga con plano de nave en alambre; traje de metal oxidado con visor cian). No se ha copiado ninguna forma registrada: la nave, la barra de vida y el plano son dibujos propios.

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

Pendiente acordado: pasar esta pantalla a la paleta cálida de las direcciones 3 y 4 (metal quemado y latón, cian solo para lo activo), para que las mesas del mismo mundo casen.

### Dirección 2 — Orden de trabajo (Encargo) · `html/direccion-2-orden-de-trabajo.html`

Concepto: encargar una novela es firmar una orden de trabajo que no admite correcciones. Impreso sobre una mesa gris; lo que la máquina imprime en azul de papel carbón, lo que el usuario rellena en serif «a mano». Los capítulos se cuentan con palotes tachados de cinco en cinco; el tono se marca con aspas; los cuatro agentes firman en una tabla de personal, y solo el Revisor tiene una potestad en rojo: detener la producción. Coste, tiempo y puntos de parada, anotados a lápiz en el margen.

Paleta: Mesa `#D9DCD6`, Papel `#F6F6F2`, Calco `#2E4A7D`, Tinta `#17191C`, Sello `#A8281F`, Lápiz `#6E726B`.
Tipografía: Helvetica / Arial 13–14 px para lo impreso; Georgia / Iowan Old Style 17 px para lo escrito por la persona; firmas en trazos SVG.
Retícula: hoja de ~860 px con etiquetas en columna de 168 px; margen de anotaciones de 300 px.
Movimiento: al firmar cae el tampón «Recibido» y la hoja se bloquea.

### Dirección 3 — Lectura bajo el traje (Lectura) · `html/direccion-3-luz-de-emergencia.html`

Concepto: la lectura ocurre sobre planchas acanaladas de metal quemado con juntas remachadas y luz ámbar de techo. Marcos y costillar de capítulos en latón envejecido; el cian del visor se reserva para lo que la máquina «ve»: el capítulo actual, los hechos fijados por el Extractor, la posición de Vlk en el plano del ramal seis. El veredicto del Revisor cruza como una línea roja de cuarentena. Columna de texto de 66 caracteres; margen con los hechos fijados (`//Vlk`, `//El cortador`...) y el conflicto en rojo.

Paleta: Metal quemado `#12100C`, Plancha `#1C1812`, Junta `#0C0A07`, Latón `#A88A52`, Óxido oscuro `#4A3D28`, Hueso `#E6DCC8`, Hueso bajo `#9C8E74`, Visor `#6FE3E6`, Revisor `#C0392B`.
Tipografía: serif antigua (Iowan Old Style / Palatino / Georgia) 20 px para el cuerpo; grotesca condensada 12,5–14 px para interfaz y marginalia.
Retícula: costillar 120 px | texto 66ch | margen fluido ≥ 240 px; cabecera fija con marco centrado.
Movimiento: «Resaltar los hechos fijados en el texto» ilumina en cian las frases que el Extractor tomó como hechos y en rojo la que entra en conflicto con el capítulo 6.

### Dirección 4 — Barra de vida (Entrada) · `html/direccion-4-barra-de-vida.html`

Concepto: cada novela es un traje colgado en el vestuario con su barra de vida: un tubo vertical de latón con un segmento por capítulo. Los cerrados brillan en cian, los pendientes están apagados, el segmento donde el Revisor detuvo la novela es rojo y las marcas rojas del tubo señalan las auditorías cada cuatro capítulos. La longitud del tubo depende del número de capítulos. El quinto traje es nuevo: treinta segmentos apagados y un campo de premisa.

Paleta: la misma de la dirección 3.
Tipografía: grotesca condensada para todo, serif solo en las premisas.
Retícula: cinco columnas iguales alineadas por la base; en cada una, barra de 64 px + datos.
Movimiento: «Conectar el traje» encienda el primer segmento y el borde de la carcasa; el botón pasa a abrir la orden de trabajo.

## Contenido real y contenido ilustrativo

Real (del encargo): la novela «El casco frío del Falcon», 30 capítulos, 6 cerrados; premisa; referencias de tono; agentes; el estado de ejemplo (revisor detenido en el capítulo 6, dos contradicciones y quince repeticiones); el fragmento del capítulo 4 «Lo que quedó despierto».

Ilustrativo (inventado para que las maquetas no tengan huecos, sustituir por datos reales): títulos de los capítulos 5 y 6, el detalle de las dos contradicciones, costes y tiempos, las horas del registro, y las otras tres novelas de la pantalla de entrada («La cuota de oxígeno», «Salmos para la tripulación de relevo», «Turno de noche en la cubierta de fundición»).

## Restricciones que cumplen las maquetas

Responsive hasta 1280 px; foco de teclado visible (`:focus-visible`); `prefers-reduced-motion` respetado; un único movimiento orquestado por dirección; sin etiquetas en mayúsculas sostenidas, sin cadenas de metadatos con puntos medios, sin monoespaciada para datos, sin marcadores numerados decorativos, sin tarjetas idénticas, sin flechas al final de botones, sin fondo crema con terracota. Las tipografías son pilas de sistema porque no se permitían dependencias externas; al fijar una dirección conviene elegir la fuente web definitiva.
