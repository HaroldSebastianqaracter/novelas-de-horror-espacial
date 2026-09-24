import { screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { renderizarEn } from "../../pruebas/renderizar";
import { partirEventos } from "./eventos";
import { servidor } from "./mocks/servidor";

describe("lector de text/event-stream", () => {
  it("parte eventos con id, nombre y datos, e ignora los comentarios", () => {
    const { eventos, resto } = partirEventos(
      ': keepalive\n\nid: 41\nevent: fase_cambiada\ndata: {"fase":"mundo"}\n\nid: 42\nevent: parada\ndata: {}\n\n',
    );
    expect(eventos).toEqual([
      { id: "41", tipo: "fase_cambiada", datos: '{"fase":"mundo"}' },
      { id: "42", tipo: "parada", datos: "{}" },
    ]);
    expect(resto).toBe("");
  });

  it("deja para el siguiente trozo un evento a medias", () => {
    const { eventos, resto } = partirEventos("id: 7\nevent: capitulo_completado\nda");
    expect(eventos).toEqual([]);
    expect(resto).toBe("id: 7\nevent: capitulo_completado\nda");
    expect(partirEventos(`${resto}ta: {}\n\n`).eventos).toEqual([{ id: "7", tipo: "capitulo_completado", datos: "{}" }]);
  });

  it("acepta finales de línea CRLF", () => {
    expect(partirEventos("id: 1\r\ndata: x\r\n\r\n").eventos).toEqual([{ id: "1", tipo: "message", datos: "x" }]);
  });
});

describe("SSE de una novela (RF-FE-DAT-02, RF-FE-DAT-04)", () => {
  it("un evento invalida la novela, un corte avisa y la reconexión manda Last-Event-ID y reconsulta", async () => {
    const cabeceras: (string | null)[] = [];
    let consultasEstructura = 0;
    // La reconexión espera a que el test la suelte: si no, con la máquina cargada, el aviso
    // aparece y desaparece antes de que el test llegue a buscarlo.
    let soltarReconexion = () => {};
    const reconexion = new Promise<void>((r) => {
      soltarReconexion = r;
    });
    servidor.use(
      http.get("*/api/novelas/3/estructura", () => {
        consultasEstructura += 1;
        return HttpResponse.json({ actos: [], capitulos: [], hilos: [], puntos_de_giro: [], siembras: [] });
      }),
      http.get("*/api/novelas/3/eventos", async ({ request }) => {
        cabeceras.push(request.headers.get("Last-Event-ID"));
        if (cabeceras.length > 1) {
          await reconexion;
          // Segunda conexión: se queda abierta sin decir nada.
          return new HttpResponse(new ReadableStream({ start() {} }), {
            headers: { "Content-Type": "text/event-stream" },
          });
        }
        // Primera: un evento y se corta.
        return new HttpResponse('id: 41\nevent: fase_cambiada\ndata: {"tipo":"fase_cambiada"}\n\n', {
          headers: { "Content-Type": "text/event-stream" },
        });
      }),
    );

    renderizarEn("/novelas/3");
    await screen.findByRole("heading", { level: 1, name: "La bodega once" });
    const antes = consultasEstructura;

    expect(await screen.findByText("Enlace perdido.")).toBeInTheDocument();
    soltarReconexion();
    await waitFor(() => expect(consultasEstructura).toBeGreaterThan(antes));

    await waitFor(() => expect(cabeceras).toEqual([null, "41"]), { timeout: 3_000 });
    await waitFor(() => expect(screen.queryByText("Enlace perdido.")).not.toBeInTheDocument());
  }, 10_000);
});
