import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Docker Compose sets BACKEND_URL=http://backend:8000; local dev falls back to localhost.
const backend = process.env.BACKEND_URL || "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    watch: { usePolling: true, interval: 500 },
    proxy: {
      "/api": backend,
    },
  },
});
