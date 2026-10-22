"""Téléchargements HTTP avec reprises et traçabilité (URL, date, sha256)."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

from myco.config import Reseau

log = logging.getLogger(__name__)

ENTETES = {"User-Agent": "mycologie-isere/0.1 (+https://github.com/PierreGR01/mycologie)"}


class ErreurReseau(RuntimeError):
    pass


def client(reseau: Reseau) -> httpx.Client:
    return httpx.Client(timeout=reseau.delai_s, follow_redirects=True, headers=ENTETES)


def _reessayable(exc: Exception) -> bool:
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code == 429 or exc.response.status_code >= 500
    return False


def _avec_reprises(action, reseau: Reseau, description: str):
    for tentative in range(reseau.tentatives):
        try:
            return action()
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            if not _reessayable(exc) or tentative == reseau.tentatives - 1:
                raise ErreurReseau(f"{description} : {exc}") from exc
            attente = 2 ** (tentative + 1)
            log.warning("%s : %s, nouvel essai dans %d s", description, exc, attente)
            time.sleep(attente)


def obtenir(url: str, reseau: Reseau, params: dict | None = None) -> httpx.Response:
    def action():
        with client(reseau) as c:
            r = c.get(url, params=params)
            r.raise_for_status()
            return r

    return _avec_reprises(action, reseau, f"GET {url}")


def telecharger(url: str, destination: Path, reseau: Reseau, params: dict | None = None) -> Path:
    """Télécharge `url` vers `destination` (sauté si le fichier existe déjà)."""
    if destination.exists():
        log.info("déjà présent : %s", destination)
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    partiel = destination.with_name(destination.name + ".part")

    def action():
        with client(reseau) as c, c.stream("GET", url, params=params) as r:
            r.raise_for_status()
            with partiel.open("wb") as f:
                for morceau in r.iter_bytes(1 << 20):
                    f.write(morceau)

    log.info("téléchargement : %s", url)
    _avec_reprises(action, reseau, f"téléchargement {url}")
    partiel.replace(destination)
    ecrire_trace(destination, url)
    return destination


def sha256(chemin: Path) -> str:
    h = hashlib.sha256()
    with chemin.open("rb") as f:
        for bloc in iter(lambda: f.read(1 << 20), b""):
            h.update(bloc)
    return h.hexdigest()


def ecrire_trace(fichier: Path, url: str, **extra) -> dict:
    """Écrit `<fichier>.source.json` à côté du fichier téléchargé ou produit."""
    trace = {
        "url": url,
        "date": datetime.now(UTC).isoformat(timespec="seconds"),
        "sha256": sha256(fichier) if fichier.is_file() else None,
        "taille": fichier.stat().st_size if fichier.is_file() else None,
        **extra,
    }
    fichier.with_name(fichier.name + ".source.json").write_text(
        json.dumps(trace, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return trace
