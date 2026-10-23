// Manifeste publié par le pipeline (web/data/latest.json) et mémorisation de la dernière carte.

export interface Manifeste {
  run: string;
  genere_le: string;
  dates: { date: string; type: "analyse" | "prevision" }[];
  especes: {
    id: string;
    nom: string;
    avertissement: string | null;
    habitat: string;
    tuiles: string;
  }[];
  legende: { min: number; libelle: string; couleur: string }[];
  zoom: { min: number; max: number };
  emprise: [number, number, number, number];
  limite: string;
  note?: string; // précision sur les données (ex. démonstration), affichée dans le panneau
  sources: {
    id: string;
    nom: string;
    licence: string;
    attribution: string;
    url: string;
    carte: boolean; // attribution affichée sur la carte (sinon : page « À propos » seulement)
  }[];
}

export interface Selection {
  espece: string;
  date: string;
  habitatSeul: boolean;
}

/** Instantané de la dernière carte consultée, pour la rouvrir hors ligne. */
export interface Instantane {
  manifeste: Manifeste;
  selection: Selection;
  url: string;
}

export const CACHE_CARTE = "derniere-carte";
const CLE_INSTANTANE = "derniere-carte-v1";

export function urlDonnees(chemin: string): string {
  return new URL(`data/${chemin}`, document.baseURI).href;
}

export function urlCarte(m: Manifeste, s: Selection): string {
  const espece = m.especes.find((e) => e.id === s.espece) ?? m.especes[0];
  const chemin = s.habitatSeul ? espece.habitat : espece.tuiles.replace("{date}", s.date);
  return urlDonnees(chemin);
}

// Le stockage local peut être indisponible (navigation privée…) : l'application doit fonctionner
// sans lui.
export function lire<T>(cle: string): T | null {
  try {
    const brut = localStorage.getItem(cle);
    return brut ? (JSON.parse(brut) as T) : null;
  } catch {
    return null;
  }
}

export function ecrire(cle: string, valeur: unknown): void {
  try {
    localStorage.setItem(cle, JSON.stringify(valeur));
  } catch {
    // pas de stockage : rien à mémoriser
  }
}

export function lireInstantane(): Instantane | null {
  return lire<Instantane>(CLE_INSTANTANE);
}

export async function chargerManifeste(): Promise<{ manifeste: Manifeste; horsLigne: boolean }> {
  const instantane = lireInstantane();
  if (!navigator.onLine && instantane) return { manifeste: instantane.manifeste, horsLigne: true };
  try {
    const reponse = await fetch(urlDonnees("latest.json"), { cache: "no-cache" });
    if (!reponse.ok) throw new Error(`latest.json : HTTP ${reponse.status}`);
    return { manifeste: (await reponse.json()) as Manifeste, horsLigne: false };
  } catch (erreur) {
    if (instantane) return { manifeste: instantane.manifeste, horsLigne: true };
    throw erreur;
  }
}

let derniereDemande = 0;

/** Garde en cache le fichier PMTiles complet de la carte affichée (et lui seul), avec le
 *  manifeste et la sélection, pour pouvoir la rouvrir hors ligne. Si l'utilisateur a changé de
 *  carte pendant le téléchargement, seule la plus récente est retenue. */
export async function memoriser(manifeste: Manifeste, selection: Selection): Promise<void> {
  if (!("caches" in window) || !navigator.onLine) return;
  const demande = ++derniereDemande;
  const url = urlCarte(manifeste, selection);
  const cache = await caches.open(CACHE_CARTE);
  if (!(await cache.match(url))) {
    const reponse = await fetch(url);
    if (reponse.status !== 200) return;
    await cache.put(url, reponse);
  }
  if (demande !== derniereDemande) return;
  ecrire(CLE_INSTANTANE, { manifeste, selection, url } satisfies Instantane);
  for (const requete of await cache.keys()) {
    if (requete.url !== url) await cache.delete(requete);
  }
}
