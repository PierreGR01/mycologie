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
import numpy as np
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


def cle_unites(df: pd.DataFrame) -> pd.Series:
    """Clé d'une unité géologique : sa notation, précédée du département pour une carte livrée par
    département (BD Charm-50), où une même notation peut désigner deux formations différentes."""
    if "departement" in df:
        return df["departement"].astype("string") + ":" + df["notation"].astype("string")
    return df["notation"].astype("string")


def chemin_csv(source: str = "bdcharm50") -> Path:
    """Table de relecture : geologie.csv (BD Charm-50), geologie_<source>.csv sinon."""
    nom = "geologie.csv" if source == "bdcharm50" else f"geologie_{source}.csv"
    return racine() / "config" / "classes" / nom


def sources_utilisees(p: Parametres) -> list[str]:
    """Sources de geol.tif (lues dans sa trace) : la carte principale, puis celle de la roche
    sous-jacente des formations superficielles si elle a servi. Par défaut, la première source
    configurée."""
    trace = p.dossier_statique / "geol.tif.source.json"
    if not trace.exists():
        return [p.geologie.sources[0]]
    t = json.loads(trace.read_text(encoding="utf-8"))
    couverture = [t["couverture"]] if t.get("couverture") else []
    return [t.get("source", p.geologie.sources[0]), *couverture]


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
    groupes = ["notation"]
    if "departement" in gdf:
        df["departement"] = gdf["departement"].astype("string")
        groupes = ["departement", "notation"]
    return (
        df.groupby(groupes, dropna=False)
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
    colonnes = (["departement"] if "departement" in df else []) + COLONNES_CSV
    return df.sort_values("surface_ha", ascending=False)[colonnes].reset_index(drop=True)


def fusionner_corrections(nouveau: pd.DataFrame, existant: pd.DataFrame | None,
                          regles: ReglesGeologie) -> pd.DataFrame:
    """Reporte les corrections manuelles (classe ≠ classe_auto) d'un CSV déjà relu."""
    if existant is None or existant.empty:
        return nouveau
    corrige = existant[existant["classe"] != existant["classe_auto"]]
    corrige = corrige.set_index(cle_unites(corrige))
    inconnues = set(corrige["classe"]) - regles.classes.keys()
    if inconnues:
        raise ValueError(f"classes inconnues dans geologie.csv : {sorted(inconnues)}")
    sortie = nouveau.copy()
    manuel = cle_unites(sortie).map(corrige["classe"]).astype("object")
    sortie["classe"] = manuel.fillna(sortie["classe"])
    if manuel.notna().any():
        log.info("%d corrections manuelles conservées", int(manuel.notna().sum()))
    return sortie


def lire_csv(chemin: Path) -> pd.DataFrame | None:
    if not chemin.exists():
        return None
    return pd.read_csv(chemin, dtype={"notation": "string", "departement": "string"},
                       keep_default_na=False)


def charger_bdcharm50(p: Parametres, grille: Grille) -> tuple[gpd.GeoDataFrame, Path]:
    """Cartes départementales assemblées ; la colonne `departement` distingue leurs notations."""
    src = p.sources["bdcharm50"]
    dossier = p.dossier_brut / "bdcharm50"
    morceaux, premiere = [], None
    for d in p.departements:
        url = src.archive.format(dep=p.code_long(d))
        archive = telecharger(url, dossier / url.rsplit("/", 1)[-1], p.reseau)
        extrait = dossier / archive.stem
        if not extrait.exists():
            with zipfile.ZipFile(archive) as z:
                z.extractall(extrait)
        couches = sorted(extrait.rglob(src.couche_motif))
        if not couches:
            raise RuntimeError(f"aucune couche {src.couche_motif} dans {archive}")
        morceaux.append(gpd.read_file(couches[0]).to_crs(grille.crs).assign(departement=d))
        premiere = premiere or couches[0]
    return gpd.GeoDataFrame(pd.concat(morceaux, ignore_index=True), crs=grille.crs), premiere


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


def classer_source(p: Parametres, cle: str, gdf: gpd.GeoDataFrame,
                   regles: ReglesGeologie) -> tuple[pd.DataFrame, pd.Series]:
    """Table de relecture de la source (écrite, corrections manuelles conservées) et classe de
    chaque polygone."""
    src = p.sources[cle]
    table = fusionner_corrections(
        classer_unites(unites(gdf, src.champs), regles), lire_csv(chemin_csv(cle)), regles
    )
    if regles.couverture and regles.couverture.source != cle:
        texte = (table["notation"] + " " + table["description"].fillna("")).map(normaliser)
        locale = texte.map(lambda t: re.search(regles.couverture.unites, t) is not None)
        table["herite_socle"] = (table["classe"] == "detritique_mixte") & locale
    table.to_csv(chemin_csv(cle), index=False)
    log.info("%s : classes de substrat (ha) : %s", cle,
             table.groupby("classe")["surface_ha"].sum().round().to_dict())
    classe = dict(zip(cle_unites(table), table["classe"], strict=True))
    return table, cles_polygones(gdf, src.champs).map(classe)


def cles_polygones(gdf: gpd.GeoDataFrame, champs: dict) -> pd.Series:
    """Clé d'unité (voir `cle_unites`) de chaque polygone."""
    notation = gdf[colonne(gdf, champs["notation"])].astype("string").fillna("").str.strip()
    df = pd.DataFrame({"notation": notation}, index=gdf.index)
    if "departement" in gdf:
        df["departement"] = gdf["departement"]
    return cle_unites(df)


def heriter_socle(p: Parametres, grille: Grille, regles: ReglesGeologie, cle: str,
                  gdf: gpd.GeoDataFrame, table: pd.DataFrame, geol: np.ndarray) -> str | None:
    """Formations superficielles locales : classe de la roche sous-jacente (`couverture`). Modifie
    `geol` en place ; renvoie la source utilisée, ou None."""
    c = regles.couverture
    if not c or c.source == cle or "herite_socle" not in table:
        return None
    try:
        socle_gdf, _ = CHARGEURS[c.source](p, grille)
    except ErreurReseau as exc:
        log.warning("roche sous-jacente (%s) inaccessible : formations superficielles gardées "
                    "telles quelles (%s)", c.source, exc)
        return None
    _, socle_classe = classer_source(p, c.source, socle_gdf, regles)
    socle = rasteriser(socle_gdf.geometry, socle_classe.map(regles.classes).fillna(0), grille)
    locales = cles_polygones(gdf, p.sources[cle].champs).isin(
        cle_unites(table[table["herite_socle"]]))
    couverte = rasteriser(gdf.geometry, locales.astype(int), grille).astype(bool)
    herite = couverte & np.isin(socle, [regles.classes[k] for k in c.classes])
    geol[herite] = socle[herite]
    log.info("formations superficielles sur roche %s : %.0f ha reclassés", c.classes,
             herite.sum() * grille.resolution ** 2 / 1e4)
    return c.source


def executer(p: Parametres, avec_base: bool = True) -> Path:
    grille = grille_reference(p)
    regles = charger_regles_geologie()
    cle, gdf, fichier = charger(p, grille)
    src = p.sources[cle]

    table, classe = classer_source(p, cle, gdf, regles)
    codes = classe.map(regles.classes).fillna(regles.classes["indetermine"])
    geol = rasteriser(gdf.geometry, codes, grille)
    couverture = heriter_socle(p, grille, regles, cle, gdf, table, geol)
    sortie = ecrire_cog(
        p.dossier_statique / "geol.tif", geol, grille,
        description="classe de substrat (config/classes/geologie_regles.yaml)",
    )
    ecrire_trace(sortie, src.url, source=cle, table=chemin_csv(cle).name, couverture=couverture)
    if avec_base:
        eng = db.moteur(p.url_base)
        nom_notation = colonne(gdf, src.champs["notation"])
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
