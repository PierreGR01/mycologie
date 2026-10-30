"""Étape 3 : score d'habitat H (0–1) par espèce sur la grille de 25 m, à partir des YAML."""

from __future__ import annotations

import logging
from contextlib import ExitStack
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from PIL import Image
from rasterio.windows import Window

from myco import regles
from myco.config import Parametres, charger_classes_foret, charger_regles_geologie
from myco.especes import Espece, FacteurTable, Habitat
from myco.ingest import grille_reference
from myco.ingest.geologie import source_utilisee
from myco.rasters import ecrire_cog
from myco.terrain import NODATA_U8, SECTEURS
from myco.tuiles import attribution, classer, ecrire_pmtiles, palette, tuiler

log = logging.getLogger(__name__)

NODATA_H = 255  # H est stocké en uint8 de 0 à 100 ; 255 = hors département
LIGNES_PAR_BLOC = 512


def sources_habitat(p: Parametres) -> list[str]:
    return ["bdforet", source_utilisee(p), "soilgrids", "rgealti"]


# Codage des couches catégorielles : code → clé du vocabulaire, et code « pas de donnée ».
NODATA_CATEGORIEL = {"foret": None, "geol": 0, "expo": NODATA_U8}


def codes_categoriels() -> dict[str, dict[int, str]]:
    return {
        "foret": {c.code: cle for cle, c in charger_classes_foret().classes.items()},
        "geol": {code: cle for cle, code in charger_regles_geologie().classes.items()},
        "expo": dict(enumerate(SECTEURS)),
    }


def decoder_continue(couche: str, brut: np.ndarray, nodata: float | None) -> np.ndarray:
    """Valeurs physiques en float32, NaN là où la couche n'a pas de donnée."""
    v = brut.astype("float32")
    if nodata is not None:
        v[brut == nodata] = np.nan
    return v / 10 if couche == "ph" else v  # ph.tif est en pH × 10


def evaluer(habitat: Habitat, couches: dict[str, np.ndarray],
            codes: dict[str, dict[int, str]]) -> np.ndarray:
    """H en float32 (0–1). Couches catégorielles : codes entiers ; continues : valeurs physiques
    avec NaN. Un facteur sans donnée est écarté de la moyenne ; un facteur `bloquant` nul ou sans
    donnée annule H. Avec plusieurs profils, H est le maximum des profils."""
    scores = []
    for profil in habitat.liste_profils().values():
        valeurs, poids = [], []
        bloque = None
        for f in profil.facteurs.values():
            if isinstance(f, FacteurTable):
                v = regles.table(couches[f.couche], codes[f.couche], f.valeurs, f.defaut,
                                 nodata=NODATA_CATEGORIEL[f.couche])
            else:
                v = regles.trapeze(couches[f.couche], f.points, f.plancher, f.plancher_haut)
            if f.bloquant:
                nul = np.isnan(v) | (v == 0)
                bloque = nul if bloque is None else bloque | nul
            valeurs.append(v)
            poids.append(f.poids)
        h = regles.moyenne_geometrique(valeurs, poids)
        if bloque is not None:
            h[bloque] = 0
        scores.append(h)
    return np.fmax.reduce(scores) if len(scores) > 1 else scores[0]


def couches_utilisees(especes: dict[str, Espece]) -> set[str]:
    return {f.couche for e in especes.values() for pr in e.habitat.liste_profils().values()
            for f in pr.facteurs.values()}


def calculer(p: Parametres, especes: dict[str, Espece]) -> dict[str, np.ndarray]:
    """H de chaque espèce en uint8 (0–100, 255 hors département), calculé par blocs de lignes."""
    grille = grille_reference(p)
    couches = sorted(couches_utilisees(especes))
    manquantes = [c for c in couches if not (p.dossier_statique / f"{c}.tif").exists()]
    if manquantes:
        raise FileNotFoundError(f"couches statiques absentes : {manquantes} (`make ingest`)")
    codes = codes_categoriels()
    sorties = {i: np.full(grille.forme, NODATA_H, dtype="uint8") for i in especes}
    with ExitStack() as pile:
        sources = {c: pile.enter_context(rasterio.open(p.dossier_statique / f"{c}.tif"))
                   for c in [*couches, "masque"]}
        for debut in range(0, grille.hauteur, LIGNES_PAR_BLOC):
            fenetre = Window(0, debut, grille.largeur, min(LIGNES_PAR_BLOC, grille.hauteur - debut))
            dedans = sources["masque"].read(1, window=fenetre).astype(bool)
            bloc = {}
            for c in couches:
                brut = sources[c].read(1, window=fenetre)
                bloc[c] = (brut if c in NODATA_CATEGORIEL
                           else decoder_continue(c, brut, sources[c].nodata))
            for i, e in especes.items():
                h = evaluer(e.habitat, bloc, codes)
                h8 = np.where(np.isnan(h), 0, np.rint(h * 100)).astype("uint8")
                h8[~dedans] = NODATA_H
                sorties[i][debut:debut + fenetre.height] = h8
    return sorties


