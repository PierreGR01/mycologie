-- Schéma PostGIS du projet (exécuté au premier démarrage du conteneur).
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE SCHEMA IF NOT EXISTS ref;
CREATE SCHEMA IF NOT EXISTS obs;
CREATE SCHEMA IF NOT EXISTS meteo;
CREATE SCHEMA IF NOT EXISTS pipeline;

-- Référentiels (étape 2)
CREATE TABLE ref.departement (
  code text PRIMARY KEY,
  nom  text,
  geom geometry(MultiPolygon, 2154) NOT NULL
);

CREATE TABLE ref.bdforet (
  id       text PRIMARY KEY,
  code_tfv text,
  tfv      text,
  essence  text,
  classe   text NOT NULL,
  geom     geometry(MultiPolygon, 2154) NOT NULL
);
CREATE INDEX ON ref.bdforet USING gist (geom);

CREATE TABLE ref.geologie (
  id         serial PRIMARY KEY,
  notation   text,
  descr      text,
  lithologie text,
  classe     text,
  geom       geometry(MultiPolygon, 2154) NOT NULL
);
CREATE INDEX ON ref.geologie USING gist (geom);

CREATE TABLE ref.source (
  id            text PRIMARY KEY,
  nom           text NOT NULL,
  url           text,
  licence       text NOT NULL,
  attribution   text NOT NULL,
  version       text,
  telecharge_le timestamptz,
  sha256        text
);

-- Observations (étape 5)
CREATE TABLE obs.taxon (
  espece           text NOT NULL,
  nom_scientifique text NOT NULL,
  gbif_key         integer,
  cd_ref           integer,
  PRIMARY KEY (espece, nom_scientifique)
);

CREATE TABLE obs.observation (
  id               bigserial PRIMARY KEY,
  source           text NOT NULL CHECK (source IN ('gbif', 'inpn')),
  source_id        text NOT NULL,
  espece           text NOT NULL,
  nom_scientifique text,
  date_obs         date,
  incertitude_m    real,
  licence          text,
  jeu_donnees      text,
  doublon_de       bigint REFERENCES obs.observation (id),
  geom             geometry(Point, 2154) NOT NULL,
  UNIQUE (source, source_id)
);
CREATE INDEX ON obs.observation USING gist (geom);

-- Météo (étape 4)
CREATE TABLE meteo.point (
  id    integer PRIMARY KEY,
  geom  geometry(Point, 2154) NOT NULL,
  z_ref real NOT NULL
);

CREATE TABLE meteo.journalier (
  run           date NOT NULL,
  point_id      integer NOT NULL REFERENCES meteo.point (id),
  jour          date NOT NULL,
  tmin          real,
  tmax          real,
  tmoy          real,
  pluie         real,
  est_prevision boolean NOT NULL,
  modele        text,
  PRIMARY KEY (run, point_id, jour)
);

-- Suivi des exécutions
CREATE TABLE pipeline.run (
  run          date PRIMARY KEY,
  debut        timestamptz,
  fin          timestamptz,
  statut       text,
  config_sha   text,
  code_version text,
  message      jsonb
);

CREATE TABLE pipeline.calibrage (
  run      date NOT NULL,
  espece   text NOT NULL,
  metrique text NOT NULL,
  valeur   real,
  details  jsonb,
  PRIMARY KEY (run, espece, metrique)
);
