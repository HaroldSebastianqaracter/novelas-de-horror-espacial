import { screen, waitFor, within } from "@testing-library/react";
import { delay, http, HttpResponse } from "msw";
import { afterEach, describe, expect, it, vi } from "vitest";
import { servidor } from "../../compartido/api/mocks/servidor";
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
    // El canon tarda: hasta que llega, la vista no está lista y no imprime.
    let soltar = () => {};
    const canon = new Promise<void>((r) => {
      soltar = r;
    });
    servidor.use(
      http.get("*/api/novelas/6/canon/personajes", async () => {
        await canon;
        return HttpResponse.json([]);
      }),
    );
    const imprimir = vi.spyOn(window, "print").mockImplementation(() => {});
    const { container } = renderizarEn("/novelas/6/lectura/imprimir?imprimir=1");
    await screen.findByRole("heading", { level: 1, name: "Deriva en el anillo Tántalo" });
    await delay(300);
    expect(container.querySelector("[data-listo-para-imprimir]")).toBeNull();
    expect(imprimir).not.toHaveBeenCalled();
    soltar();
    await waitFor(() => expect(imprimir).toHaveBeenCalledTimes(1));
    await new Promise((r) => setTimeout(r, 200));
    expect(imprimir).toHaveBeenCalledTimes(1);
  });

  it("si falla el canon no se marca lista ni imprime, y lo dice", async () => {
    servidor.use(http.get("*/api/novelas/6/canon/:entidad", () => HttpResponse.json({ detail: "x" }, { status: 500 })));
    const imprimir = vi.spyOn(window, "print").mockImplementation(() => {});
    const { container } = renderizarEn("/novelas/6/lectura/imprimir?imprimir=1");
    await waitFor(() => expect(container.querySelector("[data-error-impresion]")).not.toBeNull(), { timeout: 10_000 });
    expect(container.querySelector("[data-listo-para-imprimir]")).toBeNull();
    expect(imprimir).not.toHaveBeenCalled();
    expect(screen.getByText(/el libro no está completo para imprimirlo/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Imprimir o guardar como PDF" })).toBeDisabled();
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
