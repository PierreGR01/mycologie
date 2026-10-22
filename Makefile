VENV     = .venv
PY      ?= $(VENV)/bin/python
STATIC   = data/static
INSTALLE = $(VENV)/.installe

.PHONY: help install up down ingest test lint

help:
	@echo "make install     environnement Python (.venv)"
	@echo "make up | down   démarre / arrête PostGIS (Docker)"
	@echo "make ingest      étape 2 : couches statiques à 25 m (SANS_BASE=1 : sans PostGIS)"
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

# --- Qualité ------------------------------------------------------------------------------------
test: | $(INSTALLE)
	$(PY) -m pytest -q

lint: | $(INSTALLE)
	$(PY) -m ruff check myco tests
