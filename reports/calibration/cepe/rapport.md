# Calibrage – Cèpe

Généré le 07/11/2026. Taxons : Boletus edulis, Boletus pinophilus, Boletus aereus, Boletus reticulatus.

> **Rapport de diagnostic.** Les règles de `config/especes/cepe.yaml` ne sont pas modifiées automatiquement.

## Données

| | Nombre |
|---|---:|
| Observations GBIF dans les départements (≥ 2005, CC0, CC BY, CC BY-NC) | 201 |
| … datées au jour près (phénologie) | 201 |
| … localisées à ≤ 3000 m (habitat, météo) | 187 |
| Fond « target-group » : observations de champignons localisées | 30199 |

Principaux jeux de données (GBIF) :

- 0155b886-98a0-4d3e-88b2-9fd0513e647e : 94
- 96cb0072-426e-4c30-875d-9201aecc15ff : 23
- 50c9509d-22c7-4a22-a47d-8c48425ef4a7 : 19
- 26dfdca2-d8a1-4135-a03a-b669b67eb187 : 12
- f1a66948-f513-4746-a8c5-f463c2eed067 : 9
- 130d809d-87a5-4d74-a113-0fbf30d33e45 : 8

Requête GBIF : https://api.gbif.org/v1/occurrence/search?hasCoordinate=true&hasGeospatialIssue=false&occurrenceStatus=PRESENT&decimalLatitude=44.6959,45.8834&decimalLongitude=3.0822,6.3593&year=2005,2026&license=CC0_1_0,CC_BY_4_0,CC_BY_NC_4_0

## Phénologie

![Phénologie](phenologie.png)

Observations hors de la fenêtre saisonnière du modèle : **5 %**.

## Habitat

L'habitat est moyenné dans le cercle d'incertitude de chaque observation, puis comparé au même calcul sur le fond.

![Habitat](habitat.png)

- AUC observations / fond : 0.58 (faible)
- Indice de Boyce continu : 0.63 (correct)

### Composition : essences

Part moyenne de chaque classe dans les cercles (observations et fond), et valeur attribuée par la règle.

|  | valeur_regle | part_observations | part_fond | ratio |
|---|---|---|---|---|
| melange_feuillus | 0.80 | 0.39 | 0.36 | 1.07 |
| sapin_epicea | 0.90 | 0.27 | 0.26 | 1.06 |
| mixte_feuillus | 1.00 | 0.08 | 0.08 | 1.10 |
| chataignier | 0.90 | 0.08 | 0.07 | 1.22 |
| mixte_coniferes | 0.90 | 0.05 | 0.06 | 0.81 |
| chenes_decidus | 0.90 | 0.04 | 0.04 | 0.98 |
| autres_feuillus | 0.60 | 0.02 | 0.03 | 0.63 |
| pin_sylvestre | 0.80 | 0.00 | 0.02 | 0.17 |
| foret_ouverte | 0.50 | 0.02 | 0.02 | 0.67 |
| hetre | 1.00 | 0.01 | 0.02 | 0.42 |
| melange_coniferes | 0.70 | 0.02 | 0.01 | 1.31 |
| peupleraie | 0.00 | 0.00 | 0.01 | 0.32 |
| douglas | 0.40 | 0.01 | 0.00 | 1.44 |
| robinier | 0.10 | 0.00 | 0.00 | 1.57 |
| autres_pins | 0.50 | 0.00 | 0.00 | 0.38 |
| meleze | 0.30 | 0.00 | 0.00 | 0.00 |

### Composition : substrat

Part moyenne de chaque classe dans les cercles (observations et fond), et valeur attribuée par la règle.

|  | valeur_regle | part_observations | part_fond | ratio |
|---|---|---|---|---|
| detritique_mixte | 1.00 | 0.51 | 0.40 | 1.29 |
| calcaire | 0.60 | 0.15 | 0.20 | 0.77 |
| siliceux | 1.00 | 0.10 | 0.17 | 0.59 |
| marno_calcaire | 0.70 | 0.18 | 0.15 | 1.16 |
| alluvions_recentes | 0.40 | 0.04 | 0.07 | 0.65 |
| indetermine | 0.70 | 0.01 | 0.02 | 0.90 |

## Météo à la date d'observation

Météo historique non évaluée.

## Règles à revoir

- Habitat : AUC 0.58, le modèle distingue mal les zones observées du fond.
