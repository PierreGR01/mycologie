"""Point d'entrée : `python -m myco <commande>`."""

from __future__ import annotations

import argparse
import logging
from datetime import date
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


def habitat(config: Path | None, ids: list[str] | None, tuiles: bool) -> None:
    from myco import habitat as module
    from myco.especes import charger_especes

    p = charger_parametres(config)
    especes = charger_especes()
    if ids:
        inconnues = set(ids) - especes.keys()
        if inconnues:
            raise SystemExit(f"espèces inconnues : {sorted(inconnues)}")
        especes = {i: especes[i] for i in ids}
    for sortie in module.executer(p, especes, tuiles=tuiles):
        logging.getLogger("myco").info("écrit : %s", sortie)


def date_run(texte: str | None, p) -> date:
    from myco.meteo.recuperation import aujourdhui

    return date.fromisoformat(texte) if texte else aujourdhui(p)


def meteo(config: Path | None, jour: str | None, avec_base: bool, rafraichir: bool) -> None:
    from myco.meteo import recuperation

    p = charger_parametres(config)
    sortie = recuperation.executer(p, date_run(jour, p), avec_base=avec_base,
                                   rafraichir=rafraichir)
    logging.getLogger("myco").info("champs météo : %s", sortie)


def score(config: Path | None, jour: str | None, garder_rasters: bool) -> None:
    from myco import score as module
    from myco.especes import charger_especes

    p = charger_parametres(config)
    sortie = module.executer(p, charger_especes(), date_run(jour, p),
                             garder_rasters=garder_rasters)
    logging.getLogger("myco").info("manifeste : %s", sortie)


def calibrage(config: Path | None, ids: list[str] | None, avec_meteo: bool,
              avec_base: bool) -> None:
    from myco.calibrage import executer
    from myco.especes import charger_especes

    p = charger_parametres(config)
    especes = charger_especes()
    if ids:
        especes = {i: especes[i] for i in ids}
    for sortie in executer.executer(p, especes, avec_meteo=avec_meteo, avec_base=avec_base):
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

    p_habitat = sous.add_parser("habitat", help="étape 3 : score d'habitat par espèce")
    p_habitat.add_argument("--espece", action="append", dest="especes",
                           help="identifiant d'espèce (répétable) ; toutes par défaut")
    p_habitat.add_argument("--sans-tuiles", action="store_true", help="ne pas produire les PMTiles")

    p_meteo = sous.add_parser("meteo", help="étape 4 : récupération Open-Meteo et champs")
    p_meteo.add_argument("--date", help="date du run (AAAA-MM-JJ), aujourd'hui par défaut")
    p_meteo.add_argument("--sans-base", action="store_true")
    p_meteo.add_argument("--rafraichir", action="store_true",
                         help="ignorer le cache Open-Meteo du run")

    p_score = sous.add_parser("score", help="score H × M de J-7 à J+7, PMTiles et manifeste")
    p_score.add_argument("--date", help="date du run (AAAA-MM-JJ), aujourd'hui par défaut")
    p_score.add_argument("--garder-rasters", action="store_true",
                         help="conserver les scores à 25 m (COG) dans data/runs/")

    p_pipeline = sous.add_parser("pipeline", help="meteo puis score")
    p_pipeline.add_argument("--date")
    p_pipeline.add_argument("--sans-base", action="store_true")
    p_pipeline.add_argument("--garder-rasters", action="store_true")

    p_calib = sous.add_parser("calibrage", help="étape 5 : rapports de calibrage (GBIF)")
    p_calib.add_argument("--espece", action="append", dest="especes")
    p_calib.add_argument("--sans-meteo", action="store_true",
                         help="ne pas évaluer la météo historique (Open-Meteo)")
    p_calib.add_argument("--sans-base", action="store_true")

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbeux else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s : %(message)s",
    )
    if args.commande == "ingest":
        ingest(args.couche, args.config, avec_base=not args.sans_base)
    elif args.commande == "habitat":
        habitat(args.config, args.especes, tuiles=not args.sans_tuiles)
    elif args.commande == "meteo":
        meteo(args.config, args.date, not args.sans_base, args.rafraichir)
    elif args.commande == "score":
        score(args.config, args.date, args.garder_rasters)
    elif args.commande == "calibrage":
        calibrage(args.config, args.especes, not args.sans_meteo, not args.sans_base)
    elif args.commande == "pipeline":
        meteo(args.config, args.date, not args.sans_base, rafraichir=False)
        score(args.config, args.date, args.garder_rasters)
