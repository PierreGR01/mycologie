"""Limites des départements (ADMIN EXPRESS) et masque de référence."""

from __future__ import annotations

import logging
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

from myco import db
from myco.config import Parametres
from myco.grid import Grille
from myco.ingest import chemin_masque, colonne
from myco.rasters import ecrire_cog, rasteriser
from myco.reseau import ecrire_trace
from myco.wfs import lire_entites

log = logging.getLogger(__name__)


def chemin_limite(p: Parametres, departement: str) -> Path:
    return p.dossier_brut / "limite" / f"departement_{departement}.geojson"


def telecharger(p: Parametres, departement: str) -> Path:
    src = p.sources["admin_express"]
    destination = chemin_limite(p, departement)
    if destination.exists():
        return destination
    gdf = lire_entites(
        src.wfs,
        src.couche,
        p.reseau,
        crs=p.grille.crs,
        filtre_cql=f"{src.champ_code}='{departement}'",
    )
    if gdf.empty:
        raise RuntimeError(f"département {departement} introuvable dans {src.couche}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(destination, driver="GeoJSON")
    ecrire_trace(destination, src.wfs, couche=src.couche)
    return destination


def lire_limites(p: Parametres) -> gpd.GeoDataFrame:
    """Contours des départements configurés, une ligne par département (colonnes code, nom),
    dans le système de la grille."""
    src = p.sources["admin_express"]
    morceaux = []
    for d in p.departements:
        chemin = chemin_limite(p, d)
        if not chemin.exists():
            raise FileNotFoundError(f"{chemin} absent : lancer d'abord `myco ingest limite`")
        gdf = gpd.read_file(chemin).to_crs(p.grille.crs)
        nom = colonne(gdf, src.model_extra.get("champ_nom", "nom_officiel"))
        morceaux.append(gpd.GeoDataFrame(
            {"code": [d], "nom": [str(gdf[nom].iloc[0]) if nom else d]},
            geometry=[gdf.union_all()], crs=p.grille.crs,
        ))
    return gpd.GeoDataFrame(pd.concat(morceaux, ignore_index=True), crs=p.grille.crs)


def construire_masque(limite: gpd.GeoDataFrame, p: Parametres) -> tuple[Grille, np.ndarray]:
    """Grille englobant tous les départements, et masque : rang du département dans `limite`
    (1, 2…), 0 en dehors."""
    limite = limite.to_crs(p.grille.crs)
    grille = Grille.englobant(
        tuple(limite.total_bounds), p.grille.resolution_m, p.grille.tampon_m, p.grille.crs
    )
    masque = rasteriser(limite.geometry, range(1, len(limite) + 1), grille)
    return grille, masque


def executer(p: Parametres, avec_base: bool = True) -> Path:
    fichiers = [telecharger(p, d) for d in p.departements]
    limite = lire_limites(p)
    grille, masque = construire_masque(limite, p)
    sortie = ecrire_cog(chemin_masque(p), masque, grille,
                        description="rang du département : " + ", ".join(
                            f"{i} = {d}" for i, d in enumerate(p.departements, start=1)))
    log.info(
        "grille %d × %d px (%.0f m), %d px dans les départements %s",
        grille.largeur, grille.hauteur, grille.resolution, int((masque > 0).sum()),
        ", ".join(p.departements),
    )
    if avec_base:
        eng = db.moteur(p.url_base)
        db.remplacer_table(eng, limite, "ref", "departement")
        db.enregistrer_source(eng, "admin_express", p.sources["admin_express"], fichiers[0])
    return sortie
