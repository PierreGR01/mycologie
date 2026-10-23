import json
from datetime import date

import numpy as np
import pytest
from rasterio.windows import Window

from myco.cli import main
from myco.especes import Gel, Meteo, Saison, charger_especes
from myco.grid import Grille
from myco.meteo import openmeteo, recuperation
from myco.score import Affineur, facteur_saison, multiplicateur_gel, score_meteo
from myco.tuiles import lire_pmtiles
from tests.test_habitat import deposer_couches_statiques
from tests.test_meteo import faux_obtenir, limite_test


@pytest.mark.parametrize(
    ("jour", "attendu"),
    [(date(2026, 6, 1), 0.0), (date(2026, 6, 8), 7 / 15), (date(2026, 6, 16), 1.0),
     (date(2026, 10, 31), 1.0), (date(2026, 11, 15), 0.0), (date(2026, 12, 1), 0.0)],
)
def test_saison(jour, attendu):
    s = Saison(debut="06-01", fin="11-15", rampe_jours=15)
    assert facteur_saison(jour, s) == pytest.approx(attendu)


def test_saison_a_cheval_sur_janvier():
    s = Saison(debut="11-01", fin="02-28", rampe_jours=10)
    assert facteur_saison(date(2027, 1, 15), s) == 1.0
    assert facteur_saison(date(2026, 7, 1), s) == 0.0


def test_multiplicateur_gel():
    gel = Gel(paliers={1: 0.5, 3: 0.1})
    np.testing.assert_allclose(multiplicateur_gel(np.array([0, 1, 2, 3, 7]), gel),
                               [1, 0.5, 0.5, 0.1, 0.1])


def test_correction_altitude_et_gel():
    """Champs grossiers uniformes : T₀moy = 15 °C, T₀min = 3 °C, 75 mm sur 15 jours.
    À 0 m : 15 °C et pas de gel. À 1 000 m : 8,5 °C et gel tous les jours (isotherme 0 °C à
    ≈ 462 m)."""
    grossiere = Grille.englobant((900000, 6450000, 910000, 6460000), 2500)
    grille = Grille.englobant((902500, 6452500, 907500, 6457500), 25)
    jours = [date(2026, 10, 1 + k) for k in range(20)]
    forme = (len(jours), grossiere.hauteur, grossiere.largeur)
    champs = {"pluie": np.full(forme, 5.0), "t0moy": np.full(forme, 15.0),
              "t0min": np.full(forme, 3.0), "amplitude": np.full(forme, 10.0)}
    meteo = Meteo(
        saison=Saison(debut="01-01", fin="12-31", rampe_jours=0),
        indicateurs={"pluie_15j": {"type": "trapeze", "poids": 3, "points": [20, 50, 150, 300]},
                     "tmoy_7j": {"type": "trapeze", "poids": 2, "points": [8, 12, 20, 25]}},
        gel=Gel(paliers={1: 0.5, 3: 0.1}),
    )
    alt = np.array([[0.0, 1000.0]], dtype="float32")
    affineur = Affineur(grossiere, grille, Window(0, 0, 2, 1))
    m = score_meteo(meteo, date(2026, 10, 20), alt, affineur, champs, jours, 0.0065)
    assert m[0, 0] == pytest.approx(1.0, abs=1e-4)
    # tmoy = 8,5 °C → 0,125 ; moyenne géométrique (3 × ln 1 + 2 × ln 0,125) / 5 ; puis gel × 0,1
    attendu = np.exp(2 * np.log(0.125) / 5) * 0.1
    assert m[0, 1] == pytest.approx(attendu, rel=1e-3)


def deposer_limite(racine):
    dossier = racine / "data" / "raw" / "limite"
    dossier.mkdir(parents=True)
    limite_test().assign(code_insee="38").to_file(dossier / "departement_38.geojson",
                                                  driver="GeoJSON")


def test_pipeline_hors_ligne(projet, parametres, monkeypatch):
    deposer_couches_statiques(projet)
    deposer_limite(projet)
    monkeypatch.setattr(openmeteo, "obtenir", faux_obtenir([]))
    monkeypatch.setattr(recuperation, "aujourdhui", lambda p: date(2026, 10, 15))
    monkeypatch.setattr(parametres.meteo, "appels_par_minute", 1e9)
    monkeypatch.setattr("myco.cli.charger_parametres", lambda config: parametres)

    main(["habitat", "--sans-tuiles"])
    main(["pipeline", "--date", "2026-10-15", "--sans-base"])

    publication = projet / "web" / "public" / "data"
    manifeste = json.loads((publication / "latest.json").read_text())
    assert manifeste["run"] == "2026-10-15"
    dates = [d["date"] for d in manifeste["dates"]]
    assert dates[0] == "2026-10-08" and dates[-1] == "2026-10-22" and len(dates) == 15
    types = {d["date"]: d["type"] for d in manifeste["dates"]}
    assert types["2026-10-14"] == "analyse" and types["2026-10-15"] == "prevision"
    assert {e["id"] for e in manifeste["especes"]} == set(charger_especes())
    assert any(s["attribution"].startswith("Weather data by Open-Meteo")
               for s in manifeste["sources"])

    tuiles = sorted((publication / "runs" / "2026-10-15").rglob("*.pmtiles"))
    assert len(tuiles) == 5 * 15
    _, meta = lire_pmtiles(publication / "runs" / "2026-10-15" / "cepe" / "2026-10-15.pmtiles")
    assert meta["type"] == "score" and "Open-Meteo" in meta["attribution"]

    # La morille est hors saison en octobre : fichiers présents, mais une seule tuile vide.
    entete, _ = lire_pmtiles(publication / "runs" / "2026-10-15" / "morille" / "2026-10-15.pmtiles")
    assert entete["addressed_tiles_count"] == 1
