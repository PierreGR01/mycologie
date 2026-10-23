import maplibregl, { type Map as CarteMapLibre, type StyleSpecification } from "maplibre-gl";
import { Protocol } from "pmtiles";
import { urlDonnees, type Manifeste } from "./donnees";

// Fond Plan IGN v2 (Géoplateforme, Licence Ouverte), en WMTS au schéma XYZ.
const PLAN_IGN =
  "https://data.geopf.fr/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0" +
  "&LAYER=GEOGRAPHICALGRIDSYSTEMS.PLANIGNV2&STYLE=normal&TILEMATRIXSET=PM" +
  "&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}&FORMAT=image/png";

maplibregl.addProtocol("pmtiles", new Protocol().tile);

export function creerCarte(conteneur: string, m: Manifeste): CarteMapLibre {
  const style: StyleSpecification = {
    version: 8,
    sources: {
      "plan-ign": { type: "raster", tiles: [PLAN_IGN], tileSize: 256, maxzoom: 18 },
      limite: { type: "geojson", data: urlDonnees(m.limite) },
    },
    layers: [
      { id: "plan-ign", type: "raster", source: "plan-ign", paint: { "raster-saturation": -0.4 } },
      {
        id: "limite",
        type: "line",
        source: "limite",
        paint: { "line-color": "#1f3d2b", "line-width": 2, "line-dasharray": [3, 2] },
      },
    ],
  };
  const [ouest, sud, est, nord] = m.emprise;
  const attributions = [...new Set(m.sources.filter((s) => s.carte).map((s) => s.attribution))];
  const carte = new maplibregl.Map({
    container: conteneur,
    style,
    bounds: [ouest, sud, est, nord],
    fitBoundsOptions: { padding: 20 },
    maxBounds: [ouest - 1, sud - 0.6, est + 1, nord + 0.6],
    maxZoom: 16,
    attributionControl: { compact: true, customAttribution: attributions },
    cooperativeGestures: false,
  });
  // L'attribution compacte s'ouvre au chargement : on la replie pour ne pas masquer la carte
  // sur mobile (elle reste accessible par le bouton ⓘ et dans « À propos »).
  carte.once("load", () => {
    const attribution = carte.getContainer().querySelector(".maplibregl-ctrl-attrib");
    attribution?.classList.remove("maplibregl-compact-show");
    attribution?.removeAttribute("open");
  });
  return carte;
}

/** Remplace la couche de score. Au-delà du zoom 12 (≈ 27 m/px), les pixels sont agrandis
 *  sans interpolation : la carte ne prétend pas à plus de précision que la maille de 25 m. */
export function afficherCouche(carte: CarteMapLibre, url: string): void {
  if (carte.getLayer("score")) carte.removeLayer("score");
  if (carte.getSource("score")) carte.removeSource("score");
  carte.addSource("score", { type: "raster", url: `pmtiles://${url}`, tileSize: 256 });
  carte.addLayer(
    {
      id: "score",
      type: "raster",
      source: "score",
      paint: { "raster-opacity": 0.8, "raster-resampling": "nearest", "raster-fade-duration": 0 },
    },
    "limite",
  );
}
