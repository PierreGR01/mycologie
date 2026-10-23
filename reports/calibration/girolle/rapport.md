# Calibrage – Girolle

Généré le 23/10/2026. Taxons : Cantharellus cibarius.

> **Rapport de diagnostic.** Les règles de `config/especes/girolle.yaml` ne sont pas modifiées automatiquement.
> **Provisoire** : habitat calculé sans la carte géologique BRGM (serveur indisponible) : rapports à régénérer après son intégration.

## Données

| | Nombre |
|---|---:|
| Observations GBIF dans le département (≥ 2005, CC0 / CC BY) | 83 |
| … datées au jour près (phénologie) | 83 |
| … localisées à ≤ 3000 m (habitat, météo) | 79 |
| Fond « target-group » : observations de champignons localisées | 24163 |

Principaux jeux de données (GBIF) :

- 0155b886-98a0-4d3e-88b2-9fd0513e647e : 45
- f43dadbd-df8d-4db2-95f4-e69872c4384c : 9
- 130d809d-87a5-4d74-a113-0fbf30d33e45 : 8
- 96cb0072-426e-4c30-875d-9201aecc15ff : 8
- 26dfdca2-d8a1-4135-a03a-b669b67eb187 : 3
- d38d6841-de2a-4a16-b39e-495402d8592b : 2

Requête GBIF : https://api.gbif.org/v1/occurrence/search?hasCoordinate=true&hasGeospatialIssue=false&occurrenceStatus=PRESENT&decimalLatitude=44.6959,45.8834&decimalLongitude=4.7420,6.3593&year=2005,2026&license=CC0_1_0,CC_BY_4_0

## Phénologie

![Phénologie](phenologie.png)

Observations hors de la fenêtre saisonnière du modèle : **4 %**.

## Habitat

L'habitat est moyenné dans le cercle d'incertitude de chaque observation, puis comparé au même calcul sur le fond.

![Habitat](habitat.png)

- AUC observations / fond : 0.55 (faible)
- Indice de Boyce continu : 0.08 (faible)

### Composition : essences

Part moyenne de chaque classe dans les cercles (observations et fond), et valeur attribuée par la règle.

|  | valeur_regle | part_observations | part_fond | ratio |
|---|---|---|---|---|
| melange_feuillus | 0.80 | 0.36 | 0.37 | 0.97 |
| sapin_epicea | 0.80 | 0.32 | 0.27 | 1.20 |
| chataignier | 0.90 | 0.10 | 0.08 | 1.21 |
| mixte_feuillus | 0.90 | 0.07 | 0.07 | 0.98 |
| mixte_coniferes | 0.80 | 0.05 | 0.06 | 0.87 |
| chenes_decidus | 0.90 | 0.05 | 0.05 | 1.01 |
| foret_ouverte | 0.50 | 0.02 | 0.02 | 0.84 |
| hetre | 1.00 | 0.01 | 0.02 | 0.43 |
| autres_feuillus | 0.60 | 0.02 | 0.02 | 0.71 |
| pin_sylvestre | 0.70 | 0.00 | 0.01 | 0.10 |
| peupleraie | 0.00 | 0.00 | 0.01 | 0.09 |
| melange_coniferes | 0.60 | 0.00 | 0.01 | 0.23 |
| douglas | 0.40 | 0.00 | 0.00 | 0.74 |
| robinier | 0.10 | 0.00 | 0.00 | 0.00 |
| autres_pins | 0.40 | 0.00 | 0.00 | 0.27 |
| meleze | 0.30 | 0.00 | 0.00 | 0.00 |

## Météo à la date d'observation

Score M calculé avec la météo historique (Open-Meteo, ERA5-Land et ERA5), à l'altitude médiane des forêts du cercle, comparé aux autres jours de la saison au même endroit.

![Météo](meteo.png)

- AUC temporelle : 0.61 (correct)
- Sous-scores moyens le jour observé : pluie_15j 0.88, tmoy_7j 0.87, saison 0.97, gel 0.98

Valeurs des indicateurs les jours d'observation (déciles 10 et 90, médiane), comparées aux seuils du trapèze de la règle :

|  | seuils_regle | p10 | mediane | p90 | sous_score_moyen | jours_a_zero_pct |
|---|---|---|---|---|---|---|
| pluie_15j | 15 / 30 / 150 / 300 | 20.06 | 50.40 | 111.14 | 0.88 | 5.06 |
| tmoy_7j | 9 / 13 / 22 / 27 | 11.08 | 14.84 | 18.20 | 0.87 | 5.06 |

## Règles à revoir

- Habitat : AUC 0.55, le modèle distingue mal les zones observées du fond.
