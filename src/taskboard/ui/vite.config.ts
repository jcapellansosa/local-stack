import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// `vite build` outputs to ui/dist, which the FastAPI app serves as static.
// The `server.proxy` config is for `vite dev`, when running the UI separately
// from the backend during local UI iteration.
export default defineConfig({
  plugins: [react()],
  build: { outDir: "dist", emptyOutDir: true },
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8080",
      "/auth": "http://localhost:8080",
    },
  },
});
