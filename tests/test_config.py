import re

import pytest
from pydantic import ValidationError

from myco.config import (
    ClassesForet,
    Parametres,
    charger_classes_foret,
    charger_parametres,
    charger_regles_geologie,
    lire_yaml,
)
from tests.conftest import RACINE


def test_parametres_du_depot():
    p = charger_parametres(RACINE / "config" / "settings.yaml")
    assert p.grille.resolution_m == 25
    for cle in ("admin_express", "rgealti", "bdforet", "bdcharm50", "bdlisa", "soilgrids",
                "open_meteo"):
        assert p.sources[cle].licence and p.sources[cle].attribution
    assert p.geologie.sources == ["bdcharm50", "bdlisa"]


def test_source_geologique_non_declaree_refusee():
    brut = lire_yaml(RACINE / "config" / "settings.yaml")
    brut["geologie"]["sources"] = ["bdlisa", "inconnue"]
    with pytest.raises(ValidationError, match="inconnue"):
        Parametres.model_validate(brut)


def test_resolution_sous_25_m_refusee():
    brut = lire_yaml(RACINE / "config" / "settings.yaml")
    brut["grille"]["resolution_m"] = 10
    with pytest.raises(ValidationError):
        Parametres.model_validate(brut)


def test_database_url_surchargeable(parametres, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://x@y/z")
    assert parametres.url_base == "postgresql+psycopg://x@y/z"


def test_classes_foret_du_depot():
    classes = charger_classes_foret(RACINE / "config" / "classes" / "foret.yaml")
    assert classes.classes["hors_foret"].code == 0
    assert classes.code_par_tfv()["FF1-09-09"] == classes.classes["hetre"].code


def test_classes_foret_tfv_en_double_refuse():
    with pytest.raises(ValidationError):
        ClassesForet.model_validate({"classes": {
            "hors_foret": {"code": 0, "libelle": "x"},
            "inconnu": {"code": 9, "libelle": "x"},
            "a": {"code": 1, "libelle": "a", "tfv": ["FP"]},
            "b": {"code": 2, "libelle": "b", "tfv": ["FP"]},
        }})


def test_regles_geologie_du_depot():
    regles = charger_regles_geologie(RACINE / "config" / "classes" / "geologie_regles.yaml")
    for r in regles.regles:
        re.compile(r.notation or r.texte)
