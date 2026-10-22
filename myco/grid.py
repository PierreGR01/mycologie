"""Grille de référence : Lambert-93, pas de 25 m, origine calée sur un multiple du pas."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import rasterio
from affine import Affine
from rasterio.crs import CRS
from rasterio.transform import from_origin

# Les sources (BD Forêt, carte au 1/50 000, SoilGrids, météo) ne permettent pas plus fin.
RESOLUTION_MIN = 25.0


@dataclass(frozen=True)
class Grille:
    crs: CRS
    resolution: float
    xmin: float
    ymin: float
    xmax: float
    ymax: float

    def __post_init__(self) -> None:
        if self.resolution < RESOLUTION_MIN:
            raise ValueError(f"résolution {self.resolution} m < minimum de {RESOLUTION_MIN} m")
        for v in (self.xmin, self.ymin, self.xmax, self.ymax):
            if not math.isclose(v / self.resolution, round(v / self.resolution), abs_tol=1e-9):
                raise ValueError(f"emprise non calée sur la grille de {self.resolution} m : {v}")

    @classmethod
    def englobant(
        cls,
        bornes: tuple[float, float, float, float],
        resolution: float,
        tampon: float = 0.0,
        crs: str | CRS = "EPSG:2154",
    ) -> Grille:
        """Plus petite grille calée contenant `bornes` élargies de `tampon`."""
        r = resolution
        return cls(
            crs=CRS.from_user_input(crs),
            resolution=r,
            xmin=math.floor((bornes[0] - tampon) / r) * r,
            ymin=math.floor((bornes[1] - tampon) / r) * r,
            xmax=math.ceil((bornes[2] + tampon) / r) * r,
            ymax=math.ceil((bornes[3] + tampon) / r) * r,
        )

    @classmethod
    def depuis_raster(cls, chemin: Path) -> Grille:
        with rasterio.open(chemin) as src:
            b = src.bounds
            return cls(src.crs, src.res[0], b.left, b.bottom, b.right, b.top)

    @property
    def largeur(self) -> int:
        return round((self.xmax - self.xmin) / self.resolution)

    @property
    def hauteur(self) -> int:
        return round((self.ymax - self.ymin) / self.resolution)

    @property
    def forme(self) -> tuple[int, int]:
        return (self.hauteur, self.largeur)

    @property
    def bornes(self) -> tuple[float, float, float, float]:
        return (self.xmin, self.ymin, self.xmax, self.ymax)

    @property
    def transform(self) -> Affine:
        return from_origin(self.xmin, self.ymax, self.resolution, self.resolution)

    def profil(self, dtype: str, nodata: float | None = None) -> dict:
        return {
            "driver": "GTiff",
            "width": self.largeur,
            "height": self.hauteur,
            "count": 1,
            "dtype": dtype,
            "crs": self.crs,
            "transform": self.transform,
            "nodata": nodata,
        }
