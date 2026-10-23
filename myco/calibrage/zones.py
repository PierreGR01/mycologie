"""Statistiques zonales autour des observations : cercle de rayon égal à l'incertitude."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from myco.grid import Grille

NODATA_H = 255


class Zones:
    """Valeurs d'une couche dans le cercle de chaque observation (calculées une fois par
    position et rayon distincts : les observations floutées partagent souvent le même point)."""

    def __init__(self, grille: Grille):
        self.grille = grille
        self._disques: dict[int, np.ndarray] = {}

    def disque(self, rayon_m: float) -> np.ndarray:
        r = max(0, int(round(rayon_m / self.grille.resolution)))
        if r not in self._disques:
            y, x = np.ogrid[-r:r + 1, -r:r + 1]
            self._disques[r] = x * x + y * y <= r * r
        return self._disques[r]

    def pixels(self, couche: np.ndarray, x: float, y: float, rayon_m: float) -> np.ndarray:
        """Valeurs des pixels dont le centre est dans le cercle (tronqué au bord de la grille)."""
        d = self.disque(rayon_m)
        r = d.shape[0] // 2
        col = int((x - self.grille.xmin) // self.grille.resolution)
        lig = int((self.grille.ymax - y) // self.grille.resolution)
        l0, l1 = max(lig - r, 0), min(lig + r + 1, self.grille.hauteur)
        c0, c1 = max(col - r, 0), min(col + r + 1, self.grille.largeur)
        if l0 >= l1 or c0 >= c1:
            return np.empty(0, dtype=couche.dtype)
        masque = d[l0 - (lig - r):l1 - (lig - r), c0 - (col - r):c1 - (col - r)]
        return couche[l0:l1, c0:c1][masque]


def rayons(obs: pd.DataFrame, resolution: float) -> np.ndarray:
    """Rayon de chaque observation : son incertitude, au moins un pixel."""
    return np.maximum(obs["incertitude_m"].fillna(resolution).to_numpy(), resolution)


def h_moyen(zones: Zones, h: np.ndarray, obs: pd.DataFrame) -> np.ndarray:
    """Habitat moyen (0–1) dans le cercle, pixels du département seulement."""
    cache: dict[tuple, float] = {}
    for x, y, r in _positions(obs, zones.grille.resolution).index:
        v = zones.pixels(h, x, y, r)
        v = v[v != NODATA_H]
        cache[(x, y, r)] = float(v.mean()) / 100 if v.size else np.nan
    cles = zip(obs.geometry.x.round(), obs.geometry.y.round(),
               np.round(rayons(obs, zones.grille.resolution)), strict=True)
    return np.array([cache[c] for c in cles])


def _positions(obs: pd.DataFrame, resolution: float) -> pd.Series:
    """Nombre d'observations par position et rayon distincts (arrondis au mètre)."""
    cles = pd.DataFrame({"x": obs.geometry.x.round(), "y": obs.geometry.y.round(),
                         "r": np.round(rayons(obs, resolution))})
    return cles.value_counts()


def composition(zones: Zones, classes: np.ndarray, obs: pd.DataFrame,
                codes: dict[int, str], ignorer: set[int]) -> pd.Series:
    """Part moyenne de chaque classe dans les cercles (chaque observation pèse 1)."""
    total = np.zeros(256)
    n = 0
    exclus = np.array(sorted(ignorer))
    for (x, y, r), poids in _positions(obs, zones.grille.resolution).items():
        v = zones.pixels(classes, x, y, r)
        v = v[~np.isin(v, exclus)]
        if v.size:
            total += poids * np.bincount(v, minlength=256) / v.size
            n += poids
    return pd.Series({cle: total[code] / max(n, 1) for code, cle in codes.items()})


def auc(presences: np.ndarray, fond: np.ndarray) -> float:
    """Probabilité qu'une présence ait une valeur supérieure à un point du fond (ex æquo : ½)."""
    p, f = presences[~np.isnan(presences)], fond[~np.isnan(fond)]
    if not p.size or not f.size:
        return np.nan
    return float(stats.mannwhitneyu(p, f).statistic / (p.size * f.size))


def boyce(presences: np.ndarray, fond: np.ndarray, largeur: float = 0.1,
          pas: float = 0.01) -> tuple[float, pd.DataFrame]:
    """Indice de Boyce continu (Hirzel et al. 2006) : corrélation de Spearman entre la valeur
    d'habitat et le rapport prédit/attendu (P/E) sur des fenêtres glissantes."""
    p, f = presences[~np.isnan(presences)], fond[~np.isnan(fond)]
    if p.size < 5 or not f.size:
        return np.nan, pd.DataFrame(columns=["centre", "pe"])
    debuts = np.arange(min(p.min(), f.min()), max(p.max(), f.max()) - largeur + pas, pas)
    lignes = []
    for d in debuts:
        dp = ((p >= d) & (p <= d + largeur)).mean()
        df = ((f >= d) & (f <= d + largeur)).mean()
        if df > 0:
            lignes.append({"centre": d + largeur / 2, "pe": dp / df})
    courbe = pd.DataFrame(lignes)
    if len(courbe) < 3 or courbe["pe"].nunique() < 2:
        return np.nan, courbe
    return float(stats.spearmanr(courbe["centre"], courbe["pe"]).statistic), courbe
