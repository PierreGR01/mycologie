"""Ingestion de bout en bout sur un département fictif de 2 × 2 km, sans réseau.

Les fichiers bruts sont déposés là où les téléchargements les auraient écrits. Le pH, lu à distance
sur SoilGrids, est couvert par test_ph.py. Le second test charge aussi PostGIS si
MYCO_TEST_DATABASE_URL est défini."""

import os
import zipfile

import geopandas as gpd
import numpy as np
import pandas as pd
import py7zr
import pytest
from shapely.geometry import box
from sqlalchemy import create_engine, text

from myco import score
from myco.cli import main
from myco.config import charger_parametres
from myco.grid import Grille
from myco.habitat import sources_habitat
from myco.ingest.geologie import sources_utilisees
from myco.rasters import lire
from myco.score import licence_cartes, sources_manifeste
from tests.conftest import ecrire_asc

X0, Y0 = 900000, 6450000


def deposer_donnees_brutes(racine, dep="38", nom="Isère", x0=X0,
                           descriptions=("Moraines würmiennes", "Alluvions récentes")):
    """Département fictif de 2 × 2 km au coin (x0, Y0) : limite, MNT, BD Forêt et BD Charm-50
    (notations Gy au sud et Fz au nord, avec les descriptions données)."""
    brut = racine / "data" / "raw"
    gpd.GeoDataFrame(
        {"code_insee": [dep], "nom_officiel": [nom]},
        geometry=[box(x0, Y0, x0 + 2000, Y0 + 2000)], crs="EPSG:2154",
    ).to_file(_dossier(brut / "limite") / f"departement_{dep}.geojson", driver="GeoJSON")

    # MNT : plan montant vers le nord (pente ≈ 5,7°, exposition sud), dalles de 1 km à 5 m.
    dalles = racine / f"tmp_dalles_{dep}"
    archive = _dossier(brut / "rgealti" / f"D0{dep}") / f"RGEALTI_D0{dep}.7z"
    with py7zr.SevenZipFile(archive, "w") as z:
        for i in range(4):
            for j in range(4):
                x, y = x0 - 1000 + 1000 * i, Y0 - 1000 + 1000 * j
                nom = f"RGEALTI_FXX_{x // 1000:04d}_{(y + 1000) // 1000:04d}_MNT_LAMB93_IGN69.asc"
                d = ecrire_asc(dalles / nom, x, y, 200, 5.0, lambda xx, yy: 200 + 0.1 * (yy - Y0))
                z.write(d, f"1_DONNEES_LIVRAISON/{nom}")

    gpd.GeoDataFrame(
        {"code_tfv": ["FF1-09-09", "FF2G61-61"], "tfv": ["Hêtre", "Sapin ou épicéa"]},
        geometry=[box(x0, Y0, x0 + 1000, Y0 + 2000), box(x0 + 1000, Y0, x0 + 2000, Y0 + 2000)],
        crs="EPSG:2154",
    ).to_file(_dossier(brut / "bdforet") / f"bdforet_{dep}.gpkg", driver="GPKG")

    shp = _dossier(racine / f"tmp_geol_{dep}")
    gpd.GeoDataFrame(
        {"NOTATION": ["Gy", "Fz"], "DESCR": list(descriptions)},
        geometry=[box(x0, Y0, x0 + 2000, Y0 + 1000), box(x0, Y0 + 1000, x0 + 2000, Y0 + 2000)],
        crs="EPSG:2154",
    ).to_file(shp / f"GEO050K_HARM_0{dep}_S_FGEOL_2154.shp")
    with zipfile.ZipFile(_dossier(brut / "bdcharm50") / f"GEO050K_HARM_0{dep}.zip", "w") as z:
        for f in shp.iterdir():
            z.write(f, f"GEO050K_HARM_0{dep}/{f.name}")


def deposer_bdlisa(racine):
    """BD LISA : deux polygones élémentaires ; dans chaque pile, l'entité d'ordre 1 affleure."""
    dossier = _dossier(racine / "data" / "raw" / "bdlisa")
    gpd.GeoDataFrame(
        {"CodePoly": ["1", "2"]},
        geometry=[box(X0, Y0, X0 + 2000, Y0 + 1000), box(X0, Y0 + 1000, X0 + 2000, Y0 + 2000)],
        crs="EPSG:2154",
    ).to_file(dossier / "PolyElementEH_FXX.gpkg", driver="GPKG")
    pd.DataFrame({"CodePoly": ["1", "1", "2"], "CodeEH": ["517AA09", "585AA01", "714FA05"],
                  "OrdRelatif": [1, 2, 1]}).to_csv(dossier / "PileEntiteHydroGeol_FXX.csv")
    pd.DataFrame({"CodeEH": ["517AA09", "585AA01", "714FA05"],
                  "LibelleEH": ["Système karstique du Vercors", "Formations marno-calcaires",
                                "Alluvions de l'Isère en aval de Grenoble"]}
                 ).to_csv(dossier / "TME_FXX.csv")
    pd.DataFrame({"CodeEH": ["517AA09", "714FA05"], "CdLitho": ["1", "2"],
                  "LbLitho": ["Calcaire", "Alluvions"], "LithoPrinc": ["vrai", "vrai"]}
                 ).to_csv(dossier / "Lithologie_FXX.csv")


