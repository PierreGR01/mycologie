import random
from datetime import date, timedelta
from types import SimpleNamespace

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import Point

from myco.calibrage import analyse, gbif, historique
from myco.calibrage import zones as z
from myco.calibrage.meteo_points import score_series
from myco.cli import main
from myco.especes import Gel, Meteo, Saison, charger_especes
from myco.grid import Grille
from tests.test_habitat import deposer_couches_statiques
from tests.test_meteo import limite_test
from tests.test_score import deposer_limite

GRILLE = Grille.englobant((0, 0, 1000, 1000), 25)


def points(xy, incertitude):
    return gpd.GeoDataFrame({"incertitude_m": incertitude},
                            geometry=[Point(x, y) for x, y in xy], crs="EPSG:2154")


def test_pixels_du_cercle():
    zones = z.Zones(GRILLE)
    couche = np.arange(GRILLE.hauteur * GRILLE.largeur).reshape(GRILLE.forme)
    assert zones.pixels(couche, 500, 500, 50).size == 13          # rayon de 2 pixels
    assert zones.pixels(couche, 5, 5, 50).size == 6               # coin : cercle tronqué
    assert zones.pixels(couche, 5000, 5000, 50).size == 0         # hors grille


def test_habitat_moyen_et_composition():
    zones = z.Zones(GRILLE)
    h = np.zeros(GRILLE.forme, dtype="uint8")
    h[:, 20:] = 80                                                 # moitié est favorable
    classes = np.where(np.arange(GRILLE.largeur) < 20, 2, 8).astype("uint8")[None, :] \
        .repeat(GRILLE.hauteur, axis=0)
    obs = points([(250, 500), (750, 500), (750, 500)], [100, 100, 100])
    np.testing.assert_allclose(z.h_moyen(zones, h, obs), [0, 0.8, 0.8])
    parts = z.composition(zones, classes, obs, {2: "hetre", 8: "sapin_epicea"}, set())
    assert parts["hetre"] == pytest.approx(1 / 3) and parts["sapin_epicea"] == pytest.approx(2 / 3)


def test_auc_et_boyce():
    assert z.auc(np.array([0.9, 0.8]), np.array([0.1, 0.2])) == 1.0
    assert z.auc(np.array([0.5]), np.array([0.5])) == 0.5
    rng = np.random.default_rng(0)
    fond = rng.uniform(0, 1, 2000)
    presences = rng.beta(5, 1, 300)                               # concentrées vers 1
    indice, courbe = z.boyce(presences, fond)
    assert indice > 0.8 and len(courbe) > 10


METEO = Meteo(
    saison=Saison(debut="01-01", fin="12-31", rampe_jours=0),
    indicateurs={"pluie_15j": {"type": "trapeze", "poids": 3, "points": [20, 50, 150, 300]},
                 "tmoy_7j": {"type": "trapeze", "poids": 2, "points": [8, 12, 20, 25]}},
    gel=Gel(paliers={1: 0.5, 3: 0.1}),
)


def serie(tmoy, tmin, pluie=5.0, n=30):
    jours = [date(2026, 9, 1) + timedelta(days=k) for k in range(n)]
    return pd.DataFrame({"tmin": tmin, "tmax": tmoy + 5, "tmoy": tmoy, "pluie": pluie},
                        index=jours, dtype="float32")


def test_score_ponctuel_coherent_avec_la_grille():
    """Mêmes valeurs que tests/test_score.py::test_correction_altitude_et_gel."""
    s = score_series(METEO, serie(15.0, 10.0))
    assert s["M"].iloc[:14].isna().all()                          # fenêtre de 15 jours
    assert s["M"].iloc[-1] == pytest.approx(1.0)
    froid = score_series(METEO, serie(8.5, -3.5))
    attendu = np.exp(2 * np.log(0.125) / 5) * 0.1
    assert froid["M"].iloc[-1] == pytest.approx(attendu, rel=1e-3)
    assert froid["jours_gel"].iloc[-1] == 7


def test_phenologie_et_evaluation_temporelle(projet):
    cepe = charger_especes()["cepe"]
    obs = pd.DataFrame({"date_obs": [date(2020, 9, 3), date(2020, 9, 20), date(2020, 3, 1),
                                     None]})
    table, hors = analyse.phenologie(obs, cepe)
    assert table.loc[16, "observations"] == 1 and table.loc[17, "observations"] == 1
    assert hors == pytest.approx(100 / 3)
    scores = pd.DataFrame({
        "observation": ["a"] * 4, "M": [0.9, 0.1, 0.2, 0.9], "f_saison": [1.0] * 4,
        "observe": [True, False, False, False],
    })
    assert analyse.evaluation_temporelle(scores) == pytest.approx((2 + 0.5) / 3)


def test_regle_maximum_des_profils(projet):
    morille = charger_especes()["morille"]
    valeurs = analyse.valeurs_regle(morille, "foret")
    assert valeurs["sapin_epicea"] == 0.8 and valeurs["peupleraie"] == 0.8


