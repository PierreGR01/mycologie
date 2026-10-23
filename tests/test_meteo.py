from datetime import date, timedelta
from types import SimpleNamespace

import geopandas as gpd
import numpy as np
import pytest
from shapely.geometry import box

from myco.meteo import champs as mod_champs
from myco.meteo import openmeteo
from myco.meteo.indicateurs import INDICATEURS, agreger, fenetre
from myco.meteo.points import points_echantillonnage


def limite_test():
    return gpd.GeoDataFrame(geometry=[box(912000, 6455000, 916000, 6459000)], crs="EPSG:2154")


def test_fenetre_et_agregation():
    jours = [date(2026, 10, 1) + timedelta(days=k) for k in range(20)]
    champ = np.arange(20, dtype="float32")[:, None, None] * np.ones((1, 2, 2), dtype="float32")
    assert fenetre(date(2026, 10, 15), 3) == [date(2026, 10, 13), date(2026, 10, 14),
                                             date(2026, 10, 15)]
    somme = agreger(champ, jours, date(2026, 10, 15), INDICATEURS["pluie_15j"])
    assert somme[0, 0] == sum(range(0, 15))            # 1er au 15 octobre
    moyenne = agreger(champ, jours, date(2026, 10, 20), INDICATEURS["tmoy_7j"])
    assert moyenne[0, 0] == pytest.approx(np.mean(range(13, 20)))


def test_points_echantillonnage(parametres):
    grille, points = points_echantillonnage(limite_test(), parametres.meteo)
    assert grille.resolution == 2500 and grille.xmin % 2500 == 0
    assert points["id"].is_unique and len(points) > 4
    assert points["lon"].between(5.5, 6.0).all() and points["lat"].between(45.0, 45.4).all()
    zone = limite_test().union_all().buffer(parametres.meteo.tampon_m)
    assert points.within(zone).all()


def reponse_factice(lat, lon, debut, fin, pluie=5.0, tmoy=10.0, z=500.0):
    n = (date.fromisoformat(fin) - date.fromisoformat(debut)).days + 1
    jours = [(date.fromisoformat(debut) + timedelta(days=k)).isoformat() for k in range(n)]
    return {
        "latitude": lat, "longitude": lon, "elevation": z,
        "daily": {
            "time": jours,
            "temperature_2m_min": [tmoy - 5] * n,
            "temperature_2m_max": [tmoy + 5] * n,
            "temperature_2m_mean": [tmoy] * n,
            "precipitation_sum": [pluie] * n,
        },
    }


def faux_obtenir(appels):
    def obtenir(url, reseau, params=None):
        appels.append(params)
        lats = [float(v) for v in params["latitude"].split(",")]
        lons = [float(v) for v in params["longitude"].split(",")]
        donnees = [reponse_factice(a, o, params["start_date"], params["end_date"])
                   for a, o in zip(lats, lons, strict=True)]
        return SimpleNamespace(json=lambda: donnees)

    return obtenir


def test_telechargement_par_lots_avec_cache(parametres, monkeypatch, tmp_path):
    appels = []
    monkeypatch.setattr(openmeteo, "obtenir", faux_obtenir(appels))
    pm = parametres.meteo.model_copy(update={"taille_lot": 4, "appels_par_minute": 1e9})
    _, points = points_echantillonnage(limite_test(), pm)
    debut, fin = date(2026, 10, 1), date(2026, 10, 30)
    reponses = openmeteo.telecharger(points, debut, fin, pm, parametres.reseau, tmp_path)
    assert len(reponses) == len(points)
    assert len(appels) == -(-len(points) // 4)
    assert appels[0]["start_date"] == "2026-10-01" and "precipitation_sum" in appels[0]["daily"]

    openmeteo.telecharger(points, debut, fin, pm, parametres.reseau, tmp_path)
    assert len(appels) == -(-len(points) // 4)          # deuxième passage : tout vient du cache

    tableau = openmeteo.en_tableau(reponses, points)
    assert len(tableau) == 30 * len(points)
    assert set(tableau.columns) >= {"point_id", "jour", "tmin", "tmax", "tmoy", "pluie", "z_ref"}


def test_poids_requete():
    assert openmeteo.poids_requete(1, 14) == 1
    assert openmeteo.poids_requete(100, 30) == pytest.approx(100 * 30 / 14)


def test_champs_reduits_au_niveau_de_la_mer(parametres, tmp_path):
    grille, points = points_echantillonnage(limite_test(), parametres.meteo)
    jours = [date(2026, 10, 1), date(2026, 10, 2)]
    reponses = [reponse_factice(0, 0, "2026-10-01", "2026-10-02", z=1000.0)] * len(points)
    tableau = openmeteo.en_tableau(reponses, points)
    champs = mod_champs.champs_grossiers(tableau, points, grille, jours, 0.0065)
    assert champs["t0moy"].shape == (2, grille.hauteur, grille.largeur)
    assert not np.isnan(champs["t0moy"]).any()          # cellules sans point comblées
    np.testing.assert_allclose(champs["t0moy"], 10 + 6.5)
    np.testing.assert_allclose(champs["amplitude"], 10)

    mod_champs.ecrire(tmp_path, champs, grille, jours, {"run": "x"})
    g, j, relus, meta = mod_champs.lire(tmp_path)
    assert g == grille and j == jours and meta == {"run": "x"}
    np.testing.assert_allclose(relus["pluie"], champs["pluie"])


def test_combler():
    a = np.array([[1, np.nan], [np.nan, np.nan]], dtype="float32")
    np.testing.assert_array_equal(mod_champs.combler(a), [[1, 1], [1, 1]])
