"""Score météo M sur des séries journalières ponctuelles (même règle que myco.score)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from myco import regles
from myco.especes import Meteo
from myco.meteo.indicateurs import INDICATEURS
from myco.score import facteur_saison, multiplicateur_gel

# Variables des champs grossiers → colonnes d'une série ponctuelle déjà à l'altitude du point.
VARIABLES_SERIE = {"pluie": "pluie", "t0moy": "tmoy", "t0min": "tmin", "amplitude": "amplitude"}


def score_series(meteo: Meteo, serie: pd.DataFrame) -> pd.DataFrame:
    """Sous-scores et M pour chaque jour d'une série (index : dates consécutives ; colonnes
    tmin, tmax, tmoy, pluie, températures à l'altitude du point). M est NaN tant que la plus
    longue fenêtre n'est pas complète."""
    s = serie.assign(amplitude=serie["tmax"] - serie["tmin"])
    sortie = pd.DataFrame(index=serie.index)
    valeurs, poids = [], []
    for nom, ind in meteo.indicateurs.items():
        d = INDICATEURS[nom]
        fenetre = s[VARIABLES_SERIE[d.variable]].rolling(d.jours, min_periods=d.jours)
        v = (fenetre.sum() if d.agregation == "somme" else fenetre.mean()).to_numpy("float32")
        sortie[nom] = v
        f = regles.trapeze(v, ind.points, ind.plancher, ind.plancher_haut)
        sortie[f"f_{nom}"] = f
        valeurs.append(f)
        poids.append(ind.poids)
    m = regles.moyenne_geometrique(valeurs, poids)
    # Tant qu'une fenêtre glissante est incomplète, M n'est pas défini.
    m[np.isnan(np.stack(valeurs)).any(axis=0)] = np.nan
    sortie["f_saison"] = [facteur_saison(j, meteo.saison) for j in serie.index]
    m = m * sortie["f_saison"].to_numpy("float32")
    if meteo.gel:
        g = meteo.gel
        gel = (s["tmin"] < g.seuil_tmin).astype(float).rolling(g.fenetre_jours,
                                                               min_periods=g.fenetre_jours)
        n = gel.sum().to_numpy()
        sortie["jours_gel"] = n
        mult = multiplicateur_gel(np.nan_to_num(n).astype("uint8"), g)
        mult[np.isnan(n)] = np.nan
        sortie["f_gel"] = mult
        m = m * mult
    sortie["M"] = m
    return sortie
