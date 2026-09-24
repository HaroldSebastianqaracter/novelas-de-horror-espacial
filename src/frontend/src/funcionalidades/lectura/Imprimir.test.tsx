import { screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { sinViolaciones } from "../../pruebas/accesibilidad";
import { renderizarEn } from "../../pruebas/renderizar";

afterEach(() => vi.restoreAllMocks());

describe("vista de impresión y PDF (RF-FE-PDF-01, RF-FE-PDF-02)", () => {
  it("lleva portada, novedades, índice, capítulos y ficha, en ese orden y con anclas", async () => {
    const { container } = renderizarEn("/novelas/6/lectura/imprimir");
    await waitFor(() => expect(container.querySelector("[data-listo-para-imprimir]")).not.toBeNull());

    const hojas = [...container.querySelectorAll(".imprimir > .hoja")].map((h) => h.querySelector("h1, h2")?.textContent);
    expect(hojas).toEqual([
      "Deriva en el anillo Tántalo",
      "Novedades de la versión 2",
      "Índice",
      ...Array.from({ length: 10 }, (_, i) => `Capítulo ${i + 1}`),
      "Personajes y lugares",
    ]);

    const indice = screen.getByRole("navigation", { name: "Índice" });
    expect(within(indice).getByRole("link", { name: "Capítulo 3" })).toHaveAttribute("href", "#cap-3");
    expect(within(indice).getByRole("link", { name: "Personajes y lugares" })).toHaveAttribute("href", "#apendice-ficha");
    expect(container.querySelector("#cap-3")).toHaveTextContent("Nala ladró dos veces");
    const novedades = screen.getByRole("region", { name: "Novedades de la versión 2" });
    expect(within(novedades).getByRole("link", { name: "el capítulo 5" })).toHaveAttribute("href", "#cap-5");

    const ficha = screen.getByRole("region", { name: "Personajes y lugares" });
    const nala = within(ficha).getByRole("heading", { name: "Nala", level: 4 }).closest("li") as HTMLElement;
    expect(within(nala).getByRole("link", { name: "capítulo 3" })).toHaveAttribute("href", "#cap-3");
  });

  it("la primera versión no lleva novedades", async () => {
    const { container } = renderizarEn("/novelas/6/lectura/imprimir?version=1");
    await waitFor(() => expect(container.querySelector("[data-listo-para-imprimir]")).not.toBeNull());
    expect(screen.queryByRole("region", { name: /Novedades/ })).not.toBeInTheDocument();
    expect(container.querySelector("#cap-3")).toHaveTextContent("Toby ladró dos veces");
  });

  it("con ?imprimir=1 abre el diálogo de imprimir cuando está lista, una sola vez", async () => {
    const imprimir = vi.spyOn(window, "print").mockImplementation(() => {});
    renderizarEn("/novelas/6/lectura/imprimir?imprimir=1");
    await waitFor(() => expect(imprimir).toHaveBeenCalledTimes(1));
    await new Promise((r) => setTimeout(r, 200));
    expect(imprimir).toHaveBeenCalledTimes(1);
  });

  it("la portada de la lectura enlaza a exportar a PDF", async () => {
    renderizarEn("/novelas/6/lectura");
    expect(await screen.findByRole("link", { name: "Exportar a PDF" })).toHaveAttribute(
      "href",
      "/novelas/6/lectura/imprimir?imprimir=1",
    );
  });

  it("no tiene violaciones de accesibilidad automáticas", async () => {
    const { container } = renderizarEn("/novelas/6/lectura/imprimir");
    await waitFor(() => expect(container.querySelector("[data-listo-para-imprimir]")).not.toBeNull());
    await sinViolaciones(container);
  });
});
