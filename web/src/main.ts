import "maplibre-gl/dist/maplibre-gl.css";
import "./styles.css";
import { registerSW } from "virtual:pwa-register";
import { afficherCouche, creerCarte } from "./carte";
import {
  chargerManifeste,
  ecrire,
  lire,
  lireInstantane,
  memoriser,
  urlCarte,
  type Manifeste,
  type Selection,
} from "./donnees";

const CLE_AVERTISSEMENT = "avertissement-accepte-v1";
const CLE_SELECTION = "selection-v1";

const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;
const formatDate = new Intl.DateTimeFormat("fr-FR", {
  weekday: "long",
  day: "numeric",
  month: "long",
});

registerSW({ immediate: true });

function afficherAvertissement(): Promise<void> {
  const dialogue = $<HTMLDialogElement>("avertissement");
  const lu = $<HTMLInputElement>("avertissement-lu");
  const ok = $<HTMLButtonElement>("avertissement-ok");
  return new Promise((fin) => {
    if (lire<boolean>(CLE_AVERTISSEMENT)) return fin();
    lu.addEventListener("change", () => (ok.disabled = !lu.checked));
    // Le dialogue ne se ferme qu'en acceptant l'avertissement.
    dialogue.addEventListener("cancel", (e) => e.preventDefault());
    ok.addEventListener("click", () => {
      ecrire(CLE_AVERTISSEMENT, true);
      dialogue.close();
      fin();
    });
    dialogue.showModal();
  });
}

function bandeau(texte: string | null): void {
  const b = $("bandeau");
  b.hidden = !texte;
  b.textContent = texte ?? "";
}

function selectionInitiale(m: Manifeste, horsLigne: boolean): Selection {
  const instantane = lireInstantane();
  if ((horsLigne || !navigator.onLine) && instantane) return instantane.selection;
  const precedente = lire<Selection>(CLE_SELECTION);
  const dates = m.dates.map((d) => d.date);
  return {
    espece: m.especes.some((e) => e.id === precedente?.espece)
      ? precedente!.espece
      : m.especes[0].id,
    date: dates.includes(m.run) ? m.run : dates[Math.floor(dates.length / 2)],
    habitatSeul: precedente?.habitatSeul ?? false,
  };
}

async function demarrer(): Promise<void> {
  await afficherAvertissement();
  let manifeste: Manifeste;
  let horsLigne: boolean;
  try {
    ({ manifeste, horsLigne } = await chargerManifeste());
  } catch {
    bandeau("Données indisponibles. Vérifiez la connexion puis rechargez la page.");
    return;
  }

  let selection = selectionInitiale(manifeste, horsLigne);
  const carte = creerCarte("carte", manifeste);
  (window as unknown as { __carte: unknown }).__carte = carte; // tests de bout en bout

  // Espèces
  const especes = $("especes");
  for (const e of manifeste.especes) {
    const bouton = document.createElement("button");
    bouton.type = "button";
    bouton.className = "puce";
    bouton.textContent = e.nom;
    bouton.dataset.espece = e.id;
    bouton.setAttribute("role", "radio");
    bouton.addEventListener("click", () => changer({ ...selection, espece: e.id }));
    especes.append(bouton);
  }

  // Dates
  const curseur = $<HTMLInputElement>("curseur-date");
  curseur.max = String(manifeste.dates.length - 1);
  curseur.addEventListener("input", () =>
    changer({ ...selection, date: manifeste.dates[Number(curseur.value)].date }),
  );
  const habitatSeul = $<HTMLInputElement>("habitat-seul");
  habitatSeul.addEventListener("change", () =>
    changer({ ...selection, habitatSeul: habitatSeul.checked }),
  );

  // Graduations : écart en jours entre la première / dernière date et le jour du run.
  const jRun = Math.max(0, manifeste.dates.findIndex((d) => d.date === manifeste.run));
  const [premiere, , derniere] = $("graduations").children;
  premiere.textContent = `J-${jRun}`;
  derniere.textContent = `J+${manifeste.dates.length - 1 - jRun}`;
  if (manifeste.note) {
    const note = $("note-donnees");
    note.hidden = false;
    note.textContent = manifeste.note;
  }

  // Légende
  $("legende").replaceChildren(
    ...manifeste.legende.map((c) => {
      const li = document.createElement("li");
      const pastille = document.createElement("span");
      pastille.className = "pastille";
      pastille.style.background = c.couleur;
      li.append(pastille, c.libelle);
      return li;
    }),
  );

  // À propos
  $("apropos-run").textContent =
    `Météo du run du ${formatDate.format(new Date(manifeste.run))}, ` +
    `cartes calculées le ${new Date(manifeste.genere_le).toLocaleString("fr-FR")}.`;
  $("sources").replaceChildren(
    ...manifeste.sources.map((s) => {
      const li = document.createElement("li");
      const lien = document.createElement("a");
      lien.href = s.url;
      lien.rel = "noopener";
      lien.target = "_blank";
      lien.textContent = s.nom;
      li.append(lien, ` — ${s.licence}. ${s.attribution}`);
      return li;
    }),
  );
  const licenceCartes = $("licence-cartes");
  licenceCartes.textContent = manifeste.licence_cartes ?? "";
  licenceCartes.hidden = !manifeste.licence_cartes;
  const apropos = $<HTMLDialogElement>("apropos");
  $("bouton-apropos").addEventListener("click", () => apropos.showModal());
  $("apropos-fermer").addEventListener("click", () => apropos.close());

  function mettreAJourInterface(): void {
    for (const b of especes.querySelectorAll<HTMLButtonElement>(".puce")) {
      b.setAttribute("aria-checked", String(b.dataset.espece === selection.espece));
    }
    const i = manifeste.dates.findIndex((d) => d.date === selection.date);
    curseur.value = String(i);
    curseur.disabled = selection.habitatSeul;
    habitatSeul.checked = selection.habitatSeul;
    const jour = manifeste.dates[i];
    $("date-libelle").textContent = selection.habitatSeul
      ? "Habitat seul"
      : formatDate.format(new Date(jour.date));
    const type = $("date-type");
    type.hidden = selection.habitatSeul;
    type.textContent = jour.type === "prevision" ? "prévision" : "analyse";
    type.dataset.type = jour.type;
    const espece = manifeste.especes.find((e) => e.id === selection.espece)!;
    const avert = $("avertissement-espece");
    avert.hidden = !espece.avertissement;
    avert.textContent = espece.avertissement ?? "";
  }

  function changer(nouvelle: Selection): void {
    if (horsLigne && urlCarte(manifeste, nouvelle) !== lireInstantane()?.url) {
      bandeau("Hors ligne : seule la dernière carte consultée est disponible.");
      mettreAJourInterface();
      return;
    }
    selection = nouvelle;
    ecrire(CLE_SELECTION, selection);
    mettreAJourInterface();
    afficherCouche(carte, urlCarte(manifeste, selection));
    carte.once("idle", () => void memoriser(manifeste, selection).catch(() => undefined));
  }

  // Le manifeste peut venir du cache du service worker : l'état du réseau prime.
  const etatReseau = () => {
    horsLigne = !navigator.onLine;
    bandeau(
      horsLigne
        ? `Hors ligne : dernière carte consultée (météo du ${formatDate.format(new Date(manifeste.run))}).`
        : null,
    );
  };
  window.addEventListener("online", etatReseau);
  window.addEventListener("offline", etatReseau);
  if (horsLigne || !navigator.onLine) etatReseau();

  carte.on("load", () => changer(selection));
}

void demarrer();
