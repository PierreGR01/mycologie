"""Indicateurs météo quotidiens. Les fichiers espèces les désignent par leur nom."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

import numpy as np


@dataclass(frozen=True)
class Indicateur:
    variable: str                         # champ journalier (voir myco.meteo.champs)
    agregation: Literal["somme", "moyenne"]
    jours: int                            # fenêtre glissante se terminant le jour considéré
    corrige_altitude: bool                # True : champ réduit au niveau de la mer (T₀)


INDICATEURS = {
    "pluie_15j": Indicateur("pluie", "somme", 15, False),
    "tmoy_7j": Indicateur("t0moy", "moyenne", 7, True),
    "amplitude_7j": Indicateur("amplitude", "moyenne", 7, False),
}
# Plus longue fenêtre admise (indicateurs et gel) : détermine les jours à télécharger.
FENETRE_MAX = 15


def fenetre(jour: date, jours: int) -> list[date]:
    return [jour - timedelta(days=k) for k in range(jours - 1, -1, -1)]


def agreger(champ: np.ndarray, dates: list[date], jour: date, ind: Indicateur) -> np.ndarray:
    """Agrège un champ (n_jours, ny, nx) sur la fenêtre de l'indicateur se terminant à `jour`."""
    indices = [dates.index(d) for d in fenetre(jour, ind.jours)]
    bloc = champ[indices]
    return bloc.sum(axis=0) if ind.agregation == "somme" else bloc.mean(axis=0)
