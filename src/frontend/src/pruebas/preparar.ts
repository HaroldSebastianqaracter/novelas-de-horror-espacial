import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterAll, afterEach, beforeAll } from "vitest";
import { servidor } from "../compartido/api/mocks/servidor";

// Los tests siempre corren contra MSW (RF-FE-API-03); una petición sin manejador es un fallo.
beforeAll(() => servidor.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  cleanup();
  servidor.resetHandlers();
});
afterAll(() => servidor.close());
