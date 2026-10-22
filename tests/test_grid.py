import numpy as np
import pytest

from myco.grid import Grille
from myco.rasters import ecrire_cog, lire


def test_englobant_cale_sur_25_m():
    g = Grille.englobant((837012.3, 6400007.0, 967990.0, 6531999.9), 25, tampon=1000)
    assert (g.xmin, g.ymin, g.xmax, g.ymax) == (836000, 6399000, 969000, 6533000)
    assert g.forme == (5360, 5320)
    assert g.transform.a == 25 and g.transform.e == -25


def test_resolution_sous_25_m_interdite():
    with pytest.raises(ValueError, match="minimum"):
        Grille.englobant((0, 0, 1000, 1000), 10)


def test_emprise_non_calee_refusee():
    with pytest.raises(ValueError, match="calée"):
        Grille(Grille.englobant((0, 0, 100, 100), 25).crs, 25, 3, 0, 103, 100)


def test_aller_retour_cog(tmp_path):
    g = Grille.englobant((900000, 6450000, 901000, 6450500), 25)
    donnees = np.arange(g.hauteur * g.largeur, dtype="float32").reshape(g.forme)
    chemin = ecrire_cog(tmp_path / "x.tif", donnees, g, nodata=-9999)
    relu, profil = lire(chemin)
    np.testing.assert_array_equal(relu, donnees)
    assert Grille.depuis_raster(chemin) == g
    assert profil["nodata"] == -9999
