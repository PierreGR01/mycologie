"""Client Open-Meteo : séries journalières par lots de points, avec cache et débit maîtrisé."""

from __future__ import annotations

import json
import logging
import math
import time
from datetime import date
from pathlib import Path

import pandas as pd

from myco.config import ParamMeteo, Reseau
from myco.reseau import obtenir

log = logging.getLogger(__name__)

# Variables journalières demandées → nom court utilisé dans le projet.
VARIABLES = {
    "temperature_2m_min": "tmin",
    "temperature_2m_max": "tmax",
    "temperature_2m_mean": "tmoy",
    "precipitation_sum": "pluie",
}


def poids_requete(n_points: int, n_jours: int, n_variables: int = len(VARIABLES)) -> float:
    """Nombre d'« appels » décomptés par Open-Meteo : un appel par point jusqu'à 10 variables et
    14 jours, au prorata au-delà."""
    return n_points * max(1.0, n_variables / 10) * max(1.0, n_jours / 14)


def telecharger(points: pd.DataFrame, debut: date, fin: date, pm: ParamMeteo, reseau: Reseau,
                cache: Path) -> list[dict]:
    """Une réponse Open-Meteo par point, dans l'ordre de `points` (colonnes lon, lat).

    Chaque lot est mis en cache dans `cache/lot_NNN.json` : une reprise ne retélécharge que les
    lots manquants. Les requêtes sont espacées pour respecter `appels_par_minute`."""
    cache.mkdir(parents=True, exist_ok=True)
    n_jours = (fin - debut).days + 1
    reponses: list[dict] = []
    prochaine = 0.0
    for i, depart in enumerate(range(0, len(points), pm.taille_lot)):
        lot = points.iloc[depart:depart + pm.taille_lot]
        fichier = cache / f"lot_{i:03d}.json"
        if fichier.exists():
            donnees = json.loads(fichier.read_text())
        else:
            attente = prochaine - time.monotonic()
            if attente > 0:
                time.sleep(attente)
            params = {
                "latitude": ",".join(f"{v:.5f}" for v in lot["lat"]),
                "longitude": ",".join(f"{v:.5f}" for v in lot["lon"]),
                "daily": ",".join(VARIABLES),
                "timezone": pm.fuseau,
                "models": pm.modele,
                "start_date": debut.isoformat(),
                "end_date": fin.isoformat(),
            }
            donnees = obtenir(pm.url, reseau, params=params).json()
            donnees = donnees if isinstance(donnees, list) else [donnees]
            fichier.write_text(json.dumps(donnees))
            delai = 60 * poids_requete(len(lot), n_jours) / pm.appels_par_minute
            prochaine = time.monotonic() + delai
            log.info("Open-Meteo : lot %d, %d points", i, len(lot))
        if len(donnees) != len(lot):
            raise RuntimeError(f"lot {i} : {len(donnees)} réponses pour {len(lot)} points")
        reponses.extend(donnees)
    return reponses


def en_tableau(reponses: list[dict], points: pd.DataFrame) -> pd.DataFrame:
    """Tableau long : point_id, jour, tmin, tmax, tmoy, pluie, z_ref (altitude renvoyée)."""
    morceaux = []
    for pid, r in zip(points["id"], reponses, strict=True):
        quotidien = r["daily"]
        df = pd.DataFrame({court: quotidien[long] for long, court in VARIABLES.items()})
        df.insert(0, "jour", pd.to_datetime(quotidien["time"]).date)
        df.insert(0, "point_id", pid)
        df["z_ref"] = r["elevation"]
        morceaux.append(df)
    return pd.concat(morceaux, ignore_index=True)


def lots_estimes(n_points: int, pm: ParamMeteo) -> int:
    return math.ceil(n_points / pm.taille_lot)
