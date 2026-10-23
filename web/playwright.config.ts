import { defineConfig, devices } from "@playwright/test";

// Tests de bout en bout sur l'application construite (`npm run build`) et servie par
// `vite preview`, avec les données réelles de web/data (produites par `make pipeline`).
const proxy = process.env.HTTPS_PROXY;

export default defineConfig({
  testDir: "tests",
  timeout: 90_000,
  workers: 1,
  use: {
    baseURL: "http://localhost:4173/",
    ...devices["Pixel 7"],
    // Fond Plan IGN : accès Internet éventuellement via le proxy de l'environnement.
    proxy: proxy ? { server: proxy, bypass: "localhost,127.0.0.1" } : undefined,
  },
  webServer: {
    command: "npx vite preview --port 4173 --strictPort",
    url: "http://localhost:4173/",
    reuseExistingServer: true,
  },
});
