import "@testing-library/jest-dom/vitest";
import { cleanup, configure } from "@testing-library/react";
import { afterAll, afterEach, beforeAll } from "vitest";
import { restaurarDatos } from "../compartido/api/mocks/datos";
import { restaurarLectura } from "../compartido/api/mocks/lectura";
import { restaurarSimulacion } from "../compartido/api/mocks/manejadores";
import { servidor } from "../compartido/api/mocks/servidor";

// Con toda la suite en paralelo y la máquina compartida, un render puede tardar varios segundos.
configure({ asyncUtilTimeout: 5_000 });

// Los tests siempre corren contra MSW (RF-FE-API-03); una petición sin manejador es un fallo.
beforeAll(() => servidor.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  cleanup();
  servidor.resetHandlers();
  restaurarDatos();
  restaurarLectura();
  restaurarSimulacion();
  sessionStorage.clear();
});
afterAll(() => servidor.close());
