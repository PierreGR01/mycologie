# Calibrage – Girolle

Généré le 07/11/2026. Taxons : Cantharellus cibarius.

> **Rapport de diagnostic.** Les règles de `config/especes/girolle.yaml` ne sont pas modifiées automatiquement.

## Données

| | Nombre |
|---|---:|
| Observations GBIF dans les départements (≥ 2005, CC0, CC BY, CC BY-NC) | 93 |
| … datées au jour près (phénologie) | 93 |
| … localisées à ≤ 3000 m (habitat, météo) | 85 |
| Fond « target-group » : observations de champignons localisées | 30199 |

Principaux jeux de données (GBIF) :

- 0155b886-98a0-4d3e-88b2-9fd0513e647e : 45
- f43dadbd-df8d-4db2-95f4-e69872c4384c : 9
- 96cb0072-426e-4c30-875d-9201aecc15ff : 8
- 130d809d-87a5-4d74-a113-0fbf30d33e45 : 8
- 50c9509d-22c7-4a22-a47d-8c48425ef4a7 : 6
- 26dfdca2-d8a1-4135-a03a-b669b67eb187 : 3

Requête GBIF : https://api.gbif.org/v1/occurrence/search?hasCoordinate=true&hasGeospatialIssue=false&occurrenceStatus=PRESENT&decimalLatitude=44.6959,45.8834&decimalLongitude=3.0822,6.3593&year=2005,2026&license=CC0_1_0,CC_BY_4_0,CC_BY_NC_4_0

## Phénologie

![Phénologie](phenologie.png)

Observations hors de la fenêtre saisonnière du modèle : **4 %**.

## Habitat

L'habitat est moyenné dans le cercle d'incertitude de chaque observation, puis comparé au même calcul sur le fond.

![Habitat](habitat.png)

- AUC observations / fond : 0.59 (faible)
- Indice de Boyce continu : -0.05 (faible)

### Composition : essences

Part moyenne de chaque classe dans les cercles (observations et fond), et valeur attribuée par la règle.

|  | valeur_regle | part_observations | part_fond | ratio |
|---|---|---|---|---|
| melange_feuillus | 0.80 | 0.34 | 0.36 | 0.93 |
| sapin_epicea | 0.80 | 0.33 | 0.26 | 1.29 |
| mixte_feuillus | 0.90 | 0.08 | 0.08 | 1.02 |
| chataignier | 0.90 | 0.09 | 0.07 | 1.29 |
| mixte_coniferes | 0.80 | 0.06 | 0.06 | 0.92 |
| chenes_decidus | 0.90 | 0.05 | 0.04 | 1.05 |
| autres_feuillus | 0.60 | 0.01 | 0.03 | 0.51 |
| pin_sylvestre | 0.70 | 0.00 | 0.02 | 0.12 |
| foret_ouverte | 0.50 | 0.02 | 0.02 | 0.85 |
| hetre | 1.00 | 0.01 | 0.02 | 0.68 |
| melange_coniferes | 0.60 | 0.01 | 0.01 | 0.32 |
| peupleraie | 0.00 | 0.00 | 0.01 | 0.09 |
| douglas | 0.40 | 0.00 | 0.00 | 0.72 |
| robinier | 0.10 | 0.00 | 0.00 | 0.00 |
| autres_pins | 0.40 | 0.00 | 0.00 | 0.26 |
| meleze | 0.30 | 0.00 | 0.00 | 0.00 |

### Composition : substrat

Part moyenne de chaque classe dans les cercles (observations et fond), et valeur attribuée par la règle.

|  | valeur_regle | part_observations | part_fond | ratio |
|---|---|---|---|---|
| detritique_mixte | 0.80 | 0.41 | 0.40 | 1.02 |
| calcaire | 0.30 | 0.20 | 0.20 | 1.05 |
| siliceux | 1.00 | 0.12 | 0.17 | 0.74 |
| marno_calcaire | 0.40 | 0.20 | 0.15 | 1.27 |
| alluvions_recentes | 0.30 | 0.06 | 0.07 | 0.80 |
| indetermine | 0.60 | 0.01 | 0.02 | 0.87 |

## Météo à la date d'observation

Météo historique non évaluée.

## Règles à revoir

- Habitat : AUC 0.59, le modèle distingue mal les zones observées du fond.
