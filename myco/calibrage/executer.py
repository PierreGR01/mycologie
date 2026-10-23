"""Étape 5 : calibrage de chaque espèce avec les observations GBIF."""

from __future__ import annotations

import json
import logging
from datetime import UTC, date, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from sqlalchemy import text

from myco import db
from myco.calibrage import analyse, gbif, historique, rapport
from myco.calibrage import zones as z
from myco.calibrage.meteo_points import score_series
from myco.config import Parametres, charger_classes_foret, charger_regles_geologie
from myco.especes import Espece
from myco.ingest import grille_reference
from myco.meteo.recuperation import limite_departement

log = logging.getLogger(__name__)

# Classes d'occupation qui ne sont pas des peuplements forestiers (composition des cercles).
NON_FORESTIER = {"hors_foret", "lande_ligneuse", "herbacee", "inconnu"}


def _lire(chemin: Path) -> np.ndarray | None:
    if not chemin.exists():
        return None
    with rasterio.open(chemin) as src:
        return src.read(1)


def observations(p: Parametres, especes: dict[str, Espece], limite) -> tuple:
    """(observations des espèces, fond target-group, taxons résolus, requête de référence)."""
    pc = p.calibrage
    emprise = tuple(limite.to_crs("EPSG:4326").total_bounds)
    brut = p.dossier_brut / "gbif"
    params = gbif.parametres_recherche(pc, emprise, None)
    taxons, morceaux = [], []
    for i, e in especes.items():
        for nom in e.taxons:
            t = gbif.resoudre_taxon(nom, pc, p.reseau) | {"espece": i}
            taxons.append(t)
            df = gbif.telecharger(t["gbif_key"], params, pc, p.reseau,
                                  brut / f"taxon_{t['gbif_key']}.csv")
            morceaux.append(gbif.en_observations(df, i, limite))
    obs = pd.concat(morceaux, ignore_index=True).drop_duplicates(["espece", "source_id"])
    fond_t = gbif.resoudre_taxon(pc.fond_taxon, pc, p.reseau)
    fond_df = gbif.telecharger(fond_t["gbif_key"],
                               gbif.parametres_recherche(pc, emprise, pc.incertitude_max_m),
                               pc, p.reseau, brut / f"fond_{fond_t['gbif_key']}.csv")
    fond = gbif.en_observations(fond_df, "fond", limite)
    requete = f"{pc.gbif}/occurrence/search?" + "&".join(
        f"{k}={','.join(v) if isinstance(v, list) else v}" for k, v in params.items())
    return obs, fond, pd.DataFrame(taxons), requete


def meteo_observations(p: Parametres, especes: dict[str, Espece], obs: pd.DataFrame,
                       alt: np.ndarray, en_foret: np.ndarray, zones: z.Zones) -> pd.DataFrame:
    """M pour chaque jour de la saison de l'année d'observation, au point de chaque observation
    localisée et datée ; `observe` marque le jour de l'observation."""
    datees = obs[obs["date_obs"].notna()].copy()
    if datees.empty:
        return pd.DataFrame()
    wgs = datees.to_crs("EPSG:4326")
    datees["lon"], datees["lat"] = wgs.geometry.x.to_numpy(), wgs.geometry.y.to_numpy()
    series = historique.telecharger(
        historique.groupes(datees, especes, p.calibrage.cellule_deg), p,
        p.dossier_brut / "meteo_historique")
    rayons = z.rayons(datees, zones.grille.resolution)
    lignes = []
    for o, r in zip(datees.itertuples(), rayons, strict=True):
        altitude = historique.altitude_mediane(zones.pixels(alt, o.geometry.x, o.geometry.y, r),
                                               zones.pixels(en_foret, o.geometry.x,
                                                            o.geometry.y, r))
        if np.isnan(altitude):
            continue
        lon, lat = historique.cellule(o.lon, o.lat, p.calibrage.cellule_deg)
        serie = historique.a_l_altitude(series[(lon, lat, o.date_obs.year)], altitude,
                                        p.meteo.gradient_c_par_m)
        s = score_series(especes[o.espece].meteo, serie)
        s = s[(s["f_saison"] > 0) | (s.index == o.date_obs)]
        lignes.append(s.assign(observation=o.source_id, espece=o.espece, altitude=altitude,
                               observe=s.index == o.date_obs))
    return pd.concat(lignes) if lignes else pd.DataFrame()


def contexte_provisoire(p: Parametres, geol: np.ndarray | None, masque: np.ndarray) -> str | None:
    if geol is None or not (geol[masque == 1] > 0).any():
        return ("habitat calculé sans la carte géologique BRGM (serveur indisponible) : "
                "rapports à régénérer après son intégration.")
    return None


def charger_base(p: Parametres, obs, taxons: pd.DataFrame, resultats) -> None:
    eng = db.moteur(p.url_base)
    with eng.begin() as cx:
        cx.execute(text("DELETE FROM obs.observation WHERE source = 'gbif'"))
        cx.execute(text("DELETE FROM obs.taxon"))
    taxons[["espece", "nom_scientifique", "gbif_key"]].assign(cd_ref=None).to_sql(
        "taxon", eng, schema="obs", if_exists="append", index=False)
    obs.rename_geometry("geom").to_postgis("observation", eng, schema="obs",
                                           if_exists="append", index=False)
    run = date.today()
    metriques = [
        {"run": run, "espece": r.espece.id, "metrique": m, "valeur": v,
         "details": json.dumps({"n_localisees": r.n_localisees, "n_dates": r.n_dates})}
        for r in resultats
        for m, v in (("auc_habitat", r.auc_h), ("boyce_habitat", r.boyce_h),
                     ("auc_meteo", r.auc_m), ("hors_saison_pct", r.hors_saison_pct))
    ]
    with eng.begin() as cx:
        cx.execute(text("DELETE FROM pipeline.calibrage WHERE run = :run"), {"run": run})
        cx.execute(text("INSERT INTO pipeline.calibrage (run, espece, metrique, valeur, details) "
                        "VALUES (:run, :espece, :metrique, :valeur, CAST(:details AS jsonb))"),
                   [m | {"valeur": None if np.isnan(m["valeur"]) else float(m["valeur"])}
                    for m in metriques])


