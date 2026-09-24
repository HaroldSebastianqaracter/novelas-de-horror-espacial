import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent, { type UserEvent } from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { ejecuciones, novelas } from "../../compartido/api/mocks/datos";
import { terminarCambio } from "../../compartido/api/mocks/manejadores";
import { servidor } from "../../compartido/api/mocks/servidor";
import { sinViolaciones } from "../../pruebas/accesibilidad";
import { renderizarEn } from "../../pruebas/renderizar";

const CAPITULO = "/novelas/6/lectura/capitulos/3";

// En los datos de prueba la novela 3 se está generando, y eso bloquea pedir un cambio (el worker
// hace una cosa a la vez). Aquí se detiene; `restaurarDatos` la deja como estaba tras cada caso.
beforeEach(() => {
  for (const n of novelas) if (n.id !== 6 && n.estado === "generando") n.estado = "detenida";
  for (const e of Object.values(ejecuciones)) if (e.novela_id !== 6 && e.estado === "generando") e.estado = "detenida";
});

function registrarPedidas() {
  const pedidas: unknown[] = [];
  servidor.events.on("request:start", async ({ request }) => {
    if (request.method === "POST") pedidas.push(await request.clone().json());
  });
  return pedidas;
}

async function abrirPanel(usuario: UserEvent) {
  const boton = await screen.findByRole("button", { name: "Pedir un cambio" });
  await waitFor(() => expect(boton).toBeEnabled());
  await usuario.click(boton);
  return screen.findByRole("region", { name: "Pedir un cambio" });
}

async function pedir(usuario: UserEvent, panel: HTMLElement, objetivo: RegExp, peticion: string) {
  await usuario.click(await within(panel).findByRole("radio", { name: objetivo }));
  await usuario.type(within(panel).getByLabelText(/Qué quieres cambiar/), peticion);
  await usuario.click(within(panel).getByRole("button", { name: "Pedir el cambio" }));
  await usuario.click(within(panel).getByRole("button", { name: "Confirmar: pedir el cambio" }));
}

