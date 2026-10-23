"""Prépare une démo statique de la PWA : application construite et sous-ensemble des données.

Usage (depuis la racine du dépôt, après `make web` et `make pipeline`) :
    python web/scripts/preparer_demo.py SORTIE [--donnees web/data] [--jours 1] [--note "…"]

Copie web/dist, puis, depuis le dossier de données : le contour du département, les cartes
d'habitat et les cartes des dates comprises entre J-jours et J+jours. Le manifeste est réécrit
avec ces seules dates et une note affichée dans l'application. Le dossier obtenu peut être
publié tel quel (GitHub Pages, tout hébergement statique gérant les requêtes Range).
"""

import argparse
import json
import shutil
from datetime import date
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
NOTE = ("Démonstration : cartes provisoires, calculées sans la carte géologique BRGM et "
        "mises à jour manuellement.")


def main() -> None:
    args = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    args.add_argument("sortie", type=Path)
    args.add_argument("--donnees", type=Path, default=RACINE / "web" / "data")
    args.add_argument("--dist", type=Path, default=RACINE / "web" / "dist")
    args.add_argument("--jours", type=int, default=1)
    args.add_argument("--note", default=NOTE)
    a = args.parse_args()

    manifeste = json.loads((a.donnees / "latest.json").read_text())
    run = date.fromisoformat(manifeste["run"])
    dates = [d for d in manifeste["dates"]
             if abs((date.fromisoformat(d["date"]) - run).days) <= a.jours]

    if a.sortie.exists():
        shutil.rmtree(a.sortie)
    shutil.copytree(a.dist, a.sortie)
    donnees = a.sortie / "data"
    fichiers = [manifeste["limite"]] + [e["habitat"] for e in manifeste["especes"]] + [
        e["tuiles"].replace("{date}", d["date"]) for e in manifeste["especes"] for d in dates
    ]
    for f in fichiers:
        (donnees / f).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(a.donnees / f, donnees / f)
    manifeste |= {"dates": dates, "note": a.note}
    (donnees / "latest.json").write_text(json.dumps(manifeste, indent=2, ensure_ascii=False))
    (a.sortie / ".nojekyll").touch()  # GitHub Pages : servir les fichiers tels quels

    taille = sum(f.stat().st_size for f in a.sortie.rglob("*") if f.is_file())
    print(f"{a.sortie} : {len(dates)} dates, {len(fichiers)} fichiers de données, "
          f"{taille / 1e6:.1f} Mo")


if __name__ == "__main__":
    main()
