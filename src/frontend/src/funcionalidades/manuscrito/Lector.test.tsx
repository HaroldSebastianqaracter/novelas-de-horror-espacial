import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { sinViolaciones } from "../../pruebas/accesibilidad";
import { renderizarEn } from "../../pruebas/renderizar";
import { partirEnEscenas } from "./Lector";

describe("lector de capítulo (RF-FE-LEC)", () => {
  it("parte el texto compilado en escenas por `* * *` y en párrafos por las líneas en blanco", () => {
    expect(partirEnEscenas("Uno.\n\nDos.\n\n* * *\n\nTres.")).toEqual([["Uno.", "Dos."], ["Tres."]]);
    expect(partirEnEscenas("Solo una escena.")).toEqual([["Solo una escena."]]);
  });

  it("enseña el capítulo con su versión, sus palabras y sus escenas separadas", async () => {
    renderizarEn("/novelas/3/capitulos/2");
    expect(await screen.findByRole("heading", { level: 1, name: "Capítulo 2" })).toBeInTheDocument();
    expect(screen.getByText(/CAP 02 · versión 1 · \d+ palabras/)).toBeInTheDocument();
    expect(screen.getAllByRole("region", { name: /^Escena \d$/ })).toHaveLength(3);
    expect(within(screen.getByRole("region", { name: "Escena 3" })).getByText(/abierto desde dentro/)).toBeInTheDocument();
  });

  it("navega al capítulo cerrado anterior y al siguiente", async () => {
    renderizarEn("/novelas/3/capitulos/2");
    const navegacion = await screen.findByRole("navigation", { name: "Capítulos" });
    expect(within(navegacion).getByRole("link", { name: "← Capítulo 1" })).toHaveAttribute("href", "/novelas/3/capitulos/1");
    expect(await within(navegacion).findByRole("link", { name: "Capítulo 3 →" })).toHaveAttribute("href", "/novelas/3/capitulos/3");
  });

  it("en el último capítulo cerrado no ofrece siguiente", async () => {
    renderizarEn("/novelas/3/capitulos/5");
    const navegacion = await screen.findByRole("navigation", { name: "Capítulos" });
    await within(navegacion).findByRole("link", { name: "← Capítulo 4" });
    expect(within(navegacion).queryByRole("link", { name: /→/ })).not.toBeInTheDocument();
  });

  it("un capítulo sin escribir no es un error: dice que todavía no existe (RF-FE-LEC-02)", async () => {
    renderizarEn("/novelas/3/capitulos/8");
    expect(await screen.findByRole("heading", { name: "El capítulo 8 todavía no está escrito" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Reintentar" })).not.toBeInTheDocument();
  });

  it("no tiene violaciones de accesibilidad automáticas", async () => {
    const { container } = renderizarEn("/novelas/3/capitulos/2");
    await screen.findByRole("heading", { level: 1, name: "Capítulo 2" });
    await sinViolaciones(container);
  });
});
