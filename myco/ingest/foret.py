"""BD Forêt V2 : classes d'essences rastérisées sur la grille de référence."""

from __future__ import annotations

import logging
from pathlib import Path

import geopandas as gpd
import pandas as pd

from myco import db
from myco.config import ClassesForet, Parametres, charger_classes_foret
from myco.grid import Grille
from myco.ingest import colonne, grille_reference
from myco.rasters import ecrire_cog, rasteriser
from myco.reseau import ecrire_trace
from myco.wfs import lire_entites

log = logging.getLogger(__name__)


def telecharger(p: Parametres, grille: Grille) -> Path:
    src = p.sources["bdforet"]
    destination = p.dossier_brut / "bdforet" / f"bdforet_{p.departement}.gpkg"
    if destination.exists():
        return destination
    gdf = lire_entites(
        src.wfs, src.couche, p.reseau, crs=p.grille.crs, bbox=grille.bornes,
        taille_page=src.taille_page,
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(destination, driver="GPKG")
    ecrire_trace(destination, src.wfs, couche=src.couche, bbox=list(grille.bornes))
    return destination


def classer(gdf: gpd.GeoDataFrame, classes: ClassesForet, champs: dict) -> gpd.GeoDataFrame:
    """Ajoute les colonnes normalisées code_tfv, tfv, essence, classe et code."""
    sortie = gdf[["geometry"]].copy()
    for cle in ("code_tfv", "tfv", "essence"):
        nom = colonne(gdf, champs.get(cle))
        sortie[cle] = gdf[nom].astype("string").str.strip() if nom else pd.NA
    if sortie["code_tfv"].isna().all():
        raise RuntimeError(f"champ {champs.get('code_tfv')} absent de BD Forêt : vérifier `champs`")

    cle_par_tfv = {t: cle for cle, c in classes.classes.items() for t in c.tfv}
    sortie["classe"] = sortie["code_tfv"].str.upper().map(cle_par_tfv).fillna("inconnu")
    sortie["code"] = sortie["classe"].map({k: c.code for k, c in classes.classes.items()})
    sortie["code"] = sortie["code"].astype("uint8")
    return sortie


def rapport_codes(classe: gpd.GeoDataFrame) -> pd.DataFrame:
    """Codes TFV rencontrés, avec leur classe et leur surface, pour relecture."""
    return (
        classe.assign(surface_ha=classe.geometry.area / 1e4)
        .groupby(["code_tfv", "tfv", "classe"], dropna=False)
        .agg(n_polygones=("code", "size"), surface_ha=("surface_ha", "sum"))
        .reset_index()
        .sort_values("surface_ha", ascending=False)
        .round({"surface_ha": 1})
    )


def executer(p: Parametres, avec_base: bool = True) -> Path:
    grille = grille_reference(p)
    fichier = telecharger(p, grille)
    classes = charger_classes_foret()
    gdf = classer(gpd.read_file(fichier).to_crs(p.grille.crs), classes, p.sources["bdforet"].champs)

    rapport = rapport_codes(gdf)
    chemin_rapport = p.dossier_rapports / "ingestion" / "foret_codes.csv"
    chemin_rapport.parent.mkdir(parents=True, exist_ok=True)
    rapport.to_csv(chemin_rapport, index=False)
    inconnus = rapport[rapport["classe"] == "inconnu"]
    if not inconnus.empty:
        log.warning("codes TFV non reconnus (classe « inconnu ») : %s",
                    ", ".join(inconnus["code_tfv"].astype(str)))

    sortie = ecrire_cog(
        p.dossier_statique / "foret.tif", rasteriser(gdf.geometry, gdf["code"], grille), grille,
        description="classe d'essence (config/classes/foret.yaml)",
    )
    if avec_base:
        eng = db.moteur(p.url_base)
        table = gdf.drop(columns="code").assign(id=[str(i) for i in range(len(gdf))])
        db.remplacer_table(eng, table, "ref", "bdforet")
        db.enregistrer_source(eng, "bdforet", p.sources["bdforet"], fichier)
    return sortie
