"""Grille régulière de points d'échantillonnage Open-Meteo (Lambert-93)."""

from __future__ import annotations

import geopandas as gpd
import numpy as np

from myco.config import ParamMeteo
from myco.grid import Grille


def grille_grossiere(limite: gpd.GeoDataFrame, pm: ParamMeteo) -> Grille:
    """Grille dont chaque cellule a pour centre un point d'échantillonnage. Elle est calée sur un
    multiple de l'espacement et couvre le département élargi de `tampon_m`."""
    return Grille.englobant(tuple(limite.total_bounds), pm.espacement_m, pm.tampon_m,
                            limite.crs)


def points_echantillonnage(
    limite: gpd.GeoDataFrame, pm: ParamMeteo
) -> tuple[Grille, gpd.GeoDataFrame]:
    """Points au centre des cellules situés à moins de `tampon_m` du département.

    Colonnes : id, ligne, colonne, lon, lat (WGS84) et la géométrie en Lambert-93."""
    grille = grille_grossiere(limite, pm)
    lignes, colonnes = np.mgrid[0:grille.hauteur, 0:grille.largeur]
    x = grille.xmin + (colonnes.ravel() + 0.5) * grille.resolution
    y = grille.ymax - (lignes.ravel() + 0.5) * grille.resolution
    points = gpd.GeoDataFrame(
        {"ligne": lignes.ravel(), "colonne": colonnes.ravel()},
        geometry=gpd.points_from_xy(x, y), crs=limite.crs,
    )
    zone = limite.union_all().buffer(pm.tampon_m)
    points = points[points.within(zone)].reset_index(drop=True)
    wgs84 = points.to_crs("EPSG:4326")
    points["lon"], points["lat"] = wgs84.geometry.x.round(5), wgs84.geometry.y.round(5)
    points.insert(0, "id", points["ligne"] * grille.largeur + points["colonne"])
    return grille, points
