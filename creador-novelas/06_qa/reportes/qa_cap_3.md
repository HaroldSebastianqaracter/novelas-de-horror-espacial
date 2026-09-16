# Corte de QA — capítulo 3

- Muestra leída: capítulos 1, 2, 3
- Voz configurada: es-ES · tercera limitada · pasado
- Registro de recursos de partida: vacío (primer corte)

## Verificación de voz

Los tres capítulos están en castellano (es-ES), en tercera persona limitada anclada en Pedro Sánchez y en tiempo pasado. Sin hallazgos de voz.

## Hallazgos de tipo `contradiccion` (2)

### C-1 · El pasillo de servicio vuelve a estar sellado «desde las 04:26» · cap_origen: 1

Hecho vigente contradicho (cap_origen 1): «El pasillo de servicio entre la enfermería y la bodega fue sellado automáticamente a las 04:26 por una orden sin origen identificado.»

El capítulo 1 cierra ese episodio con el narrador estableciendo que el mamparo se reabre: Mesa anuncia el compartimento abierto, Pedro oye subir los pistones y el esquema marca abierto con presión nominal. El capítulo 2 afirma en cambio que el pasillo «seguía sellado desde las 04:26», con continuidad ininterrumpida, y por eso obliga a Pedro a rodear el anillo; el capítulo 3 hereda ese estado al dar el bus de control del reactor por inaccesible tras un pasillo sellado. Lo que contradice el log no es que el pasillo esté cerrado —Mesa ejecuta cierres que nadie ordena—, sino la afirmación de continuidad «desde las 04:26», que niega la reapertura ya narrada. Si el mamparo volvió a bajar, hace falta que el texto lo registre como un cierre nuevo, con su hora.

### C-2 · Horas de vigilia de Pedro incompatibles con la línea temporal · cap_origen: 1

Hecho vigente contradicho (cap_origen 1): el sellado de las 04:26, que Pedro presencia despierto y de servicio en el puente.

En el capítulo 3, la narración (estilo indirecto libre, no diálogo) explica el posible error de percepción de Pedro «porque llevaba despierto desde las cinco y media». El capítulo 1 lo muestra despertando en la butaca de sistemas a las 04:12, anotando la incidencia de la baliza a las 04:19 y presenciando el cierre de las 04:26. A la altura del capítulo 3 —posterior a las 06:41, hora del hallazgo de Larrea en el capítulo 2— lleva despierto desde las 04:12, no desde las 05:30. No es un personaje mintiendo: es la voz narrativa fijando una duración de vigilia incompatible con lo ya establecido.

## Hallazgos de tipo `repeticion` (8)

Umbral: 3 o más apariciones acumuladas. Todos con `cap_origen: null`.

### R-1 · El agua que «sabe a filtro» como prueba tranquilizadora de continuidad — caps 1, 2, 3 (3 apariciones)

El mismo gesto y la misma conclusión emocional se repiten una vez por capítulo: el agua sabe igual que siempre y ese sabor sostiene a Pedro más que los datos (cap. 1, dispensador del puente; cap. 2, cantimplora en el camarote de Larrea; cap. 3, reciclador primario durante el inventario). A la tercera, el recurso se lee como muletilla de cierre de escena.

### R-2 · Estructura de negación en cascada «No en X, no en Y: en Z» / «No era X. Era Y.» — caps 1, 2 (5 apariciones)

Cuatro veces en el capítulo 1 (la luz ámbar, el reactor en gris, la lejanía de las rutas, el campo de origen en blanco) y una en el capítulo 2 (el olor del camarote). Es el patrón sintáctico dominante del capítulo 1 y conviene racionarlo.

### R-3 · El zumbido de los ventiladores como coda de escena tras el momento de tensión — caps 1, 2, 3 (7 apariciones)

El motivo funciona, pero se usa tres veces con la misma función exacta de cierre inmediatamente después de una frase inquietante (cap. 1, tras el aviso de mantenimiento repetido; cap. 2, tras el «Capitana Larrea, confirme» de Mesa; cap. 3, con el silencio del ventilador «ni un decibelio distinto» tras el «Cuarenta días»), además de las menciones de apertura y de recuento.

### R-4 · La lista de comprobación / la tablilla como asidero psicológico, con anotación de la hora — caps 1, 2, 3 (5 apariciones)

«Primero los números, después las preguntas» y la lista laminada (cap. 1); «las listas sin hora no valen para nada» y «como si la lista de comprobación pudiera sostenerlo» (cap. 2); «porque la lista era lo único que quedaba en pie» y la marca de tinta con la hora anotada (cap. 3). La caracterización está establecida desde el capítulo 1; enunciarla explícitamente en cada capítulo la desgasta.

### R-5 · Mesa responde con una evasiva fija («Sin datos» / «Aviso de mantenimiento…») en lugar de contestar — caps 1, 2, 3 (10 apariciones)

Seis avisos de mantenimiento fuera de contexto y cuatro «Sin datos». Es el recurso central de la amenaza y por eso mismo es el más expuesto al automatismo: la estructura pregunta directa → aviso absurdo ya es previsible al tercer uso del capítulo 1.

### R-6 · La frase literal «El metal estaba frío» — caps 1, 2, 3 (3 apariciones)

Cap. 1 (tapa del armario de nodos), cap. 2 (hoja del ramal de enfermería), cap. 3 (mamparo del compartimento seis). La formulación es idéntica en las tres.

### R-7 · Las costillas doloridas por el arnés — caps 1, 2, 3 (3 apariciones)

Cap. 1 al palparse tras despertar, cap. 2 al recibir el golpe de la puerta, cap. 3 al inclinarse sobre el bloc. El dolor es un buen ancla física, pero se invoca siempre con la misma fórmula («del arnés»).

### R-8 · Pedro cuenta (respiraciones, segundos, ventiladores) para sostenerse — caps 1, 2, 3 (4 apariciones)

«Contó hasta diez» y los noventa segundos contados contra el zumbido (cap. 1), «contando hasta seis» (cap. 2), «contó tres respiraciones» (cap. 3).

## Recursos por debajo del umbral (registrados para el próximo corte)

- Olor dulce y vegetal a agua estancada — 2 apariciones (caps 2, 3).
- La escarcha blanca ramificada que no se derrite / el dibujo que se ramifica — 2 apariciones (caps 2, 3).
- El olor a plástico tibio — 3 apariciones (caps 1, 2); alcanzó umbral y figura como R-9 solo si vuelve a aparecer; se mantiene registrado.

## Observaciones que NO son hallazgos

- Capítulo 2: Mesa declara «Dos cápsulas. Ambas presentes, selladas, presión nominal», mientras el log (cap_origen 0) describe *la* cápsula de salvamento de una sola plaza. No se computa como contradicción: es Mesa —sistema de a bordo establecido como no fiable— hablando dentro de la ficción, y el narrador no confirma el número. Queda como punto a vigilar: si un capítulo posterior confirma dos cápsulas por vía narrativa, sí será contradicción de un hecho de cap_origen 0.
- Capítulo 3: la enfermería sellada (cap_origen 2) se abre, pero Pedro la abre a mano con el husillo de emergencia y traba la puerta con una llave inglesa. Está explicado; no es un sellado violado.
- Capítulo 3: «reactor secundario al treinta y uno coma cuatro por ciento» es compatible con «un tercio de potencia» (cap_origen 0). Precisión, no contradicción.
- La ambigüedad entre avería, agotamiento de Pedro y entidad (cap_origen 0) se sostiene en los tres capítulos.
