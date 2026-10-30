"""Carte géologique : classes de substrat (calcaire, siliceux…) rastérisées sur la grille.

Sources essayées dans l'ordre de `geologie.sources` (settings.yaml) : BD Charm-50 (BRGM), puis
BD LISA v3 (BRGM / SANDRE) en repli. La source retenue est notée dans geol.tif.source.json.
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import box

from myco import db
from myco.config import Parametres, ReglesGeologie, charger_regles_geologie, racine
from myco.grid import Grille
from myco.ingest import colonne, grille_reference
from myco.rasters import ecrire_cog, rasteriser
from myco.reseau import ErreurReseau, ecrire_trace, telecharger

log = logging.getLogger(__name__)

COLONNES_CSV = ["notation", "classe", "classe_auto", "regle", "surface_ha", "n_polygones",
                "description"]


def chemin_csv(source: str = "bdcharm50") -> Path:
    """Table de relecture : geologie.csv (BD Charm-50), geologie_<source>.csv sinon."""
    nom = "geologie.csv" if source == "bdcharm50" else f"geologie_{source}.csv"
    return racine() / "config" / "classes" / nom


def source_utilisee(p: Parametres) -> str:
    """Source de geol.tif (lue dans sa trace) ; la première source configurée par défaut."""
    trace = p.dossier_statique / "geol.tif.source.json"
    if trace.exists():
        return json.loads(trace.read_text(encoding="utf-8")).get("source", p.geologie.sources[0])
    return p.geologie.sources[0]


def normaliser(texte: str | None) -> str:
    """Minuscules sans accents, espaces réduits."""
    if not texte or pd.isna(texte):
        return ""
    sans_accents = unicodedata.normalize("NFKD", str(texte)).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", sans_accents.lower()).strip()


def classer_unite(notation: str, texte: str, regles: ReglesGeologie) -> tuple[str, int | None]:
    """Classe d'une unité géologique et numéro (à partir de 1) de la règle appliquée."""
    notation, texte = normaliser(notation), normaliser(f"{notation} {texte}")
    for i, r in enumerate(regles.regles, start=1):
        if r.notation and re.search(r.notation, notation):
            return r.classe, i
        if r.texte and re.search(r.texte, texte):
            return r.classe, i
    return "indetermine", None


def unites(gdf: gpd.GeoDataFrame, champs: dict) -> pd.DataFrame:
    """Une ligne par notation, avec description, surface et classe automatique."""
    nom = {cle: colonne(gdf, champs.get(cle)) for cle in ("notation", "descr", "lithologie",
                                                         "geochimie")}
    if not nom["notation"]:
        raise RuntimeError(f"champ {champs.get('notation')} absent de la carte géologique")
    df = pd.DataFrame({
        cle: gdf[c].astype("string") if c else pd.Series(pd.NA, index=gdf.index, dtype="string")
        for cle, c in nom.items()
    })
    df["notation"] = df["notation"].fillna("").str.strip()
    df["surface_ha"] = gdf.geometry.area / 1e4
    return (
        df.groupby("notation", dropna=False)
        .agg(
            description=("descr", "first"),
            lithologie=("lithologie", "first"),
            geochimie=("geochimie", "first"),
            surface_ha=("surface_ha", "sum"),
            n_polygones=("surface_ha", "size"),
        )
        .reset_index()
    )


def classer_unites(df: pd.DataFrame, regles: ReglesGeologie) -> pd.DataFrame:
    df = df.copy()
    texte = (
        df["description"].fillna("") + " " + df["lithologie"].fillna("") + " "
        + df["geochimie"].fillna("")
    )
    resultats = [classer_unite(n, t, regles) for n, t in zip(df["notation"], texte, strict=True)]
    df["classe_auto"] = [c for c, _ in resultats]
    df["regle"] = [i for _, i in resultats]
    df["regle"] = df["regle"].astype("Int64")
    df["classe"] = df["classe_auto"]
    df["surface_ha"] = df["surface_ha"].round(1)
    return df.sort_values("surface_ha", ascending=False)[COLONNES_CSV].reset_index(drop=True)


def fusionner_corrections(nouveau: pd.DataFrame, existant: pd.DataFrame | None,
                          regles: ReglesGeologie) -> pd.DataFrame:
    """Reporte les corrections manuelles (classe ≠ classe_auto) d'un CSV déjà relu."""
    if existant is None or existant.empty:
        return nouveau
    corrige = existant[existant["classe"] != existant["classe_auto"]].set_index("notation")
    inconnues = set(corrige["classe"]) - regles.classes.keys()
    if inconnues:
        raise ValueError(f"classes inconnues dans geologie.csv : {sorted(inconnues)}")
    sortie = nouveau.copy()
    manuel = sortie["notation"].map(corrige["classe"])
    sortie["classe"] = manuel.fillna(sortie["classe"])
    if manuel.notna().any():
        log.info("%d corrections manuelles conservées", int(manuel.notna().sum()))
    return sortie


