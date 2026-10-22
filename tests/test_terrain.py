import numpy as np
import pytest

from myco.terrain import NODATA_U8, PLAT, SECTEURS, pente_exposition

RES = 25.0


def plan(gradient_est: float, gradient_nord: float, n: int = 9) -> np.ndarray:
    """MNT plan ; les lignes vont du nord au sud."""
    colonnes = np.arange(n) * RES
    lignes_nord = (n - 1 - np.arange(n)) * RES
    x, y = np.meshgrid(colonnes, lignes_nord)
    return (gradient_est * x + gradient_nord * y).astype("float32")


@pytest.mark.parametrize(
    ("ge", "gn", "secteur"),
    [
        (0.0, 0.1, "S"),    # monte vers le nord : versant exposé au sud
        (0.0, -0.1, "N"),
        (0.1, 0.0, "O"),    # monte vers l'est : versant exposé à l'ouest
        (-0.1, 0.0, "E"),
        (0.1, 0.1, "SO"),
        (-0.1, -0.1, "NE"),
    ],
)
def test_exposition_et_pente(ge, gn, secteur):
    pente, expo = pente_exposition(plan(ge, gn), RES)
    attendu = round(np.degrees(np.arctan(np.hypot(ge, gn))))
    assert (pente[1:-1, 1:-1] == attendu).all()
    assert (expo[1:-1, 1:-1] == SECTEURS.index(secteur)).all()


def test_terrain_plat():
    _, expo = pente_exposition(plan(0.01, 0.0), RES)
    assert (expo == PLAT).all()


def test_nodata_propage_au_voisinage():
    z = plan(0.0, 0.1)
    z[4, 4] = np.nan
    pente, expo = pente_exposition(z, RES)
    assert (pente[3:6, 3:6] == NODATA_U8).all() and (expo[3:6, 3:6] == NODATA_U8).all()
    assert pente[0, 0] != NODATA_U8
