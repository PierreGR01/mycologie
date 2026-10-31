import io

import numpy as np
from PIL import Image
from pmtiles.tile import tileid_to_zxy

from myco.grid import Grille
from myco.tuiles import classer, legende_affichee, opacites, palette, tuiler


def test_classer(parametres):
    scores = np.array([0, 1, 19, 20, 59, 60, 80, 100, 255], dtype="uint8")
    np.testing.assert_array_equal(classer(scores, parametres.affichage),
                                  [0, 1, 1, 2, 3, 4, 5, 5, 0])
    assert len(palette(parametres.affichage)) == 768


def test_tuiler(parametres):
    grille = Grille.englobant((912000, 6455000, 916000, 6459000), 25)
    classes = np.zeros(grille.forme, dtype="uint8")
    classes[40:120, 40:120] = 4
    tuiles = tuiler(classes, grille, parametres.affichage)
    zooms = {tileid_to_zxy(t)[0] for t, _ in tuiles}
    assert zooms == set(range(8, 13))
    assert [t for t, _ in tuiles] == sorted(t for t, _ in tuiles)

    z12 = [png for t, png in tuiles if tileid_to_zxy(t)[0] == 12]
    image = Image.open(io.BytesIO(z12[0]))
    # Fond et classes masquées (« très faible » à « moyen ») transparents ; « bon » opaque.
    assert image.mode == "P" and image.info.get("transparency")[:6] == bytes([0, 0, 0, 0, 255, 255])
    valeurs = set(np.unique(np.array(image)))
    assert valeurs <= {0, 4} and 4 in valeurs


def test_classes_masquees(parametres):
    assert opacites(parametres.affichage) == bytes([0, 0, 0, 0, 255, 255])
    assert [c["libelle"] for c in legende_affichee(parametres.affichage)] == ["bon", "très bon"]
