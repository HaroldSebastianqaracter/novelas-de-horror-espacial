import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
// Primero los estilos base: los de cada pantalla van después y ganan los empates.
import "./compartido/estilo/tokens.css";
import "./compartido/estilo/base.css";
import { App } from "./app/App";

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
