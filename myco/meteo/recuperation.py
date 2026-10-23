"""Récupération météo d'un run : Open-Meteo → champs grossiers (+ PostGIS)."""

from __future__ import annotations

import logging
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import geopandas as gpd
import pandas as pd
from sqlalchemy import text

from myco import db
from myco.config import Parametres
from myco.meteo import champs as mod_champs
from myco.meteo import openmeteo
from myco.meteo.indicateurs import FENETRE_MAX
from myco.meteo.points import points_echantillonnage

log = logging.getLogger(__name__)


def aujourdhui(p: Parametres) -> date:
    return datetime.now(ZoneInfo(p.meteo.fuseau)).date()


def jours_du_run(run: date, p: Parametres) -> list[date]:
    """Jours à télécharger : de J-7 moins la plus longue fenêtre jusqu'à J+7."""
    debut = run - timedelta(days=p.meteo.jours_avant + FENETRE_MAX - 1)
    n = (run - debut).days + p.meteo.jours_apres + 1
    return [debut + timedelta(days=k) for k in range(n)]


def dossier_meteo(p: Parametres, run: date) -> Path:
    return p.dossier_runs / run.isoformat() / "meteo"


def limite_departement(p: Parametres) -> gpd.GeoDataFrame:
    chemin = p.dossier_brut / "limite" / f"departement_{p.departement}.geojson"
    if not chemin.exists():
        raise FileNotFoundError(f"{chemin} absent : lancer d'abord `myco ingest limite`")
    return gpd.read_file(chemin).to_crs(p.grille.crs)


def charger_base(p: Parametres, run: date, points: gpd.GeoDataFrame, tableau: pd.DataFrame,
                 recupere_le: date) -> None:
    eng = db.moteur(p.url_base)
    z = tableau.groupby("point_id")["z_ref"].first()
    lignes_points = [
        {"id": int(i), "x": g.x, "y": g.y, "z": float(z[i])}
        for i, g in zip(points["id"], points.geometry, strict=True)
    ]
    journalier = tableau.drop(columns="z_ref").assign(
        run=run, est_prevision=tableau["jour"] >= recupere_le, modele=p.meteo.modele
    )
    with eng.begin() as cx:
        cx.execute(text(
            "INSERT INTO meteo.point (id, geom, z_ref) "
            "VALUES (:id, ST_SetSRID(ST_MakePoint(:x, :y), 2154), :z) "
            "ON CONFLICT (id) DO UPDATE SET geom = EXCLUDED.geom, z_ref = EXCLUDED.z_ref"
        ), lignes_points)
        cx.execute(text("DELETE FROM meteo.journalier WHERE run = :run"), {"run": run})
    journalier.to_sql("journalier", eng, schema="meteo", if_exists="append", index=False,
                      method="multi", chunksize=5000)
    log.info("meteo.journalier : %d lignes pour le run %s", len(journalier), run)


def executer(p: Parametres, run: date, avec_base: bool = True, rafraichir: bool = False) -> Path:
    limite = limite_departement(p)
    grille, points = points_echantillonnage(limite, p.meteo)
    jours = jours_du_run(run, p)
    dossier = dossier_meteo(p, run)
    if rafraichir:
        shutil.rmtree(dossier / "cache", ignore_errors=True)
    poids = openmeteo.poids_requete(len(points), len(jours))
    log.info("%d points (maille %.0f m), %d jours, ≈ %.0f appels Open-Meteo, ≈ %.0f min",
             len(points), p.meteo.espacement_m, len(jours), poids,
             poids / p.meteo.appels_par_minute)

    reponses = openmeteo.telecharger(points, jours[0], jours[-1], p.meteo, p.reseau,
                                     dossier / "cache")
    tableau = openmeteo.en_tableau(reponses, points)
    manquants = tableau[list(openmeteo.VARIABLES.values())].isna().sum()
    if manquants.any():
        log.warning("valeurs manquantes Open-Meteo : %s", manquants[manquants > 0].to_dict())

    recupere_le = aujourdhui(p)
    champs = mod_champs.champs_grossiers(tableau, points, grille, jours,
                                         p.meteo.gradient_c_par_m)
    mod_champs.ecrire(dossier, champs, grille, jours, {
        "run": run.isoformat(),
        "recupere_le": recupere_le.isoformat(),
        "modele": p.meteo.modele,
        "n_points": len(points),
        "espacement_m": p.meteo.espacement_m,
        "gradient_c_par_m": p.meteo.gradient_c_par_m,
    })
    points.drop(columns=["lon", "lat"]).to_file(dossier / "points.gpkg", driver="GPKG")
    if avec_base:
        charger_base(p, run, points, tableau, recupere_le)
    return dossier
