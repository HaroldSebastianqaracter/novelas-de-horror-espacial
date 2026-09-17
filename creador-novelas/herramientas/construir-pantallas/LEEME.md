# Cómo se construyen las cuatro pantallas

Cada pantalla de `app/static/` **no se escribe a mano**: se genera a partir de una maqueta de
`falcon-diseno*/html/`. El generador toma la maqueta, se queda con su `<head>` entero —todo el CSS
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

Cada uno lleva `BASE` apuntando a la raíz del repo y lee de `falcon-diseno/html/`. **Para migrar a
una entrega nueva del diseño, se cambia esa carpeta en los cuatro y se vuelven a ejecutar.**

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

Usa el Chrome del sistema en modo headless (`channel="chrome"`): no hay chromium descargado.

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
