# Calibrage – Girolle

Généré le 31/10/2026. Taxons : Cantharellus cibarius.

> **Rapport de diagnostic.** Les règles de `config/especes/girolle.yaml` ne sont pas modifiées automatiquement.

## Données

| | Nombre |
|---|---:|
| Observations GBIF dans le département (≥ 2005, CC0, CC BY, CC BY-NC) | 91 |
| … datées au jour près (phénologie) | 91 |
| … localisées à ≤ 3000 m (habitat, météo) | 84 |
| Fond « target-group » : observations de champignons localisées | 25125 |

Principaux jeux de données (GBIF) :

- 0155b886-98a0-4d3e-88b2-9fd0513e647e : 45
- f43dadbd-df8d-4db2-95f4-e69872c4384c : 9
- 96cb0072-426e-4c30-875d-9201aecc15ff : 8
- 130d809d-87a5-4d74-a113-0fbf30d33e45 : 8
- 50c9509d-22c7-4a22-a47d-8c48425ef4a7 : 6
- 26dfdca2-d8a1-4135-a03a-b669b67eb187 : 3

Requête GBIF : https://api.gbif.org/v1/occurrence/search?hasCoordinate=true&hasGeospatialIssue=false&occurrenceStatus=PRESENT&decimalLatitude=44.6959,45.8834&decimalLongitude=4.7420,6.3593&year=2005,2026&license=CC0_1_0,CC_BY_4_0,CC_BY_NC_4_0

## Phénologie

![Phénologie](phenologie.png)

Observations hors de la fenêtre saisonnière du modèle : **3 %**.

## Habitat

L'habitat est moyenné dans le cercle d'incertitude de chaque observation, puis comparé au même calcul sur le fond.

![Habitat](habitat.png)

- AUC observations / fond : 0.57 (faible)
- Indice de Boyce continu : 0.33 (faible)

### Composition : essences

Part moyenne de chaque classe dans les cercles (observations et fond), et valeur attribuée par la règle.

|  | valeur_regle | part_observations | part_fond | ratio |
|---|---|---|---|---|
| melange_feuillus | 0.80 | 0.34 | 0.36 | 0.94 |
| sapin_epicea | 0.80 | 0.33 | 0.27 | 1.23 |
| chataignier | 0.90 | 0.09 | 0.08 | 1.16 |
| mixte_feuillus | 0.90 | 0.08 | 0.08 | 1.00 |
| mixte_coniferes | 0.80 | 0.06 | 0.06 | 0.96 |
| chenes_decidus | 0.90 | 0.05 | 0.05 | 0.97 |
| autres_feuillus | 0.60 | 0.01 | 0.02 | 0.65 |
| foret_ouverte | 0.50 | 0.02 | 0.02 | 0.88 |
| hetre | 1.00 | 0.01 | 0.02 | 0.67 |
| pin_sylvestre | 0.70 | 0.00 | 0.01 | 0.09 |
| peupleraie | 0.00 | 0.00 | 0.01 | 0.08 |
| melange_coniferes | 0.60 | 0.00 | 0.01 | 0.22 |
| douglas | 0.40 | 0.00 | 0.00 | 0.72 |
| robinier | 0.10 | 0.00 | 0.00 | 0.00 |
| autres_pins | 0.40 | 0.00 | 0.00 | 0.24 |
| meleze | 0.30 | 0.00 | 0.00 | 0.00 |

### Composition : substrat

Part moyenne de chaque classe dans les cercles (observations et fond), et valeur attribuée par la règle.

|  | valeur_regle | part_observations | part_fond | ratio |
|---|---|---|---|---|
| detritique_mixte | 0.80 | 0.32 | 0.31 | 1.02 |
| calcaire | 0.30 | 0.28 | 0.28 | 1.00 |
| marno_calcaire | 0.40 | 0.17 | 0.18 | 0.95 |
| alluvions_recentes | 0.30 | 0.10 | 0.13 | 0.80 |
| siliceux | 1.00 | 0.12 | 0.07 | 1.80 |
| indetermine | 0.60 | 0.00 | 0.03 | 0.06 |

## Météo à la date d'observation

Score M calculé avec la météo historique (Open-Meteo, ERA5-Land et ERA5), à l'altitude médiane des forêts du cercle, comparé aux autres jours de la saison au même endroit.

![Météo](meteo.png)

- AUC temporelle : 0.61 (correct)
- Sous-scores moyens le jour observé : pluie_15j 0.87, tmoy_7j 0.87, saison 0.97, gel 0.98

Valeurs des indicateurs les jours d'observation (déciles 10 et 90, médiane), comparées aux seuils du trapèze de la règle :

|  | seuils_regle | p10 | mediane | p90 | sous_score_moyen | jours_a_zero_pct |
|---|---|---|---|---|---|---|
| pluie_15j | 15 / 30 / 150 / 300 | 19.20 | 50.50 | 109.40 | 0.87 | 4.76 |
| tmoy_7j | 9 / 13 / 22 / 27 | 11.16 | 14.83 | 18.53 | 0.87 | 4.76 |

## Règles à revoir

- Habitat : AUC 0.57, le modèle distingue mal les zones observées du fond.
