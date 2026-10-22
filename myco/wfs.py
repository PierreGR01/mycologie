"""Lecture paginée d'une couche WFS 2.0 (Géoplateforme IGN) en GeoDataFrame."""

from __future__ import annotations

import logging

import geopandas as gpd

from myco.config import Reseau
from myco.reseau import obtenir

log = logging.getLogger(__name__)


def lire_entites(
    url: str,
    couche: str,
    reseau: Reseau,
    *,
    crs: str,
    filtre_cql: str | None = None,
    bbox: tuple[float, float, float, float] | None = None,
    taille_page: int = 5000,
) -> gpd.GeoDataFrame:
    if filtre_cql and bbox:
        raise ValueError("BBOX et CQL_FILTER ne peuvent pas être combinés")
    params = {
        "SERVICE": "WFS",
        "VERSION": "2.0.0",
        "REQUEST": "GetFeature",
        "TYPENAMES": couche,
        "OUTPUTFORMAT": "application/json",
        "SRSNAME": crs,
        "COUNT": taille_page,
        "STARTINDEX": 0,
    }
    if filtre_cql:
        params["CQL_FILTER"] = filtre_cql
    if bbox:
        params["BBOX"] = ",".join(str(v) for v in bbox) + f",{crs}"

    entites: list[dict] = []
    while True:
        page = obtenir(url, reseau, params=params).json().get("features", [])
        entites.extend(page)
        log.info("%s : %d entités", couche, len(entites))
        if len(page) < taille_page:
            break
        params["STARTINDEX"] += taille_page
    return gpd.GeoDataFrame.from_features(entites, crs=crs)
