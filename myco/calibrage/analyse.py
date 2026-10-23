"""Indicateurs de calibrage par espèce : phénologie, habitat, météo à la date d'observation.

Les seuils d'alerte ci-dessous signalent les règles que les observations contredisent ; ils ne
modifient jamais les fichiers espèces (décision humaine).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import numpy as np
import pandas as pd

from myco.especes import Espece, FacteurTable
from myco.score import facteur_saison

N_MIN = 20                 # effectif minimal pour interpréter un indicateur
HORS_SAISON_MAX = 10       # % d'observations hors fenêtre saisonnière toléré
AUC_FAIBLE = 0.6           # pouvoir discriminant jugé faible en dessous
RATIO_FORT, RATIO_FAIBLE = 1.5, 0.5
NUL_MAX = 20               # % de jours observés où un indicateur vaut 0 au-delà duquel on alerte
VALEUR_BASSE, VALEUR_HAUTE = 0.3, 0.8
MOIS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.",
        "nov.", "déc."]


@dataclass
class Resultat:
    espece: Espece
    n_total: int
    n_dates: int
    n_localisees: int
    n_fond: int
    phenologie: pd.DataFrame
    hors_saison_pct: float
    h_presences: np.ndarray | None = None
    h_fond: np.ndarray | None = None
    auc_h: float = np.nan
    boyce_h: float = np.nan
    courbe_boyce: pd.DataFrame | None = None
    compositions: dict[str, pd.DataFrame] = field(default_factory=dict)
    meteo: pd.DataFrame | None = None
    indicateurs: pd.DataFrame | None = None
    auc_m: float = np.nan
    alertes: list[str] = field(default_factory=list)
    jeux: pd.Series | None = None


def valeurs_regle(espece: Espece, couche: str) -> dict[str, float]:
    """Valeurs du facteur `table` portant sur `couche` (maximum sur les profils)."""
    valeurs: dict[str, float] = {}
    for profil in espece.habitat.liste_profils().values():
        for f in profil.facteurs.values():
            if isinstance(f, FacteurTable) and f.couche == couche:
                for cle in set(valeurs) | set(f.valeurs):
                    valeurs[cle] = max(valeurs.get(cle, f.defaut), f.valeurs.get(cle, f.defaut))
    return valeurs


def phenologie(obs: pd.DataFrame, espece: Espece) -> tuple[pd.DataFrame, float]:
    """Observations par quinzaine et facteur saisonnier du modèle au milieu de la quinzaine."""
    dates = obs["date_obs"].dropna()
    quinzaine = dates.map(lambda d: (d.month - 1) * 2 + (d.day > 15))
    comptes = quinzaine.value_counts().reindex(range(24), fill_value=0)
    milieux = [date(2001, q // 2 + 1, 23 if q % 2 else 8) for q in range(24)]
    table = pd.DataFrame({
        "quinzaine": [f"{MOIS[q // 2]} {'2' if q % 2 else '1'}" for q in range(24)],
        "observations": comptes.to_numpy(),
        "saison_modele": [round(facteur_saison(m, espece.meteo.saison), 2) for m in milieux],
    })
    hors = sum(facteur_saison(d, espece.meteo.saison) == 0 for d in dates)
    return table, 100 * hors / max(len(dates), 1)


def composition_comparee(part_p: pd.Series, part_f: pd.Series,
                         regle: dict[str, float]) -> pd.DataFrame:
    """Parts de chaque classe autour des observations et du fond, et valeur de la règle."""
    t = pd.DataFrame({"part_observations": part_p, "part_fond": part_f}).fillna(0)
    t = t[(t["part_observations"] > 0) | (t["part_fond"] > 0)]
    t["ratio"] = t["part_observations"] / t["part_fond"].replace(0, np.nan)
    t.insert(0, "valeur_regle", [regle.get(c, np.nan) for c in t.index])
    return t.sort_values("part_fond", ascending=False).round(3)


def alertes_composition(t: pd.DataFrame, nom_couche: str, n: int) -> list[str]:
    if n < N_MIN:
        return []
    sortie = []
    for classe, ligne in t.iterrows():
        if ligne["part_observations"] < 0.05 and ligne["part_fond"] < 0.05:
            continue
        if ligne["ratio"] >= RATIO_FORT and ligne["valeur_regle"] <= VALEUR_BASSE:
            sortie.append(f"{nom_couche} « {classe} » : sur-représentée près des observations "
                          f"(× {ligne['ratio']:.1f}) mais notée {ligne['valeur_regle']:.1f}.")
        if ligne["ratio"] <= RATIO_FAIBLE and ligne["valeur_regle"] >= VALEUR_HAUTE:
            sortie.append(f"{nom_couche} « {classe} » : sous-représentée près des observations "
                          f"(× {ligne['ratio']:.1f}) mais notée {ligne['valeur_regle']:.1f}.")
    return sortie


def evaluation_temporelle(scores: pd.DataFrame) -> float:
    """AUC temporelle : probabilité que M le jour observé dépasse M un autre jour de la saison au
    même point (moyenne sur les observations)."""
    valeurs = []
    for _, g in scores.groupby("observation"):
        jour = g.loc[g["observe"], "M"]
        autres = g.loc[~g["observe"] & (g["f_saison"] > 0), "M"].dropna()
        if jour.empty or np.isnan(jour.iloc[0]) or autres.empty:
            continue
        m = jour.iloc[0]
        valeurs.append(((autres < m).sum() + 0.5 * (autres == m).sum()) / len(autres))
    return float(np.mean(valeurs)) if valeurs else np.nan


def indicateurs_observes(meteo_obs: pd.DataFrame, espece: Espece) -> pd.DataFrame:
    """Valeurs des indicateurs les jours d'observation, comparées aux seuils de la règle."""
    jour = meteo_obs[meteo_obs["observe"]]
    lignes = []
    for nom, ind in espece.meteo.indicateurs.items():
        v = jour[nom].dropna()
        if v.empty:
            continue
        lignes.append({
            "indicateur": nom,
            "seuils_regle": " / ".join(f"{x:g}" for x in ind.points),
            "p10": v.quantile(0.1), "mediane": v.median(), "p90": v.quantile(0.9),
            "sous_score_moyen": jour[f"f_{nom}"].mean(),
            "jours_a_zero_pct": 100 * (jour[f"f_{nom}"] == 0).mean(),
        })
    return pd.DataFrame(lignes).set_index("indicateur").round(2)


def alertes_indicateurs(t: pd.DataFrame, n: int) -> list[str]:
    if n < N_MIN:
        return []
    return [f"Météo : « {nom} » vaut 0 pour {ligne['jours_a_zero_pct']:.0f} % des jours "
            f"observés (médiane observée {ligne['mediane']:g}, seuils {ligne['seuils_regle']})."
            for nom, ligne in t.iterrows() if ligne["jours_a_zero_pct"] >= NUL_MAX]
