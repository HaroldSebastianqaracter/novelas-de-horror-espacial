import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createBrowserRouter, RouterProvider } from "react-router";
import { IntencionesProvider } from "../compartido/api/intenciones";
import { rutas } from "./rutas";

const cliente = new QueryClient({
  defaultOptions: {
    // Volver a la pestaña cuenta como reconexión: se reconsulta (RF-FE-DAT-04).
    queries: { refetchOnWindowFocus: true, refetchOnReconnect: true, staleTime: 2_000 },
  },
});

const enrutador = createBrowserRouter(rutas);

export function App() {
  return (
    <QueryClientProvider client={cliente}>
      <IntencionesProvider>
        <RouterProvider router={enrutador} />
      </IntencionesProvider>
    </QueryClientProvider>
  );
}
