import numpy as np
import pytest
import rasterio

from myco.config import charger_classes_foret, charger_regles_geologie
from myco.especes import charger_especes
from myco.grid import Grille
from myco.habitat import NODATA_H, codes_categoriels, evaluer, executer
from myco.rasters import ecrire_cog
from myco.terrain import SECTEURS
from myco.tuiles import lire_pmtiles


def code_foret(cle):
    return charger_classes_foret().classes[cle].code


def code_geol(cle):
    return charger_regles_geologie().classes[cle]


def couches(foret, geol, ph, alt, pente, expo):
    return {
        "foret": np.array([code_foret(c) for c in foret], dtype="uint8"),
        "geol": np.array([code_geol(c) if c else 0 for c in geol], dtype="uint8"),
        "ph": np.array(ph, dtype="float32"),
        "alt": np.array(alt, dtype="float32"),
        "pente": np.array(pente, dtype="float32"),
        "expo": np.array([SECTEURS.index(e) for e in expo], dtype="uint8"),
    }


def test_evaluer_cepe(projet):
    habitat = charger_especes()["cepe"].habitat
    c = couches(
        foret=["hetre", "herbacee", "hetre"],
        geol=["siliceux", "siliceux", None],          # 3e pixel : pas de donnée géologique
        ph=[5.0, 5.0, np.nan],                       # 3e pixel : pas de pH
        alt=[800, 800, 2000],
        pente=[10, 10, 10],
        expo=["N", "N", "S"],
    )
    h = evaluer(habitat, c, codes_categoriels())
    assert h[0] == pytest.approx(1.0)
    assert h[1] == 0                                  # essence bloquante nulle
    # Restent essence (1, poids 3), altitude (0,25, poids 1) et pente (1, poids 1).
    assert h[2] == pytest.approx(0.25 ** (1 / 5), rel=1e-5)


def test_morille_maximum_des_profils(projet):
    habitat = charger_especes()["morille"].habitat
    c = couches(
        foret=["sapin_epicea", "peupleraie"],
        geol=["calcaire", "alluvions_recentes"],
        ph=[6.5, 7.0], alt=[1200, 250], pente=[10, 2], expo=["N", "plat"],
    )
    h = evaluer(habitat, c, codes_categoriels())
    # Pixel 1 : profil montagne (sapin 0,8, calcaire 0,9, autres à 1) ; pixel 2 : profil plaine.
    attendu_montagne = np.exp((3 * np.log(0.8) + 2 * np.log(0.9)) / 7.5)
    attendu_plaine = np.exp(3 * np.log(0.8) / 7.5)
    assert h[0] == pytest.approx(attendu_montagne, rel=1e-5)
    assert h[1] == pytest.approx(attendu_plaine, rel=1e-5)


def deposer_couches_statiques(racine):
    """Département fictif de 3 × 3 km près de Grenoble, moitié hêtraie, moitié prairie."""
    grille = Grille.englobant((912000, 6455000, 916000, 6459000), 25)
    s = racine / "data" / "static"
    masque = np.zeros(grille.forme, dtype="uint8")
    masque[20:140, 20:140] = 1
    foret = np.full(grille.forme, code_foret("herbacee"), dtype="uint8")
    foret[:, :80] = code_foret("hetre")
    ecrire_cog(s / "masque.tif", masque, grille)
    ecrire_cog(s / "foret.tif", foret, grille)
    ecrire_cog(s / "geol.tif", np.full(grille.forme, code_geol("siliceux"), "uint8"), grille,
               nodata=0)
    ecrire_cog(s / "ph.tif", np.full(grille.forme, 55, "uint8"), grille, nodata=0)
    alt = np.tile(np.linspace(500, 2100, grille.largeur, dtype="float32"), (grille.hauteur, 1))
    ecrire_cog(s / "alt.tif", alt, grille, nodata=-9999)
    ecrire_cog(s / "pente.tif", np.full(grille.forme, 10, "uint8"), grille, nodata=255)
    ecrire_cog(s / "expo.tif", np.full(grille.forme, 0, "uint8"), grille, nodata=255)
    return grille, masque


def test_executer_rasters_tuiles_apercus(parametres, projet):
    grille, masque = deposer_couches_statiques(projet)
    especes = charger_especes()
    sorties = executer(parametres, {"cepe": especes["cepe"], "morille": especes["morille"]})

    raster = projet / "data" / "habitat" / "cepe.tif"
    assert raster in sorties
    assert Grille.depuis_raster(raster) == grille
    with rasterio.open(raster) as src:
        h = src.read(1)
    assert (h[masque == 0] == NODATA_H).all()
    dedans = masque == 1
    assert (h[dedans & (np.arange(grille.largeur) >= 80)] == 0).all()   # prairie
    assert h[dedans & (np.arange(grille.largeur) < 80)].min() > 50      # hêtraie

    entete, meta = lire_pmtiles(projet / "web" / "public" / "data" / "habitat" / "cepe.pmtiles")
    assert entete["min_zoom"] == 8 and entete["max_zoom"] == 12
    assert meta["espece"] == "cepe" and len(meta["legende"]) == 5
    assert "IGN" in meta["attribution"] and "ISRIC" in meta["attribution"]

    rapports = projet / "reports" / "habitat"
    assert (rapports / "cepe.png").exists() and (rapports / "resume.csv").exists()
