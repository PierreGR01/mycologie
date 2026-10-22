"""Étape 2 : ingestion des couches statiques sur la grille de référence de 25 m."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from myco.config import Parametres
from myco.grid import Grille


def chemin_masque(p: Parametres) -> Path:
    return p.dossier_statique / "masque.tif"


def grille_reference(p: Parametres) -> Grille:
    """La grille de référence est celle de masque.tif, produit par `myco ingest limite`."""
    masque = chemin_masque(p)
    if not masque.exists():
        raise FileNotFoundError(f"{masque} absent : lancer d'abord `myco ingest limite`")
    return Grille.depuis_raster(masque)


def colonne(df: pd.DataFrame, nom: str | None) -> str | None:
    """Nom réel d'une colonne, sans tenir compte de la casse (None si absente)."""
    if not nom:
        return None
    for c in df.columns:
        if c.lower() == nom.lower():
            return c
    return None
