"""Point d'entrée : `python -m myco <commande>`."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from myco.config import charger_parametres

COUCHES = ("limite", "relief", "foret", "geologie", "ph")


def ingest(couche: str, config: Path | None, avec_base: bool) -> None:
    from myco.ingest import foret, geologie, limite, ph, relief

    modules = {"limite": limite, "relief": relief, "foret": foret, "geologie": geologie, "ph": ph}
    p = charger_parametres(config)
    for nom in COUCHES if couche == "tout" else (couche,):
        logging.getLogger("myco").info("ingestion : %s", nom)
        sortie = modules[nom].executer(p, avec_base=avec_base)
        logging.getLogger("myco").info("écrit : %s", sortie)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="myco", description=__doc__)
    parser.add_argument("--config", type=Path, help="chemin de settings.yaml")
    parser.add_argument("-v", "--verbeux", action="store_true")
    sous = parser.add_subparsers(dest="commande", required=True)

    p_ingest = sous.add_parser("ingest", help="étape 2 : couches statiques à 25 m")
    p_ingest.add_argument("couche", choices=(*COUCHES, "tout"))
    p_ingest.add_argument("--sans-base", action="store_true",
                          help="ne pas charger PostGIS (rasters seulement)")

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbeux else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s : %(message)s",
    )
    if args.commande == "ingest":
        ingest(args.couche, args.config, avec_base=not args.sans_base)
