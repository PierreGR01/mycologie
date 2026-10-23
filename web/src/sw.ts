/// <reference lib="webworker" />
import { CacheableResponsePlugin } from "workbox-cacheable-response";
import { clientsClaim } from "workbox-core";
import { ExpirationPlugin } from "workbox-expiration";
import { cleanupOutdatedCaches, precacheAndRoute } from "workbox-precaching";
import { createPartialResponse } from "workbox-range-requests";
import { registerRoute } from "workbox-routing";
import { CacheFirst, NetworkFirst } from "workbox-strategies";
import { CACHE_CARTE } from "./donnees";

declare let self: ServiceWorkerGlobalScope;

// Coquille de l'application (HTML, JS, CSS, icônes), disponible hors ligne.
precacheAndRoute(self.__WB_MANIFEST);
cleanupOutdatedCaches();
self.skipWaiting();
clientsClaim();

// Manifeste et contour du département : réseau d'abord, dernière version connue sinon.
registerRoute(
  ({ url }) => /\/data\/(latest\.json|departement\.geojson)$/.test(url.pathname),
  new NetworkFirst({ cacheName: "donnees", networkTimeoutSeconds: 5 }),
);

// Cartes PMTiles : réseau ; hors ligne, la dernière carte consultée, mise en cache en entier par
// la page, est servie par plages d'octets (requêtes HTTP Range de PMTiles).
registerRoute(
  ({ url }) => url.pathname.endsWith(".pmtiles"),
  async ({ request }) => {
    try {
      return await fetch(request);
    } catch (erreur) {
      const cache = await caches.open(CACHE_CARTE);
      const complet = await cache.match(request.url, { ignoreSearch: true });
      if (!complet) throw erreur;
      return request.headers.has("range") ? createPartialResponse(request, complet) : complet;
    }
  },
);

// Fond Plan IGN : tuiles consultées gardées 30 jours (2 000 au plus).
registerRoute(
  ({ url }) => url.hostname === "data.geopf.fr" && url.pathname.startsWith("/wmts"),
  new CacheFirst({
    cacheName: "fond-ign",
    plugins: [
      new CacheableResponsePlugin({ statuses: [200] }),
      new ExpirationPlugin({ maxEntries: 2000, maxAgeSeconds: 30 * 24 * 3600 }),
    ],
  }),
);
