import shutil

import pytest
import yaml
from pydantic import ValidationError

from myco.especes import charger_especes, dossier_especes


def ecrire(dossier, nom, donnees):
    (dossier / f"{nom}.yaml").write_text(yaml.safe_dump(donnees, allow_unicode=True))


def cepe(projet):
    return yaml.safe_load((projet / "config" / "especes" / "cepe.yaml").read_text())


def test_especes_du_depot(projet):
    especes = charger_especes()
    assert set(especes) == {"cepe", "girolle", "trompette", "pied_de_mouton", "morille"}
    assert set(especes["morille"].habitat.liste_profils()) == {"plaine", "montagne"}
    assert especes["morille"].avertissement


def test_ajouter_une_espece_sans_toucher_au_code(projet):
    donnees = cepe(projet) | {"id": "nouvelle", "nom": "Nouvelle espèce"}
    ecrire(dossier_especes(), "nouvelle", donnees)
    assert "nouvelle" in charger_especes()


@pytest.mark.parametrize(
    ("modif", "message"),
    [
        (lambda d: d["habitat"]["facteurs"]["essence"]["valeurs"].update(baobab=1.0), "baobab"),
        (lambda d: d["habitat"]["facteurs"]["pente"].update(couche="foret"), "trapeze"),
        (lambda d: d["habitat"]["facteurs"]["pente"].update(points=[0, 30, 25, 45]), "croissants"),
        (lambda d: d["habitat"]["facteurs"]["ph"].update(plancher=1.5), "less than or equal"),
        (lambda d: d["habitat"].update(profils={}), "soit `facteurs`"),
    ],
)
def test_erreurs_de_saisie(projet, modif, message):
    donnees = cepe(projet)
    modif(donnees)
    dossier = projet / "autres"
    dossier.mkdir()
    ecrire(dossier, "cepe", donnees)
    with pytest.raises((ValidationError, ValueError), match=message):
        charger_especes(dossier)


def test_identifiant_different_du_nom_de_fichier(projet):
    dossier = projet / "autres"
    dossier.mkdir()
    shutil.copy(projet / "config" / "especes" / "cepe.yaml", dossier / "bolet.yaml")
    with pytest.raises(ValueError, match="bolet"):
        charger_especes(dossier)
