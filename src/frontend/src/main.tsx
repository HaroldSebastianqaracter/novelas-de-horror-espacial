import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./app/App";
import "./compartido/estilo/tokens.css";
import "./compartido/estilo/base.css";

async function arrancar() {
  // Con `npm run dev:mocks` el frontend corre entero sin backend (RF-FE-API-03).
  if (import.meta.env.VITE_MOCKS === "1") {
    const { trabajador } = await import("./compartido/api/mocks/navegador");
    await trabajador.start({ onUnhandledRequest: "bypass" });
  }
  const raiz = document.getElementById("raiz");
  if (!raiz) throw new Error("Falta el elemento #raiz en index.html");
  createRoot(raiz).render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
}

void arrancar();
