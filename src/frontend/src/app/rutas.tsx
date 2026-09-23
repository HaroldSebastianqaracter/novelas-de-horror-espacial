import type { RouteObject } from "react-router";
import { AlertaParada, TableroGeneral, TableroNovela } from "../funcionalidades/ejecucion";
import { Lector } from "../funcionalidades/manuscrito";
import { CrearNovela } from "../funcionalidades/novela";
import { Marco } from "./Marco";
import { NoEncontrada } from "./NoEncontrada";

/** Rutas de RF-FE-COD-03. */
export const rutas: RouteObject[] = [
  {
    element: <Marco />,
    children: [
      { path: "/", element: <TableroGeneral /> },
      { path: "/crear", element: <CrearNovela /> },
      { path: "/novelas/:id", element: <TableroNovela /> },
      { path: "/novelas/:id/paradas/:pid", element: <AlertaParada /> },
      { path: "/novelas/:id/capitulos/:n", element: <Lector /> },
      { path: "*", element: <NoEncontrada /> },
    ],
  },
];
