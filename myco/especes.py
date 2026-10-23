"""Fichiers espèces (config/especes/*.yaml) : schéma, chargement et contrôle des vocabulaires.

Ajouter une espèce revient à ajouter un fichier YAML : le code ne connaît aucune espèce.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from myco.config import charger_classes_foret, charger_regles_geologie, lire_yaml, racine
from myco.meteo.indicateurs import FENETRE_MAX, INDICATEURS
from myco.terrain import SECTEURS

Fraction = Annotated[float, Field(ge=0, le=1)]

# Couches statiques utilisables par les facteurs d'habitat (data/static/<couche>.tif).
COUCHES_CATEGORIELLES = ("foret", "geol", "expo")
COUCHES_CONTINUES = ("alt", "pente", "ph")


class _Facteur(BaseModel):
    couche: str
    poids: float = Field(gt=0)
    bloquant: bool = False


class FacteurTable(_Facteur):
    type: Literal["table"]
    valeurs: dict[str, Fraction]
    defaut: Fraction = 0.0

    @model_validator(mode="after")
    def _couche(self) -> FacteurTable:
        if self.couche not in COUCHES_CATEGORIELLES:
            raise ValueError(f"`table` attend une couche parmi {COUCHES_CATEGORIELLES}")
        return self


class FacteurTrapeze(_Facteur):
    type: Literal["trapeze"]
    points: tuple[float, float, float, float]
    plancher: Fraction = 0.0
    plancher_haut: Fraction | None = None

    @field_validator("points")
    @classmethod
    def _croissants(cls, v):
        if list(v) != sorted(v):
            raise ValueError(f"points non croissants : {v}")
        return v

    @model_validator(mode="after")
    def _couche(self) -> FacteurTrapeze:
        if self.couche not in COUCHES_CONTINUES:
            raise ValueError(f"`trapeze` attend une couche parmi {COUCHES_CONTINUES}")
        return self


Facteur = Annotated[FacteurTable | FacteurTrapeze, Field(discriminator="type")]


class Profil(BaseModel):
    facteurs: dict[str, Facteur]


class Habitat(BaseModel):
    combinaison: Literal["moyenne_geometrique"] = "moyenne_geometrique"
    facteurs: dict[str, Facteur] | None = None
    # Plusieurs profils (ex. morille de plaine et de montagne) : H = max des profils.
    profils: dict[str, Profil] | None = None
    combinaison_profils: Literal["max"] = "max"

    @model_validator(mode="after")
    def _facteurs_ou_profils(self) -> Habitat:
        if (self.facteurs is None) == (self.profils is None):
            raise ValueError("renseigner soit `facteurs`, soit `profils`")
        return self

    def liste_profils(self) -> dict[str, Profil]:
        return self.profils if self.profils is not None else {"": Profil(facteurs=self.facteurs)}


class Saison(BaseModel):
    """Fenêtre saisonnière (MM-JJ). Le facteur monte de 0 à 1 sur les `rampe_jours` premiers jours
    et redescend sur les `rampe_jours` derniers ; la fenêtre peut chevaucher le 1er janvier."""

    debut: str = Field(pattern=r"^(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$")
    fin: str = Field(pattern=r"^(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$")
    rampe_jours: int = Field(ge=0, le=60)


class IndicateurTrapeze(BaseModel):
    type: Literal["trapeze"]
    poids: float = Field(gt=0)
    points: tuple[float, float, float, float]
    plancher: Fraction = 0.0
    plancher_haut: Fraction | None = None

    @field_validator("points")
    @classmethod
    def _croissants(cls, v):
        if list(v) != sorted(v):
            raise ValueError(f"points non croissants : {v}")
        return v


class Gel(BaseModel):
    """Multiplicateur selon le nombre de jours où Tmin < seuil sur la fenêtre."""

    seuil_tmin: float = 0.0
    fenetre_jours: int = Field(default=7, ge=1, le=FENETRE_MAX)
    paliers: dict[int, Fraction] = Field(min_length=1)

    @field_validator("paliers")
    @classmethod
    def _positifs(cls, v):
        if min(v) < 1:
            raise ValueError("les paliers de gel commencent à 1 jour")
        return v


class Meteo(BaseModel):
    saison: Saison
    combinaison: Literal["moyenne_geometrique"] = "moyenne_geometrique"
    indicateurs: dict[str, IndicateurTrapeze] = Field(min_length=1)
    gel: Gel | None = None

    @field_validator("indicateurs")
    @classmethod
    def _connus(cls, v):
        inconnus = set(v) - INDICATEURS.keys()
        if inconnus:
            raise ValueError(f"indicateurs inconnus : {sorted(inconnus)} "
                             f"(disponibles : {sorted(INDICATEURS)})")
        return v


class Espece(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9_]+$")
    nom: str
    taxons: list[str] = Field(min_length=1)
    avertissement: str | None = None
    habitat: Habitat
    meteo: Meteo
    sources: list[str] = []


def vocabulaires() -> dict[str, set[str]]:
    """Clés admises par les facteurs `table`, par couche catégorielle."""
    return {
        "foret": set(charger_classes_foret().classes),
        "geol": set(charger_regles_geologie().classes),
        "expo": set(SECTEURS),
    }


def controler_vocabulaire(espece: Espece, vocab: dict[str, set[str]]) -> None:
    for nom_profil, profil in espece.habitat.liste_profils().items():
        for nom, f in profil.facteurs.items():
            if isinstance(f, FacteurTable):
                inconnues = set(f.valeurs) - vocab[f.couche]
                if inconnues:
                    ou = f"{espece.id}/{nom_profil + '/' if nom_profil else ''}{nom}"
                    raise ValueError(f"{ou} : classes inconnues de `{f.couche}` : "
                                     f"{sorted(inconnues)}")


def dossier_especes() -> Path:
    return racine() / "config" / "especes"


def charger_especes(dossier: Path | None = None) -> dict[str, Espece]:
    dossier = dossier or dossier_especes()
    vocab = vocabulaires()
    especes = {}
    for chemin in sorted(dossier.glob("*.yaml")):
        espece = Espece.model_validate(lire_yaml(chemin))
        if espece.id != chemin.stem:
            raise ValueError(f"{chemin.name} : l'identifiant doit être « {chemin.stem} »")
        controler_vocabulaire(espece, vocab)
        especes[espece.id] = espece
    if not especes:
        raise FileNotFoundError(f"aucun fichier espèce dans {dossier}")
    return especes
