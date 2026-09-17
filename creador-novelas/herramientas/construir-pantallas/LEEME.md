# Cómo se construyen las cuatro pantallas

Cada pantalla de `app/static/` **no se escribe a mano**: se genera a partir de una maqueta de
`falcon-diseno_2/html/`. El generador toma la maqueta, se queda con su `<head>` entero —todo el CSS
del diseñador, intacto— y sustituye el `<body>`, que es contenido inventado, por uno vacío que se
rellena desde la API del harness.

Se hace así por un motivo concreto: cuando llega una versión nueva del diseño, solo hay que apuntar
el generador a la maqueta nueva y volver a ejecutarlo. Editar el HTML a mano significaría rehacer
la conexión entera cada vez.

| Generador | Maqueta de origen | Produce | Ruta |
|---|---|---|---|
| `construir_vestuario.py` | dirección 4, barra de vida | `vestuario.html` | `/` |
| `construir_encargo.py` | dirección 2, orden de trabajo | `encargo.html` | `/encargo` |
| `construir_consola.py` | dirección 1, sala de máquinas | `consola.html` | `/consola` |
| `construir_lectura.py` | dirección 3, luz de emergencia | `lectura.html` | `/lectura` |

Lo común a los cuatro vive en `comun.py`: la carpeta de maquetas (`MAQUETAS`), la raíz del repo
deducida de la posición del archivo, la barra de navegación y las capas de atmósfera de las
direcciones 2, 3 y 4. **Para migrar a una entrega nueva del diseño se cambia `MAQUETAS` ahí y se
vuelven a ejecutar los cuatro.** Cada generador lleva `assert`s sobre los trozos de la maqueta que
toca; si la entrega nueva los movió, fallan con el nombre del trozo en vez de producir una pantalla
rota en silencio.

```
python herramientas/construir-pantallas/construir_vestuario.py
```

## De dónde saca los datos cada pantalla

| Endpoint | Lo usa |
|---|---|
| `GET /api/indice` | biblioteca, lectura |
| `GET /api/capitulo/<n>` | lectura |
| `GET /api/estado` | consola |
| `GET /api/eventos` | consola |
| `GET /api/qa` | consola, lectura |
| `GET /api/coste` | biblioteca, consola |
| `GET /api/formulario` | encargo |
| `POST /guardar` | encargo |
| `POST /api/fase/<nombre>` | consola |
| `POST /api/borrar-novela` | biblioteca |

## Revisar el resultado

`inspeccion.py` abre una pantalla, espera a que pinte, captura, y devuelve los errores de consola,
los 404 y el texto que queda recortado por su contenedor. Casi todos los defectos que aparecieron
durante la conexión eran invisibles leyendo el código y evidentes en esa salida.

```
python herramientas/construir-pantallas/inspeccion.py http://127.0.0.1:8765/consola salida.png "#acciones button,.plano svg"
```

Usa el Chrome del sistema en modo headless (`channel="chrome"`): no hay chromium descargado. El
Playwright está en un entorno aparte (`~/.pwdrv`), no en el `.venv` del harness.

## Lo que se aprendió conectando la primera entrega

Vale la pena leerlo antes de migrar, porque casi todo vuelve a aplicar:

- **Las maquetas traen contenido inventado.** Títulos, costes y estados que parecen datos y no lo
  son. Hay que sustituirlos todos o la pantalla miente con mucha convicción.
- **Las rejillas están dimensionadas para ese contenido.** La columna de la hora del registro
  medía 44px para «14:52» y el harness anota «12:04:11»; la biblioteca repartía cinco columnas
  porque enseñaba cinco novelas inventadas.
- **El diseño promete cosas que el harness no tiene.** El «tono» del encargo, el minimapa con la
  posición del personaje. Cada una hay que decidirla: se sustituye, se omite o se implementa.
- **Los acentos se pierden al generar** si el script pasa por un shell. Conviene revisarlos al
  final con una búsqueda de «capitulo», «produccion», «senal».
- **Las rutas bonitas son redirecciones** a `/static/*.html`, así que `location.pathname` no sirve
  para saber en qué sección estás: hay que mirar el nombre del archivo.

## Lo que añadió la segunda entrega (`falcon-diseno_2`)

- **La atmósfera va en el `<body>`, no en el `<head>`.** Las direcciones 2, 3 y 4 apoyan su aspecto
  en filtros SVG y en una decena de `div.atm-*` dentro de un contenedor `.escena`. Cambiar solo la
  cabeza deja la pantalla sin grano, sin sangre y sin viñeta: por eso `comun.atmosfera_de()` los
  copia de la maqueta al cuerpo.
- **El CSS del diseñador tiene reglas que pierden contra sí mismas.** El bloque nuevo (`.trajes{
  align-items:start;padding-top:64px}`) está *antes* que la base (`align-items:end;padding:0`) y
  la base gana. En la maqueta no se nota porque las cinco barras miden casi lo mismo; con un libro
  de seis capítulos la barra caía al fondo y el gancho flotaba lejos del riel. Lo que se quiera
  conservar de esos bloques hay que repetirlo al final de la hoja.
- **`overflow:hidden` en `.escena` rompe `position:sticky`** de la cabecera de lectura, porque
  convierte la escena en contenedor de desplazamiento. `overflow:clip` recorta igual sin ese efecto.
- **Los estados de la maqueta son un interruptor; los del harness, varios.** La consola gobierna
  todo con `body.en-marcha` (reanudar/detener). Aquí manda `body[data-vista]` (estado del
  manifiesto) y `body[data-activo]` (agente trabajando), y hay animaciones que en la maqueta
  latían siempre (el ramal rojo) porque una `animation` pisa la `opacity` del elemento: hay que
  condicionarlas o se ven encendidas cuando no toca.
- **Los colores del SVG se pisan desde el CSS.** Las presentaciones (`stroke="#A8281F"`) pierden
  contra cualquier regla; el diseñador cuenta con eso (`.margen svg #hitos path{...!important}`),
  así que lo que se dibuje desde JS tiene que usar la misma estructura (`<g id="hitos">`) para
  heredar el color.
- **Un `::first-letter` de capital alcanza más de lo que parece.** `.texto p:first-of-type` también
  es el `<p>` del cierre dentro de la cabecera del capítulo. Hay que excluirlo a mano.
