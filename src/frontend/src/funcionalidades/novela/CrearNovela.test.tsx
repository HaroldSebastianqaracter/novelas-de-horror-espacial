import { screen, waitFor, within } from "@testing-library/react";
import userEvent, { type UserEvent } from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { analisisDeError } from "../../compartido/api/brief";
import { ErrorApi } from "../../compartido/api/cliente";
import { servidor } from "../../compartido/api/mocks/servidor";
import { sinViolaciones } from "../../pruebas/accesibilidad";
import { renderizarEn } from "../../pruebas/renderizar";
import { aBrief, borradorVacio, erroresDeForma, erroresDelAnalisis, primerPasoConErrores } from "./borrador";

describe("del borrador al brief", () => {
  it("no envía lo vacío, recorta, parte listas y nunca manda texto_libre, codigo ni cita (RF-FE-BRF-02, RF-FE-BRF-03)", () => {
    const b = {
      ...borradorVacio(),
      nombre: "  Nombre   de prueba ",
      edad: "30",
      rasgos: [
        { id: "a", texto: " Terca ", obligatorio: true },
        { id: "b", texto: "   ", obligatorio: true },
      ],
      allegados: [{ id: "c", nombre: "Perro de prueba", relacion: "su perro", rasgos: "miedoso, viejo", obligatorio: false }],
      vetados: "arañas,\nsangre",
    };
    const brief = aBrief(b);
    expect(brief.destinatario).toEqual({ nombre: "Nombre   de prueba", edad: 30, rasgos: [{ texto: "Terca", obligatorio: true }] });
    expect(brief.allegados).toEqual([{ nombre: "Perro de prueba", relacion: "su perro", rasgos: ["miedoso", "viejo"], obligatorio: false }]);
    expect(brief.vetados).toEqual(["arañas", "sangre"]);
    expect(brief.capitulos).toBe(10);
    const json = JSON.stringify(brief);
    for (const prohibido of ["texto_libre", "codigo", "cita", "ocasion", "subgenero"]) expect(json).not.toContain(`"${prohibido}"`);
  });

  it("los límites de forma se comprueban en el cliente; qué falta, no", () => {
    expect(erroresDeForma(borradorVacio())).toEqual({});
    const e = erroresDeForma({
      ...borradorVacio(),
      edad: "doce",
      capitulos: "2",
      allegados: [{ id: "x", nombre: "Sin relación", relacion: "", rasgos: "", obligatorio: true }],
    });
    expect(Object.keys(e).sort()).toEqual(["allegados", "capitulos", "destinatario.edad"]);
  });

  it("lleva cada faltante y cada contradicción a su campo y su paso", () => {
    const e = erroresDelAnalisis({
      faltantes: ["tono"],
      contradicciones: [
        { codigo: "elemento_con_vetado", campos: ["vetados", "rasgo RAS1"], mensaje: "Vetado en un rasgo." },
      ],
    });
    expect(e).toEqual({ tono: ["Falta este dato."], vetados: ["Vetado en un rasgo."], "destinatario.rasgos": ["Vetado en un rasgo."] });
    expect(primerPasoConErrores(e)).toBe(0);
  });

  it("reconoce el 422 de brief_incompleto y nada más", () => {
    const detalle = JSON.stringify({ faltantes: ["ocasion"], contradicciones: [] });
    expect(analisisDeError(new ErrorApi(422, { codigo: "brief_incompleto", detalle }))).toEqual({ faltantes: ["ocasion"], contradicciones: [] });
    expect(analisisDeError(new ErrorApi(422, { codigo: "peticion_invalida", mensaje: "x" }))).toBeNull();
    expect(analisisDeError(new Error("red"))).toBeNull();
  });
});

async function rellenar(usuario: UserEvent, edad: string) {
  await usuario.type(await screen.findByLabelText(/^Nombre/), "Destinataria de prueba");
  await usuario.type(screen.getByLabelText(/^Edad/), edad);
  await usuario.click(screen.getByRole("radio", { name: "Ella" }));
  await usuario.type(screen.getByLabelText("Rasgo 1"), "Terca");
  await usuario.click(screen.getByRole("button", { name: "Siguiente" }));

  await usuario.type(await screen.findByLabelText("Recuerdo 1"), "Veranos en un faro");
  await usuario.click(screen.getByRole("button", { name: "Siguiente" }));

  await usuario.selectOptions(await screen.findByLabelText(/^Ocasión/), "cumpleanos");
  await usuario.type(screen.getByLabelText(/^Quién regala/), "Alguien que la quiere");
  await usuario.click(screen.getByRole("button", { name: "Siguiente" }));

  await usuario.click(await screen.findByRole("radio", { name: /^Tensión/ }));
  await usuario.click(screen.getByRole("radio", { name: /^Emotivo/ }));
  await usuario.click(screen.getByRole("button", { name: "Siguiente" }));
  await screen.findByRole("heading", { name: "5 · Revisión" });
}

