import { screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { servidor } from "../compartido/api/mocks/servidor";
import { renderizarEn } from "../pruebas/renderizar";

describe("andamiaje", () => {
  it("el tablero pinta las novelas que sirve la API", async () => {
    renderizarEn("/");
    expect(await screen.findByRole("link", { name: "La bodega once" })).toBeInTheDocument();
    // Una novela sin título todavía no lo tiene porque lo propone el arquitecto (RF3-PER-01).
    expect(screen.getByRole("link", { name: "Sin título" })).toBeInTheDocument();
  });

  it("sin novelas, el tablero lleva a crear la primera", async () => {
    servidor.use(http.get("*/api/novelas", () => HttpResponse.json([])));
    renderizarEn("/");
    expect(await screen.findByRole("link", { name: "Crea la primera" })).toHaveAttribute("href", "/crear");
  });

  it("un fallo de la API se muestra con reintento", async () => {
    servidor.use(http.get("*/api/novelas", () => HttpResponse.json({ mensaje: "Base ocupada" }, { status: 500 })));
    renderizarEn("/");
    expect(await screen.findByRole("alert")).toHaveTextContent("Base ocupada");
    expect(screen.getByRole("button", { name: "Reintentar" })).toBeInTheDocument();
  });

  it.each(["/crear", "/novelas/3", "/novelas/4/paradas/93", "/novelas/6/capitulos/1"])(
    "la ruta %s tiene pantalla",
    async (ruta) => {
      renderizarEn(ruta);
      expect(await screen.findByRole("heading", { level: 1 })).toBeInTheDocument();
    },
  );

  it("una ruta desconocida lo dice", async () => {
    renderizarEn("/no-existe");
    expect(await screen.findByRole("heading", { name: "Ruta desconocida" })).toBeInTheDocument();
  });
});
