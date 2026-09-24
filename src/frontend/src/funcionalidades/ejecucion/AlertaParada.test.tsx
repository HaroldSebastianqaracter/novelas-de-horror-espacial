import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { paradas } from "../../compartido/api/mocks/datos";
import { servidor } from "../../compartido/api/mocks/servidor";
import { DIBUJOS } from "../../compartido/imagenes";
import type { Parada } from "../../compartido/api/tipos";
import { sinViolaciones } from "../../pruebas/accesibilidad";
import { renderizarEn } from "../../pruebas/renderizar";

const RUTA = "/novelas/4/paradas/93";

function conParada(cambios: Partial<Parada>) {
  const parada = { ...(paradas[93] as Parada), ...cambios };
  servidor.use(http.get("*/api/novelas/4/paradas/93", () => HttpResponse.json(parada)));
}

function registrarPedidas() {
  const pedidas: unknown[] = [];
  servidor.use(
    http.post("*/api/intenciones", async ({ request }) => {
      pedidas.push(await request.json());
      return HttpResponse.json({ id: 500, tipo: "resolver_parada", estado: "pendiente" }, { status: 202 });
    }),
  );
  return pedidas;
}

describe("la parada de verificación formal (RF-FE-PAR-02, spec-lean)", () => {
  // El informe con la forma de `ResultadoPuerta.informe` del backend (puerta_base.py).
  const formal = (comprobacion: string, descripcion = "La tripulante aparece en el día 12 y murió el día 9.") =>
    conParada({
      tipo: "formal",
      capitulo: 3,
      informe: {
        puerta: 6,
        veredicto: "falla",
        conflictos: [{ comprobacion, descripcion, aviso: false, escena_id: null, capitulo: 3, datos: {} }],
      },
    });

  it("ofrece relanzar, dice que Lean verificará otra vez y nombra la comprobación", async () => {
    formal("lean_nadie_tras_morir");
    const usuario = userEvent.setup();
    renderizarEn(RUTA);
    expect(await screen.findByRole("heading", { level: 1, name: /parada de verificación formal/ })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Lean: alguien aparece después de morir" })).toBeInTheDocument();
    expect(screen.queryByText(/no conoce el tipo de parada/)).not.toBeInTheDocument();
    const acciones = screen.getByRole("group", { name: "Acciones de resolución" });
    expect(within(acciones).getAllByRole("button").map((b) => b.textContent)).toEqual(["Relanzar"]);
    await usuario.click(within(acciones).getByRole("button", { name: "Relanzar" }));
    expect(acciones).toHaveTextContent("Lean verifica otra vez la cronología");
    expect(acciones).not.toHaveTextContent("hasta que se instale");
    // Relanzar desde el capítulo de la parada, que es desde donde el backend la abrió.
    const pedidas = registrarPedidas();
    await usuario.click(within(acciones).getByRole("button", { name: "Confirmar: relanzar" }));
    await waitFor(() =>
      expect(pedidas).toEqual([
        { tipo: "resolver_parada", novela_id: 4, payload: { parada_id: 93, accion: "relanzar", desde_capitulo: 3 } },
      ]),
    );
  });

  it("con Lean no disponible, dice las dos causas y no da por hecho que falte instalarlo", async () => {
    formal("lean_no_disponible", "Lean no termino en 120 s: la cronologia no se ha comprobado y la version no se publica. Relanza para reintentarlo.");
    renderizarEn(RUTA);
    expect(await screen.findByRole("heading", { name: "Lean no está disponible" })).toBeInTheDocument();
    expect(screen.getByText(/Relanza para reintentarlo/)).toBeInTheDocument();
    const acciones = screen.getByRole("group", { name: "Acciones de resolución" });
    expect(acciones).toHaveTextContent("si solo no terminó a tiempo, relanzar lo reintenta");
  });
});

describe("informe de la parada (RF-FE-PAR-01)", () => {
  it("enseña los conflictos, el cara a cara entre texto y canon, y la prosa rechazada", async () => {
    renderizarEn(RUTA);
    expect(await screen.findByRole("heading", { name: "2 conflictos y 1 aviso" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Continuidad factual" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Conocimiento no adquirido" })).toBeInTheDocument();

    const texto = screen.getByText("Lo que dice el texto").closest("figure") as HTMLElement;
    const canon = screen.getByText("Lo que dice el canon").closest("figure") as HTMLElement;
    expect(within(texto).getByText("naranja")).toBeInTheDocument();
    expect(within(canon).getByText("gris")).toBeInTheDocument();
    expect(within(canon).getByText(/traje gris, todavía con el polvo/)).toBeInTheDocument();

    expect(screen.getByText("Prosa del capítulo rechazado (2 escenas)")).toBeInTheDocument();
  });

  it("la cabecera lleva el pictograma de parada, decorativo (RF-FE-IMG-03)", async () => {
    renderizarEn(RUTA);
    const titulo = await screen.findByRole("heading", { level: 1 });
    const pictograma = titulo.parentElement?.querySelector(".dibujo--parada") as HTMLElement;
    expect(pictograma).toHaveAttribute("aria-hidden", "true");
    expect(pictograma.style.getPropertyValue("--dibujo")).toContain(DIBUJOS.parada);
  });

  it("enseña la segunda opinión legible: una línea por conflicto, con su veredicto y su motivo (RF3-JUE-01)", async () => {
    renderizarEn(RUTA);
    const opinion = (await screen.findByRole("heading", { name: "Segunda opinión del revisor de continuidad" })).closest(
      "section",
    ) as HTMLElement;
    const filas = within(opinion).getAllByRole("listitem").filter((li) => li.classList.contains("opinion__fila"));
    expect(filas).toHaveLength(2);
    expect(filas[0]).toHaveTextContent("#1Parece realNinguna escena cuenta un cambio de traje");
    expect(filas[1]).toHaveTextContent("#2Falso positivo");
    expect(within(filas[0] as HTMLElement).getByRole("link", { name: "#1" })).toHaveAttribute("href", "#conflicto-1");
    expect(document.getElementById("conflicto-1")).toHaveTextContent("Continuidad factual");
    expect(within(opinion).getByText(/Relanzar el capítulo 3 o dar por sabido/)).toBeInTheDocument();
    expect(within(opinion).queryByText(/"opiniones"/)).not.toBeInTheDocument();
  });

  it("el número de la opinión cuenta la lista entera, avisos incluidos", async () => {
    const informe = paradas[93]?.informe as { conflictos: Record<string, unknown>[] };
    const [factual, conocimiento, aviso] = informe.conflictos;
    conParada({
      informe: {
        conflictos: [aviso, factual, conocimiento],
        segunda_opinion: { resumen: "Un aviso va delante.", opiniones: [{ conflicto: 2, parece: "real", motivo: "El traje cambia sin explicación." }] },
      },
    });
    renderizarEn(RUTA);
    const enlace = await screen.findByRole("link", { name: "#2" });
    expect(enlace).toHaveAttribute("href", "#conflicto-2");
    expect(document.getElementById("conflicto-2")).toHaveTextContent("Continuidad factual");
    expect(document.getElementById("conflicto-1")).toHaveTextContent("Palabras filtro");
  });

  it("una opinión fuera del esquema no pierde nada, y un número sin ficha no se enlaza", async () => {
    conParada({
      informe: {
        conflictos: [{ comprobacion: "continuidad_factual", descripcion: "Uno.", aviso: false }],
        segunda_opinion: {
          resumen: 42,
          opiniones: [
            { conflicto: 7, parece: "dudoso", motivo: "Número inventado.", confianza: "media" },
            "una opinión suelta",
          ],
          explicacion_por_conflicto: [{ texto: "no es una cadena" }],
        },
      },
    });
    renderizarEn(RUTA);
    const opinion = (await screen.findByRole("heading", { name: "Segunda opinión del revisor de continuidad" })).closest(
      "section",
    ) as HTMLElement;
    expect(within(opinion).queryByRole("link", { name: "#7" })).not.toBeInTheDocument();
    expect(within(opinion).getByText("#7")).toBeInTheDocument();
    expect(within(opinion).getByText("confianza")).toBeInTheDocument();
    expect(within(opinion).getByText("una opinión suelta")).toBeInTheDocument();
    expect(within(opinion).getByText("resumen")).toBeInTheDocument();
    expect(within(opinion).getByText("42")).toBeInTheDocument();
    expect(within(opinion).getByText(/no es una cadena/)).toBeInTheDocument();
  });

  it("sin segunda opinión lo dice, y la parada sigue", async () => {
    conParada({ informe: { ...(paradas[93]?.informe as Record<string, unknown>), segunda_opinion: null } });
    renderizarEn(RUTA);
    expect(await screen.findByText(/Sin segunda opinión: todavía no ha llegado o la llamada al revisor falló/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "2 conflictos y 1 aviso" })).toBeInTheDocument();
  });

  it("no pierde claves que no conoce y pinta los bloques de presupuesto como tabla", async () => {
    conParada({
      tipo: "presupuesto",
      informe: { motivo: "El paquete supera el techo.", bloques: { canon: 41000, anterior: 9000 }, total_tokens: 104000 },
    });
    renderizarEn(RUTA);
    expect(await screen.findByText("El paquete supera el techo.")).toBeInTheDocument();
    expect(screen.getByRole("table", { name: "Bloques del paquete" })).toHaveTextContent("canon41000");
    expect(screen.getByText("total_tokens")).toBeInTheDocument();
    expect(screen.getByText("104000")).toBeInTheDocument();
  });
});

