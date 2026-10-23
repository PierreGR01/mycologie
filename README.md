# mycologie

Prévision des zones et périodes favorables à la cueillette de champignons en Isère (38) :
cèpe, girolle, trompette de la mort, pied-de-mouton et morille.

Le score final vaut habitat × météo, sur une maille de 25 m. La conception est décrite dans [PLAN.md](PLAN.md).

> Projet en cours. Les étapes 2 (ingestion), 3 (habitat), 4 (météo, score quotidien) et 6 (PWA)
> sont implémentées. La géologie BRGM reste à ingérer : le serveur infoterre est indisponible.
> L'étape 5 (calibrage) reste à faire.

## Prérequis

- Python ≥ 3.11
- Node.js ≥ 20 (PWA)
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
| `web/data/habitat/<espece>.pmtiles` | Tuiles PNG z8–z12 en 5 classes, avec légende et attributions dans les métadonnées |
| `reports/habitat/<espece>.png` | Aperçu de contrôle à 100 m sur fond de relief |
| `reports/habitat/resume.csv` | Part du département dans chaque classe, par espèce |

Les classes d'affichage (seuils et couleurs) sont communes à toutes les espèces. Elles sont
définies dans `config/settings.yaml`, rubrique `affichage`.

## Étape 4 : pipeline quotidien

```bash
make pipeline                    # cartes du jour : J-7 à J+7, 5 espèces
make pipeline DATE=2026-10-15    # rejouer un run
```

`make pipeline` lance si nécessaire l'ingestion et l'habitat, puis :
1. `myco meteo` : ≈ 1 600 points Open-Meteo (maille de 2,5 km), de J-21 à J+7. Le
   téléchargement prend ≈ 8 min pour respecter la limite de l'API gratuite. Les réponses sont
   mises en cache dans `data/runs/<date>/meteo/cache/` (`--rafraichir` pour les ignorer).
2. `myco score` : S = H × M à 25 m, avec température et gel corrigés de l'altitude (−0,65 °C
   par 100 m), puis une carte PMTiles par espèce et par date dans
   `web/data/runs/<date>/<espece>/<date>.pmtiles`, et `web/data/latest.json`
   (≈ 10 min, 88 Mo par run).

Les 3 derniers runs sont conservés (`meteo.retention_runs`). Pour une mise à jour quotidienne,
planifiez `make pipeline` avec cron, par exemple à 6 h.

## Étape 6 : PWA

```bash
make web      # construit l'application dans web/dist
make serve    # Nginx (Docker) : http://localhost:8080, PWA + données de web/data sous /data/
cd web && npm run dev   # développement (Vite), données servies depuis web/data
```

L'application, en Vite, TypeScript et MapLibre GL JS, lit `data/latest.json`. Elle affiche la
carte de l'espèce et de la date choisies (J-7 à J+7), la légende, et une bascule « habitat
seul ». Au premier lancement, un avertissement sur les risques d'intoxication doit être accepté.
L'application ne propose aucune fonction d'identification.

**Hors ligne** : le service worker garde l'application et les tuiles du fond Plan IGN déjà
consultées. La page met en cache le fichier PMTiles complet de la dernière carte affichée
(≈ 1,5 Mo), puis le service worker le sert par plages d'octets. Hors ligne, l'application
rouvre cette carte et l'indique par un bandeau.

**Hébergement** : n'importe quel serveur statique qui gère les requêtes HTTP Range (Nginx,
stockage objet S3 ou équivalent, GitHub Pages…). L'installation sur mobile exige HTTPS, sauf
sur `localhost`. Les fichiers `index.html`, `sw.js` et `data/` doivent être revalidés à chaque
visite (voir `web/nginx.conf`).

## Tests

```bash
make test   # tests sur données synthétiques, sans réseau
make lint
```

Tests de bout en bout de la PWA (Playwright, Chromium) : `make test-web`. Ils utilisent les
données présentes dans `web/data` et vérifient l'avertissement, les sélecteurs, l'installation
(manifeste, service worker) et la réouverture de la dernière carte hors ligne.

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
