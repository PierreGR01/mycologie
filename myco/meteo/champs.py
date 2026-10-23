"""Champs journaliers sur la grille grossière, réduits au niveau de la mer pour la température.

Variables stockées (une bande par jour, data/runs/<run>/meteo/<variable>.tif) :
- pluie : cumul journalier (mm) ;
- t0moy, t0min : température moyenne et minimale ramenées au niveau de la mer, T₀ = T + γ·z ;
- amplitude : Tmax − Tmin (°C), indépendante de γ.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from scipy.ndimage import distance_transform_edt

from myco.grid import Grille

VARIABLES_CHAMPS = ("pluie", "t0moy", "t0min", "amplitude")


def champs_grossiers(tableau: pd.DataFrame, points: pd.DataFrame, grille: Grille,
                     jours: list[date], gradient: float) -> dict[str, np.ndarray]:
    """(n_jours, ny, nx) par variable. Les cellules sans point sont comblées par la valeur du
    point le plus proche, pour que l'interpolation fine reste définie en bordure."""
    t = tableau.merge(points[["id", "ligne", "colonne"]], left_on="point_id", right_on="id")
    t = t.assign(
        t0moy=t["tmoy"] + gradient * t["z_ref"],
        t0min=t["tmin"] + gradient * t["z_ref"],
        amplitude=t["tmax"] - t["tmin"],
    )
    rang = {j: k for k, j in enumerate(jours)}
    k = t["jour"].map(rang).to_numpy()
    champs = {}
    for v in VARIABLES_CHAMPS:
        a = np.full((len(jours), grille.hauteur, grille.largeur), np.nan, dtype="float32")
        a[k, t["ligne"].to_numpy(), t["colonne"].to_numpy()] = t[v].to_numpy()
        champs[v] = np.stack([combler(b) for b in a])
    return champs


def combler(a: np.ndarray) -> np.ndarray:
    """Remplace les NaN par la valeur valide la plus proche."""
    vide = np.isnan(a)
    if not vide.any() or vide.all():
        return a
    _, (i, j) = distance_transform_edt(vide, return_indices=True)
    return a[i, j]


def ecrire(dossier: Path, champs: dict[str, np.ndarray], grille: Grille, jours: list[date],
           meta: dict) -> None:
    dossier.mkdir(parents=True, exist_ok=True)
    profil = grille.profil("float32") | {"count": len(jours), "compress": "deflate"}
    for v, a in champs.items():
        with rasterio.open(dossier / f"{v}.tif", "w", **profil) as dst:
            dst.write(a)
            for b, j in enumerate(jours, start=1):
                dst.set_band_description(b, j.isoformat())
    (dossier / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))


def lire(dossier: Path) -> tuple[Grille, list[date], dict[str, np.ndarray], dict]:
    champs = {}
    for v in VARIABLES_CHAMPS:
        with rasterio.open(dossier / f"{v}.tif") as src:
            champs[v] = src.read()
            jours = [date.fromisoformat(d) for d in src.descriptions]
    meta = json.loads((dossier / "meta.json").read_text())
    return Grille.depuis_raster(dossier / "pluie.tif"), jours, champs, meta