describe("decisión de la parada (RF-FE-PAR-02 a RF-FE-PAR-04)", () => {
  it("solo ofrece las acciones de su tipo", async () => {
    renderizarEn(RUTA);
    const grupo = await screen.findByRole("group", { name: "Acciones de resolución" });
    expect(within(grupo).getAllByRole("button").map((b) => b.textContent)).toEqual([
      "Aceptar retcon",
      "Dar por sabido",
      "Relanzar",
    ]);
  });

  it("una parada de estructura solo se rehace, y dice que la puerta 1 se reevalúa", async () => {
    conParada({ tipo: "estructura", capitulo: null, informe: { puerta: 1, conflictos: [] } });
    renderizarEn(RUTA);
    const grupo = await screen.findByRole("group", { name: "Acciones de resolución" });
    expect(within(grupo).getAllByRole("button").map((b) => b.textContent)).toEqual(["Rehacer"]);
    expect(within(grupo).getByText(/La puerta 1 se reevalúa/)).toBeInTheDocument();
  });

  it("el primer clic arma la acción, Escape la desarma y el segundo clic la envía", async () => {
    const pedidas = registrarPedidas();
    const usuario = userEvent.setup();
    renderizarEn(RUTA);

    await usuario.click(await screen.findByRole("button", { name: "Aceptar retcon" }));
    expect(pedidas).toEqual([]);
    expect(screen.getByRole("button", { name: "Confirmar: aceptar retcon" })).toBeInTheDocument();

    await usuario.keyboard("{Escape}");
    expect(screen.getByRole("button", { name: "Aceptar retcon" })).toBeInTheDocument();

    await usuario.click(screen.getByRole("button", { name: "Aceptar retcon" }));
    await usuario.click(screen.getByRole("button", { name: "Confirmar: aceptar retcon" }));
    await waitFor(() =>
      expect(pedidas).toEqual([
        { tipo: "resolver_parada", novela_id: 4, payload: { parada_id: 93, accion: "aceptar_retcon" } },
      ]),
    );
    expect(await screen.findByText(/Resolución en cola/)).toBeInTheDocument();
  });

  it("relanzar manda el capítulo elegido, como mucho el de la parada", async () => {
    const pedidas = registrarPedidas();
    const usuario = userEvent.setup();
    renderizarEn(RUTA);

    const selector = await screen.findByLabelText("Desde el capítulo");
    await waitFor(() => expect(within(selector).getAllByRole("option").map((o) => o.textContent)).toEqual(["01", "02", "03"]));
    await usuario.selectOptions(selector, "02");
    expect(screen.getByText(/Revierte lo escrito desde el capítulo 2/)).toBeInTheDocument();
    await usuario.click(screen.getByRole("button", { name: "Relanzar" }));
    await usuario.click(screen.getByRole("button", { name: "Confirmar: relanzar" }));
    await waitFor(() =>
      expect(pedidas).toEqual([
        { tipo: "resolver_parada", novela_id: 4, payload: { parada_id: 93, accion: "relanzar", desde_capitulo: 2 } },
      ]),
    );
  });

  it("avisa sin bloquear cuando el worker va a rechazar aceptar_retcon o dar_por_sabido", async () => {
    conParada({
      informe: { conflictos: [{ comprobacion: "presencia_imposible", descripcion: "Dos sitios a la vez.", datos: {} }] },
    });
    renderizarEn(RUTA);
    expect(await screen.findByText(/Ningún conflicto señala un hecho establecido/)).toBeInTheDocument();
    expect(screen.getByText(/Ningún conflicto es de conocimiento no adquirido/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Aceptar retcon" })).toBeEnabled();
  });

  it("cuando el worker la hace, vuelve al tablero de la novela", async () => {
    const usuario = userEvent.setup();
    renderizarEn(RUTA);
    await usuario.click(await screen.findByRole("button", { name: "Dar por sabido" }));
    await usuario.click(screen.getByRole("button", { name: "Confirmar: dar por sabido" }));
    expect(await screen.findByRole("heading", { level: 1, name: "Perforación en el pozo siete" }, { timeout: 6_000 })).toBeInTheDocument();
  }, 10_000);

  it("una parada resuelta se enseña en modo lectura, con su resolución", async () => {
    conParada({ estado: "resuelta", resolucion: "aceptar_retcon" });
    renderizarEn(RUTA);
    expect(await screen.findByText("Se aceptó el retcon")).toBeInTheDocument();
    expect(screen.queryByRole("group", { name: "Acciones de resolución" })).not.toBeInTheDocument();
    expect(screen.getByText(/Esta parada ya está resuelta/)).toBeInTheDocument();
  });

  it("no tiene violaciones de accesibilidad automáticas", async () => {
    const { container } = renderizarEn(RUTA);
    await screen.findByRole("group", { name: "Acciones de resolución" });
    await sinViolaciones(container);
  });
});
