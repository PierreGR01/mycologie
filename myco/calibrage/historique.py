"""Météo historique (Open-Meteo Historical API) aux observations, regroupées par cellule."""

from __future__ import annotations

import json
import logging
import math
import time
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from myco.config import Parametres
from myco.especes import Espece
from myco.meteo.indicateurs import FENETRE_MAX
from myco.meteo.openmeteo import VARIABLES, poids_requete
from myco.reseau import obtenir

log = logging.getLogger(__name__)
TAILLE_LOT = 50


def cellule(lon: float, lat: float, pas: float) -> tuple[float, float]:
    """Centre de la cellule de `pas` degrés contenant le point."""
    return (round(math.floor(lon / pas) * pas + pas / 2, 4),
            round(math.floor(lat / pas) * pas + pas / 2, 4))


def periode(jour: date, espece: Espece) -> tuple[date, date]:
    """Jours nécessaires pour noter toute la saison de l'année d'observation (et le jour observé),
    fenêtres glissantes comprises."""
    s = espece.meteo.saison
    debut = date(jour.year, *map(int, s.debut.split("-")))
    fin = date(jour.year, *map(int, s.fin.split("-")))
    if fin < debut:  # saison à cheval sur le 1er janvier : toute l'année
        debut, fin = date(jour.year, 1, 1), date(jour.year, 12, 31)
    debut = min(debut, jour) - timedelta(days=FENETRE_MAX - 1)
    return debut, max(fin, jour)


def groupes(obs: pd.DataFrame, especes: dict[str, Espece], pas: float) -> pd.DataFrame:
    """Une ligne par (cellule, année) avec la période à télécharger."""
    lignes = []
    for o in obs.itertuples():
        lon, lat = cellule(o.lon, o.lat, pas)
        debut, fin = periode(o.date_obs, especes[o.espece])
        lignes.append({"lon": lon, "lat": lat, "annee": o.date_obs.year, "debut": debut,
                       "fin": fin})
    df = pd.DataFrame(lignes)
    return df.groupby(["lon", "lat", "annee"], as_index=False).agg(debut=("debut", "min"),
                                                                    fin=("fin", "max"))


def _cle(g) -> str:
    return f"{g.lon:.4f}_{g.lat:.4f}_{g.debut}_{g.fin}"


def telecharger(grp: pd.DataFrame, p: Parametres, cache: Path) -> dict[tuple, pd.DataFrame]:
    """Séries journalières (tmin, tmax, tmoy, pluie, z_ref) par (lon, lat, année). Les groupes
    de même période partagent une requête ; chaque réponse est mise en cache."""
    pc = p.calibrage
    cache.mkdir(parents=True, exist_ok=True)
    manquants = [g for g in grp.itertuples() if not (cache / f"{_cle(g)}.json").exists()]
    poids = sum(poids_requete(1, (g.fin - g.debut).days + 1) for g in manquants)
    if manquants:
        log.info("météo historique : %d séries à télécharger, ≈ %.0f appels, ≈ %.0f min",
                 len(manquants), poids, poids / pc.appels_par_minute)
    prochaine = 0.0
    par_periode: dict[tuple, list] = {}
    for g in manquants:
        par_periode.setdefault((g.debut, g.fin), []).append(g)
    for (debut, fin), liste in par_periode.items():
        for i in range(0, len(liste), TAILLE_LOT):
            lot = liste[i:i + TAILLE_LOT]
            attente = prochaine - time.monotonic()
            if attente > 0:
                time.sleep(attente)
            reponse = obtenir(pc.archive, p.reseau, params={
                "latitude": ",".join(f"{g.lat:.4f}" for g in lot),
                "longitude": ",".join(f"{g.lon:.4f}" for g in lot),
                "daily": ",".join(VARIABLES),
                "timezone": p.meteo.fuseau,
                "models": pc.modele_historique,
                "start_date": debut.isoformat(),
                "end_date": fin.isoformat(),
            }).json()
            reponse = reponse if isinstance(reponse, list) else [reponse]
            for g, r in zip(lot, reponse, strict=True):
                (cache / f"{_cle(g)}.json").write_text(json.dumps(r))
            prochaine = time.monotonic() + 60 * poids_requete(len(lot), (fin - debut).days + 1) \
                / pc.appels_par_minute
    series = {}
    for g in grp.itertuples():
        r = json.loads((cache / f"{_cle(g)}.json").read_text())
        q = r["daily"]
        df = pd.DataFrame({court: q[long] for long, court in VARIABLES.items()},
                          index=pd.to_datetime(q["time"]).date, dtype="float32")
        df.attrs["z_ref"] = r["elevation"]
        series[(g.lon, g.lat, g.annee)] = df
    return series


def a_l_altitude(serie: pd.DataFrame, z: float, gradient: float) -> pd.DataFrame:
    """Températures ramenées de l'altitude de la série à l'altitude z (−γ par mètre)."""
    dt = gradient * (serie.attrs["z_ref"] - z)
    s = serie.copy()
    for c in ("tmin", "tmax", "tmoy"):
        s[c] = s[c] + dt
    return s


def altitude_mediane(valeurs_alt: np.ndarray, en_foret: np.ndarray) -> float:
    """Altitude médiane des pixels forestiers du cercle (de tous les pixels s'il n'y en a pas)."""
    valides = valeurs_alt > -1000
    foret = valides & en_foret
    choix = valeurs_alt[foret] if foret.any() else valeurs_alt[valides]
    return float(np.median(choix)) if choix.size else np.nan
