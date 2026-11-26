import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Em produção o FastAPI serve o build (frontend/dist). Em dev, o Vite repassa a API para ele.
const backend = "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  build: { outDir: "dist", emptyOutDir: true, target: "es2019" },
  server: {
    port: 5173,
    proxy: {
      "/api": backend,
      "/oauth": backend,
      "/admin/login": backend,
      "/admin/logout": backend,
    },
  },
});