def _dossier(chemin):
    chemin.mkdir(parents=True, exist_ok=True)
    return chemin


def test_ingestion_hors_ligne(projet):
    deposer_donnees_brutes(projet)
    deposer_bdlisa(projet)
    for couche in ("limite", "relief", "foret", "geologie"):
        main(["ingest", couche, "--sans-base"])

    statique = projet / "data" / "static"
    grille = Grille.depuis_raster(statique / "masque.tif")
    assert grille.forme == (160, 160) and grille.resolution == 25
    for nom in ("alt", "pente", "expo", "foret", "geol"):
        assert Grille.depuis_raster(statique / f"{nom}.tif") == grille

    masque, _ = lire(statique / "masque.tif")
    assert masque.sum() == 2000 * 2000 / 625

    alt, profil = lire(statique / "alt.tif")
    assert profil["nodata"] == -9999 and (alt != -9999).all()
    np.testing.assert_allclose(alt[-1, 0], 200 + 0.1 * (12.5 - 1000), atol=1e-2)
    pente, _ = lire(statique / "pente.tif")
    expo, _ = lire(statique / "expo.tif")
    assert (pente[1:-1, 1:-1] == 6).all() and (expo[1:-1, 1:-1] == 4).all()

    foret, _ = lire(statique / "foret.tif")
    dedans = masque == 1
    assert set(np.unique(foret[dedans])) == {2, 8}
    assert (foret[~dedans] == 0).all()

    # Moraine (détritique) sur le karst du Vercors de la BD LISA : classe calcaire héritée.
    geol, _ = lire(statique / "geol.tif")
    assert set(np.unique(geol[dedans])) == {1, 5}

    table = pd.read_csv(projet / "config" / "classes" / "geologie.csv")
    assert dict(zip(table["notation"], table["classe"], strict=True)) == {
        "Gy": "detritique_mixte", "Fz": "alluvions_recentes"}
    assert dict(zip(table["notation"], table["herite_socle"], strict=True)) == {
        "Gy": True, "Fz": False}
    assert (projet / "config" / "classes" / "geologie_bdlisa.csv").exists()
    p = charger_parametres()
    assert sources_utilisees(p) == ["bdcharm50", "bdlisa"]
    assert "CC BY-NC-SA" in licence_cartes(p)
    rapport = pd.read_csv(projet / "reports" / "ingestion" / "foret_codes.csv")
    assert set(rapport["classe"]) == {"hetre", "sapin_epicea"}


def test_geologie_bdlisa_en_repli(projet):
    """Sans BD Charm-50 (source désactivée ici), la BD LISA fournit geol.tif et sa table."""
    deposer_donnees_brutes(projet)
    deposer_bdlisa(projet)
    settings = projet / "config" / "settings.yaml"
    settings.write_text(settings.read_text().replace(
        "sources: [bdcharm50, bdlisa]", "sources: [bdlisa]"))
    for couche in ("limite", "geologie"):
        main(["ingest", couche, "--sans-base"])

    statique = projet / "data" / "static"
    masque, _ = lire(statique / "masque.tif")
    geol, _ = lire(statique / "geol.tif")
    # Bande sud : karst du Vercors (calcaire = 1), bande nord : alluvions récentes (5).
    assert set(np.unique(geol[masque == 1])) == {1, 5}
    lignes, colonnes = np.nonzero(masque == 1)
    assert geol[lignes.max(), colonnes.min()] == 1 and geol[lignes.min(), colonnes.min()] == 5
    table = pd.read_csv(projet / "config" / "classes" / "geologie_bdlisa.csv")
    assert dict(zip(table["notation"], table["classe"], strict=True)) == {
        "517AA09": "calcaire", "714FA05": "alluvions_recentes"}
    assert not (projet / "config" / "classes" / "geologie.csv").exists()

    p = charger_parametres()
    assert sources_utilisees(p) == ["bdlisa"]
    assert sources_habitat(p) == ["bdforet", "bdlisa", "soilgrids", "rgealti"]
    ids = {s["id"] for s in sources_manifeste(p)}
    assert "bdlisa" in ids and "bdcharm50" not in ids
    assert "CC BY-NC-SA" in licence_cartes(p)


