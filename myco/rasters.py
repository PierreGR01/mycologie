"""Lecture et écriture des rasters de la grille de référence (COG compressés)."""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import rasterio
import rasterio.shutil
from rasterio.features import rasterize
from rasterio.io import MemoryFile

from myco.grid import Grille


def ecrire_cog(
    chemin: Path,
    tableau: np.ndarray,
    grille: Grille,
    *,
    nodata: float | None = None,
    reechantillonnage_apercus: str = "NEAREST",
    description: str | None = None,
) -> Path:
    """Écrit `tableau` en Cloud Optimized GeoTIFF, de façon atomique."""
    if tableau.shape != grille.forme:
        raise ValueError(f"forme {tableau.shape} différente de la grille {grille.forme}")
    chemin.parent.mkdir(parents=True, exist_ok=True)
    predicteur = "3" if np.issubdtype(tableau.dtype, np.floating) else "2"
    temporaire = chemin.with_name(chemin.name + ".tmp")
    with MemoryFile() as mem:
        with mem.open(**grille.profil(str(tableau.dtype), nodata)) as dst:
            dst.write(tableau, 1)
            if description:
                dst.set_band_description(1, description)
        with mem.open() as src:
            rasterio.shutil.copy(
                src,
                temporaire,
                driver="COG",
                COMPRESS="DEFLATE",
                PREDICTOR=predicteur,
                BLOCKSIZE=512,
                RESAMPLING=reechantillonnage_apercus,
            )
    os.replace(temporaire, chemin)
    return chemin


def lire(chemin: Path) -> tuple[np.ndarray, dict]:
    with rasterio.open(chemin) as src:
        return src.read(1), src.profile


def rasteriser(geometries, valeurs, grille: Grille, dtype: str = "uint8") -> np.ndarray:
    """Rastérise des polygones (centre des pixels). Les valeurs nulles et les géométries vides
    sont ignorées ; le fond vaut 0."""
    formes = [
        (g, int(v))
        for g, v in zip(geometries, valeurs, strict=True)
        if v and g is not None and not g.is_empty
    ]
    if not formes:
        return np.zeros(grille.forme, dtype=dtype)
    return rasterize(
        formes, out_shape=grille.forme, transform=grille.transform, fill=0, dtype=dtype
    )