def lire_csv(chemin: Path) -> pd.DataFrame | None:
    if not chemin.exists():
        return None
    return pd.read_csv(chemin, dtype={"notation": "string"}, keep_default_na=False)


def charger_bdcharm50(p: Parametres, grille: Grille) -> tuple[gpd.GeoDataFrame, Path]:
    src = p.sources["bdcharm50"]
    dossier = p.dossier_brut / "bdcharm50"
    archive = telecharger(src.archive, dossier / src.archive.rsplit("/", 1)[-1], p.reseau)
    extrait = dossier / "extrait"
    if not extrait.exists():
        with zipfile.ZipFile(archive) as z:
            z.extractall(extrait)
    couches = sorted(extrait.rglob(src.couche_motif))
    if not couches:
        raise RuntimeError(f"aucune couche {src.couche_motif} dans {archive}")
    return gpd.read_file(couches[0]).to_crs(grille.crs), couches[0]


def charger_bdlisa(p: Parametres, grille: Grille) -> tuple[gpd.GeoDataFrame, Path]:
    """Entité affleurante (ordre relatif 1) de chaque polygone élémentaire, avec son libellé et
    ses lithologies (la dominante en premier)."""
    src = p.sources["bdlisa"]
    dossier = p.dossier_brut / "bdlisa"
    f = {cle: telecharger(f"{src.base}/{chemin}", dossier / chemin.rsplit("/", 1)[-1], p.reseau)
         for cle, chemin in src.fichiers.items()}
    poly = gpd.clip(gpd.read_file(f["polygones"], bbox=grille.bornes).to_crs(grille.crs),
                    box(*grille.bornes))
    piles = pd.read_csv(f["piles"], dtype="string")
    dessus = piles[piles["OrdRelatif"] == "1"][["CodePoly", "CodeEH"]]
    entites = pd.read_csv(f["entites"], dtype="string")[["CodeEH", "LibelleEH"]]
    litho = pd.read_csv(f["lithologie"], dtype="string")
    litho["secondaire"] = litho["LithoPrinc"].str.lower() != "vrai"
    litho = (litho.sort_values(["CodeEH", "secondaire"]).groupby("CodeEH")["LbLitho"]
             .agg(", ".join).rename("lithologie").reset_index())
    gdf = (poly.merge(dessus, on="CodePoly", how="left").merge(entites, on="CodeEH", how="left")
           .merge(litho, on="CodeEH", how="left"))
    return gdf, f["polygones"]


CHARGEURS = {"bdcharm50": charger_bdcharm50, "bdlisa": charger_bdlisa}


def charger(p: Parametres, grille: Grille) -> tuple[str, gpd.GeoDataFrame, Path]:
    """Première source de `geologie.sources` accessible."""
    for cle in p.geologie.sources:
        try:
            gdf, fichier = CHARGEURS[cle](p, grille)
        except ErreurReseau as exc:
            log.warning("carte géologique %s inaccessible (%s) : source suivante", cle, exc)
            continue
        log.info("carte géologique : %s", p.sources[cle].nom)
        return cle, gdf, fichier
    raise RuntimeError(f"aucune carte géologique accessible parmi {p.geologie.sources}")


def executer(p: Parametres, avec_base: bool = True) -> Path:
    grille = grille_reference(p)
    regles = charger_regles_geologie()
    cle, gdf, fichier = charger(p, grille)
    src = p.sources[cle]

    table = fusionner_corrections(
        classer_unites(unites(gdf, src.champs), regles), lire_csv(chemin_csv(cle)), regles
    )
    table.to_csv(chemin_csv(cle), index=False)
    log.info("classes de substrat (ha) : %s",
             table.groupby("classe")["surface_ha"].sum().round().to_dict())

    nom_notation = colonne(gdf, src.champs["notation"])
    classe = gdf[nom_notation].astype("string").fillna("").str.strip().map(
        dict(zip(table["notation"], table["classe"], strict=True))
    )
    codes = classe.map(regles.classes).fillna(regles.classes["indetermine"])
    sortie = ecrire_cog(
        p.dossier_statique / "geol.tif", rasteriser(gdf.geometry, codes, grille), grille,
        description="classe de substrat (config/classes/geologie_regles.yaml)",
    )
    ecrire_trace(sortie, src.url, source=cle, table=chemin_csv(cle).name)
    if avec_base:
        eng = db.moteur(p.url_base)
        descr = colonne(gdf, src.champs.get("descr"))
        litho = colonne(gdf, src.champs.get("lithologie"))
        couche_db = gpd.GeoDataFrame(
            {
                "notation": gdf[nom_notation],
                "descr": gdf[descr] if descr else None,
                "lithologie": gdf[litho] if litho else None,
                "classe": classe,
            },
            geometry=gdf.geometry,
            crs=p.grille.crs,
        )
        db.remplacer_table(eng, couche_db, "ref", "geologie")
        db.enregistrer_source(eng, cle, src, fichier)
    return sortie
