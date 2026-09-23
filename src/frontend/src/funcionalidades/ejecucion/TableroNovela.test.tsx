import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { ejecuciones } from "../../compartido/api/mocks/datos";
import { servidor } from "../../compartido/api/mocks/servidor";
import { sinViolaciones } from "../../pruebas/accesibilidad";
import { renderizarEn } from "../../pruebas/renderizar";

const columna = (nombre: string) => screen.getByRole("region", { name: new RegExp(`^${nombre}`) });

describe("tablero de una novela (RF-FE-NOV)", () => {
  it("sin capítulos, enseña la barra de pasos con el paso en curso (RF-FE-NOV-02)", async () => {
    Object.assign(ejecuciones[1] ?? {}, { estado: "planificando", fase: "mundo" });
    renderizarEn("/novelas/1");

    const pasos = await screen.findByRole("list", { name: "Pasos de la planificación" });
    const arquitecto = within(pasos).getByText("Arquitecto").closest("li");
    const mundo = within(pasos).getByText("Mundo").closest("li");
    expect(arquitecto).toHaveAttribute("data-paso", "hecho");
    expect(mundo).toHaveAttribute("aria-current", "step");
    expect(within(mundo as HTMLElement).getByText("En curso")).toBeInTheDocument();
    expect(within(pasos).getByText("Estructura").closest("li")).toHaveAttribute("data-paso", "pendiente");
  });

  it("con capítulos, los reparte en Pendiente, En curso y Cerrado (RF-FE-NOV-03)", async () => {
    renderizarEn("/novelas/3");
    await screen.findByRole("heading", { level: 1, name: "La bodega once" });

    const enCurso = await screen.findByRole("region", { name: /^En curso/ });
    expect(within(enCurso).getByRole("heading", { name: "Capítulo 6" })).toBeInTheDocument();
    expect(within(enCurso).getByText("Redacción").closest("li")).toHaveAttribute("aria-current", "step");
    expect(within(enCurso).getByLabelText("Intento 2 de 3")).toBeInTheDocument();
    // Un capítulo en curso no existe para el lector: no enlaza a texto.
    expect(within(enCurso).queryByRole("link")).not.toBeInTheDocument();

    expect(within(columna("Pendiente")).getAllByRole("listitem")).toHaveLength(4);
    const cerrados = within(columna("Cerrado")).getAllByRole("link");
    expect(cerrados).toHaveLength(5);
    expect(cerrados[0]).toHaveAttribute("href", "/novelas/3/capitulos/5");
  });

  it("una novela en parada enseña la franja que lleva a la alerta (RF-FE-NOV-04)", async () => {
    renderizarEn("/novelas/4");
    const franja = await screen.findByRole("link", { name: /Parada P-93 · la ejecución espera tu decisión/ });
    expect(franja).toHaveAttribute("href", "/novelas/4/paradas/93");
  });

  it("una novela en error enseña el último error y no deja reintentar si otra está en curso", async () => {
    renderizarEn("/novelas/5");
    expect(await screen.findByText(/agotó sus dos reintentos/)).toBeInTheDocument();
    const reintentar = screen.getByRole("button", { name: /Reintentar/ });
    await waitFor(() => expect(reintentar).toBeDisabled());
    expect(screen.getByText("Ya hay una novela en curso: solo se genera una a la vez.")).toBeInTheDocument();
  });

  it("relanzar pide desde qué capítulo, dice qué se rehace y encola la intención", async () => {
    const pedidas: unknown[] = [];
    servidor.use(
      http.post("*/api/intenciones", async ({ request }) => {
        pedidas.push(await request.json());
        return HttpResponse.json({ id: 90, tipo: "relanzar", estado: "pendiente" }, { status: 202 });
      }),
    );
    const usuario = userEvent.setup();
    renderizarEn("/novelas/6");

    await usuario.click(await screen.findByRole("button", { name: /Relanzar…/ }));
    await usuario.selectOptions(screen.getByLabelText("Desde el capítulo"), "03");
    expect(screen.getByText("Se rehacen 8 capítulos ya cerrados, del 03 en adelante.")).toBeInTheDocument();
    await usuario.click(screen.getByRole("button", { name: "Relanzar" }));

    await waitFor(() =>
      expect(pedidas).toEqual([{ tipo: "relanzar", novela_id: 6, payload: { desde_capitulo: 3 } }]),
    );
    expect(await screen.findByText(/Relanzar en cola/)).toBeInTheDocument();
  });

  it("una novela que no existe lo dice con reintento", async () => {
    renderizarEn("/novelas/99");
    expect(await screen.findByRole("alert")).toHaveTextContent("No existe la novela");
  });

  it("no tiene violaciones de accesibilidad automáticas", async () => {
    const { container } = renderizarEn("/novelas/3");
    await screen.findByRole("heading", { name: "Capítulo 6" });
    await sinViolaciones(container);
  });
});