def test_ingestion_deux_departements(projet):
    """Deux départements disjoints (38, 43) : une grille commune, un masque au rang du
    département, des téléchargements par département et des notations BD Charm-50 distinguées
    par département (Gy : moraine en Isère, basalte en Haute-Loire)."""
    settings = projet / "config" / "settings.yaml"
    settings.write_text(settings.read_text().replace(
        'departements: ["38"]', 'departements: ["38", "43"]'))
    deposer_donnees_brutes(projet)
    deposer_donnees_brutes(projet, "43", "Haute-Loire", X0 + 6000,
                           ("Formations volcaniques laviques - basaltes", "Alluvions modernes"))
    deposer_bdlisa(projet)
    for couche in ("limite", "relief", "foret", "geologie"):
        main(["ingest", couche, "--sans-base"])

    statique = projet / "data" / "static"
    grille = Grille.depuis_raster(statique / "masque.tif")
    assert grille.forme == (160, 400)  # 8 km d'Isère au bout de la Haute-Loire, + 1 km de marge
    masque, _ = lire(statique / "masque.tif")
    assert (masque == 1).sum() == (masque == 2).sum() == 2000 * 2000 / 625
    assert (masque[:, :120] != 2).all() and (masque[:, 200:] != 1).all()

    alt, _ = lire(statique / "alt.tif")
    assert (alt[masque > 0] != -9999).all()
    foret, _ = lire(statique / "foret.tif")
    assert set(np.unique(foret[masque == 2])) == {2, 8}

    table = pd.read_csv(projet / "config" / "classes" / "geologie.csv", dtype=str)
    classes = dict(zip(table["departement"] + ":" + table["notation"], table["classe"],
                       strict=True))
    assert classes == {"38:Gy": "detritique_mixte", "38:Fz": "alluvions_recentes",
                       "43:Gy": "siliceux", "43:Fz": "alluvions_recentes"}
    geol, _ = lire(statique / "geol.tif")
    sud = np.zeros_like(masque, dtype=bool)
    sud[80:, :] = True  # y < Y0 + 1000 : bande sud (Gy) des deux départements
    assert set(np.unique(geol[(masque == 1) & sud])) == {1}  # moraine sur karst : calcaire
    assert set(np.unique(geol[(masque == 2) & sud])) == {3}  # basalte : siliceux

    # Une correction manuelle ne vaut que pour son département.
    table.loc[(table["departement"] == "43") & (table["notation"] == "Fz"), "classe"] = "calcaire"
    table.to_csv(projet / "config" / "classes" / "geologie.csv", index=False)
    main(["ingest", "geologie", "--sans-base"])
    table = pd.read_csv(projet / "config" / "classes" / "geologie.csv", dtype=str)
    corrigees = table[table["classe"] != table["classe_auto"]]
    assert list(corrigees["departement"] + ":" + corrigees["notation"]) == ["43:Fz"]

    p = charger_parametres()
    territoires = score.territoires(p)
    assert [(t["code"], t["nom"]) for t in territoires] == [("38", "Isère"), ("43", "Haute-Loire")]
    assert territoires[0]["emprise"][2] < territoires[1]["emprise"][0]  # ici, 38 à l'ouest


@pytest.mark.skipif(not os.environ.get("MYCO_TEST_DATABASE_URL"),
                    reason="MYCO_TEST_DATABASE_URL non défini (base PostGIS de test)")
def test_ingestion_avec_postgis(projet, monkeypatch):
    url = os.environ["MYCO_TEST_DATABASE_URL"]
    monkeypatch.setenv("DATABASE_URL", url)
    deposer_donnees_brutes(projet)
    deposer_bdlisa(projet)
    for couche in ("limite", "relief", "foret", "geologie"):
        main(["ingest", couche])

    with create_engine(url).connect() as cx:
        compte = {t: cx.execute(text(f"SELECT count(*) FROM ref.{t}")).scalar()
                  for t in ("departement", "bdforet", "geologie")}
        sources = set(cx.execute(text("SELECT id FROM ref.source")).scalars())
        classes = set(cx.execute(text("SELECT DISTINCT classe FROM ref.geologie")).scalars())
    assert compte == {"departement": 1, "bdforet": 2, "geologie": 2}
    assert {"admin_express", "rgealti", "bdforet", "bdcharm50"} <= sources
    assert classes == {"detritique_mixte", "alluvions_recentes"}
