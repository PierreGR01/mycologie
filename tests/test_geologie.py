import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import box

from myco.config import charger_regles_geologie
from myco.ingest.geologie import (
    classer_unite,
    classer_unites,
    fusionner_corrections,
    normaliser,
    unites,
)

CHAMPS = {"notation": "NOTATION", "descr": "DESCR", "lithologie": "LITHOLOGIE",
          "geochimie": "GEOCHIMIE"}


def test_normaliser():
    assert normaliser("  Éboulis   CALCAIRES ") == "eboulis calcaires"
    assert normaliser(None) == ""


@pytest.mark.parametrize(
    ("notation", "texte", "attendu"),
    [
        ("Fz", "Alluvions récentes de l'Isère", "alluvions_recentes"),
        ("F", "Alluvions fluviatiles actuelles", "alluvions_recentes"),
        ("n4-5U", "Calcaires urgoniens massifs", "calcaire"),
        ("j8", "Marnes et calcaires marneux", "marno_calcaire"),
        ("E", "Éboulis calcaires actifs", "calcaire"),
        ("Gx", "Moraines würmiennes à blocs cristallins", "detritique_mixte"),
        ("Fy", "Alluvions fluviatiles würmiennes (terrasse)", "detritique_mixte"),
        ("m", "Molasse marneuse miocène", "detritique_mixte"),
        ("ζ", "Gneiss et micaschistes de Belledonne", "siliceux"),
        ("t", "Grès et quartzites du Trias", "siliceux"),
        ("x", "Série transgressive argileuse", "indetermine"),
    ],
)
def test_classer_unite(projet, notation, texte, attendu):
    classe, _ = classer_unite(notation, texte, charger_regles_geologie())
    assert classe == attendu


def test_unites_et_corrections_manuelles(projet):
    regles = charger_regles_geologie()
    gdf = gpd.GeoDataFrame(
        {"notation": ["Fz", "Fz", "j8", "x"],
         "descr": ["Alluvions récentes", "Alluvions récentes", "Marnes", "Argiles"]},
        geometry=[box(0, 0, 100, 100), box(0, 100, 100, 200), box(200, 0, 300, 100),
                  box(400, 0, 500, 100)],
        crs="EPSG:2154",
    )
    table = classer_unites(unites(gdf, CHAMPS), regles)
    assert dict(zip(table["notation"], table["classe"], strict=True)) == {
        "Fz": "alluvions_recentes", "j8": "marno_calcaire", "x": "indetermine"}
    assert table.loc[table["notation"] == "Fz", "n_polygones"].item() == 2

    # Relecture : « x » corrigé à la main ; « j8 » non corrigé mais dont la règle a changé.
    relu = table.copy()
    relu.loc[relu["notation"] == "x", "classe"] = "siliceux"
    relu.loc[relu["notation"] == "j8", ["classe", "classe_auto"]] = "calcaire"
    fusion = fusionner_corrections(table, relu, regles)
    classes = dict(zip(fusion["notation"], fusion["classe"], strict=True))
    assert classes["x"] == "siliceux"
    assert classes["j8"] == "marno_calcaire"

    relu.loc[relu["notation"] == "x", "classe"] = "basalte"
    with pytest.raises(ValueError, match="basalte"):
        fusionner_corrections(table, relu, regles)


def test_csv_sans_correction(projet):
    nouveau = pd.DataFrame({"notation": ["a"], "classe": ["calcaire"], "classe_auto": ["calcaire"]})
    assert fusionner_corrections(nouveau, None, charger_regles_geologie()) is nouveau
