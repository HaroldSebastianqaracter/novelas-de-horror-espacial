# Uso del browser MCP: validación visual de la lectura

Lo pide la entrega (sección 5a, y el apartado de Claude Code): el agente abre la novela en el navegador, navega por ella y comprueba que el índice, la ficha de personajes y lugares y la portada se ven bien, y si detecta un error lo registra y lo devuelve a quien corresponde.

**Cómo se hizo.** Claude Code, con el servidor **Playwright MCP** de [.mcp.json](../../.mcp.json), el 24 de septiembre de 2026. La web (`npm run dev`) y la API (`main.py`) corrían sobre **copias** de la novela de diez capítulos: primero `novela_10cap_web.db`, la novela tal cual, y después `novela_10cap_video.db`, la misma tras un cambio del lector real. La novela original no se tocó. Además de mirar las capturas, el agente comprobó cada punto con JavaScript en la página (`browser_evaluate`), para no fiarse solo de la vista.

## Qué inspeccionó y qué vio

| # | Qué | Cómo se comprobó | Resultado |
| --- | --- | --- | --- |
| 1 | **Portada** con dedicatoria personalizada | Captura y texto de la página | Bien: título, dedicatoria con el nombre del destinatario y la firma de quien regala, ocasión e imagen de portada ([captura](browser-mcp/01-portada.png)) |
| 2 | **Índice** navegable | Los diez enlaces y su destino | Bien: diez capítulos, cada uno con su enlace y su número de palabras |
| 3 | **Ficha de personajes y lugares** generada desde la story bible | Cada entrada y sus enlaces a capítulos | Bien: 5 personajes y 11 lugares, cada uno con enlaces a los capítulos donde aparece ([captura](browser-mcp/02-ficha.png)) |
| 4 | Los enlaces de la ficha llevan al capítulo correcto | Clic en «capítulo 7» de la Esclusa EVA, y después, con una consulta a la story bible, cada lugar contra el texto de los capítulos que enlaza | Bien. Tres lugares no aparecen con su nombre exacto en algún capítulo enlazado (la «Cocina-comedor» en el 4, la «Esclusa EVA» en el 7, la «Cámara del núcleo» en el 3 y el 5), pero la prosa sí los nombra con otras palabras («la cocina», «el traje», «la puerta del núcleo»): la ficha enlaza por la escena que ocurre allí, que es lo correcto |
| 5 | **Lectura en móvil** (390 px) | Ancho del documento y elementos que se salen de la pantalla | Bien: ningún desbordamiento horizontal ([captura](browser-mcp/03-capitulo-movil.png)). La cabecera parte «Versión 1» en una segunda línea: es estético y no se tocó |
| 6 | **Vista de impresión** (la que se exporta a PDF) | Capítulos, índice, ficha, dedicatoria, enlaces internos e imágenes | Bien: los diez capítulos, índice, ficha y dedicatoria; **91 enlaces internos, ninguno roto**; ninguna imagen rota |
| 7 | **Capítulos cambiados** tras un cambio del lector real | El índice de la versión 2 | Bien: solo los capítulos 1 y 2 dicen «cambió en la versión 2», y son exactamente los que el cambio tocó ([captura](browser-mcp/04-indice-version-2.png)) |
| 8 | **Historial de versiones** | La página de versiones | Bien: la versión 2 con la petición del lector y «Cambiaron: capítulo 1, capítulo 2», y la versión 1 como primera edición, las dos legibles ([captura](browser-mcp/05-versiones.png)) |
| 9 | **Comparación con la versión anterior** | El capítulo 1 con los cambios a la vista | Bien: marca lo añadido («ozono», «café recalentado») y lo quitado («metal», «aceite de juntas»), y nada más ([captura](browser-mcp/06-comparacion-capitulo-1.png)) |
| 10 | **La versión anterior se conserva** | El capítulo 1 de la versión 1 | Bien: sigue diciendo «aceite de juntas», y la página avisa de que los cambios solo se piden sobre la última versión |
| 11 | **Errores de consola** en todas las páginas | `browser_console_messages` | **Un error en cada página: `favicon.ico` da 404** |

El cambio del lector de las filas 7 a 10 fue real (Claude Code, Opus 5.5) sobre la copia: «la bahía de soporte vital huele a ozono y a café recalentado», un hecho que usan los capítulos 1 y 2. Se reescribieron solo esos dos, pasaron otra vez el juez de oficio y la cronología en Lean, y nació la versión 2. Tardó 11 minutos y costó 2,15 $.

## Qué detectó y qué cambió

- **El favicon que faltaba** (fila 11): el único error real, un 404 en la consola en cada página. Se añadió `src/frontend/public/favicon.svg` (tres destellos, como el faro de la novela) y su `<link rel="icon">` en `index.html`. Es un cambio pequeño, pero es el que pide la entrega: un fallo que se veía en el navegador y ningún test del frontend cazaba.
- **Nada más que corregir** en la portada, el índice, la ficha, las versiones ni la vista del PDF. La pasada confirma en el navegador lo que prometen la [spec del frontend](../../specs/spec-frontend.md) y los tests con datos ficticios, ahora con una novela real de diez capítulos y un cambio del lector real.
- **Relacionado, visto al probar la web con el puerto falso:** el revisor de demostración partía por la mitad las etiquetas de la seudonimización al recortar sus citas, y el cambio fracasaba en `cambio_sin_cita`. Lo encontró la sesión del frontend al recorrer la web, y se corrigió en `compartido/puerto/demo.py` (commit `1ff7541`). El revisor real cita palabras enteras y no tenía el fallo.

## Punto ciego

La pasada es una foto del 24 de septiembre, no un test que se repita solo en cada versión: el browser MCP es una herramienta del desarrollo, no una puerta del pipeline. Lo que sí se repite en cada cambio del frontend son sus tests (`npm run test`) y la comprobación de tipos contra el contrato de la API.