describe("formulario del brief (RF-FE-BRF)", () => {
  beforeEach(() => localStorage.clear());

  it("con un brief completo, crea la novela y lleva a su tablero (RF-FE-BRF-05)", async () => {
    const enviados: unknown[] = [];
    servidor.events.on("request:start", async ({ request }) => {
      if (request.method === "POST") enviados.push(await request.clone().json());
    });
    const usuario = userEvent.setup();
    renderizarEn("/crear");
    await rellenar(usuario, "30");

    expect(screen.getByText("Tensión (desde 14 años)")).toBeInTheDocument();
    await usuario.click(screen.getByRole("button", { name: "Crear novela" }));
    expect(await screen.findByText(/esperando asignación/)).toBeInTheDocument();

    expect(await screen.findByRole("heading", { level: 1, name: "Sin título" }, { timeout: 6_000 })).toBeInTheDocument();
    const cuerpo = enviados[0] as { tipo: string; payload: { brief: Record<string, unknown> } };
    expect(cuerpo.tipo).toBe("crear_novela");
    expect(cuerpo.payload.brief).toMatchObject({ intensidad: "tension", tono: "emotivo", ocasion: "cumpleanos" });
    expect(localStorage.getItem("novelasv2.borrador-brief")).toBeNull();
    servidor.events.removeAllListeners();
  }, 30_000);

  it("un 422 de brief_incompleto lleva al paso del campo y lo marca con el mensaje del servidor (RF-FE-BRF-04)", async () => {
    const usuario = userEvent.setup();
    renderizarEn("/crear");
    await rellenar(usuario, "12");
    await usuario.click(screen.getByRole("button", { name: "Crear novela" }));

    // Edad (paso 1) e intensidad (paso 4) se contradicen: se va al primero.
    expect(await screen.findByRole("heading", { name: "1 · Destinatario" })).toBeInTheDocument();
    const edad = screen.getByLabelText(/^Edad/);
    expect(edad).toHaveAttribute("aria-invalid", "true");
    expect(edad).toHaveAccessibleDescription(/pide al menos 14 años y el destinatario tiene 12/);
    const pasos = screen.getByRole("list", { name: "Pasos del brief" });
    expect(within(pasos).getByRole("button", { name: "Paso 4: El terror, con errores" })).toBeInTheDocument();
  }, 30_000);

  it("un error de forma no se envía: se marca en su paso", async () => {
    let enviadas = 0;
    servidor.use(
      http.post("*/api/intenciones", () => {
        enviadas += 1;
        return HttpResponse.json({ id: 1, tipo: "crear_novela", estado: "pendiente" }, { status: 202 });
      }),
    );
    const usuario = userEvent.setup();
    renderizarEn("/crear");
    await usuario.type(await screen.findByLabelText(/^Edad/), "doce");
    await usuario.click(screen.getByRole("button", { name: "Paso 5: Revisión" }));
    await usuario.click(await screen.findByRole("button", { name: "Crear novela" }));

    expect(await screen.findByRole("heading", { name: "1 · Destinatario" })).toBeInTheDocument();
    expect(screen.getByLabelText(/^Edad/)).toHaveAccessibleDescription(/Un número entero entre 1 y 110/);
    expect(enviadas).toBe(0);
  });

  it("el borrador sobrevive a salir y volver", async () => {
    const usuario = userEvent.setup();
    const { unmount } = renderizarEn("/crear");
    await usuario.type(await screen.findByLabelText(/^Nombre/), "Guardado");
    unmount();
    renderizarEn("/crear");
    expect(await screen.findByLabelText(/^Nombre/)).toHaveValue("Guardado");
  });

  it("la intensidad enseña su edad mínima y lo que admite (RF-FE-BRF-01)", async () => {
    const usuario = userEvent.setup();
    renderizarEn("/crear");
    await usuario.click(await screen.findByRole("button", { name: "Paso 4: El terror" }));
    const tension = await screen.findByRole("radio", { name: /^Tensión/ });
    const caja = tension.closest("label") as HTMLElement;
    expect(caja).toHaveTextContent("Desde 14 años");
    expect(caja).toHaveTextContent("No admite: violencia gráfica");
    expect(screen.getByRole("option", { name: "Que lo elija el arquitecto" })).toBeInTheDocument();
  });

  it("no tiene violaciones de accesibilidad automáticas en ningún paso", async () => {
    const usuario = userEvent.setup();
    const { container } = renderizarEn("/crear");
    for (const [i, paso] of ["Destinatario", "Su mundo", "El encargo", "El terror", "Revisión"].entries()) {
      await usuario.click(await screen.findByRole("button", { name: `Paso ${i + 1}: ${paso}` }));
      await waitFor(() => expect(screen.getByRole("heading", { level: 2, name: `${i + 1} · ${paso}` })).toBeInTheDocument());
      await sinViolaciones(container);
    }
  }, 30_000);
});
