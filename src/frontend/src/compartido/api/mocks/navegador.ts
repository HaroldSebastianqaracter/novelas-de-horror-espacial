import { setupWorker } from "msw/browser";
import { manejadores } from "./manejadores";

export const trabajador = setupWorker(...manejadores);
