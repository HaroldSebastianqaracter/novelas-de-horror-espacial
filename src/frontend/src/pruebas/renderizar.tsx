import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { rutas } from "../app/rutas";

/** Monta la app entera en una ruta, con una caché nueva y sin reintentos. */
export function renderizarEn(ruta: string) {
  const cliente = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const enrutador = createMemoryRouter(rutas, { initialEntries: [ruta] });
  return render(
    <QueryClientProvider client={cliente}>
      <RouterProvider router={enrutador} />
    </QueryClientProvider>,
  );
}