def test_periode_et_altitude(projet):
    cepe = charger_especes()["cepe"]
    debut, fin = historique.periode(date(2020, 9, 10), cepe)
    assert debut == date(2020, 6, 1) - timedelta(days=14) and fin == date(2020, 11, 15)
    assert historique.cellule(5.731, 45.188, 0.1) == (5.75, 45.15)
    s = serie(10.0, 5.0)
    s.attrs["z_ref"] = 500
    assert historique.a_l_altitude(s, 1500, 0.0065)["tmoy"].iloc[0] == pytest.approx(3.5)
    assert historique.altitude_mediane(np.array([300., 900., 1000.]),
                                       np.array([False, True, True])) == 950


def test_en_observations_dans_le_departement():
    limite = limite_test()
    df = pd.DataFrame({
        "gbifID": ["1", "2", "3"], "scientificName": ["Boletus edulis"] * 3,
        "eventDate": ["2020-09-10T10:00", "2020-09", "2020-09-12"],
        "day": [10, None, 12], "decimalLongitude": [5.725, 5.725, 6.5],
        "decimalLatitude": [45.179, 45.179, 45.2], "coordinateUncertaintyInMeters": [2821, None, 5],
        "license": ["CC_BY_4_0"] * 3, "datasetKey": ["d"] * 3,
    })
    obs = gbif.en_observations(df, "cepe", limite)
    assert list(obs["source_id"]) == ["1", "2"]                   # le 3e est hors département
    assert obs["date_obs"].iloc[0] == date(2020, 9, 10) and pd.isna(obs["date_obs"].iloc[1])


def faux_reseau(limite):
    """Réponses factices : GBIF (taxons, occurrences) et archive Open-Meteo."""
    rng = random.Random(1)
    x0, y0, x1, y1 = limite.to_crs("EPSG:4326").total_bounds

    def occurrences(cle, n):
        return [{
            "gbifID": f"{cle}-{k}", "taxonKey": cle, "scientificName": f"taxon {cle}",
            "eventDate": f"2020-{rng.randint(8, 10):02d}-{rng.randint(1, 28):02d}",
            "year": 2020, "month": 9, "day": 1,
            "decimalLatitude": rng.uniform(y0 + 0.005, y1 - 0.005),
            "decimalLongitude": rng.uniform(x0 + 0.005, x1 - 0.005),
            "coordinateUncertaintyInMeters": rng.choice([10, 500]),
            "license": "CC_BY_4_0", "datasetKey": "jeu-test", "basisOfRecord": "HUMAN_OBSERVATION",
        } for k in range(n)]

    def obtenir(url, reseau, params=None):
        if url.endswith("/species/match"):
            cle = 5 if params["name"] == "Fungi" else 100 + len(params["name"])
            r = {"usageKey": cle, "matchType": "EXACT", "rank": "SPECIES", "status": "ACCEPTED",
                 "scientificName": params["name"]}
        elif url.endswith("/occurrence/search"):
            n = 120 if params["taxonKey"] == 5 else 25
            r = {"results": occurrences(params["taxonKey"], n), "endOfRecords": True}
        else:  # archive Open-Meteo
            debut, fin = (date.fromisoformat(params[k]) for k in ("start_date", "end_date"))
            jours = [(debut + timedelta(days=k)).isoformat() for k in range((fin - debut).days + 1)]
            n = len(jours)
            r = [{"elevation": 500.0, "daily": {
                "time": jours, "temperature_2m_min": [6.0] * n, "temperature_2m_max": [18.0] * n,
                "temperature_2m_mean": [12.0] * n, "precipitation_sum": [4.0] * n}}
                for _ in params["latitude"].split(",")]
        return SimpleNamespace(json=lambda: r)

    return obtenir


def test_calibrage_hors_ligne(projet, parametres, monkeypatch):
    deposer_couches_statiques(projet)
    deposer_limite(projet)
    faux = faux_reseau(limite_test())
    monkeypatch.setattr(gbif, "obtenir", faux)
    monkeypatch.setattr(historique, "obtenir", faux)
    monkeypatch.setattr(parametres.calibrage, "appels_par_minute", 1e9)
    monkeypatch.setattr("myco.cli.charger_parametres", lambda config: parametres)

    main(["habitat", "--sans-tuiles"])
    main(["calibrage", "--sans-base"])

    dossier = projet / "reports" / "calibration"
    index = (dossier / "README.md").read_text()
    assert "Provisoire" not in index                              # géologie présente
    for e in charger_especes():
        rapport = (dossier / e / "rapport.md").read_text()
        assert "## Phénologie" in rapport and "AUC observations / fond" in rapport
        assert (dossier / e / "phenologie.png").exists() and (dossier / e / "habitat.png").exists()
    assert (dossier / "cepe" / "meteo.png").exists()
