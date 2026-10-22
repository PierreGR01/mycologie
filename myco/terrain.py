"""Pente et exposition à partir d'un MNT (méthode de Horn)."""

from __future__ import annotations

import numpy as np

NODATA_U8 = 255
# Secteurs d'exposition : 0 N, 1 NE, 2 E, 3 SE, 4 S, 5 SO, 6 O, 7 NO, 8 plat.
SECTEURS = ("N", "NE", "E", "SE", "S", "SO", "O", "NO", "plat")
PLAT = 8


def pente_exposition(
    altitude: np.ndarray, resolution: float, seuil_plat: float = 3.0
) -> tuple[np.ndarray, np.ndarray]:
    """Renvoie (pente en degrés, secteur d'exposition), en uint8, 255 = pas de donnée.

    `altitude` contient NaN là où le MNT n'a pas de valeur. Les lignes du tableau vont du nord au
    sud et les colonnes de l'ouest à l'est.
    """
    z = np.pad(altitude.astype("float32"), 1, mode="edge")
    a, b, c = z[:-2, :-2], z[:-2, 1:-1], z[:-2, 2:]
    d, f = z[1:-1, :-2], z[1:-1, 2:]
    g, h, i = z[2:, :-2], z[2:, 1:-1], z[2:, 2:]
    dz_est = ((c + 2 * f + i) - (a + 2 * d + g)) / (8 * resolution)
    dz_nord = ((a + 2 * b + c) - (g + 2 * h + i)) / (8 * resolution)

    pente = np.degrees(np.arctan(np.hypot(dz_est, dz_nord)))
    # L'exposition est la direction de plus grande descente, en azimut depuis le nord.
    azimut = np.degrees(np.arctan2(-dz_est, -dz_nord)) % 360
    secteur = np.floor((azimut + 22.5) / 45) % 8
    secteur = np.where(pente < seuil_plat, PLAT, secteur)

    invalide = np.isnan(pente) | np.isnan(altitude)
    pente_u8 = np.where(invalide, NODATA_U8, np.clip(np.rint(pente), 0, 90)).astype("uint8")
    secteur_u8 = np.where(invalide, NODATA_U8, secteur).astype("uint8")
    return pente_u8, secteur_u8
