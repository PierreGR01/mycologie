"""Score final S = H × M par espèce et par date (J-7 à J+7), tuiles PMTiles et manifeste."""

from __future__ import annotations

import json
import logging
import os
import shutil
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.warp import reproject, transform_bounds
from rasterio.windows import Window
from rasterio.windows import transform as transform_fenetre

from myco import regles
from myco.config import Parametres
from myco.especes import Espece, Gel, Meteo, Saison
from myco.grid import Grille
from myco.habitat import LIGNES_PAR_BLOC, NODATA_H
from myco.ingest import grille_reference
from myco.meteo import champs as mod_champs
from myco.meteo.indicateurs import INDICATEURS, agreger, fenetre
from myco.meteo.recuperation import dossier_meteo
from myco.rasters import ecrire_cog
from myco.tuiles import attribution, classer, ecrire_pmtiles, tuiler

log = logging.getLogger(__name__)

SOURCES_SCORE = ["bdforet", "bdcharm50", "soilgrids", "rgealti", "open_meteo"]
ANNEE_REF = 2001  # année non bissextile servant à numéroter les jours


def _jour_annee(mois: int, jour: int) -> int:
    return date(ANNEE_REF, mois, min(jour, 28) if mois == 2 else jour).timetuple().tm_yday


def facteur_saison(jour: date, s: Saison) -> float:
    debut = _jour_annee(*map(int, s.debut.split("-")))
    fin = _jour_annee(*map(int, s.fin.split("-")))
    longueur = (fin - debut) % 365
    x = (_jour_annee(jour.month, jour.day) - debut) % 365
    if x > longueur:
        return 0.0
    rampe = min(s.rampe_jours, longueur / 2)
    return float(regles.trapeze(np.array([x]), [0, rampe, longueur - rampe, longueur])[0])


def multiplicateur_gel(jours_de_gel: np.ndarray, gel: Gel) -> np.ndarray:
    m = np.ones(jours_de_gel.shape, dtype="float32")
    for seuil in sorted(gel.paliers):
        m[jours_de_gel >= seuil] = gel.paliers[seuil]
    return m


class Affineur:
    """Interpole les champs grossiers sur un bloc de lignes de la grille fine (spline cubique),
    en gardant en cache les champs déjà calculés pour le bloc."""

    def __init__(self, grossiere: Grille, grille: Grille, fenetre: Window):
        self.grossiere, self.grille, self.fenetre = grossiere, grille, fenetre
        self.cache: dict[str, np.ndarray] = {}

    def __call__(self, cle: str, champ: np.ndarray) -> np.ndarray:
        if cle not in self.cache:
            fin = np.empty((self.fenetre.height, self.fenetre.width), dtype="float32")
            reproject(
                champ.astype("float32"), fin,
                src_transform=self.grossiere.transform, src_crs=self.grossiere.crs,
                dst_transform=transform_fenetre(self.fenetre, self.grille.transform),
                dst_crs=self.grille.crs, resampling=Resampling.cubic_spline,
            )
            self.cache[cle] = fin
        return self.cache[cle]


def score_meteo(meteo: Meteo, jour: date, alt: np.ndarray, affiner: Affineur,
                champs: dict[str, np.ndarray], jours: list[date], gradient: float) -> np.ndarray:
    """M (0–1) sur un bloc : saison × moyenne géométrique des indicateurs × gel."""
    valeurs, poids = [], []
    for nom, ind in meteo.indicateurs.items():
        definition = INDICATEURS[nom]
        v = affiner(f"{nom}/{jour}", agreger(champs[definition.variable], jours, jour, definition))
        if definition.corrige_altitude:
            v = v - gradient * alt
        if definition.agregation == "somme":
            v = np.maximum(v, 0)
        valeurs.append(regles.trapeze(v, ind.points, ind.plancher, ind.plancher_haut))
        poids.append(ind.poids)
    m = regles.moyenne_geometrique(valeurs, poids) * facteur_saison(jour, meteo.saison)
    if meteo.gel:
        g = meteo.gel
        n = np.zeros(alt.shape, dtype="uint8")
        for d in fenetre(jour, g.fenetre_jours):
            # Tmin(x) = Tmin₀ − γ·z(x) < seuil  ⇔  z(x) > (Tmin₀ − seuil) / γ
            t0min = champs["t0min"][jours.index(d)]
            z_seuil = affiner(f"gel/{g.seuil_tmin}/{d}", (t0min - g.seuil_tmin) / gradient)
            n += alt > z_seuil
        m = m * multiplicateur_gel(n, g)
    return np.nan_to_num(m, nan=0.0)


def dates_affichees(run: date, p: Parametres) -> list[date]:
    return [run + timedelta(days=k) for k in range(-p.meteo.jours_avant, p.meteo.jours_apres + 1)]


