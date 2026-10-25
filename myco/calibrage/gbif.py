"""Observations GBIF : résolution des taxons et téléchargement par l'API de recherche."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from pathlib import Path

import geopandas as gpd
import pandas as pd

from myco.config import ParamCalibrage, Reseau
from myco.reseau import obtenir

log = logging.getLogger(__name__)

TAILLE_PAGE = 300  # maximum de l'API de recherche
SEUIL_DECOUPAGE = 6000
LIBELLES_LICENCES = {"CC0_1_0": "CC0", "CC_BY_4_0": "CC BY", "CC_BY_NC_4_0": "CC BY-NC"}
CHAMPS = ["gbifID", "taxonKey", "scientificName", "eventDate", "year", "month", "day",
          "decimalLatitude", "decimalLongitude", "coordinateUncertaintyInMeters", "license",
          "datasetKey", "basisOfRecord"]


def resoudre_taxon(nom: str, pc: ParamCalibrage, reseau: Reseau) -> dict:
    """Clé GBIF d'un nom scientifique (règne Fungi). Un synonyme renvoie au taxon accepté."""
    r = obtenir(f"{pc.gbif}/species/match", reseau,
                params={"name": nom, "kingdom": "Fungi", "strict": "true"}).json()
    if r.get("matchType") in (None, "NONE") or "usageKey" not in r:
        raise ValueError(f"taxon introuvable dans GBIF : {nom}")
    cle = r.get("acceptedUsageKey") or r["usageKey"]
    return {"nom_scientifique": nom, "gbif_key": cle, "rang": r.get("rank"),
            "statut": r.get("status"), "nom_gbif": r.get("scientificName")}


def parametres_recherche(pc: ParamCalibrage, emprise: tuple[float, float, float, float],
                         incertitude_max: float | None) -> dict:
    ouest, sud, est, nord = emprise
    params = {
        "hasCoordinate": "true",
        "hasGeospatialIssue": "false",
        "occurrenceStatus": "PRESENT",
        "decimalLatitude": f"{sud:.4f},{nord:.4f}",
        "decimalLongitude": f"{ouest:.4f},{est:.4f}",
        "year": f"{pc.annee_min},{datetime.now(UTC).year}",
        "license": pc.licences,
    }
    if incertitude_max is not None:
        params["coordinateUncertaintyInMeters"] = f"0,{incertitude_max:.0f}"
    return params


def _pages(url: str, params: dict, reseau: Reseau) -> list[dict]:
    lignes, decalage = [], 0
    while True:
        page = obtenir(url, reseau, params={**params, "limit": TAILLE_PAGE,
                                            "offset": decalage}).json()
        lignes += [{c: r.get(c) for c in CHAMPS} for r in page["results"]]
        decalage += TAILLE_PAGE
        if page["endOfRecords"] or decalage >= 100_000:
            return lignes


def empreinte(params: dict) -> str:
    """Empreinte courte des paramètres de requête : un changement de filtre (licences, années…)
    donne un autre fichier de cache."""
    return hashlib.sha1(json.dumps(params, sort_keys=True).encode()).hexdigest()[:8]


def _compte(url: str, params: dict, reseau: Reseau) -> int:
    return obtenir(url, reseau, params={**params, "limit": 0}).json()["count"]


def telecharger(cle: int, params: dict, pc: ParamCalibrage, reseau: Reseau,
                cache: Path) -> pd.DataFrame:
    """Toutes les occurrences d'un taxon (descendants compris), mises en cache en CSV.

    La pagination profonde de l'API de recherche est très lente (plus de 2 min par page au-delà
    de 30 000 résultats) : la requête est découpée par année, et par mois au-delà de
    `SEUIL_DECOUPAGE` résultats. Chaque tranche est mise en cache, ce qui rend le téléchargement
    reprenable."""
    if cache.exists():
        return pd.read_csv(cache, dtype={"gbifID": "string", "datasetKey": "string"})
    url = f"{pc.gbif}/occurrence/search"
    tranches = cache.with_suffix("")
    tranches.mkdir(parents=True, exist_ok=True)
    debut, fin = (int(a) for a in params["year"].split(","))
    for annee in range(debut, fin + 1):
        fichier = tranches / f"{annee}.csv"
        if fichier.exists():
            continue
        p = {**params, "taxonKey": cle, "year": str(annee)}
        if _compte(url, p, reseau) > SEUIL_DECOUPAGE:
            lignes = [ligne for mois in range(1, 13)
                      for ligne in _pages(url, {**p, "month": str(mois)}, reseau)]
        else:
            lignes = _pages(url, p, reseau)
        pd.DataFrame(lignes, columns=CHAMPS).to_csv(fichier, index=False)
        log.info("GBIF taxon %s, %d : %d occurrences", cle, annee, len(lignes))
    df = pd.concat([pd.read_csv(f, dtype={"gbifID": "string", "datasetKey": "string"})
                    for f in sorted(tranches.glob("*.csv"))], ignore_index=True)
    df.to_csv(cache, index=False)
    cache.with_suffix(".requete.json").write_text(json.dumps(
        {"url": f"{pc.gbif}/occurrence/search", "taxonKey": cle, **params,
         "date": datetime.now(UTC).isoformat(timespec="seconds")}, indent=2))
    return df


def en_observations(df: pd.DataFrame, espece: str, limite: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Occurrences situées dans le département, en Lambert-93, au format de obs.observation."""
    jour = pd.to_datetime(df["eventDate"].astype("string").str[:10], errors="coerce",
                          format="%Y-%m-%d")
    obs = gpd.GeoDataFrame(
        {
            "source": "gbif",
            "source_id": df["gbifID"].astype("string"),
            "espece": espece,
            "nom_scientifique": df["scientificName"],
            # Une date n'est retenue que si le jour est connu (pas un intervalle).
            "date_obs": jour.where(df["day"].notna()).dt.date,
            "incertitude_m": pd.to_numeric(df["coordinateUncertaintyInMeters"], errors="coerce"),
            "licence": df["license"],
            "jeu_donnees": df["datasetKey"],
        },
        geometry=gpd.points_from_xy(df["decimalLongitude"], df["decimalLatitude"]),
        crs="EPSG:4326",
    ).to_crs(limite.crs)
    dedans = obs.within(limite.union_all())
    return obs[dedans].drop_duplicates("source_id").reset_index(drop=True)
