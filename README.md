# mycologie

Prévision des zones et périodes favorables à la cueillette de champignons en Isère (38) :
cèpe, girolle, trompette de la mort, pied-de-mouton et morille.

Le score final vaut habitat × météo, sur une maille de 25 m. La conception est décrite dans [PLAN.md](PLAN.md).

> Projet en cours. Les étapes 2 (ingestion) et 3 (habitat) sont implémentées. La géologie BRGM
> reste à ingérer : le serveur infoterre est indisponible.

## Prérequis

- Python ≥ 3.11
- GNU Make
- Docker et Docker Compose, pour PostGIS
- Accès HTTPS aux domaines suivants :

| Domaine | Usage |
|---------|-------|
| `data.geopf.fr` | IGN Géoplateforme : WFS ADMIN EXPRESS et BD Forêt, téléchargement du RGE ALTI |
| `infoterre.brgm.fr` | Carte géologique BD Charm-50 |
| `files.isric.org` | SoilGrids (pH) |
| `api.open-meteo.com`, `archive-api.open-meteo.com` | Météo (étapes 4 et 5) |
| `api.gbif.org`, `openobs.mnhn.fr`, `taxref.mnhn.fr` | Observations (étape 5) |

## Installation

```bash
make install   # environnement virtuel .venv et dépendances
make up        # PostGIS dans Docker ; le schéma db/init.sql est appliqué au premier démarrage
```

La connexion par défaut est `postgresql+psycopg://myco:myco@localhost:5432/myco`. Elle peut être
surchargée par la variable `DATABASE_URL`.

## Étape 2 : ingestion

```bash
make ingest              # télécharge, découpe et rééchantillonne à 25 m, puis charge PostGIS
make ingest SANS_BASE=1  # rasters seulement, sans PostGIS
```

Chaque couche peut aussi être lancée seule :
`.venv/bin/python -m myco ingest {limite|relief|foret|geologie|ph}`. Commencer par `limite`, qui
définit la grille.

| Sortie (`data/static/`, COG, EPSG:2154, 25 m) | Contenu |
|-----------------------------------------------|---------|
| `masque.tif` | 1 = département. Ce fichier définit la grille de référence |
| `alt.tif` | Altitude (m), moyenne du RGE ALTI 5 m. Nodata −9999 |
| `pente.tif` | Pente (°). Nodata 255 |
| `expo.tif` | Exposition : 0 N, 1 NE … 7 NO, 8 plat. Nodata 255 |
| `foret.tif` | Classe d'essence ([config/classes/foret.yaml](config/classes/foret.yaml)) |
| `geol.tif` | Classe de substrat ([config/classes/geologie_regles.yaml](config/classes/geologie_regles.yaml)) |
| `ph.tif` | pH eau × 10, moyenne 0–30 cm (SoilGrids). 0 = pas de donnée |

Les téléchargements bruts sont rangés dans `data/raw/`. Ils ne sont pas retéléchargés s'ils sont
déjà présents. Chaque fichier est accompagné d'un `.source.json` qui donne l'URL, la date et le
sha256. Une archive RGE ALTI introuvable automatiquement peut être déposée à la main dans
`data/raw/rgealti/`.

**À relire après la première ingestion :**

- `config/classes/geologie.csv` : classe de substrat de chaque unité géologique. Pour corriger une
  unité, modifiez sa colonne `classe` : la correction est conservée aux exécutions suivantes.
- `reports/ingestion/foret_codes.csv` : codes BD Forêt rencontrés. Les codes rangés en `inconnu`
  sont à ajouter dans `foret.yaml`.

## Étape 3 : habitat

```bash
make habitat                                        # toutes les espèces
.venv/bin/python -m myco habitat --espece morille   # une seule espèce
```

Les règles de chaque espèce sont dans `config/especes/<espece>.yaml`. Ajouter une espèce revient
à ajouter un fichier : son identifiant doit être le nom du fichier. Les classes utilisables par
les facteurs `table` sont celles de `config/classes/` (essences, substrats) et les secteurs
d'exposition `N`, `NE`, `E`, `SE`, `S`, `SO`, `O`, `NO` et `plat`. En YAML, écrivez ces secteurs
entre guillemets : sans guillemets, `NO` est lu comme « faux ».

| Sortie | Contenu |
|--------|---------|
| `data/habitat/<espece>.tif` | H de 0 à 100 (uint8), 255 hors département |
| `web/public/data/habitat/<espece>.pmtiles` | Tuiles PNG z8–z12 en 5 classes, avec légende et attributions dans les métadonnées |
| `reports/habitat/<espece>.png` | Aperçu de contrôle à 100 m sur fond de relief |
| `reports/habitat/resume.csv` | Part du département dans chaque classe, par espèce |

Les classes d'affichage (seuils et couleurs) sont communes à toutes les espèces. Elles sont
définies dans `config/settings.yaml`, rubrique `affichage`.

## Tests

```bash
make test   # tests sur données synthétiques, sans réseau
make lint
```

Pour tester aussi le chargement PostGIS, définissez `MYCO_TEST_DATABASE_URL` vers une base
PostGIS initialisée avec `db/init.sql`. **Attention : ce test vide les tables `ref.*` de cette base.**

## Sources et licences

Toutes les sources sont ouvertes. Leurs licences et attributions sont déclarées dans
[config/settings.yaml](config/settings.yaml) et seront affichées dans l'application.

| Source | Licence |
|--------|---------|
| IGN : RGE ALTI®, BD Forêt® V2, ADMIN EXPRESS, Plan IGN | Licence Ouverte Etalab 2.0 |
| BRGM : BD Charm-50 | Licence Ouverte Etalab 2.0 (à confirmer) |
| ISRIC : SoilGrids 2.0 | CC BY 4.0 |
| Open-Meteo | CC BY 4.0 (API gratuite, usage non commercial) |
| GBIF | CC0 et CC BY 4.0 uniquement |
| INPN / OpenObs | À confirmer |
