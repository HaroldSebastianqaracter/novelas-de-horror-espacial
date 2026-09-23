import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { servidor } from "../../compartido/api/mocks/servidor";
import type { Ejecucion, Intencion, NovelaResumen } from "../../compartido/api/tipos";
import { renderizarEn } from "../../pruebas/renderizar";

/** Un backend mínimo con estado: dos novelas y la intención que se pida, que el test cierra a mano. */
function escenario(estadoA: string, estadoB: string) {
  const ahora = new Date().toISOString();
  const novela = (id: number, titulo: string, estado: string): NovelaResumen => ({
    id, titulo, genero: "terror_espacial", creado_en: ahora, estado, capitulos_completados: 0,
  });
  const estado = { 1: estadoA, 2: estadoB } as Record<number, string>;
  const pedidas: { tipo: string; novela_id: number }[] = [];
  const intencion: { estado: string; motivo: string | null } = { estado: "pendiente", motivo: null };

  servidor.use(
    http.get("*/api/novelas", () =>
      HttpResponse.json([novela(1, "Esclusa norte", estado[1] as string), novela(2, "La bodega once", estado[2] as string)]),
    ),
    http.get("*/api/novelas/:id/ejecucion", ({ params }) =>
      HttpResponse.json<Ejecucion>({
        novela_id: Number(params.id),
        estado: estado[Number(params.id)] as string,
        actualizado_en: ahora,
        total_capitulos: 10,
        capitulos_completados: 0,
        intento_actual: 1,
      }),
    ),
    http.post("*/api/intenciones", async ({ request }) => {
      pedidas.push((await request.json()) as { tipo: string; novela_id: number });
      return HttpResponse.json({ id: 70, tipo: pedidas.at(-1)?.tipo, estado: "pendiente" }, { status: 202 });
    }),
    http.get("*/api/intenciones/70", () =>
      HttpResponse.json<Intencion>({
        id: 70, tipo: "arrancar", estado: intencion.estado, motivo: intencion.motivo, resultado: null, creado_en: ahora,
      }),
    ),
  );

  return {
    pedidas,
    /** El worker atiende la intención: la cierra y, si la hace, cambia el estado de la novela. */
    cerrar(resultado: "hecha" | "rechazada", cambio?: { novela: number; estado: string }, motivo: string | null = null) {
      if (cambio) estado[cambio.novela] = cambio.estado;
      intencion.estado = resultado;
      intencion.motivo = motivo;
    },
  };
}

const columna = (nombre: string) => screen.getByRole("region", { name: new RegExp(`^${nombre}`) });
const tarjetaDe = (titulo: string) => screen.getByRole("article", { name: titulo });
const ESPERA_LARGA = { timeout: 5_000 };

describe("intenciones desde el tablero (RF-FE-TAB-03, RF-FE-DAT-05)", () => {
  beforeEach(() => sessionStorage.clear());

  it("arrancar deja la tarjeta pendiente en su columna y la mueve cuando la ejecución lo confirma", async () => {
    const backend = escenario("detenida", "completada");
    const usuario = userEvent.setup();
    renderizarEn("/");

    await usuario.click(await screen.findByRole("button", { name: "Acciones: Esclusa norte" }));
    await usuario.click(screen.getByRole("menuitem", { name: "Arrancar" }));

    expect(await within(tarjetaDe("Esclusa norte")).findByRole("status")).toHaveTextContent("Arrancar en cola");
    expect(backend.pedidas).toEqual([{ tipo: "arrancar", novela_id: 1, payload: {} }]);
    // Sigue en «En espera»: la intención encolada no es la verdad.
    expect(within(columna("En espera")).getByRole("article", { name: "Esclusa norte" })).toBeInTheDocument();

    backend.cerrar("hecha", { novela: 1, estado: "planificando" });
    await waitFor(
      () => expect(within(columna("Planificando")).getByRole("article", { name: "Esclusa norte" })).toBeInTheDocument(),
      ESPERA_LARGA,
    );
    expect(within(tarjetaDe("Esclusa norte")).queryByRole("status")).not.toBeInTheDocument();
  }, 15_000);

  it("un rechazo deja la tarjeta donde estaba y dice el motivo en lenguaje legible", async () => {
    const backend = escenario("configurada", "completada");
    const usuario = userEvent.setup();
    renderizarEn("/");

    await usuario.click(await screen.findByRole("button", { name: "Acciones: Esclusa norte" }));
    await usuario.click(screen.getByRole("menuitem", { name: "Arrancar" }));
    backend.cerrar("rechazada", undefined, "otra_ejecucion_activa");

    const alerta = await within(tarjetaDe("Esclusa norte")).findByRole("alert", {}, ESPERA_LARGA);
    expect(alerta).toHaveTextContent("Arrancar: rechazada. Ya hay otra novela en curso: solo se genera una a la vez.");
    expect(within(columna("En espera")).getByRole("article", { name: "Esclusa norte" })).toBeInTheDocument();

    await usuario.click(within(alerta).getByRole("button", { name: "Entendido" }));
    expect(within(tarjetaDe("Esclusa norte")).queryByRole("alert")).not.toBeInTheDocument();
  }, 15_000);

  it("parar se pide desde el menú de la novela en curso", async () => {
    const backend = escenario("configurada", "generando");
    const usuario = userEvent.setup();
    renderizarEn("/");

    await usuario.click(await screen.findByRole("button", { name: "Acciones: La bodega once" }));
    await usuario.click(screen.getByRole("menuitem", { name: "Parar" }));
    await waitFor(() => expect(backend.pedidas).toEqual([{ tipo: "parar", novela_id: 2, payload: {} }]));
  });

  it("con otra novela en curso, «Arrancar» se ve desactivado, explica por qué y no pide nada (RF-FE-TAB-04)", async () => {
    const backend = escenario("configurada", "generando");
    const usuario = userEvent.setup();
    renderizarEn("/");

    await usuario.click(await screen.findByRole("button", { name: "Acciones: Esclusa norte" }));
    const arrancar = await screen.findByRole("menuitem", { name: /Arrancar/ });
    expect(arrancar).toHaveAttribute("aria-disabled", "true");
    expect(arrancar).toHaveTextContent("Ya hay una novela en curso");
    await usuario.click(arrancar);
    expect(backend.pedidas).toEqual([]);
  });

  it("una tarjeta de «Requiere atención» solo ofrece abrirla", async () => {
    renderizarEn("/");
    const usuario = userEvent.setup();
    await usuario.click(await screen.findByRole("button", { name: "Acciones: Señal de relevo" }));
    expect(screen.getAllByRole("menuitem").map((m) => m.textContent)).toEqual(["Abrir"]);
  });

  it("el menú se maneja con teclado y Escape devuelve el foco al botón (RF-FE-TAB-05)", async () => {
    escenario("configurada", "completada");
    const usuario = userEvent.setup();
    renderizarEn("/");

    const boton = await screen.findByRole("button", { name: "Acciones: Esclusa norte" });
    boton.focus();
    await usuario.keyboard("{Enter}");
    expect(screen.getByRole("menuitem", { name: "Arrancar" })).toHaveFocus();
    await usuario.keyboard("{ArrowDown}");
    expect(screen.getByRole("menuitem", { name: "Abrir" })).toHaveFocus();
    await usuario.keyboard("{Escape}");
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
    expect(boton).toHaveFocus();
  });
});
