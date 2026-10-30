import shutil
from pathlib import Path

import numpy as np
import pytest

from myco.config import charger_parametres

RACINE = Path(__file__).resolve().parent.parent


@pytest.fixture
def projet(tmp_path, monkeypatch):
    """Copie de config/ dans un répertoire temporaire servant de racine du projet."""
    shutil.copytree(RACINE / "config", tmp_path / "config")
    for table in (tmp_path / "config" / "classes").glob("geologie*.csv"):
        table.unlink()
    monkeypatch.setenv("MYCO_RACINE", str(tmp_path))
    return tmp_path


@pytest.fixture
def parametres(projet):
    return charger_parametres()


def ecrire_asc(chemin: Path, x0: float, y0: float, n: int, res: float, fonction,
               nodata: float = -99999) -> Path:
    """Dalle ESRI ASCII de n × n pixels, coin inférieur gauche (x0, y0), comme le RGE ALTI."""
    xs = x0 + res * (np.arange(n) + 0.5)
    ys = y0 + res * (n - np.arange(n) - 0.5)
    z = fonction(*np.meshgrid(xs, ys))
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with chemin.open("w") as f:
        f.write(f"ncols {n}\nnrows {n}\nxllcorner {x0}\nyllcorner {y0}\n")
        f.write(f"cellsize {res}\nNODATA_value {nodata}\n")
        np.savetxt(f, z, fmt="%.3f")
    return chemin
