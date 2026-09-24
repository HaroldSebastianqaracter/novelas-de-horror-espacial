// Exporta a PDF la vista de impresión de una novela (RF-FE-PDF-03).
//
//   npm run pdf -- <url de la vista de impresión> <salida.pdf>
//   npm run pdf -- http://localhost:5173/novelas/6/lectura/imprimir ../../ejemplos/novela-ejemplo.pdf
//
// Espera a que la vista diga que está lista (`data-listo-para-imprimir`) y a las fuentes, y guarda
// el PDF con el tamaño de página de la hoja de estilos, los fondos y el esquema de títulos.
import { chromium } from "playwright";

const [url, salida] = process.argv.slice(2);
if (!url || !salida) {
  console.error("Uso: npm run pdf -- <url de /novelas/:id/lectura/imprimir> <salida.pdf>");
  process.exit(2);
}
if (!/\/lectura\/imprimir\/?([?#]|$)/.test(url)) {
  console.error("La URL tiene que ser la vista de impresión: /novelas/:id/lectura/imprimir");
  process.exit(2);
}

const navegador = await chromium.launch();
try {
  const pagina = await navegador.newPage();
  const errores = [];
  pagina.on("pageerror", (e) => errores.push(String(e)));
  await pagina.goto(url, { waitUntil: "load" });
  try {
    await pagina.waitForSelector("[data-listo-para-imprimir], [data-error-impresion]", { timeout: 30_000 });
  } catch {
    throw new Error(
      "La vista de impresión no llegó a estar lista en 30 s. ¿La novela tiene versiones publicadas y el servidor está en marcha?",
    );
  }
  if (await pagina.locator("[data-error-impresion]").count()) {
    throw new Error("La vista de impresión no pudo cargar la ficha (canon o escaleta): no se guarda un PDF incompleto.");
  }
  await pagina.evaluate(() => document.fonts.ready);
  await pagina.emulateMedia({ media: "print" });
  await pagina.pdf({ path: salida, preferCSSPageSize: true, printBackground: true, tagged: true, outline: true });
  const capitulos = await pagina.locator("article.capitulo").count();
  console.log(`PDF guardado en ${salida}: ${capitulos} capítulos.`);
  if (errores.length) console.warn("Errores de la página:", errores.join(" | "));
} catch (e) {
  console.error(e instanceof Error ? e.message : e);
  process.exitCode = 1;
} finally {
  await navegador.close();
}
