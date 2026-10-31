import numpy as np
import pytest

from myco.regles import moyenne_geometrique, produit_pondere, table, trapeze


@pytest.mark.parametrize(
    ("x", "attendu"),
    [(-1, 0.2), (0, 0.2), (5, 0.6), (10, 1.0), (20, 1.0), (25, 0.6), (30, 0.2), (40, 0.2)],
)
def test_trapeze(x, attendu):
    assert trapeze(np.array([x]), [0, 10, 20, 30], plancher=0.2)[0] == pytest.approx(attendu)


def test_trapeze_plancher_haut_et_nan():
    f = trapeze(np.array([-1, 40, np.nan]), [0, 10, 20, 30], plancher_haut=0.5)
    assert f[0] == 0 and f[1] == 0.5 and np.isnan(f[2])


def test_trapeze_marche():
    # [0, 0, 25, 45] : 1 dès 0, sans rampe montante (pente).
    np.testing.assert_allclose(trapeze(np.array([0, 25, 35, 60]), [0, 0, 25, 45], 0.3),
                               [1, 1, 0.65, 0.3])


def test_table():
    codes = np.array([1, 2, 3, 255], dtype="uint8")
    f = table(codes, {1: "a", 2: "b", 3: "c"}, {"a": 1.0, "b": 0.4}, defaut=0.1, nodata=255)
    np.testing.assert_allclose(f[:3], [1.0, 0.4, 0.1])
    assert np.isnan(f[3])


def test_moyenne_geometrique():
    a = np.array([0.5, 0.0, np.nan, np.nan], dtype="float32")
    b = np.array([1.0, 1.0, 0.25, np.nan], dtype="float32")
    m = moyenne_geometrique([a, b], [1, 1])
    assert m[0] == pytest.approx(np.sqrt(0.5))
    assert m[1] == 0                      # un facteur nul annule
    assert m[2] == pytest.approx(0.25)    # facteur sans donnée écarté, poids renormalisés
    assert np.isnan(m[3])


def test_produit_pondere():
    a = np.array([0.5, 0.0, np.nan, np.nan, 0.81], dtype="float32")
    b = np.array([0.5, 1.0, 0.25, np.nan, 1.0], dtype="float32")
    m = produit_pondere([a, b], [2, 1])
    assert m[0] == pytest.approx(0.5 * np.sqrt(0.5))   # poids 1 sur 2 : racine carrée
    assert m[1] == 0
    assert m[2] == pytest.approx(0.5)                  # facteur sans donnée écarté
    assert np.isnan(m[3])
    # Même classement que la moyenne géométrique, mais plus contrasté.
    geo = moyenne_geometrique([a, b], [2, 1])
    assert m[0] < geo[0] and m[4] == pytest.approx(geo[4] ** 1.5)