def executer(p: Parametres, especes: dict[str, Espece], avec_meteo: bool = True,
             avec_base: bool = True) -> list[Path]:
    pc = p.calibrage
    limite = limite_departement(p)
    grille = grille_reference(p)
    zones = z.Zones(grille)
    obs, fond, taxons, requete = observations(p, especes, limite)
    log.info("observations : %s ; fond : %d", obs["espece"].value_counts().to_dict(), len(fond))

    s = p.dossier_statique
    masque, foret, alt, geol = (_lire(s / f"{c}.tif") for c in ("masque", "foret", "alt", "geol"))
    classes_foret = charger_classes_foret().classes
    codes_foret = {c.code: k for k, c in classes_foret.items()}
    ignorer_foret = {classes_foret[k].code for k in NON_FORESTIER}
    en_foret = ~np.isin(foret, list(ignorer_foret))
    codes_geol = {code: k for k, code in charger_regles_geologie().classes.items()}
    geol_ok = geol is not None and (geol[masque == 1] > 0).any()

    fond_loc = fond[fond["incertitude_m"] <= pc.incertitude_max_m]
    localisees = obs[obs["incertitude_m"] <= pc.incertitude_max_m]
    scores_meteo = (meteo_observations(p, especes, localisees, alt, en_foret, zones)
                    if avec_meteo else pd.DataFrame())
    # Composition du fond : indépendante de l'espèce, calculée une fois.
    fond_essences = z.composition(zones, foret, fond_loc, codes_foret, ignorer_foret)
    fond_substrat = (z.composition(zones, geol, fond_loc, codes_geol, {0}) if geol_ok else None)

    contexte = {
        "date": datetime.now(UTC).strftime("%d/%m/%Y"),
        "annee_min": pc.annee_min,
        "incertitude_max_m": pc.incertitude_max_m,
        "requete": requete,
        "provisoire": contexte_provisoire(p, geol, masque),
    }
    resultats, sorties = [], []
    for i, e in especes.items():
        o = obs[obs["espece"] == i]
        loc = localisees[localisees["espece"] == i]
        table_pheno, hors = analyse.phenologie(o, e)
        r = analyse.Resultat(
            espece=e, n_total=len(o), n_dates=int(o["date_obs"].notna().sum()),
            n_localisees=len(loc), n_fond=len(fond_loc), phenologie=table_pheno,
            hors_saison_pct=hors, jeux=o["jeu_donnees"].value_counts(),
        )
        if r.n_dates >= analyse.N_MIN and hors > analyse.HORS_SAISON_MAX:
            mois = [analyse.MOIS[m - 1] for m in sorted(
                {d.month for d in o["date_obs"].dropna()
                 if analyse.facteur_saison(d, e.meteo.saison) == 0})]
            r.alertes.append(f"Phénologie : {hors:.0f} % des observations hors saison du modèle "
                             f"({', '.join(mois)}).")
        h = _lire(p.dossier_habitat / f"{i}.tif")
        if h is not None and len(loc):
            r.h_presences = z.h_moyen(zones, h, loc)
            r.h_fond = z.h_moyen(zones, h, fond_loc)
            r.auc_h = z.auc(r.h_presences, r.h_fond)
            r.boyce_h, r.courbe_boyce = z.boyce(r.h_presences, r.h_fond)
            if r.n_localisees >= analyse.N_MIN and r.auc_h < analyse.AUC_FAIBLE:
                r.alertes.append(f"Habitat : AUC {r.auc_h:.2f}, le modèle distingue mal les "
                                 "zones observées du fond.")
            r.compositions["essences"] = analyse.composition_comparee(
                z.composition(zones, foret, loc, codes_foret, ignorer_foret), fond_essences,
                analyse.valeurs_regle(e, "foret"))
            r.alertes += analyse.alertes_composition(r.compositions["essences"], "Essence",
                                                     r.n_localisees)
            if geol_ok:
                r.compositions["substrat"] = analyse.composition_comparee(
                    z.composition(zones, geol, loc, codes_geol, {0}), fond_substrat,
                    analyse.valeurs_regle(e, "geol"))
                r.alertes += analyse.alertes_composition(r.compositions["substrat"],
                                                         "Substrat", r.n_localisees)
        if not scores_meteo.empty and (scores_meteo["espece"] == i).any():
            r.meteo = scores_meteo[scores_meteo["espece"] == i]
            r.auc_m = analyse.evaluation_temporelle(r.meteo)
            n = int(r.meteo["observe"].sum())
            if n >= analyse.N_MIN and r.auc_m < analyse.AUC_FAIBLE:
                r.alertes.append(f"Météo : AUC temporelle {r.auc_m:.2f}, les jours observés ne "
                                 "sont pas nettement mieux notés que les autres jours.")
        resultats.append(r)
        sorties.append(rapport.ecrire(r, p.dossier_rapports / "calibration" / i, contexte))
    sorties.append(rapport.ecrire_index(resultats, p.dossier_rapports / "calibration", contexte))
    if avec_base:
        charger_base(p, obs, taxons, resultats)
    return sorties
