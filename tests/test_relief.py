from types import SimpleNamespace

import numpy as np
import py7zr

from myco.config import Reseau
from myco.grid import Grille
from myco.ingest import relief
from tests.conftest import ecrire_asc


def test_agreger_mnt_moyenne_5x5(tmp_path):
    # Deux dalles de 1 km à 5 m, z = x : la moyenne d'un pixel de 25 m vaut le x de son centre.
    dalles = [
        ecrire_asc(tmp_path / f"d{i}.asc", 1000.0 * i, 0.0, 200, 5.0, lambda x, y: x)
        for i in range(2)
    ]
    grille = Grille.englobant((0, 0, 2500, 1000), 25)  # déborde de 500 m à l'est
    alt = relief.agreger_mnt(dalles, grille, -99999)
    assert alt.shape == (40, 100)
    np.testing.assert_allclose(alt[:, :80], np.broadcast_to(12.5 + 25 * np.arange(80), (40, 80)),
                               atol=1e-3)
    assert np.isnan(alt[:, 80:]).all()


def test_agreger_mnt_ignore_nodata(tmp_path):
    def z(x, y):
        return np.where(x < 25, -99999, 100.0)

    dalle = ecrire_asc(tmp_path / "d.asc", 0.0, 0.0, 20, 5.0, z)
    alt = relief.agreger_mnt([dalle], Grille.englobant((0, 0, 100, 100), 25), -99999)
    assert np.isnan(alt[:, 0]).all()
    np.testing.assert_allclose(alt[:, 1:], 100.0)


def test_extraire_dalles_multivolume(tmp_path):
    mnt = ecrire_asc(tmp_path / "src" / "RGEALTI_FXX_0900_6450_MNT_LAMB93_IGN69.asc",
                     0, 0, 4, 5.0, lambda x, y: x)
    annexe = ecrire_asc(tmp_path / "src" / "RGEALTI_FXX_0900_6450_SRC_LAMB93_IGN69.asc",
                        0, 0, 4, 5.0, lambda x, y: x)
    archive = tmp_path / "RGEALTI_D038.7z"
    with py7zr.SevenZipFile(archive, "w") as z:
        z.write(mnt, "1_DONNEES_LIVRAISON/MNT/" + mnt.name)
        z.write(annexe, "3_SUPPLEMENTS/SRC/" + annexe.name)
    octets = archive.read_bytes()
    parties = []
    for i, debut in enumerate(range(0, len(octets), len(octets) // 2 + 1), start=1):
        partie = tmp_path / "raw" / f"RGEALTI_D038.7z.{i:03d}"
        partie.parent.mkdir(exist_ok=True)
        partie.write_bytes(octets[debut:debut + len(octets) // 2 + 1])
        parties.append(partie)

    dalles = relief.extraire_dalles(parties, tmp_path / "raw" / "dalles", r"_MNT_.*\.asc$")
    assert [d.name for d in dalles] == [mnt.name]
    assert not (tmp_path / "raw" / "RGEALTI_D038.7z").exists()


ATOM = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  {liens}
</feed>"""


def test_trouver_archives_garde_edition_recente(monkeypatch):
    base = "https://exemple/telechargement/resource/RGEALTI"
    pages = {
        base: ATOM.format(liens=f"""
            <entry><link href="{base}/RGEALTI_2-0_5M_ASC_LAMB93-IGN69_D038_2020-10-15"/></entry>
            <entry><link href="{base}/RGEALTI_2-0_5M_ASC_LAMB93-IGN69_D073_2020-10-15"/></entry>
            <link rel="next" href="{base}?page=2"/>"""),
        f"{base}?page=2": ATOM.format(liens=f"""
            <entry><link href="{base}/RGEALTI_2-0_5M_ASC_LAMB93-IGN69_D038_2023-01-01"/></entry>
            """),
        f"{base}/RGEALTI_2-0_5M_ASC_LAMB93-IGN69_D038_2020-10-15": ATOM.format(liens="""
            <link href="https://exemple/dl/RGEALTI_2-0_5M_ASC_LAMB93-IGN69_D038_2020-10-15.7z"/>
            """),
        f"{base}/RGEALTI_2-0_5M_ASC_LAMB93-IGN69_D038_2023-01-01": ATOM.format(liens="""
            <link href="https://exemple/dl/RGEALTI_2-0_5M_ASC_LAMB93-IGN69_D038_2023-01-01.7z.002"/>
            <link href="https://exemple/dl/RGEALTI_2-0_5M_ASC_LAMB93-IGN69_D038_2023-01-01.7z.001"/>
            """),
    }
    monkeypatch.setattr(relief, "obtenir", lambda url, reseau, params=None:
                        SimpleNamespace(text=pages[url]))
    urls = relief.trouver_archives(base, "RGEALTI_2-0_5M_ASC_LAMB93-IGN69_D038", Reseau())
    assert urls == [
        "https://exemple/dl/RGEALTI_2-0_5M_ASC_LAMB93-IGN69_D038_2023-01-01.7z.001",
        "https://exemple/dl/RGEALTI_2-0_5M_ASC_LAMB93-IGN69_D038_2023-01-01.7z.002",
    ]
