import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { versionesDe } from "../../compartido/api/mocks/lectura";
import { servidor } from "../../compartido/api/mocks/servidor";
import { sinViolaciones } from "../../pruebas/accesibilidad";
import { renderizarEn } from "../../pruebas/renderizar";

describe("portada, novedades e índice (RF-FE-LEE-01 a RF-FE-LEE-03, RF-FE-LEE-06)", () => {
  it("lee la última versión: título, dedicatoria, novedades y capítulos cambiados marcados", async () => {
    renderizarEn("/novelas/6/lectura");
    expect(await screen.findByRole("heading", { level: 1, name: "Deriva en el anillo Tántalo" })).toBeInTheDocument();
    expect(screen.getByText("Para Oda, que nunca deja un problema a medias.")).toBeInTheDocument();
    expect(await screen.findByText("Para Oda Varga · De Lía y Marcos · Cumpleaños")).toBeInTheDocument();
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

describe("la portada ilustrada (RF-FE-IMG-01)", () => {
  const ilustracion = async () => {
    const titulo = await screen.findByRole("heading", { level: 1, name: "Deriva en el anillo Tántalo" });
    const portada = titulo.closest("article") as HTMLElement;
    return () => portada.style.getPropertyValue("--portada");
  };

  it("lleva la ilustración de su subgénero, en tamaño de pantalla", async () => {
    renderizarEn("/novelas/6/lectura");
    const fondo = await ilustracion();
    await waitFor(() => expect(fondo()).toContain("portada-horror_cosmico-web"));
  });

  it("sin subgénero, la genérica; y hasta saberlo, ninguna", async () => {
    let soltar = () => {};
    const detalle = new Promise<void>((r) => {
      soltar = r;
    });
    servidor.use(
      http.get("*/api/novelas/6", async () => {
        await detalle;
        return HttpResponse.json({
          novela: { id: 6, titulo: "Deriva en el anillo Tántalo", genero: "terror_espacial", creado_en: "2026-09-20 10:00:00", subgenero_dominante: null },
          restricciones: {},
          estilo: null,
          dedicatoria: null,
          regalo: null,
        });
      }),
    );
    renderizarEn("/novelas/6/lectura");
    const fondo = await ilustracion();
    expect(fondo()).toBe("");
    soltar();
    await waitFor(() => expect(fondo()).toContain("portada-generica-web"));
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
    expect(screen.getByText(/sale de la story bible/)).toBeInTheDocument();
  });

  it("«aparece en» es lo que dice /apariciones, por id y solo con capítulos de la versión", async () => {
    servidor.use(
      http.get("*/api/novelas/6/apariciones", () =>
        HttpResponse.json({
          personajes: [
            { id: 5, nombre: "Eco", capitulos: [7, 12] },
            { id: 4, nombre: "Otro nombre", capitulos: [] },
          ],
          lugares: [],
        }),
      ),
    );
    renderizarEn("/novelas/6/lectura/ficha");
    const personajes = await screen.findByRole("region", { name: "Personajes" });
    const eco = within(personajes).getByRole("heading", { name: "Eco" }).closest("li") as HTMLElement;
    await waitFor(() => expect(eco).toHaveTextContent("Aparece en el capítulo 7"));
    expect(within(eco).getAllByRole("link").map((a) => a.getAttribute("aria-label"))).toEqual(["capítulo 7"]);
    const nala = within(personajes).getByRole("heading", { name: "Nala" }).closest("li") as HTMLElement;
    expect(nala).toHaveTextContent("No aparece en esta versión");
  });
});

describe("la ficha de una versión anterior (RF-FE-LEE-04)", () => {
  it("lleva los nombres de esa versión, con las apariciones de la story bible, y avisa de que la ficha es la actual", async () => {
    renderizarEn("/novelas/6/lectura/ficha?version=1");
    const personajes = await screen.findByRole("region", { name: "Personajes" });
    const toby = (await within(personajes).findByRole("heading", { name: "Toby (ahora Nala)" })).closest("li") as HTMLElement;
    expect(toby).toHaveTextContent("Aparece en los capítulos 3 y 5");
    expect(within(toby).getByRole("link", { name: "capítulo 3" })).toHaveAttribute("href", "/novelas/6/lectura/capitulos/3?version=1");
    expect(within(personajes).queryByRole("heading", { name: "Nala" })).not.toBeInTheDocument();
    expect(screen.getByText(/Esta ficha es la de la versión 2, la actual, con los nombres de la versión que lees/)).toBeInTheDocument();
    const oda = within(personajes).getByRole("heading", { name: "Oda Varga" }).closest("li") as HTMLElement;
    expect(within(oda).getByRole("link", { name: "capítulo 1" })).toHaveAttribute("href", "/novelas/6/lectura/capitulos/1?version=1");
  });
});

describe("un renombre deshecho después (RF-FE-LEE-04)", () => {
  it("no pone «(ahora …)» si el nombre de entonces es el de ahora", async () => {
    servidor.use(
      http.get("*/api/novelas/6/cambios", () =>
        HttpResponse.json([
          { id: 1, estado: "aplicado", peticion: "Nala", objetivo: { tipo: "entidad", entidad: "personajes", id: 4 }, cita: null, cambio: { tipo: "renombrar", antes: "Nala", despues: "Kira", tabla: "personaje", entidad_id: 4 }, capitulos: [3], version: 2, creado_en: "2026-09-24 10:00:00" },
          { id: 2, estado: "aplicado", peticion: "Nala otra vez", objetivo: { tipo: "entidad", entidad: "personajes", id: 4 }, cita: null, cambio: { tipo: "renombrar", antes: "Kira", despues: "Nala", tabla: "personaje", entidad_id: 4 }, capitulos: [3], version: 3, creado_en: "2026-09-24 11:00:00" },
        ]),
      ),
    );
    renderizarEn("/novelas/6/lectura/ficha?version=1");
    const personajes = await screen.findByRole("region", { name: "Personajes" });
    expect(await within(personajes).findByRole("heading", { name: "Nala" })).toBeInTheDocument();
    expect(within(personajes).queryByText(/ahora/)).not.toBeInTheDocument();
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

describe("navegar, títulos y pistas (RF-FE-LEE-07, RF-FE-LEE-08)", () => {
  it("al cambiar de capítulo se vuelve arriba y el foco va al texto; al cargar, no", async () => {
    const usuario = userEvent.setup();
    renderizarEn("/novelas/6/lectura/capitulos/3");
    await screen.findByRole("heading", { level: 1, name: "Capítulo 3" });
    const principal = document.getElementById("contenido-lectura") as HTMLElement;
    expect(principal).not.toHaveFocus();

    document.documentElement.scrollTop = 800;
    await usuario.click(screen.getByRole("link", { name: "Capítulo 4 →" }));
    await screen.findByRole("heading", { level: 1, name: "Capítulo 4" });
    await waitFor(() => expect(principal).toHaveFocus());
    expect(document.documentElement.scrollTop).toBe(0);
  });

  it("los estados de aviso también cambian el título de la pestaña", async () => {
    const { unmount } = renderizarEn("/novelas/3/lectura");
    await screen.findByRole("heading", { name: "Esta novela todavía no tiene lectura" });
    await waitFor(() => expect(document.title).toBe("Sin lectura todavía · novelasv2"));
    unmount();
    renderizarEn("/novelas/6/lectura?version=9");
    await screen.findByRole("heading", { name: "No existe la versión 9" });
    await waitFor(() => expect(document.title).toBe("No existe la versión 9 · novelasv2"));
  });

  it("lo añadido y lo quitado llevan pista para lectores de pantalla, y una escena nueva se marca", async () => {
    const version1 = structuredClone(versionesDe[6]?.[0]);
    const tres = version1?.capitulos.find((c) => c.numero === 3);
    // En la versión 1, el capítulo 3 no tenía la última escena: en la 2 aparece entera.
    if (tres) tres.texto = tres.texto.split("\n\n* * *\n\n").slice(0, 2).join("\n\n* * *\n\n");
    servidor.use(http.get("*/api/novelas/6/versiones/1", () => HttpResponse.json(version1)));
    renderizarEn("/novelas/6/lectura/capitulos/3?cambios=1");
    const escenaNueva = await screen.findByText("(escena nueva)");
    expect(escenaNueva.closest("p")).toHaveAttribute("data-cambio", "nuevo");
    const insertado = screen.getAllByText(/Nala ladró dos veces/, { selector: "ins" })[0] as HTMLElement;
    expect(insertado).toHaveTextContent("[añadido: Nala ladró dos veces");
  });
});
