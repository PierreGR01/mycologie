import { createReadStream, statSync } from "node:fs";
import type { IncomingMessage, ServerResponse } from "node:http";
import { resolve, sep } from "node:path";
import { defineConfig, type Plugin } from "vite";
import { VitePWA } from "vite-plugin-pwa";

// Données produites par le pipeline (PMTiles, latest.json). Elles ne passent pas par le build :
// en production, le serveur statique les sert sous /data/ (voir nginx.conf).
const DONNEES = resolve(__dirname, "data");

/** Sert web/data sous /data/ en développement et en prévisualisation, avec les requêtes HTTP
 *  Range indispensables à PMTiles. */
function servirDonnees(): Plugin {
  const servir = (req: IncomingMessage, res: ServerResponse, suite: () => void) => {
    const url = new URL(req.url ?? "/", "http://local");
    if (!url.pathname.startsWith("/data/")) return suite();
    const chemin = resolve(DONNEES, decodeURIComponent(url.pathname.slice("/data/".length)));
    if (!chemin.startsWith(DONNEES + sep)) {
      res.statusCode = 403;
      return res.end();
    }
    let taille: number;
    try {
      taille = statSync(chemin).size;
    } catch {
      res.statusCode = 404;
      return res.end();
    }
    const json = chemin.endsWith(".json") || chemin.endsWith(".geojson");
    res.setHeader("Content-Type", json ? "application/json" : "application/octet-stream");
    res.setHeader("Accept-Ranges", "bytes");
    res.setHeader("Cache-Control", "no-cache");
    const plage = /^bytes=(\d*)-(\d*)$/.exec(req.headers.range ?? "");
    if (!plage) {
      res.setHeader("Content-Length", taille);
      return createReadStream(chemin).pipe(res);
    }
    const debut = plage[1] ? Number(plage[1]) : Math.max(0, taille - Number(plage[2]));
    const fin = plage[1] && plage[2] ? Math.min(Number(plage[2]), taille - 1) : taille - 1;
    if (debut > fin || debut >= taille) {
      res.statusCode = 416;
      res.setHeader("Content-Range", `bytes */${taille}`);
      return res.end();
    }
    res.statusCode = 206;
    res.setHeader("Content-Range", `bytes ${debut}-${fin}/${taille}`);
    res.setHeader("Content-Length", fin - debut + 1);
    createReadStream(chemin, { start: debut, end: fin }).pipe(res);
  };
  return {
    name: "servir-donnees",
    configureServer: (serveur) => void serveur.middlewares.use(servir),
    configurePreviewServer: (serveur) => void serveur.middlewares.use(servir),
  };
}

export default defineConfig({
  base: "./",
  build: { target: "es2022", chunkSizeWarningLimit: 1500 },
  plugins: [
    servirDonnees(),
    VitePWA({
      strategies: "injectManifest",
      srcDir: "src",
      filename: "sw.ts",
      injectRegister: false,
      registerType: "autoUpdate",
      injectManifest: {
        globPatterns: ["**/*.{js,css,html,png,svg,webmanifest}"],
        maximumFileSizeToCacheInBytes: 3 * 1024 * 1024,
      },
      manifest: {
        name: "Champignons Isère – zones favorables",
        short_name: "Champis 38",
        description:
          "Carte des zones et périodes favorables à la cueillette de champignons en Isère. " +
          "Aucune fonction d'identification.",
        lang: "fr",
        start_url: ".",
        scope: ".",
        display: "standalone",
        orientation: "portrait",
        background_color: "#f4f1ea",
        theme_color: "#1f3d2b",
        icons: [
          { src: "icons/icone-192.png", sizes: "192x192", type: "image/png" },
          { src: "icons/icone-512.png", sizes: "512x512", type: "image/png" },
          { src: "icons/icone-masquable-512.png", sizes: "512x512", type: "image/png",
            purpose: "maskable" },
        ],
      },
    }),
  ],
});
