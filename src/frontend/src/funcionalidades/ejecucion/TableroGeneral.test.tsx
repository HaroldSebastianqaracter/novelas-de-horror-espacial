import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { servidor } from "../../compartido/api/mocks/servidor";
import { renderizarEn } from "../../pruebas/renderizar";
import { sinViolaciones } from "../../pruebas/accesibilidad";

const columna = (nombre: string) => screen.getByRole("region", { name: new RegExp(`^${nombre}`) });

describe("miniaturas de portada en el tablero (RF-FE-IMG-06)", () => {
  it("las novelas terminadas llevan la de su subgénero, y las demás ninguna", async () => {
    const { container } = renderizarEn("/");
    const terminada = (await screen.findByRole("link", { name: "Deriva en el anillo Tántalo" })).closest("article") as HTMLElement;
    const miniatura = terminada.querySelector(".miniatura-portada") as HTMLElement;
    expect(miniatura).toHaveAttribute("aria-hidden", "true");
    expect(miniatura.style.getPropertyValue("--portada")).toContain("portada-horror_cosmico-web");
    expect(container.querySelectorAll(".tarjeta .miniatura-portada")).toHaveLength(1);
  });

  it("manda el estado de la ejecución si la hay, y el del resumen si no; y cuenta también «completada»", async () => {
    const resumen = (id: number, titulo: string, subgenero: string | null) => ({
      id, titulo, genero: "terror_espacial", creado_en: "2026-09-24 10:00:00", estado: "completada", capitulos_completados: 10, subgenero_dominante: subgenero,
    });
    const ejecucion = (id: number, estado: string) => ({
      novela_id: id, estado, fase: estado === "generando" ? "revision" : null, capitulo_actual: 3, intento_actual: 1,
      capitulos_completados: 10, total_capitulos: 10, parada_abierta_id: null, ultimo_error: null, actualizado_en: "2026-09-24 10:00:00",
    });
    servidor.use(
      http.get("*/api/novelas", () =>
        HttpResponse.json([resumen(20, "Limpia", "supervivencia"), resumen(21, "Reescribiéndose", "ia_hostil"), resumen(22, "Sin ejecución", null)]),
      ),
      http.get("*/api/novelas/:id/ejecucion", ({ params }) => {
        const id = Number(params.id);
        if (id === 20) return HttpResponse.json(ejecucion(20, "completada"));
        // El resumen dice completada, pero la ejecución ya está aplicando un cambio del lector.
        if (id === 21) return HttpResponse.json(ejecucion(21, "generando"));
        return HttpResponse.json({ codigo: "no_encontrada", mensaje: "No existe" }, { status: 404 });
      }),
    );
    renderizarEn("/");
    const tarjeta = async (titulo: string) => (await screen.findByRole("link", { name: titulo })).closest("article") as HTMLElement;
    const limpia = await tarjeta("Limpia");
    await waitFor(() => expect(limpia).toHaveAttribute("data-estado", "completada"));
    expect((limpia.querySelector(".miniatura-portada") as HTMLElement).style.getPropertyValue("--portada")).toContain("portada-supervivencia-web");
    const reescribiendose = await tarjeta("Reescribiéndose");
    await waitFor(() => expect(reescribiendose).toHaveAttribute("data-estado", "generando"));
    expect(reescribiendose.querySelector(".miniatura-portada")).toBeNull();
    const sinEjecucion = await tarjeta("Sin ejecución");
    expect((sinEjecucion.querySelector(".miniatura-portada") as HTMLElement).style.getPropertyValue("--portada")).toContain("portada-generica-web");
  });
});

describe("tablero general (RF-FE-TAB)", () => {
  it("cada novela está en la columna de su estado", async () => {
    renderizarEn("/");
    await screen.findByRole("link", { name: "La bodega once" });

    expect(within(columna("En espera")).getByRole("link", { name: "Esclusa norte" })).toBeInTheDocument();
    expect(within(columna("En espera")).getByRole("link", { name: "Sin título" })).toBeInTheDocument();
    expect(within(columna("Escribiendo")).getByRole("link", { name: "La bodega once" })).toBeInTheDocument();
    expect(within(columna("Terminada")).getByRole("link", { name: "Deriva en el anillo Tántalo" })).toBeInTheDocument();
    expect(within(columna("Planificando")).getByText(/Suelta aquí/)).toBeInTheDocument();
  });

  it("parada y error van al carril de atención y no a otra columna", async () => {
    renderizarEn("/");
    await screen.findByRole("link", { name: "La bodega once" });
    const carril = columna("Requiere atención");

    expect(within(carril).getByRole("link", { name: "Perforación en el pozo siete" })).toBeInTheDocument();
    expect(within(carril).getByRole("link", { name: "Señal de relevo" })).toBeInTheDocument();
    expect(within(columna("En espera")).queryByRole("link", { name: "Señal de relevo" })).not.toBeInTheDocument();
  });

  it("una tarjeta en parada lleva a su alerta y una en error enseña el último error", async () => {
    renderizarEn("/");
    expect(await screen.findByRole("link", { name: "Perforación en el pozo siete" })).toHaveAttribute(
      "href",
      "/novelas/4/paradas/93",
    );
    expect(await screen.findByText(/agotó sus dos reintentos/)).toBeInTheDocument();
  });

  it("la tarjeta en curso muestra fase, capítulo, intento y progreso", async () => {
    renderizarEn("/");
    const tarjeta = (await screen.findByRole("link", { name: "La bodega once" })).closest("article");
    if (!tarjeta) throw new Error("La tarjeta no es un <article>");
    expect(await within(tarjeta).findByText("Fase Redacción · cap. 6 · intento 2/3")).toBeInTheDocument();
    expect(within(tarjeta).getByRole("progressbar")).toHaveAttribute("aria-valuetext", "5 de 10 capítulos cerrados");
    expect(within(tarjeta).getByText("Generando")).toBeInTheDocument();
  });

  it("el resumen nombra la novela en curso y cuántas requieren atención", async () => {
    renderizarEn("/");
    expect(await screen.findByText(/6 novelas · en curso:/)).toHaveTextContent("en curso: La bodega once · 2 requieren atención");
  });

  it("un estado que el cliente no conoce se pinta tal cual y no esconde la novela", async () => {
    servidor.use(
      http.get("*/api/novelas", () =>
        HttpResponse.json([
          { id: 9, titulo: "Estado raro", genero: "terror_espacial", creado_en: new Date().toISOString(), estado: "revisando", capitulos_completados: 0 },
        ]),
      ),
      http.get("*/api/novelas/9/ejecucion", () =>
        HttpResponse.json({ novela_id: 9, estado: "revisando", actualizado_en: new Date().toISOString() }),
      ),
    );
    renderizarEn("/");
    expect(await screen.findByRole("link", { name: "Estado raro" })).toBeInTheDocument();
    expect(within(columna("En espera")).getByText("revisando")).toBeInTheDocument();
  });

  it("no tiene violaciones de accesibilidad automáticas", async () => {
    const { container } = renderizarEn("/");
    await screen.findByText("Fase Redacción · cap. 6 · intento 2/3");
    await sinViolaciones(container);
  });
});