def resume(scores: dict[str, np.ndarray], p: Parametres) -> pd.DataFrame:
    """Part de la surface du département dans chaque classe d'affichage, par espèce."""
    lignes = []
    for i, h in scores.items():
        dedans = h != NODATA_H
        classes = classer(h[dedans], p.affichage)
        n = dedans.sum()
        ligne = {"espece": i, "H_nul_%": round(100 * (classes == 0).sum() / n, 1)}
        for k, c in enumerate(p.affichage.classes, start=1):
            ligne[f"{c.libelle}_%"] = round(100 * (classes == k).sum() / n, 2)
        ligne["H_moyen_hors_zeros"] = round(float(h[dedans & (h > 0)].mean()) / 100, 3)
        lignes.append(ligne)
    return pd.DataFrame(lignes)


def apercu(h: np.ndarray, alt: np.ndarray, p: Parametres, facteur: int = 4) -> Image.Image:
    """Image de contrôle à 100 m : estompage du relief et classes de H (moyenne des pixels non
    nuls de chaque bloc)."""
    hh, ww = (s // facteur * facteur for s in h.shape)

    def blocs(a):
        return a[:hh, :ww].reshape(hh // facteur, facteur, ww // facteur, facteur)

    hb = blocs(h).astype("float32")
    nonnul = (hb > 0) & (hb != NODATA_H)
    somme = np.where(nonnul, hb, 0).sum(axis=(1, 3))
    n = nonnul.sum(axis=(1, 3))
    h_bloc = np.where(n > 0, np.rint(somme / np.maximum(n, 1)), 0).astype("uint8")
    dehors = (blocs(h) == NODATA_H).all(axis=(1, 3))

    z = blocs(np.where(alt < -1000, np.nan, alt)).mean(axis=(1, 3))
    dy, dx = np.gradient(np.nan_to_num(z, nan=0.0), 25.0 * facteur)
    pente, azimut = np.arctan(np.hypot(dx, dy)), np.arctan2(-dx, dy)
    ombre = np.sin(np.radians(45)) * np.cos(pente) + np.cos(np.radians(45)) * np.sin(pente) * \
        np.cos(np.radians(315) - azimut)
    fond = (180 + 75 * np.clip(ombre, 0, 1)).astype("uint8")

    rgb = np.repeat(fond[..., None], 3, axis=2)
    pal = np.array(palette(p.affichage), dtype="uint8").reshape(256, 3)
    cl = classer(h_bloc, p.affichage)
    couleur = cl > 0
    rgb[couleur] = (0.25 * rgb[couleur] + 0.75 * pal[cl[couleur]]).astype("uint8")
    rgb[dehors] = 255
    return Image.fromarray(rgb, mode="RGB")


def executer(p: Parametres, especes: dict[str, Espece], tuiles: bool = True) -> list[Path]:
    grille = grille_reference(p)
    scores = calculer(p, especes)
    sorties = []
    rapports = p.dossier_rapports / "habitat"
    rapports.mkdir(parents=True, exist_ok=True)
    with rasterio.open(p.dossier_statique / "alt.tif") as src:
        alt = src.read(1)
    for i, h in scores.items():
        sorties.append(ecrire_cog(p.dossier_habitat / f"{i}.tif", h, grille, nodata=NODATA_H,
                                  description=f"habitat {i} (0–100)"))
        apercu(h, alt, p).save(rapports / f"{i}.png", optimize=True)
        if tuiles:
            sorties.append(ecrire_pmtiles(
                p.dossier_publication / "habitat" / f"{i}.pmtiles",
                tuiler(classer(h, p.affichage), grille, p.affichage), grille, p.affichage,
                {"name": f"Habitat – {especes[i].nom}", "espece": i, "type": "habitat",
                 "attribution": attribution(p.sources, sources_habitat(p))},
            ))
    tableau = resume(scores, p)
    tableau.to_csv(rapports / "resume.csv", index=False)
    log.info("résumé habitat :\n%s", tableau.to_string(index=False))
    return sorties
