import "@testing-library/jest-dom/vitest";
import { cleanup, configure } from "@testing-library/react";
import { afterAll, afterEach, beforeAll } from "vitest";
import { restaurarDatos } from "../compartido/api/mocks/datos";
import { servidor } from "../compartido/api/mocks/servidor";

// Con toda la suite en paralelo, el primer render puede tardar más del segundo por defecto.
configure({ asyncUtilTimeout: 3_000 });

// Los tests siempre corren contra MSW (RF-FE-API-03); una petición sin manejador es un fallo.
beforeAll(() => servidor.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  cleanup();
  servidor.resetHandlers();
  restaurarDatos();
  sessionStorage.clear();
});
afterAll(() => servidor.close());
