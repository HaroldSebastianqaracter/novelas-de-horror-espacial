import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { sinViolaciones } from "../../pruebas/accesibilidad";
import { renderizarEn } from "../../pruebas/renderizar";

describe("portada, novedades e índice (RF-FE-LEE-01 a RF-FE-LEE-03, RF-FE-LEE-06)", () => {
  it("lee la última versión: título, dedicatoria, novedades y capítulos cambiados marcados", async () => {
    renderizarEn("/novelas/6/lectura");
    expect(await screen.findByRole("heading", { level: 1, name: "Deriva en el anillo Tántalo" })).toBeInTheDocument();
    expect(screen.getByText("Para Oda, que nunca deja un problema a medias.")).toBeInTheDocument();
    expect(screen.getByText("Versión 2", { selector: ".lectura__version" })).toBeInTheDocument();

    const novedades = screen.getByRole("region", { name: "Novedades de la versión 2" });
    expect(novedades).toHaveTextContent("Cambio pedido por el lector");
    expect(novedades).toHaveTextContent("El perro se llama Nala");
    expect(within(novedades).getByRole("link", { name: "el capítulo 3" })).toHaveAttribute(
      "href",
      "/novelas/6/lectura/capitulos/3?cambios=1",
    );

    const indice = screen.getByRole("navigation", { name: "Índice" });
    const entradas = within(indice).getAllByRole("listitem");
    expect(entradas).toHaveLength(10);
    expect(entradas[2]).toHaveTextContent("cambió en la versión 2");
    expect(entradas[0]).not.toHaveTextContent("cambió");
    expect(indice).not.toHaveTextContent("Objetivo");
  });

  it("una versión anterior se lee entera y sin novedades si es la primera", async () => {
    renderizarEn("/novelas/6/lectura?version=1");
    expect(await screen.findByRole("heading", { level: 1, name: "Deriva en el anillo Tántalo" })).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: /Novedades/ })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "ir a la última (2)" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Capítulo 3" })).toHaveAttribute("href", "/novelas/6/lectura/capitulos/3?version=1");
  });

  it("una novela sin versiones no tiene lectura y lo dice", async () => {
    renderizarEn("/novelas/3/lectura");
    expect(await screen.findByRole("heading", { name: "Esta novela todavía no tiene lectura" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ver cómo va en la consola" })).toHaveAttribute("href", "/novelas/3");
  });

  it("una versión que no existe lo dice", async () => {
    renderizarEn("/novelas/6/lectura?version=9");
    expect(await screen.findByRole("heading", { name: "No existe la versión 9" })).toBeInTheDocument();
  });
});

describe("capítulo y qué cambió (RF-FE-LEE-05, RF-FE-LEE-07)", () => {
  it("pinta el capítulo de la versión con sus escenas y navega entre capítulos", async () => {
    renderizarEn("/novelas/6/lectura/capitulos/3");
    expect(await screen.findByRole("heading", { level: 1, name: "Capítulo 3" })).toBeInTheDocument();
    expect(screen.getAllByRole("region", { name: /^Escena/ })).toHaveLength(3);
    expect(screen.getByText(/Nala ladró dos veces/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "← Capítulo 2" })).toHaveAttribute("href", "/novelas/6/lectura/capitulos/2");
    expect(screen.getByRole("link", { name: "Capítulo 4 →" })).toBeInTheDocument();
    await waitFor(() => expect(document.title).toBe("Capítulo 3 · Deriva en el anillo Tántalo · novelasv2"));
  });

  it("«ver qué cambió» compara con la versión anterior, con lo añadido y lo quitado marcados", async () => {
    const usuario = userEvent.setup();
    renderizarEn("/novelas/6/lectura/capitulos/3");
    await usuario.click(await screen.findByRole("button", { name: "Ver qué cambió en la versión 2" }));
    const insertados = await screen.findAllByText("Nala", { selector: "ins" });
    expect(insertados.length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText("Toby", { selector: "del" }).length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText(/Comparado con la versión 1/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ocultar los cambios" })).toHaveAttribute("aria-pressed", "true");
  });

  it("un capítulo que no cambió no ofrece comparar, y el enlace de novedades la abre ya activada", async () => {
    const { unmount } = renderizarEn("/novelas/6/lectura/capitulos/2");
    expect(await screen.findByRole("heading", { level: 1, name: "Capítulo 2" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Ver qué cambió/ })).not.toBeInTheDocument();
    unmount();
    renderizarEn("/novelas/6/lectura/capitulos/5?cambios=1");
    expect(await screen.findAllByText("Nala", { selector: "ins" })).not.toHaveLength(0);
  });
});

describe("personajes y lugares (RF-FE-LEE-04)", () => {
  it("cada personaje y lugar enlaza a los capítulos donde aparece, sin destripar la historia", async () => {
    renderizarEn("/novelas/6/lectura/ficha");
    const personajes = await screen.findByRole("region", { name: "Personajes" });
    const nala = within(personajes).getByRole("heading", { name: "Nala" }).closest("li") as HTMLElement;
    expect(nala).toHaveTextContent("Perra de la ingeniera · 6 años");
    expect(within(nala).getAllByRole("link").map((a) => a.getAttribute("aria-label"))).toEqual(["capítulo 3", "capítulo 5"]);
    expect(nala).toHaveTextContent("Aparece en los capítulos 3 y 5");
    expect(within(nala).getByRole("link", { name: "capítulo 3" })).toHaveAttribute("href", "/novelas/6/lectura/capitulos/3");

    const eco = within(personajes).getByRole("heading", { name: "Eco" }).closest("li") as HTMLElement;
    expect(eco).toHaveTextContent("No aparece en esta versión");
    expect(screen.queryByText(/No debería leerse/)).not.toBeInTheDocument();

    const lugares = screen.getByRole("region", { name: "Lugares" });
    const puente = within(lugares).getByRole("heading", { name: "Puente de mando" }).closest("li") as HTMLElement;
    expect(within(puente).getAllByRole("link").length).toBeGreaterThan(0);
    expect(screen.getByText(/sale de la escaleta/)).toBeInTheDocument();
  });
});

describe("la ficha de una versión anterior (RF-FE-LEE-04)", () => {
  it("busca «aparece en» en el texto de esa versión y avisa de que la ficha es la actual", async () => {
    renderizarEn("/novelas/6/lectura/ficha?version=1");
    const personajes = await screen.findByRole("region", { name: "Personajes" });
    const nala = within(personajes).getByRole("heading", { name: "Nala" }).closest("li") as HTMLElement;
    expect(nala).toHaveTextContent("No aparece en esta versión");
    expect(screen.getByText(/Esta ficha es la de la versión 2, la actual/)).toBeInTheDocument();
    const oda = within(personajes).getByRole("heading", { name: "Oda Varga" }).closest("li") as HTMLElement;
    expect(within(oda).getByRole("link", { name: "capítulo 1" })).toHaveAttribute("href", "/novelas/6/lectura/capitulos/1?version=1");
  });
});

describe("versiones (RF-FE-LEE-06)", () => {
  it("lista las versiones, la más nueva primero, con sus capítulos cambiados enlazados", async () => {
    renderizarEn("/novelas/6/lectura/versiones");
    const lista = await screen.findByRole("list");
    const entradas = within(lista).getAllByRole("listitem");
    expect(entradas[0]).toHaveTextContent("Versión 2la últimala que lees");
    expect(within(entradas[0] as HTMLElement).getByRole("link", { name: "capítulo 5" })).toHaveAttribute(
      "href",
      "/novelas/6/lectura/capitulos/5?cambios=1",
    );
    expect(within(entradas[1] as HTMLElement).getByRole("link", { name: "Leer la versión 1" })).toHaveAttribute(
      "href",
      "/novelas/6/lectura?version=1",
    );
    expect(entradas[1]).toHaveTextContent("Primera edición");
  });
});

describe("la lectura desde la consola y su accesibilidad (RF-FE-LEE-08)", () => {
  it("una novela completada enlaza a su lectura", async () => {
    renderizarEn("/novelas/6");
    expect(await screen.findByRole("link", { name: "Leer la novela" })).toHaveAttribute("href", "/novelas/6/lectura");
  });

  it("no tiene violaciones de accesibilidad automáticas", async () => {
    for (const ruta of [
      "/novelas/6/lectura",
      "/novelas/6/lectura/capitulos/3?cambios=1",
      "/novelas/6/lectura/ficha",
      "/novelas/6/lectura/versiones",
    ]) {
      const { container, unmount } = renderizarEn(ruta);
      await screen.findAllByRole("heading", { level: 1 });
      await waitFor(() => expect(screen.queryByText("Consultando…")).not.toBeInTheDocument());
      await sinViolaciones(container);
      unmount();
    }
  }, 20_000);
});
