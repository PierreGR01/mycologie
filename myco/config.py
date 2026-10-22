"""Chargement et validation de la configuration (config/settings.yaml et config/classes/)."""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from myco.grid import RESOLUTION_MIN


def racine() -> Path:
    """Racine du projet : MYCO_RACINE si définie, sinon le répertoire courant."""
    return Path(os.environ.get("MYCO_RACINE", Path.cwd())).resolve()


class ParamGrille(BaseModel):
    crs: str
    resolution_m: float = Field(ge=RESOLUTION_MIN)
    tampon_m: float = Field(ge=0)


class Chemins(BaseModel):
    brut: Path
    statique: Path
    rapports: Path


class Reseau(BaseModel):
    delai_s: float = 300
    tentatives: int = Field(default=4, ge=1)


class Source(BaseModel):
    """Source de données. Les champs propres à chaque source restent accessibles en attributs."""

    model_config = ConfigDict(extra="allow")

    nom: str
    licence: str
    attribution: str
    url: str


class Parametres(BaseModel):
    departement: str
    grille: ParamGrille
    chemins: Chemins
    base_de_donnees: str
    reseau: Reseau = Reseau()
    sources: dict[str, Source]

    @property
    def url_base(self) -> str:
        return os.environ.get("DATABASE_URL", self.base_de_donnees)

    def chemin(self, *morceaux: str | Path) -> Path:
        return racine().joinpath(*morceaux)

    @property
    def dossier_brut(self) -> Path:
        return self.chemin(self.chemins.brut)

    @property
    def dossier_statique(self) -> Path:
        return self.chemin(self.chemins.statique)

    @property
    def dossier_rapports(self) -> Path:
        return self.chemin(self.chemins.rapports)


def lire_yaml(chemin: Path) -> dict:
    with open(chemin, encoding="utf-8") as f:
        return yaml.safe_load(f)


def charger_parametres(chemin: Path | None = None) -> Parametres:
    chemin = chemin or racine() / "config" / "settings.yaml"
    return Parametres.model_validate(lire_yaml(chemin))


# --- Classes d'essences (config/classes/foret.yaml) ---------------------------------------------


class ClasseForet(BaseModel):
    code: int = Field(ge=0, le=254)
    libelle: str
    tfv: list[str] = []


class ClassesForet(BaseModel):
    classes: dict[str, ClasseForet]

    @model_validator(mode="after")
    def _coherence(self) -> ClassesForet:
        codes = [c.code for c in self.classes.values()]
        if len(codes) != len(set(codes)):
            raise ValueError("codes de classes d'essences en double")
        tfv = [t for c in self.classes.values() for t in c.tfv]
        if len(tfv) != len(set(tfv)):
            raise ValueError("un code TFV est rattaché à plusieurs classes")
        for cle in ("hors_foret", "inconnu"):
            if cle not in self.classes:
                raise ValueError(f"classe obligatoire manquante : {cle}")
        if self.classes["hors_foret"].code != 0:
            raise ValueError("la classe hors_foret doit avoir le code 0")
        return self

    def code_par_tfv(self) -> dict[str, int]:
        return {t: c.code for c in self.classes.values() for t in c.tfv}


def charger_classes_foret(chemin: Path | None = None) -> ClassesForet:
    chemin = chemin or racine() / "config" / "classes" / "foret.yaml"
    return ClassesForet.model_validate(lire_yaml(chemin))


# --- Règles géologiques (config/classes/geologie_regles.yaml) -----------------------------------


class RegleGeologie(BaseModel):
    classe: str
    notation: str | None = None
    texte: str | None = None

    @model_validator(mode="after")
    def _au_moins_un_critere(self) -> RegleGeologie:
        if not (self.notation or self.texte):
            raise ValueError("une règle doit porter sur `notation` ou `texte`")
        return self


class ReglesGeologie(BaseModel):
    classes: dict[str, int]
    regles: list[RegleGeologie]

    @model_validator(mode="after")
    def _coherence(self) -> ReglesGeologie:
        if "indetermine" not in self.classes:
            raise ValueError("classe obligatoire manquante : indetermine")
        if 0 in self.classes.values():
            raise ValueError("le code 0 est réservé à l'absence de donnée")
        inconnues = {r.classe for r in self.regles} - self.classes.keys()
        if inconnues:
            raise ValueError(f"classes inconnues dans les règles : {sorted(inconnues)}")
        return self


def charger_regles_geologie(chemin: Path | None = None) -> ReglesGeologie:
    chemin = chemin or racine() / "config" / "classes" / "geologie_regles.yaml"
    return ReglesGeologie.model_validate(lire_yaml(chemin))
