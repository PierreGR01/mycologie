"""Tuiles raster PNG (EPSG:3857) empaquetées en PMTiles, pour la PWA (hébergement statique)."""

from __future__ import annotations

import io
import math
import os
from pathlib import Path

import numpy as np
from PIL import Image
from pmtiles.reader import MmapSource, Reader
from pmtiles.tile import Compression, TileType, zxy_to_tileid
from pmtiles.writer import Writer
from rasterio.crs import CRS
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.warp import reproject, transform_bounds

from myco.config import Affichage
from myco.grid import Grille

TAILLE = 256
ORIGINE = math.pi * 6378137.0  # demi-circonférence terrestre en Web Mercator (m)
WEB_MERCATOR = CRS.from_epsg(3857)
TRANSPARENT = 0


def classer(score: np.ndarray, affichage: Affichage, nodata: int = 255) -> np.ndarray:
    """Score uint8 0–100 → indice de classe d'affichage (1…n), 0 = transparent (score nul ou
    pas de donnée)."""
    bornes = np.array([c.min * 100 for c in affichage.classes])
    correspondance = np.searchsorted(bornes, np.arange(256), side="right").astype("uint8")
    correspondance[[0, nodata]] = TRANSPARENT
    return correspondance[score]


def palette(affichage: Affichage) -> list[int]:
    couleurs = [(0, 0, 0)] + [
        tuple(int(c.couleur[i:i + 2], 16) for i in (1, 3, 5)) for c in affichage.classes
    ]
    return [v for rgb in couleurs for v in rgb] + [0] * (3 * (256 - len(couleurs)))


def _png(tuile: np.ndarray, pal: list[int]) -> bytes:
    image = Image.fromarray(tuile, mode="P")
    image.putpalette(pal)
    tampon = io.BytesIO()
    image.save(tampon, format="PNG", compress_level=6, transparency=TRANSPARENT)
    return tampon.getvalue()


def _tuiles_couvrant(bornes: tuple[float, float, float, float], z: int):
    cote = 2 * ORIGINE / 2**z
    x0 = int((bornes[0] + ORIGINE) // cote)
    x1 = int((bornes[2] + ORIGINE) // cote)
    y0 = int((ORIGINE - bornes[3]) // cote)
    y1 = int((ORIGINE - bornes[1]) // cote)
    return cote, range(x0, x1 + 1), range(y0, y1 + 1)


def tuiler(classes: np.ndarray, grille: Grille, affichage: Affichage) -> list[tuple[int, bytes]]:
    """Tuiles non vides (tileid, PNG) de zoom_min à zoom_max, triées par tileid.

    Au zoom maximal, le rééchantillonnage est au plus proche voisin ; aux zooms inférieurs, la
    classe majoritaire des pixels non transparents est retenue."""
    bornes = transform_bounds(grille.crs, WEB_MERCATOR, *grille.bornes)
    pal = palette(affichage)
    tuiles = []
    for z in range(affichage.zoom_min, affichage.zoom_max + 1):
        cote, xs, ys = _tuiles_couvrant(bornes, z)
        mosaique = np.zeros((len(ys) * TAILLE, len(xs) * TAILLE), dtype="uint8")
        reproject(
            classes,
            mosaique,
            src_transform=grille.transform,
            src_crs=grille.crs,
            src_nodata=TRANSPARENT,
            dst_transform=from_origin(-ORIGINE + xs[0] * cote, ORIGINE - ys[0] * cote,
                                      cote / TAILLE, cote / TAILLE),
            dst_crs=WEB_MERCATOR,
            dst_nodata=TRANSPARENT,
            resampling=Resampling.nearest if z == affichage.zoom_max else Resampling.mode,
        )
        for j, y in enumerate(ys):
            for i, x in enumerate(xs):
                tuile = mosaique[j * TAILLE:(j + 1) * TAILLE, i * TAILLE:(i + 1) * TAILLE]
                if tuile.any():
                    tuiles.append((zxy_to_tileid(z, x, y), _png(tuile, pal)))
    return sorted(tuiles)


def tuiles_transparentes(grille: Grille, affichage: Affichage,
                         presentes: set[int]) -> list[tuple[int, bytes]]:
    """Tuiles vides au zoom minimal, là où l'emprise n'en a pas : MapLibre ne termine pas le
    chargement d'une source PMTiles dont une tuile manque au zoom minimal."""
    bornes = transform_bounds(grille.crs, WEB_MERCATOR, *grille.bornes)
    _, xs, ys = _tuiles_couvrant(bornes, affichage.zoom_min)
    vide = _png(np.zeros((TAILLE, TAILLE), dtype="uint8"), palette(affichage))
    ids = (zxy_to_tileid(affichage.zoom_min, x, y) for x in xs for y in ys)
    return [(i, vide) for i in ids if i not in presentes]


def ecrire_pmtiles(
    chemin: Path,
    tuiles: list[tuple[int, bytes]],
    grille: Grille,
    affichage: Affichage,
    metadonnees: dict,
) -> Path:
    # Jour sans pixel favorable (hors saison…) ou peu favorable : zoom minimal complété.
    tuiles = sorted(tuiles + tuiles_transparentes(grille, affichage, {i for i, _ in tuiles}))
    ouest, sud, est, nord = transform_bounds(grille.crs, "EPSG:4326", *grille.bornes)
    entete = {
        "tile_type": TileType.PNG,
        "tile_compression": Compression.NONE,
        "min_lon_e7": int(ouest * 1e7),
        "min_lat_e7": int(sud * 1e7),
        "max_lon_e7": int(est * 1e7),
        "max_lat_e7": int(nord * 1e7),
        "center_zoom": affichage.zoom_min + 1,
        "center_lon_e7": int((ouest + est) / 2 * 1e7),
        "center_lat_e7": int((sud + nord) / 2 * 1e7),
    }
    legende = [{"min": c.min, "libelle": c.libelle, "couleur": c.couleur}
               for c in affichage.classes]
    chemin.parent.mkdir(parents=True, exist_ok=True)
    temporaire = chemin.with_name(chemin.name + ".tmp")
    with temporaire.open("wb") as f:
        writer = Writer(f)
        for tileid, donnees in tuiles:
            writer.write_tile(tileid, donnees)
        writer.finalize(entete, {**metadonnees, "legende": legende})
    os.replace(temporaire, chemin)
    return chemin


def attribution(sources: dict, cles: list[str]) -> str:
    return " · ".join(sources[c].attribution for c in cles)


def lire_pmtiles(chemin: Path) -> tuple[dict, dict]:
    """(en-tête, métadonnées) d'un fichier PMTiles."""
    with chemin.open("rb") as f:
        lecteur = Reader(MmapSource(f))
        return lecteur.header(), lecteur.metadata()
