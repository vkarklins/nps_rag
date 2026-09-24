import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In development, the React app runs on :5173 and forwards /api to the FastAPI server.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
});
