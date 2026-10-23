VENV     = .venv
PY      ?= $(VENV)/bin/python
STATIC   = data/static
INSTALLE = $(VENV)/.installe

.PHONY: help install up down ingest habitat pipeline test lint

help:
	@echo "make install     environnement Python (.venv)"
	@echo "make up | down   démarre / arrête PostGIS (Docker)"
	@echo "make ingest      étape 2 : couches statiques à 25 m (SANS_BASE=1 : sans PostGIS)"
	@echo "make habitat     étape 3 : score d'habitat par espèce (rasters, PMTiles, aperçus)"
	@echo "make pipeline    étape 4 : cartes du jour J-7…J+7 (DATE=AAAA-MM-JJ pour rejouer)"
	@echo "make test | lint tests et analyse statique"

install: $(INSTALLE)
$(INSTALLE): pyproject.toml
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install -q -e ".[dev]"
	@touch $@

up:
	docker compose up -d --wait postgis

down:
	docker compose down

# --- Étape 2 : ingestion ------------------------------------------------------------------------
ingest: $(STATIC)/masque.tif $(STATIC)/alt.tif $(STATIC)/foret.tif $(STATIC)/geol.tif $(STATIC)/ph.tif

$(STATIC)/masque.tif: config/settings.yaml | $(INSTALLE)
	$(PY) -m myco ingest limite $(if $(SANS_BASE),--sans-base)

# alt.tif est écrit en dernier, après pente.tif et expo.tif.
$(STATIC)/alt.tif: $(STATIC)/masque.tif
	$(PY) -m myco ingest relief $(if $(SANS_BASE),--sans-base)

$(STATIC)/foret.tif: $(STATIC)/masque.tif config/classes/foret.yaml
	$(PY) -m myco ingest foret $(if $(SANS_BASE),--sans-base)

$(STATIC)/geol.tif: $(STATIC)/masque.tif config/classes/geologie_regles.yaml $(wildcard config/classes/geologie.csv)
	$(PY) -m myco ingest geologie $(if $(SANS_BASE),--sans-base)

$(STATIC)/ph.tif: $(STATIC)/masque.tif
	$(PY) -m myco ingest ph $(if $(SANS_BASE),--sans-base)

# --- Étape 3 : habitat ---------------------------------------------------------------------------
HABITAT_FAIT = data/habitat/.fait
habitat: $(HABITAT_FAIT)
$(HABITAT_FAIT): $(STATIC)/masque.tif $(STATIC)/alt.tif $(STATIC)/foret.tif $(STATIC)/geol.tif \
                 $(STATIC)/ph.tif $(wildcard config/especes/*.yaml) config/classes/foret.yaml
	$(PY) -m myco habitat
	@touch $@

# --- Étape 4 : pipeline quotidien (météo, score H × M, PMTiles, latest.json) ----------------------
# DATE=AAAA-MM-JJ pour rejouer un run ; par défaut, la date du jour à Paris.
pipeline: $(HABITAT_FAIT)
	$(PY) -m myco pipeline $(if $(DATE),--date $(DATE)) $(if $(SANS_BASE),--sans-base)

# --- Qualité ------------------------------------------------------------------------------------
test: | $(INSTALLE)
	$(PY) -m pytest -q

lint: | $(INSTALLE)
	$(PY) -m ruff check myco tests
