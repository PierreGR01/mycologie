import geopandas as gpd
from shapely.geometry import box

from myco.config import charger_classes_foret
from myco.grid import Grille
from myco.ingest.foret import classer, rapport_codes
from myco.rasters import rasteriser

CHAMPS = {"code_tfv": "code_tfv", "tfv": "tfv", "essence": "essence"}


def foret_test() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {
            "CODE_TFV": ["FF1G01-01", "FP", "XX9", None],
            "TFV": ["Forêt fermée de hêtre pur", "Peupleraie", "?", None],
        },
        geometry=[box(0, 0, 100, 100), box(100, 0, 200, 100), box(0, 100, 100, 200),
                  box(100, 100, 200, 200)],
        crs="EPSG:2154",
    )


def test_classer_insensible_a_la_casse_et_codes_inconnus(projet):
    classes = charger_classes_foret()
    gdf = classer(foret_test(), classes, CHAMPS)
    assert list(gdf["classe"]) == ["hetre", "peupleraie", "inconnu", "inconnu"]
    assert list(gdf["code"]) == [2, 7, 19, 19]

    rapport = rapport_codes(gdf)
    assert set(rapport["classe"]) == {"hetre", "peupleraie", "inconnu"}
    assert rapport["surface_ha"].sum() == 4.0


def test_rasteriser_centre_des_pixels(projet):
    gdf = classer(foret_test(), charger_classes_foret(), CHAMPS)
    grille = Grille.englobant((0, 0, 300, 200), 25)
    r = rasteriser(gdf.geometry, gdf["code"], grille)
    assert r.shape == (8, 12)
    assert (r[4:, :4] == 2).all()      # hêtre au sud-ouest
    assert (r[4:, 4:8] == 7).all()     # peupleraie
    assert (r[:, 8:] == 0).all()       # hors forêt
