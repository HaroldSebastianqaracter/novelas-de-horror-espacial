# novelasv2 · propuesta B «papel técnico» · decisiones

> **Nota al guardarlo en el repo (23-09-2026).** Es el prototipo tal como lo entregó el agente de diseño, y se conserva como referencia visual de [specs/spec-frontend.md](../../../specs/spec-frontend.md). La propuesta A y su `DECISIONES.md`, que se citan abajo, no se guardaron. El comportamiento lo fija la spec, y donde difiera del prototipo manda la spec.

Segunda propuesta visual del mismo prototipo. Nace de una crítica a la A: demasiado oscura y demasiado cargada. Se abre igual, con doble clic en `index.html`.

**Qué cambia respecto a la A:** solo `tokens.css`, `estilos.css`, la fuente cargada en `index.html` y la pieza 3D (`ambiente.js`, que ahora dibuja en tinta azul). También los mensajes, que ahora salen en frase normal y no en mayúsculas: lo hace una función `frase()` añadida en `app.js`.

**Qué NO cambia:** pantallas, rutas, reglas de arrastre, intenciones, reconexión, datos ni simulación. Las decisiones de comportamiento de `../novelasv2/DECISIONES.md`, sección 3, siguen vigentes.

## 1. Dirección de arte

1. **Paleta.** Papel cálido `#f4f1ea` como fondo, tarjetas casi blancas `#fffdf9` y tinta `#1f1d1a`. Un único acento, el azul cianotipo `#2b4c7e` de los planos técnicos, para acciones, paso activo y selección. Verde `#2e6b36` para lo confirmado; ocre `#7a5300` para avisos y rechazos. Rojo `#b3261e`, igual que en la A, reservado solo para `parada` y `error`.
2. **Tipografías.** IBM Plex Sans para la interfaz. IBM Plex Mono solo en códigos, números técnicos y la marca. Source Serif 4 para el manuscrito y las citas.
3. **Textura.** Ninguna: sin scanlines, sin halos y sin interruptor CRT. Solo la retícula de plano de fondo en la pieza 3D. La profundidad sale de sombras muy suaves y de tres tonos de papel.
4. **Forma.** Radios de 6–10 px, chips en píldora tintada, progreso en una línea fina continua y pasos de planificación como círculos unidos por una línea.
5. **Voz.** Sigue siendo breve y precisa, pero en frase normal: «Ranura ocupada: EXP-0409 está en curso.», no «RANURA OCUPADA». Los códigos (`EXP-0409`, `P-0093`, `crear_novela`) conservan el toque técnico.
6. **Ciencia ficción, en los detalles.** La tipografía mono de los códigos, la estación dibujada como plano, la franja roja de «Alerta de a bordo» en la parada y los nombres técnicos de los campos.

## 2. Tokens

Contraste medido con WCAG 2.x. Los nombres de rol son los de la A, así que React puede cambiar de propuesta cambiando solo el fichero de tokens.

