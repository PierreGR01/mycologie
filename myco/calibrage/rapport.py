"""Rapport de calibrage par espèce (Markdown + figures PNG)."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from myco.calibrage.analyse import AUC_FAIBLE, N_MIN, Resultat  # noqa: E402

COULEUR_OBS, COULEUR_FOND, COULEUR_MODELE = "#bd0026", "#8c8c8c", "#1f3d2b"


def _fig_phenologie(r: Resultat, chemin: Path) -> None:
    t = r.phenologie
    fig, ax = plt.subplots(figsize=(9, 3.2))
    ax.bar(range(24), t["observations"], color=COULEUR_OBS, label="observations")
    ax.set_xticks(range(0, 24, 2), [q.split()[0] for q in t["quinzaine"][::2]])
    ax.set_ylabel("observations")
    ax2 = ax.twinx()
    ax2.plot(range(24), t["saison_modele"], color=COULEUR_MODELE, lw=2, label="saison du modèle")
    ax2.set_ylim(0, 1.05)
    ax2.set_ylabel("facteur saisonnier")
    ax.set_title(f"{r.espece.nom} : observations par quinzaine et fenêtre saisonnière")
    fig.tight_layout()
    fig.savefig(chemin, dpi=110)
    plt.close(fig)


def _fig_habitat(r: Resultat, chemin: Path) -> None:
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(9, 3.2))
    bins = np.linspace(0, 1, 21)
    a1.hist(r.h_fond[~np.isnan(r.h_fond)], bins=bins, density=True, color=COULEUR_FOND,
            alpha=0.6, label="fond (tous champignons)")
    a1.hist(r.h_presences[~np.isnan(r.h_presences)], bins=bins, density=True,
            color=COULEUR_OBS, alpha=0.6, label="observations")
    a1.set_xlabel("habitat moyen dans le cercle d'incertitude")
    a1.legend(fontsize=8)
    if r.courbe_boyce is not None and len(r.courbe_boyce):
        a2.plot(r.courbe_boyce["centre"], r.courbe_boyce["pe"], color=COULEUR_OBS)
    a2.axhline(1, color=COULEUR_FOND, ls="--", lw=1)
    a2.set_xlabel("habitat")
    a2.set_ylabel("rapport prédit / attendu")
    a2.set_title(f"Boyce = {r.boyce_h:.2f}", fontsize=10)
    fig.tight_layout()
    fig.savefig(chemin, dpi=110)
    plt.close(fig)


def _fig_meteo(r: Resultat, chemin: Path) -> None:
    s = r.meteo
    jour = s.loc[s["observe"], "M"].dropna()
    autres = s.loc[~s["observe"] & (s["f_saison"] > 0), "M"].dropna()
    fig, ax = plt.subplots(figsize=(6, 3.2))
    bins = np.linspace(0, 1, 21)
    ax.hist(autres, bins=bins, density=True, color=COULEUR_FOND, alpha=0.6,
            label="autres jours de la saison")
    ax.hist(jour, bins=bins, density=True, color=COULEUR_OBS, alpha=0.6, label="jour observé")
    ax.set_xlabel("score météo M")
    ax.set_title(f"AUC temporelle = {r.auc_m:.2f}", fontsize=10)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(chemin, dpi=110)
    plt.close(fig)


def _f(v) -> str:
    if isinstance(v, float | np.floating):
        return "–" if np.isnan(v) else f"{v:.2f}"
    return str(v)


def _table(df: pd.DataFrame) -> str:
    """Tableau Markdown (index en première colonne)."""
    entete = ["", *map(str, df.columns)]
    lignes = ["| " + " | ".join(entete) + " |", "|" + "---|" * len(entete)]
    for idx, ligne in df.iterrows():
        lignes.append("| " + " | ".join([str(idx), *map(_f, ligne.to_list())]) + " |")
    return "\n".join(lignes)


def _qualite(valeur: float, n: int, seuil: float = AUC_FAIBLE) -> str:
    if np.isnan(valeur):
        return "non calculable"
    if n < N_MIN:
        return f"{valeur:.2f} (effectif < {N_MIN} : indicatif)"
    return f"{valeur:.2f} ({'faible' if valeur < seuil else 'correct'})"


def ecrire(r: Resultat, dossier: Path, contexte: dict) -> Path:
    dossier.mkdir(parents=True, exist_ok=True)
    e = r.espece
    lignes = [
        f"# Calibrage – {e.nom}",
        "",
        f"Généré le {contexte['date']}. Taxons : {', '.join(e.taxons)}.",
        "",
        "> **Rapport de diagnostic.** Les règles de `config/especes/"
        f"{e.id}.yaml` ne sont pas modifiées automatiquement.",
    ]
    if contexte.get("provisoire"):
        lignes += ["> **Provisoire** : " + contexte["provisoire"]]
    lignes += [
        "",
        "## Données",
        "",
        "| | Nombre |",
        "|---|---:|",
        f"| Observations GBIF dans le département (≥ {contexte['annee_min']}, "
        f"{contexte['licences']}) "
        f"| {r.n_total} |",
        f"| … datées au jour près (phénologie) | {r.n_dates} |",
        f"| … localisées à ≤ {contexte['incertitude_max_m']:.0f} m (habitat, météo) "
        f"| {r.n_localisees} |",
        f"| Fond « target-group » : observations de champignons localisées | {r.n_fond} |",
        "",
    ]
    if r.jeux is not None and len(r.jeux):
        lignes += ["Principaux jeux de données (GBIF) :", ""]
        lignes += [f"- {nom} : {n}" for nom, n in r.jeux.head(6).items()]
        lignes += ["", f"Requête GBIF : {contexte['requete']}", ""]

    _fig_phenologie(r, dossier / "phenologie.png")
    lignes += [
        "## Phénologie",
        "",
        "![Phénologie](phenologie.png)",
        "",
        f"Observations hors de la fenêtre saisonnière du modèle : **{r.hors_saison_pct:.0f} %**.",
        "",
    ]

    lignes += ["## Habitat", ""]
    if r.h_presences is not None and r.n_localisees:
        _fig_habitat(r, dossier / "habitat.png")
        lignes += [
            "L'habitat est moyenné dans le cercle d'incertitude de chaque observation, puis "
            "comparé au même calcul sur le fond.",
            "",
            "![Habitat](habitat.png)",
            "",
            f"- AUC observations / fond : {_qualite(r.auc_h, r.n_localisees)}",
            f"- Indice de Boyce continu : {_qualite(r.boyce_h, r.n_localisees, 0.5)}",
            "",
        ]
        for nom, t in r.compositions.items():
            lignes += [f"### Composition : {nom}", "",
                       "Part moyenne de chaque classe dans les cercles (observations et fond), "
                       "et valeur attribuée par la règle.", "", _table(t), ""]
    else:
        lignes += ["Aucune observation localisée : habitat non évalué.", ""]

    lignes += ["## Météo à la date d'observation", ""]
    if r.meteo is not None and r.meteo["observe"].any():
        _fig_meteo(r, dossier / "meteo.png")
        n = int(r.meteo.loc[r.meteo["observe"], "M"].notna().sum())
        jour = r.meteo[r.meteo["observe"]]
        colonnes = [c for c in jour.columns if c.startswith("f_") and jour[c].notna().any()]
        lignes += [
            "Score M calculé avec la météo historique (Open-Meteo, ERA5-Land et ERA5), à "
            "l'altitude médiane des forêts du cercle, comparé aux autres jours de la saison "
            "au même endroit.",
            "",
            "![Météo](meteo.png)",
            "",
            f"- AUC temporelle : {_qualite(r.auc_m, n)}",
            "- Sous-scores moyens le jour observé : "
            + ", ".join(f"{c[2:]} {jour[c].mean():.2f}" for c in colonnes),
            "",
        ]
        if r.indicateurs is not None and len(r.indicateurs):
            lignes += ["Valeurs des indicateurs les jours d'observation (déciles 10 et 90, "
                       "médiane), comparées aux seuils du trapèze de la règle :", "",
                       _table(r.indicateurs), ""]
    else:
        lignes += ["Météo historique non évaluée.", ""]

    lignes += ["## Règles à revoir", ""]
    lignes += [f"- {a}" for a in r.alertes] or ["Aucune contradiction nette avec les données."]
    lignes += [""]
    chemin = dossier / "rapport.md"
    chemin.write_text("\n".join(lignes), encoding="utf-8")
    return chemin


def ecrire_index(resultats: list[Resultat], dossier: Path, contexte: dict) -> Path:
    lignes = ["# Rapports de calibrage", "", f"Généré le {contexte['date']}.", ""]
    if contexte.get("provisoire"):
        lignes += ["> **Provisoire** : " + contexte["provisoire"], ""]
    lignes += ["| Espèce | Obs. | Datées | Localisées | Hors saison | AUC habitat | Boyce "
               "| AUC météo | Alertes |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for r in resultats:
        lignes.append(
            f"| [{r.espece.nom}]({r.espece.id}/rapport.md) | {r.n_total} | {r.n_dates} "
            f"| {r.n_localisees} | {r.hors_saison_pct:.0f} % | {_f(r.auc_h)} | {_f(r.boyce_h)} "
            f"| {_f(r.auc_m)} | {len(r.alertes)} |")
    lignes += ["", "Seuils d'alerte : effectif < 20 (indicatif), plus de 10 % d'observations "
               "hors saison, AUC < 0,6, classe sur-représentée × 1,5 mais notée ≤ 0,3 ou "
               "sous-représentée × 0,5 mais notée ≥ 0,8.", ""]
    chemin = dossier / "README.md"
    chemin.write_text("\n".join(lignes), encoding="utf-8")
    return chemin
