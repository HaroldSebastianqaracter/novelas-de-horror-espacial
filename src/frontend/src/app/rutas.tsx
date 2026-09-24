import type { RouteObject } from "react-router";
import { AlertaParada, TableroGeneral, TableroNovela } from "../funcionalidades/ejecucion";
import { CapituloLectura, Ficha, Imprimir, MarcoLectura, Portada, Versiones } from "../funcionalidades/lectura";
import { Lector } from "../funcionalidades/manuscrito";
import { CrearNovela } from "../funcionalidades/novela";
import { Marco } from "./Marco";
import { NoEncontrada } from "./NoEncontrada";

/** Rutas de RF-FE-COD-03. La lectura (RF-FE-LEE) tiene su propio marco, sin la barra de la consola. */
export const rutas: RouteObject[] = [
  {
    path: "/novelas/:id/lectura",
    element: <MarcoLectura />,
    children: [
      { index: true, element: <Portada /> },
      { path: "ficha", element: <Ficha /> },
      { path: "versiones", element: <Versiones /> },
      { path: "imprimir", element: <Imprimir /> },
      { path: "capitulos/:n", element: <CapituloLectura /> },
    ],
  },
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
