"""Fonctions élémentaires des règles écologiques, vectorisées sur des tableaux numpy.

Les paramètres viennent des fichiers config/especes/*.yaml : aucune valeur propre à une espèce
n'est écrite ici. Une valeur NaN signifie « pas de donnée ».
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np


def trapeze(
    x: np.ndarray,
    points: Sequence[float],
    plancher: float = 0.0,
    plancher_haut: float | None = None,
) -> np.ndarray:
    """Fonction trapèze : 1 entre b et c, rampes linéaires entre a et b puis entre c et d.

    Vaut `plancher` sous a et `plancher_haut` (par défaut `plancher`) au-delà de d.
    """
    a, b, c, d = points
    haut = plancher if plancher_haut is None else plancher_haut
    x = np.asarray(x, dtype="float32")
    with np.errstate(divide="ignore", invalid="ignore"):
        montee = plancher + (1 - plancher) * (x - a) / (b - a) if b > a else np.ones_like(x)
        descente = haut + (1 - haut) * (d - x) / (d - c) if d > c else np.ones_like(x)
    f = np.select(
        [x < a, x < b, x <= c, x <= d],
        [plancher, montee, 1.0, descente],
        default=haut,
    ).astype("float32")
    f[np.isnan(x)] = np.nan
    return f


def table(
    codes: np.ndarray,
    cle_par_code: Mapping[int, str],
    valeurs: Mapping[str, float],
    defaut: float = 0.0,
    nodata: int | None = None,
) -> np.ndarray:
    """Variable catégorielle codée en entiers 0–255 : valeur de la classe, `defaut` sinon."""
    lut = np.full(256, defaut, dtype="float32")
    for code, cle in cle_par_code.items():
        lut[code] = valeurs.get(cle, defaut)
    if nodata is not None:
        lut[nodata] = np.nan
    return lut[codes]


def moyenne_geometrique(facteurs: Sequence[np.ndarray], poids: Sequence[float]) -> np.ndarray:
    """Moyenne géométrique pondérée. Un facteur nul l'annule ; un facteur sans donnée (NaN) est
    écarté et les poids des autres sont renormalisés. NaN si aucun facteur n'a de donnée."""
    somme = np.zeros(facteurs[0].shape, dtype="float32")
    total = np.zeros(facteurs[0].shape, dtype="float32")
    with np.errstate(divide="ignore", invalid="ignore"):
        for f, w in zip(facteurs, poids, strict=True):
            valide = ~np.isnan(f)
            somme[valide] += w * np.log(f[valide])
            total[valide] += w
        return np.where(total > 0, np.exp(somme / total), np.nan).astype("float32")
