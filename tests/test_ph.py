import numpy as np
import rasterio
from rasterio.transform import from_origin

from myco.grid import Grille
from myco.ingest.ph import NODATA_PH, ph_pondere


def ecrire_wgs84(chemin, valeur, nodata_ouest=False):
    """Raster SoilGrids factice en EPSG:4326 autour de Grenoble, en pH × 10."""
    res = 0.002
    data = np.full((100, 100), valeur, dtype="int16")
    if nodata_ouest:
        data[:, :50] = -32768
    with rasterio.open(
        chemin, "w", driver="GTiff", width=100, height=100, count=1, dtype="int16",
        crs="EPSG:4326", transform=from_origin(5.62, 45.28, res, res), nodata=-32768,
    ) as dst:
        dst.write(data, 1)
    return str(chemin)


def test_moyenne_ponderee_par_epaisseur(tmp_path):
    # Grille de 2 km × 1 km au centre du raster factice (≈ 5,72° E ; 45,18° N).
    grille = Grille.englobant((913000, 6457000, 915000, 6458000), 25)
    sources = {
        ecrire_wgs84(tmp_path / "a.tif", 50, nodata_ouest=True): 5,
        ecrire_wgs84(tmp_path / "b.tif", 60): 10,
        ecrire_wgs84(tmp_path / "c.tif", 70): 15,
    }
    ph = ph_pondere(sources, grille)
    assert ph.dtype == np.uint8 and ph.shape == grille.forme
    valeurs = set(np.unique(ph))
    assert valeurs <= {63, 66, 64, 65}       # 63 avec les trois horizons, 66 sans le premier
    assert 63 in valeurs or 66 in valeurs
    assert NODATA_PH not in valeurs


def test_hors_couverture(tmp_path):
    grille = Grille.englobant((700000, 6600000, 701000, 6601000), 25)  # loin du raster
    ph = ph_pondere({ecrire_wgs84(tmp_path / "a.tif", 50): 5}, grille)
    assert (ph == NODATA_PH).all()