describe("pedir un cambio desde el texto (RF-FE-CAM-01 a RF-FE-CAM-03)", () => {
  it("dice el alcance antes de confirmar y manda el payload del contrato", async () => {
    const pedidas = registrarPedidas();
    const usuario = userEvent.setup();
    renderizarEn(CAPITULO);
    const panel = await abrirPanel(usuario);
    expect(within(panel).getByText(/Sin fragmento/)).toBeInTheDocument();

    await usuario.click(await within(panel).findByRole("radio", { name: "Nala (personaje)" }));
    expect(await within(panel).findByText("Se reescribirán los capítulos 3 y 5.")).toBeInTheDocument();
    await usuario.type(within(panel).getByLabelText(/Qué quieres cambiar/), "El perro se llama Luna");
    await usuario.click(within(panel).getByRole("button", { name: "Pedir el cambio" }));
    expect(within(panel).getByText(/cuesta dinero/)).toBeInTheDocument();
    await usuario.click(within(panel).getByRole("button", { name: "Confirmar: pedir el cambio" }));

    await waitFor(() =>
      expect(pedidas).toEqual([
        {
          tipo: "cambio_lector",
          novela_id: 6,
          payload: { version_base: 2, objetivo: { tipo: "entidad", entidad: "personajes", id: 4 }, peticion: "El perro se llama Luna" },
        },
      ]),
    );
    servidor.events.removeAllListeners();
  });

  it("al seleccionar texto aparece «Pedir un cambio» y la cita va con el cambio", async () => {
    const pedidas = registrarPedidas();
    const usuario = userEvent.setup();
    renderizarEn(CAPITULO);
    const parrafo = await screen.findByText(/Nala ladró dos veces/);
    await waitFor(() => expect(screen.getByRole("button", { name: "Pedir un cambio" })).toBeEnabled());
    act(() => {
      const rango = document.createRange();
      rango.selectNodeContents(parrafo);
      const sel = document.getSelection();
      sel?.removeAllRanges();
      sel?.addRange(rango);
      document.dispatchEvent(new Event("selectionchange"));
    });
    const burbujas = await screen.findAllByRole("button", { name: "Pedir un cambio" });
    await usuario.click(burbujas.at(-1) as HTMLElement);
    const panel = await screen.findByRole("region", { name: "Pedir un cambio" });
    expect(within(panel).getByText(/Nala ladró dos veces hacia el conducto/, { selector: "blockquote" })).toBeInTheDocument();
    expect(within(panel).getByRole("radio", { name: "El fragmento tal cual" })).toBeInTheDocument();
    expect(within(panel).queryByRole("radio", { name: /Ciro Lenz/ })).not.toBeInTheDocument();

    await pedir(usuario, panel, /^El fragmento tal cual/, "Que ladre tres veces");
    await waitFor(() => expect(pedidas).toHaveLength(1));
    expect(pedidas[0]).toMatchObject({
      payload: { objetivo: { tipo: "fragmento" }, cita: { capitulo: 3, texto: expect.stringContaining("Nala ladró dos veces") } },
    });
    servidor.events.removeAllListeners();
  });

  it("si la API no da el alcance, lo dice y no se inventa uno", async () => {
    servidor.use(http.get("*/api/novelas/6/cambios/alcance", () => HttpResponse.json({ detail: "Not Found" }, { status: 404 })));
    const usuario = userEvent.setup();
    renderizarEn(CAPITULO);
    const panel = await abrirPanel(usuario);
    await usuario.click(await within(panel).findByRole("radio", { name: "Nala (personaje)" }));
    expect(await within(panel).findByText(/No se pudo calcular qué capítulos se reescribirán/)).toBeInTheDocument();
    expect(within(panel).queryByText(/Se reescribirán/)).not.toBeInTheDocument();
  });

  it("un 422 cambio_invalido se enseña en el panel y no se pierde lo escrito", async () => {
    servidor.use(
      http.post("*/api/intenciones", () =>
        HttpResponse.json(
          {
            codigo: "cambio_invalido",
            mensaje: "El cambio pedido no es valido",
            detalle: JSON.stringify([{ campo: "peticion", error: "demasiado corta" }]),
          },
          { status: 422 },
        ),
      ),
    );
    const usuario = userEvent.setup();
    renderizarEn(CAPITULO);
    const panel = await abrirPanel(usuario);
    await pedir(usuario, panel, /Nala/, "El perro se llama Luna");
    expect(await within(panel).findByRole("alert")).toHaveTextContent("El cambio pedido no es valido (peticion: demasiado corta)");
    expect(within(panel).getByLabelText(/Qué quieres cambiar/)).toHaveValue("El perro se llama Luna");
  });

  it("con otra novela generándose tampoco, y lo dice", async () => {
    const tres = novelas.find((n) => n.id === 3);
    if (tres) tres.estado = "generando";
    renderizarEn(CAPITULO);
    expect(await screen.findByText("Hay otra novela generándose: el worker hace una cosa a la vez.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Pedir un cambio" })).toBeDisabled();
  });

  it("solo sobre la última versión y con la novela terminada: si no, dice por qué", async () => {
    const { unmount } = renderizarEn(`${CAPITULO}?version=1`);
    expect(await screen.findByRole("button", { name: "Pedir un cambio" })).toBeDisabled();
    expect(screen.getByText("Solo se pide sobre la última versión.")).toBeInTheDocument();
    unmount();

    Object.assign(ejecuciones[6] ?? {}, { estado: "generando", fase: "revision" });
    renderizarEn(CAPITULO);
    expect(await screen.findByText("La novela se está generando o no está terminada.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Pedir un cambio" })).toBeDisabled();
  });
});

