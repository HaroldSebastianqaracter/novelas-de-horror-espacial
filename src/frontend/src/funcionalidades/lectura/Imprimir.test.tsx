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

    expect(screen.getByText("Para Oda Varga · De Lía y Marcos · Cumpleaños")).toBeInTheDocument();
    // La portada del PDF, en tamaño de impresión (RF-FE-IMG-01).
    const portada = container.querySelector(".imprimir > .portada") as HTMLElement;
    expect(portada.style.getPropertyValue("--portada")).toMatch(/portada-horror_cosmico\.webp/);
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
    // La ficha del apéndice lleva el nombre de esa versión: no se marca lista sin los cambios.
    const ficha = screen.getByRole("region", { name: "Personajes y lugares" });
    expect(within(ficha).getByRole("heading", { name: "Toby (ahora Nala)", level: 4 })).toBeInTheDocument();
  });

  it("en una versión anterior, si fallan los cambios no se marca lista", async () => {
    servidor.use(http.get("*/api/novelas/6/cambios", () => HttpResponse.json({ detail: "x" }, { status: 500 })));
    const { container } = renderizarEn("/novelas/6/lectura/imprimir?version=1");
    await waitFor(() => expect(container.querySelector("[data-error-impresion]")).not.toBeNull(), { timeout: 10_000 });
    expect(container.querySelector("[data-listo-para-imprimir]")).toBeNull();
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

  it("no se marca lista hasta decodificar la portada y el plano, y un fallo de carga no la bloquea (RF-FE-IMG-04)", async () => {
    // jsdom no tiene `decode`: se simula con promesas que el test resuelve a mano.
    const pendientes: { resolver: () => void; rechazar: (e: Error) => void }[] = [];
    const prototipo = HTMLImageElement.prototype as { decode?: () => Promise<void> };
    const original = prototipo.decode;
    prototipo.decode = () => new Promise<void>((resolver, rechazar) => pendientes.push({ resolver, rechazar }));
    try {
      const { container } = renderizarEn("/novelas/6/lectura/imprimir");
      await waitFor(() => expect(pendientes.length).toBeGreaterThanOrEqual(2));
      await screen.findByRole("region", { name: "Personajes y lugares" });
      await delay(300);
      expect(container.querySelector("[data-listo-para-imprimir]")).toBeNull();
      // La portada carga y el plano falla: decorativo, no bloquea.
      pendientes.forEach((p, i) => (i % 2 === 0 ? p.resolver() : p.rechazar(new Error("no carga"))));
      await waitFor(() => expect(container.querySelector("[data-listo-para-imprimir]")).not.toBeNull());
    } finally {
      if (original) prototipo.decode = original;
      else delete prototipo.decode;
    }
  });

  it("si fallan las apariciones tampoco se marca lista", async () => {
    servidor.use(http.get("*/api/novelas/6/apariciones", () => HttpResponse.json({ detail: "x" }, { status: 500 })));
    const { container } = renderizarEn("/novelas/6/lectura/imprimir");
    await waitFor(() => expect(container.querySelector("[data-error-impresion]")).not.toBeNull(), { timeout: 10_000 });
    expect(container.querySelector("[data-listo-para-imprimir]")).toBeNull();
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
