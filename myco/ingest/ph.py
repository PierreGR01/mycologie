"""SoilGrids : pH eau moyen sur 0–30 cm, interpolé sur la grille (indicateur secondaire)."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.vrt import WarpedVRT

from myco import db
from myco.config import Parametres
from myco.grid import Grille
from myco.ingest import grille_reference
from myco.rasters import ecrire_cog
from myco.reseau import ecrire_trace

log = logging.getLogger(__name__)

NODATA_PH = 0


def ph_pondere(sources: dict[str, float], grille: Grille) -> np.ndarray:
    """Moyenne pondérée de rasters de pH × 10 (une source par horizon, poids = épaisseur),
    rééchantillonnés en bilinéaire sur la grille. Renvoie du uint8 en pH × 10, 0 = pas de donnée."""
    somme = np.zeros(grille.forme, dtype="float32")
    poids = np.zeros(grille.forme, dtype="float32")
    for chemin, w in sources.items():
        with rasterio.open(chemin) as src, WarpedVRT(
            src,
            crs=grille.crs,
            transform=grille.transform,
            width=grille.largeur,
            height=grille.hauteur,
            resampling=Resampling.bilinear,
        ) as vrt:
            valeurs = vrt.read(1, masked=True)
        valide = ~np.ma.getmaskarray(valeurs) & (valeurs.filled(0) > 0)
        somme[valide] += w * valeurs.data[valide]
        poids[valide] += w
    ph10 = np.divide(somme, poids, out=np.zeros_like(somme), where=poids > 0)
    return np.where(poids > 0, np.clip(np.rint(ph10), 1, 140), NODATA_PH).astype("uint8")


def options_gdal() -> dict:
    """Accès HTTP de GDAL : reprises, et certificat du proxy éventuel."""
    options = {
        "GDAL_HTTP_MAX_RETRY": 4,
        "GDAL_HTTP_RETRY_DELAY": 2,
        "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
        "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".vrt,.tif",
    }
    ca = os.environ.get("CURL_CA_BUNDLE") or os.environ.get("SSL_CERT_FILE")
    if ca:
        options["CURL_CA_BUNDLE"] = ca
    return options


def executer(p: Parametres, avec_base: bool = True) -> Path:
    grille = grille_reference(p)
    src = p.sources["soilgrids"]
    urls = {src.vrt.format(profondeur=prof): float(ep) for prof, ep in src.profondeurs.items()}
    log.info("lecture SoilGrids : %s", ", ".join(urls))
    with rasterio.Env(**options_gdal()):
        ph = ph_pondere({f"/vsicurl/{u}": w for u, w in urls.items()}, grille)
    sortie = ecrire_cog(
        p.dossier_statique / "ph.tif", ph, grille, nodata=NODATA_PH,
        reechantillonnage_apercus="AVERAGE", description="pH eau × 10, moyenne 0–30 cm",
    )
    ecrire_trace(sortie, src.vrt, profondeurs=src.profondeurs)
    if avec_base:
        db.enregistrer_source(db.moteur(p.url_base), "soilgrids", src, sortie)
    return sortie
