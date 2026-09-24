import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// En desarrollo, /api va al backend sin CORS (RF-FE-API-02), también el SSE.
// NOVELAS_API cambia el destino, p. ej. para probar contra una API en otro puerto.
const destino = process.env.NOVELAS_API || "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: destino,
        changeOrigin: true,
        rewrite: (ruta) => ruta.replace(/^\/api/, ""),
      },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["src/pruebas/preparar.ts"],
    css: false,
    // Con toda la suite en paralelo, los flujos de varios pasos (cambio del lector) pasan de 5 s.
    testTimeout: 15_000,
    // La máquina se comparte con el backend y sus workers: la mitad de los núcleos es más estable.
    maxWorkers: "50%",
  },
});
