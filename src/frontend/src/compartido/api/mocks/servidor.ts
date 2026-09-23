import { setupServer } from "msw/node";
import { manejadores } from "./manejadores";

export const servidor = setupServer(...manejadores);