| Token | Valor | Rol | Contraste |
|---|---|---|---|
| `--color-fondo` | `#f4f1ea` | Papel de fondo | — |
| `--color-superficie` | `#ece8df` | Columnas, zonas agrupadas | — |
| `--color-superficie-elevada` | `#fffdf9` | Tarjetas, campos, menús | — |
| `--color-superficie-hundida` | `#e6e1d6` | Pistas de progreso, chips neutros | — |
| `--color-superficie-activa` | `#f6f2e9` | Hover | — |
| `--color-borde` | `#ddd6c8` | Separadores decorativos | — |
| `--color-borde-fuerte` | `#8c8475` | Bordes de controles | 3,6:1 sobre tarjeta |
| `--color-texto` | `#1f1d1a` | Tinta principal | 14,9:1 |
| `--color-texto-secundario` | `#4f4a43` | Metadatos | 7,8:1 |
| `--color-texto-tenue` | `#645d54` | Códigos y pistas | ≥5,1:1 en superficie |
| `--color-texto-invertido` | `#ffffff` | Sobre acento / alerta | 8,6:1 / 6,5:1 |
| `--color-acento` / `-velo` | `#2b4c7e` / `#e8edf5` | Acción, paso activo, selección | 7,6:1 |
| `--color-confirmado` / `-velo` | `#2e6b36` / `#e5f0e3` | Confirmado, enlace, cerrado | 5,7:1 |
| `--color-aviso` / `-velo` | `#7a5300` / `#faf1d9` | Avisos, rechazos, validación | 6,1:1 |
| `--color-alerta` | `#b3261e` | Solo parada y error | 5,8:1 |
| `--color-alerta-texto` | `#8f1d17` | Texto sobre fondo de alerta | 7,7:1 |
| `--color-alerta-fondo` / `-borde` | `#fbeae7` / `#e3a39c` | Carril y alerta de parada | — |
| `--color-lectura-*` | `#fbf8f2` / `#24211d` / `#645d54` | Lector | 15,1:1 / 5,5:1 |
| `--color-herramienta-*` | oscuros | Panel de simulación (fuera del producto) | 13:1 |
| `--color-foco` | `#0b3d91` | Anillo de foco | 8,9:1 |
| `--sombra-tarjeta`, `--sombra-elevada` | sombras suaves | Nuevas en B: profundidad sin bordes pesados | — |
| `--brillo-*`, `--scanlines-*`, `--vineta` | `none` / 0 | Se conservan para compatibilidad con la A, anulados | — |
| `--fuente-interfaz` / `--fuente-codigo` / `--fuente-lectura` | Plex Sans / Plex Mono / Source Serif 4 | `--fuente-codigo` es nueva en B | — |
| `--texto-base` | 15 px | Cuerpo algo mayor que en la A (14 px) | — |
| `--radio-sm` / `--radio-md` / `--radio-pildora` | 6 / 10 / 999 px | Más suaves que en la A | — |
| Resto (`--espacio-*`, `--duracion-*`, `--z-*`, anchos) | iguales a la A | — | — |

## 3. Decisiones propias (y la alternativa descartada)

- **Acento azul cianotipo en vez de ámbar.** Sobre papel, un ámbar legible como texto se vuelve marrón y choca con el ocre de los avisos. *Descartado:* ámbar tostado como acento.
- **El panel de simulación es oscuro.** Sobre una interfaz clara es donde más se distingue como herramienta ajena al producto. *Descartado:* mantener el gris de la A.
- **La alerta de parada conserva una franja roja sólida.** El resto de la pantalla es papel blanco, así que la tensión sube sin que todo sea rojo. *Descartado:* toda la pantalla tintada de rojo, como en la A.
- **Los números de columna («01 · En espera») y los códigos de sección («A», «B») se ocultan por CSS.** Siguen en el HTML. *Descartado:* borrarlos del marcado, porque la A los necesita.
- **Pasos de planificación como círculos numerados con una línea de progreso.** En móvil pasan a una lista vertical. *Descartado:* las celdas rectangulares de la A.
- **Progreso en una línea fina continua, coloreada por estado** (azul en curso, gris detenida, ocre con avisos, rojo en alerta). *Descartado:* la barra segmentada de la A, que añadía ruido.
- **Estado exacto (`generando`) en mono pequeño junto al chip**, solo en la cabecera de la novela. *Descartado:* mostrarlo también en cada tarjeta.
- **Mensajes del servidor convertidos a frase normal en la interfaz** con `frase()`. El servidor sigue devolviendo lo mismo. *Descartado:* reescribir todos los textos del servidor simulado.
- **Carril «Requiere atención» vacío: borde discontinuo y texto gris, sin fondo.** *Descartado:* ocultarlo.
- **Sin interruptor CRT.** No hay efectos que apagar. El atributo `data-crt="off"` se mantiene por compatibilidad. *Descartado:* mantener el botón inactivo.
