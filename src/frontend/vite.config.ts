import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// En desarrollo, /api va al backend sin CORS (RF-FE-API-02), también el SSE.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        rewrite: (ruta) => ruta.replace(/^\/api/, ""),
      },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["src/pruebas/preparar.ts"],
    css: false,
  },
});