describe("seguir el cambio (RF-FE-CAM-04, RF-FE-CAM-05)", () => {
  it("se sigue hasta la versión nueva, que marca sus capítulos, y la anterior queda", async () => {
    const usuario = userEvent.setup();
    renderizarEn(CAPITULO);
    await pedir(usuario, await abrirPanel(usuario), /Nala/, "El perro se llama Luna");

    const franja = await screen.findByRole("status", { name: "Tu cambio" });
    expect(franja).toHaveTextContent("Tu cambio: El perro se llama Luna");
    await waitFor(() => expect(franja).toHaveTextContent(/Reescribiendo por tu cambio los capítulos 3 y 5 · Aplicando tu cambio/), {
      timeout: 8_000,
    });
    expect(screen.getByRole("button", { name: "Pedir un cambio" })).toBeDisabled();

    terminarCambio(6);
    const hecho = await screen.findByText(/Versión 3:/, {}, { timeout: 8_000 });
    const seccion = hecho.closest("section") as HTMLElement;
    expect(seccion).toHaveTextContent("Versión 3: cambiaron los capítulos 3 y 5. La versión 2 se sigue pudiendo leer.");
    expect(within(seccion).getByRole("link", { name: "3" })).toHaveAttribute("href", "/novelas/6/lectura/capitulos/3?cambios=1");
  }, 25_000);

  it("un cambio que no es de la historia se rechaza con su explicación", async () => {
    const usuario = userEvent.setup();
    renderizarEn(CAPITULO);
    await pedir(usuario, await abrirPanel(usuario), /Nala/, "Hazlo más triste");
    const alerta = await screen.findByRole("alert", { name: "Tu cambio" }, { timeout: 8_000 });
    expect(alerta).toHaveTextContent("No se aplicó. Ese cambio no se puede aplicar como un cambio de la historia.");
    expect(alerta).toHaveTextContent("es una indicación de estilo");
    await usuario.click(within(alerta).getByRole("button", { name: "Cerrar" }));
    expect(screen.queryByRole("alert", { name: "Tu cambio" })).not.toBeInTheDocument();
  }, 15_000);

  it("un cambio que fracasa no abre parada: lo dice y no hay versión nueva", async () => {
    const usuario = userEvent.setup();
    renderizarEn(CAPITULO);
    await pedir(usuario, await abrirPanel(usuario), /Nala/, "Que el cambio fracase");
    await screen.findByText(/Reescribiendo por tu cambio/, {}, { timeout: 8_000 });
    terminarCambio(6);
    const alerta = await screen.findByRole("alert", { name: "Tu cambio" }, { timeout: 8_000 });
    expect(alerta).toHaveTextContent("No se pudo aplicar tu cambio. La novela sigue como estaba, sin versión nueva.");
    expect(alerta).toHaveTextContent("Tres intentos sin pasar la puerta 4");
  }, 25_000);

  it("tras un rechazo se puede pedir otro cambio, aunque la franja siga a la vista", async () => {
    const usuario = userEvent.setup();
    renderizarEn(CAPITULO);
    await pedir(usuario, await abrirPanel(usuario), /Nala/, "Hazlo más triste");
    await screen.findByRole("alert", { name: "Tu cambio" }, { timeout: 8_000 });
    await waitFor(() => expect(screen.getByRole("button", { name: "Pedir un cambio" })).toBeEnabled());
    expect(screen.queryByText("Ya hay un cambio tuyo en marcha.")).not.toBeInTheDocument();
  }, 20_000);

  it("la franja sobrevive a recargar: se reconstruye desde el GET", async () => {
    const usuario = userEvent.setup();
    const { unmount } = renderizarEn(CAPITULO);
    await pedir(usuario, await abrirPanel(usuario), /Nala/, "El perro se llama Luna");
    await screen.findByRole("status", { name: "Tu cambio" });
    unmount();
    renderizarEn(CAPITULO);
    const franja = await screen.findByRole("status", { name: "Tu cambio" });
    expect(franja).toHaveTextContent("Tu cambio: El perro se llama Luna");
    await waitFor(() => expect(franja).toHaveTextContent(/Reescribiendo por tu cambio los capítulos 3 y 5/), { timeout: 8_000 });
  }, 25_000);

  it("un cambio interrumpido dice que se detuvo, no que falló", async () => {
    servidor.use(
      http.get("*/api/novelas/6/cambios/:cid", ({ params }) =>
        HttpResponse.json({ id: Number(params.cid), estado: "interrumpido", peticion: "x", objetivo: { tipo: "fragmento" }, cita: null, cambio: null, capitulos: [3], informe: null, version: null, creado_en: "2026-09-24 10:00:00" }),
      ),
    );
    const usuario = userEvent.setup();
    renderizarEn(CAPITULO);
    await pedir(usuario, await abrirPanel(usuario), /Nala/, "El perro se llama Luna");
    const alerta = await screen.findByRole("alert", { name: "Tu cambio" }, { timeout: 8_000 });
    expect(alerta).toHaveTextContent("Se detuvo antes de terminar. No se aplicó nada y no hay versión nueva.");
  }, 20_000);

  it("al cancelar, el foco vuelve al botón que abrió el panel", async () => {
    const usuario = userEvent.setup();
    renderizarEn(CAPITULO);
    const panel = await abrirPanel(usuario);
    expect(within(panel).getByRole("heading", { name: "Pedir un cambio" })).toHaveFocus();
    await usuario.click(within(panel).getByRole("button", { name: "Cancelar" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Pedir un cambio" })).toHaveFocus());
  });

  it("el panel no tiene violaciones de accesibilidad automáticas", async () => {
    const usuario = userEvent.setup();
    const { container } = renderizarEn(CAPITULO);
    const panel = await abrirPanel(usuario);
    await within(panel).findByRole("radio", { name: "Nala (personaje)" });
    await sinViolaciones(container);
  });
});
