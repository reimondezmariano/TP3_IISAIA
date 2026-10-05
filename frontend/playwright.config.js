import { fileURLToPath } from "node:url";
import { defineConfig } from "@playwright/test";

const BACKEND = fileURLToPath(new URL("../backend", import.meta.url));

// Levanta backend y frontend si no están corriendo. El backend usa backend/.env
// (o el Postgres local de docker-compose si no hay .env).
export default defineConfig({
  testDir: "./e2e",
  use: { baseURL: "http://localhost:5173" },
  webServer: [
    {
      command: ".venv/bin/uvicorn app.main:app --port 8000",
      cwd: BACKEND,
      url: "http://localhost:8000/api/health",
      reuseExistingServer: true,
      timeout: 60_000,
    },
    {
      command: "npm run dev -- --port 5173 --strictPort",
      url: "http://localhost:5173",
      reuseExistingServer: true,
      timeout: 60_000,
    },
  ],
});