def calculer_date(p: Parametres, especes: dict[str, Espece], jour: date,
                  habitats: dict[str, np.ndarray], alt: np.ndarray, grille: Grille,
                  grossiere: Grille, jours: list[date], champs: dict[str, np.ndarray]
                  ) -> dict[str, np.ndarray]:
    """S de chaque espèce pour une date, en uint8 (0–100, 255 hors département)."""
    sorties = {i: np.full(grille.forme, NODATA_H, dtype="uint8") for i in especes}
    for debut in range(0, grille.hauteur, LIGNES_PAR_BLOC):
        hauteur = min(LIGNES_PAR_BLOC, grille.hauteur - debut)
        affiner = Affineur(grossiere, grille, Window(0, debut, grille.largeur, hauteur))
        lignes = slice(debut, debut + hauteur)
        for i, e in especes.items():
            h = habitats[i][lignes]
            m = score_meteo(e.meteo, jour, alt[lignes], affiner, champs, jours,
                            p.meteo.gradient_c_par_m)
            s = np.rint(h.astype("float32") * m).astype("uint8")
            s[h == NODATA_H] = NODATA_H
            sorties[i][lignes] = s
    return sorties


def ecrire_manifeste(p: Parametres, especes: dict[str, Espece], run: date, dates: list[date],
                     recupere_le: date, grille: Grille) -> Path:
    racine_runs = f"runs/{run.isoformat()}"
    manifeste = {
        "run": run.isoformat(),
        "genere_le": datetime.now(UTC).isoformat(timespec="seconds"),
        "dates": [{"date": d.isoformat(), "type": "prevision" if d >= recupere_le else "analyse"}
                  for d in dates],
        "especes": [
            {"id": i, "nom": e.nom, "avertissement": e.avertissement,
             "habitat": f"habitat/{i}.pmtiles", "tuiles": f"{racine_runs}/{i}/{{date}}.pmtiles"}
            for i, e in especes.items()
        ],
        "legende": [{"min": c.min, "libelle": c.libelle, "couleur": c.couleur}
                    for c in p.affichage.classes],
        "zoom": {"min": p.affichage.zoom_min, "max": p.affichage.zoom_max},
        "emprise": list(transform_bounds(grille.crs, "EPSG:4326", *grille.bornes)),
        "sources": [
            {"nom": s.nom, "licence": s.licence, "attribution": s.attribution, "url": s.url}
            for s in p.sources.values()
        ],
    }
    chemin = p.dossier_publication / "latest.json"
    temporaire = chemin.with_name("latest.json.tmp")
    temporaire.write_text(json.dumps(manifeste, indent=2, ensure_ascii=False))
    os.replace(temporaire, chemin)
    return chemin


def purger(dossier: Path, garder: int, courant: str) -> None:
    """Supprime les runs les plus anciens (sous-dossiers AAAA-MM-JJ) au-delà de `garder`."""
    if not dossier.exists():
        return
    runs = sorted(d.name for d in dossier.iterdir() if d.is_dir())
    for nom in runs[:-garder]:
        if nom != courant:
            shutil.rmtree(dossier / nom)
            log.info("run purgé : %s/%s", dossier.name, nom)


def executer(p: Parametres, especes: dict[str, Espece], run: date,
             garder_rasters: bool = False) -> Path:
    grille = grille_reference(p)
    grossiere, jours, champs, meta = mod_champs.lire(dossier_meteo(p, run))
    recupere_le = date.fromisoformat(meta["recupere_le"])
    habitats = {}
    for i in especes:
        chemin = p.dossier_habitat / f"{i}.tif"
        if not chemin.exists():
            raise FileNotFoundError(f"{chemin} absent : lancer `myco habitat`")
        with rasterio.open(chemin) as src:
            habitats[i] = src.read(1)
    with rasterio.open(p.dossier_statique / "alt.tif") as src:
        alt = src.read(1).astype("float32")
        alt[alt == src.nodata] = np.nan

    dates = dates_affichees(run, p)
    publication = p.dossier_publication / "runs" / run.isoformat()
    attrib = attribution(p.sources, SOURCES_SCORE)
    for jour in dates:
        scores = calculer_date(p, especes, jour, habitats, alt, grille, grossiere, jours, champs)
        for i, s in scores.items():
            if garder_rasters:
                ecrire_cog(p.dossier_runs / run.isoformat() / "scores" / i / f"{jour}.tif",
                           s, grille, nodata=NODATA_H)
            ecrire_pmtiles(
                publication / i / f"{jour}.pmtiles",
                tuiler(classer(s, p.affichage), grille, p.affichage),
                grille, p.affichage,
                {"name": f"{especes[i].nom} – {jour}", "espece": i, "date": jour.isoformat(),
                 "run": run.isoformat(), "type": "score", "attribution": attrib},
            )
        log.info("%s : part du département en classe « bon » ou mieux : %s", jour,
                 {i: f"{100 * (s[s != NODATA_H] >= 60).mean():.1f} %" for i, s in scores.items()})
    manifeste = ecrire_manifeste(p, especes, run, dates, recupere_le, grille)
    purger(p.dossier_publication / "runs", p.meteo.retention_runs, run.isoformat())
    purger(p.dossier_runs, p.meteo.retention_runs, run.isoformat())
    return manifeste
