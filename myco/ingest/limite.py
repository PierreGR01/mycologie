"""Limite du département (ADMIN EXPRESS) et masque de référence."""

from __future__ import annotations

import logging
from pathlib import Path

import geopandas as gpd
import numpy as np

from myco import db
from myco.config import Parametres
from myco.grid import Grille
from myco.ingest import chemin_masque, colonne
from myco.rasters import ecrire_cog, rasteriser
from myco.reseau import ecrire_trace
from myco.wfs import lire_entites

log = logging.getLogger(__name__)


def telecharger(p: Parametres) -> Path:
    src = p.sources["admin_express"]
    destination = p.dossier_brut / "limite" / f"departement_{p.departement}.geojson"
    if destination.exists():
        return destination
    gdf = lire_entites(
        src.wfs,
        src.couche,
        p.reseau,
        crs=p.grille.crs,
        filtre_cql=f"{src.champ_code}='{p.departement}'",
    )
    if gdf.empty:
        raise RuntimeError(f"département {p.departement} introuvable dans {src.couche}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(destination, driver="GeoJSON")
    ecrire_trace(destination, src.wfs, couche=src.couche)
    return destination


def construire_masque(limite: gpd.GeoDataFrame, p: Parametres) -> tuple[Grille, np.ndarray]:
    limite = limite.to_crs(p.grille.crs)
    grille = Grille.englobant(
        tuple(limite.total_bounds), p.grille.resolution_m, p.grille.tampon_m, p.grille.crs
    )
    masque = rasteriser(limite.geometry, [1] * len(limite), grille)
    return grille, masque


def executer(p: Parametres, avec_base: bool = True) -> Path:
    fichier = telecharger(p)
    limite = gpd.read_file(fichier)
    grille, masque = construire_masque(limite, p)
    sortie = ecrire_cog(chemin_masque(p), masque, grille, description="département")
    log.info(
        "grille %d × %d px (%.0f m), %d px dans le département",
        grille.largeur, grille.hauteur, grille.resolution, int(masque.sum()),
    )
    if avec_base:
        eng = db.moteur(p.url_base)
        src = p.sources["admin_express"]
        nom = colonne(limite, src.model_extra.get("champ_nom", "nom_officiel"))
        table = gpd.GeoDataFrame(
            {
                "code": [p.departement] * len(limite),
                "nom": limite[nom] if nom else None,
            },
            geometry=limite.to_crs(p.grille.crs).geometry.values,
            crs=p.grille.crs,
        )
        db.remplacer_table(eng, table, "ref", "departement")
        db.enregistrer_source(eng, "admin_express", src, fichier)
    return sortie
