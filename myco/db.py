"""Chargement des couches vecteur et des métadonnées de sources dans PostGIS."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import geopandas as gpd
from shapely.geometry import MultiPolygon, Polygon
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from myco.config import Source

log = logging.getLogger(__name__)


def moteur(url: str) -> Engine:
    eng = create_engine(url)
    try:
        with eng.connect() as cx:
            cx.execute(text("SELECT 1"))
    except Exception as exc:
        raise RuntimeError(
            f"PostGIS injoignable ({exc.__class__.__name__}). Lancer `make up`, "
            "ou relancer avec --sans-base pour ne produire que les rasters."
        ) from exc
    return eng


def en_multipolygones(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    gdf, nom = gdf.copy(), gdf.geometry.name
    gdf[nom] = gdf.geometry.apply(lambda g: MultiPolygon([g]) if isinstance(g, Polygon) else g)
    return gdf.set_geometry(nom)


def remplacer_table(eng: Engine, gdf: gpd.GeoDataFrame, schema: str, table: str) -> None:
    """Vide la table (créée par db/init.sql) puis y insère `gdf`."""
    gdf = en_multipolygones(gdf).rename_geometry("geom")
    with eng.begin() as cx:
        cx.execute(text(f"TRUNCATE {schema}.{table}"))
    gdf.to_postgis(table, eng, schema=schema, if_exists="append", index=False)
    log.info("%s.%s : %d lignes", schema, table, len(gdf))


def enregistrer_source(eng: Engine, cle: str, source: Source, fichier: Path) -> None:
    """Reporte la trace `<fichier>.source.json` dans ref.source."""
    trace_json = fichier.with_name(fichier.name + ".source.json")
    trace = json.loads(trace_json.read_text(encoding="utf-8")) if trace_json.exists() else {}
    with eng.begin() as cx:
        cx.execute(
            text(
                """
                INSERT INTO ref.source (id, nom, url, licence, attribution, version,
                                        telecharge_le, sha256)
                VALUES (:id, :nom, :url, :licence, :attribution, :version, :date, :sha256)
                ON CONFLICT (id) DO UPDATE SET
                  nom = EXCLUDED.nom, url = EXCLUDED.url, licence = EXCLUDED.licence,
                  attribution = EXCLUDED.attribution, version = EXCLUDED.version,
                  telecharge_le = EXCLUDED.telecharge_le, sha256 = EXCLUDED.sha256
                """
            ),
            {
                "id": cle,
                "nom": source.nom,
                "url": trace.get("url", source.url),
                "licence": source.licence,
                "attribution": source.attribution,
                "version": fichier.name,
                "date": trace.get("date"),
                "sha256": trace.get("sha256"),
            },
        )
