"""RGE ALTI 5 m : altitude moyenne à 25 m, puis pente et exposition."""

from __future__ import annotations

import logging
import re
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urljoin

import numpy as np
import py7zr
from rasterio.enums import Resampling
from rasterio.merge import merge

from myco import db
from myco.config import Parametres, Reseau
from myco.grid import Grille
from myco.ingest import grille_reference
from myco.rasters import ecrire_cog
from myco.reseau import obtenir, telecharger
from myco.terrain import NODATA_U8, pente_exposition

log = logging.getLogger(__name__)

ARCHIVE = re.compile(r"\.7z(\.\d{3})?$", re.IGNORECASE)
NODATA_ALT = -9999.0


# --- Téléchargement ------------------------------------------------------------------------------


def _liens(xml: str) -> list[tuple[str, str]]:
    """Couples (rel, href) des éléments <link> d'un flux Atom, quel que soit l'espace de noms."""
    return [
        (el.get("rel", ""), el.get("href", ""))
        for el in ET.fromstring(xml).iter()
        if el.tag.rsplit("}", 1)[-1] == "link" and el.get("href")
    ]


def trouver_archives(flux: str, motif: str, reseau: Reseau, profondeur: int = 2) -> list[str]:
    """Parcourt le flux Atom du service de téléchargement et renvoie les parties de l'archive la
    plus récente dont l'URL contient `motif`."""
    archives: set[str] = set()
    a_visiter, vus = [flux], set()
    for _ in range(profondeur + 1):
        suivants = []
        for page in a_visiter:
            while page and page not in vus:
                vus.add(page)
                suivante = None
                for rel, href in _liens(obtenir(page, reseau).text):
                    href = urljoin(page, href)
                    if rel == "next":
                        suivante = href
                    elif motif in href and ARCHIVE.search(href):
                        archives.add(href)
                    elif motif in href:
                        suivants.append(href)
                page = suivante
        if archives:
            break
        a_visiter = [u for u in suivants if u not in vus]
    if not archives:
        return []
    # Plusieurs éditions possibles : on garde la plus récente (date en fin de nom).
    editions = {ARCHIVE.sub("", a.rsplit("/", 1)[-1]) for a in archives}
    derniere = max(editions)
    return sorted(a for a in archives if a.rsplit("/", 1)[-1].startswith(derniere))


def telecharger_archives(p: Parametres) -> list[Path]:
    src = p.sources["rgealti"]
    dossier = p.dossier_brut / "rgealti"
    locales = sorted(f for f in dossier.glob("*") if ARCHIVE.search(f.name))
    if locales:
        return locales
    urls = [src.archive] if src.archive else trouver_archives(src.flux, src.motif, p.reseau)
    if not urls:
        raise RuntimeError(
            f"archive RGE ALTI introuvable dans {src.flux} (motif {src.motif}). Renseigner "
            "sources.rgealti.archive dans config/settings.yaml, ou déposer l'archive dans "
            f"{dossier}."
        )
    return [telecharger(u, dossier / u.rsplit("/", 1)[-1], p.reseau) for u in urls]


def extraire_dalles(archives: list[Path], dossier: Path, motif_dalles: str) -> list[Path]:
    """Extrait les dalles .asc du MNT. Une archive en plusieurs volumes (.7z.001, .7z.002…) est
    un simple découpage binaire : on la reconstitue par concaténation."""
    deja = sorted(dossier.rglob("*.asc")) if dossier.exists() else []
    if deja:
        return deja
    dossier.mkdir(parents=True, exist_ok=True)
    archive = archives[0]
    if len(archives) > 1:
        archive = dossier.parent / ARCHIVE.sub(".7z", archives[0].name)
        with archive.open("wb") as sortie:
            for partie in sorted(archives):
                with partie.open("rb") as entree:
                    shutil.copyfileobj(entree, sortie)
    regex = re.compile(motif_dalles, re.IGNORECASE)
    with py7zr.SevenZipFile(archive) as z:
        cibles = [n for n in z.getnames() if regex.search(n.rsplit("/", 1)[-1])]
        if not cibles:
            raise RuntimeError(f"aucune dalle ne correspond à {motif_dalles} dans {archive}")
        z.extract(path=dossier, targets=cibles)
    if len(archives) > 1:
        archive.unlink()
    return sorted(dossier.rglob("*.asc"))


# --- Traitement ----------------------------------------------------------------------------------


def agreger_mnt(dalles: list[Path], grille: Grille, nodata_source: float) -> np.ndarray:
    """Mosaïque les dalles et les agrège par moyenne sur la grille (5 × 5 pixels de 5 m par
    pixel de 25 m). Renvoie un tableau float32 avec NaN hors données."""
    # Le nodata de sortie est NaN : celui des dalles (-99999) est ignoré par la moyenne GDAL.
    tableau, transform = merge(
        [str(d) for d in dalles],
        bounds=grille.bornes,
        res=grille.resolution,
        nodata=np.nan,
        dtype="float32",
        resampling=Resampling.average,
    )
    if tableau.shape[1:] != grille.forme or not transform.almost_equals(grille.transform):
        raise RuntimeError("la mosaïque du MNT n'est pas alignée sur la grille de référence")
    alt = tableau[0]
    return np.where(alt == nodata_source, np.nan, alt).astype("float32")


def executer(p: Parametres, avec_base: bool = True) -> Path:
    src = p.sources["rgealti"]
    grille = grille_reference(p)
    archives = telecharger_archives(p)
    dalles = extraire_dalles(archives, p.dossier_brut / "rgealti" / "dalles", src.motif_dalles)
    log.info("%d dalles RGE ALTI", len(dalles))

    alt = agreger_mnt(dalles, grille, src.nodata)
    pente, expo = pente_exposition(alt, grille.resolution)
    s = p.dossier_statique
    ecrire_cog(s / "pente.tif", pente, grille, nodata=NODATA_U8, description="pente (degrés)")
    ecrire_cog(s / "expo.tif", expo, grille, nodata=NODATA_U8,
               description="exposition : 0 N … 7 NO, 8 plat")
    sortie = ecrire_cog(
        s / "alt.tif", np.nan_to_num(alt, nan=NODATA_ALT), grille, nodata=NODATA_ALT,
        reechantillonnage_apercus="AVERAGE", description="altitude (m)",
    )
    if avec_base:
        db.enregistrer_source(db.moteur(p.url_base), "rgealti", src, archives[0])
    return sortie
