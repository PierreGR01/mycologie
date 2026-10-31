# Calibrage – Cèpe

Généré le 31/10/2026. Taxons : Boletus edulis, Boletus pinophilus, Boletus aereus, Boletus reticulatus.

> **Rapport de diagnostic.** Les règles de `config/especes/cepe.yaml` ne sont pas modifiées automatiquement.

## Données

| | Nombre |
|---|---:|
| Observations GBIF dans le département (≥ 2005, CC0, CC BY, CC BY-NC) | 187 |
| … datées au jour près (phénologie) | 187 |
| … localisées à ≤ 3000 m (habitat, météo) | 180 |
| Fond « target-group » : observations de champignons localisées | 25125 |

Principaux jeux de données (GBIF) :

- 0155b886-98a0-4d3e-88b2-9fd0513e647e : 94
- 96cb0072-426e-4c30-875d-9201aecc15ff : 23
- 26dfdca2-d8a1-4135-a03a-b669b67eb187 : 12
- 50c9509d-22c7-4a22-a47d-8c48425ef4a7 : 11
- f1a66948-f513-4746-a8c5-f463c2eed067 : 9
- 130d809d-87a5-4d74-a113-0fbf30d33e45 : 8

Requête GBIF : https://api.gbif.org/v1/occurrence/search?hasCoordinate=true&hasGeospatialIssue=false&occurrenceStatus=PRESENT&decimalLatitude=44.6959,45.8834&decimalLongitude=4.7420,6.3593&year=2005,2026&license=CC0_1_0,CC_BY_4_0,CC_BY_NC_4_0

## Phénologie

![Phénologie](phenologie.png)

Observations hors de la fenêtre saisonnière du modèle : **3 %**.

## Habitat

L'habitat est moyenné dans le cercle d'incertitude de chaque observation, puis comparé au même calcul sur le fond.

![Habitat](habitat.png)

- AUC observations / fond : 0.56 (faible)
- Indice de Boyce continu : 0.71 (correct)

### Composition : essences

Part moyenne de chaque classe dans les cercles (observations et fond), et valeur attribuée par la règle.

|  | valeur_regle | part_observations | part_fond | ratio |
|---|---|---|---|---|
| melange_feuillus | 0.80 | 0.40 | 0.36 | 1.10 |
| sapin_epicea | 0.90 | 0.27 | 0.27 | 0.99 |
| chataignier | 0.90 | 0.09 | 0.08 | 1.13 |
| mixte_feuillus | 1.00 | 0.09 | 0.08 | 1.13 |
| mixte_coniferes | 0.90 | 0.05 | 0.06 | 0.89 |
| chenes_decidus | 0.90 | 0.05 | 0.05 | 0.93 |
| autres_feuillus | 0.60 | 0.02 | 0.02 | 0.80 |
| foret_ouverte | 0.50 | 0.02 | 0.02 | 0.70 |
| hetre | 1.00 | 0.01 | 0.02 | 0.42 |
| pin_sylvestre | 0.80 | 0.00 | 0.01 | 0.19 |
| peupleraie | 0.00 | 0.00 | 0.01 | 0.30 |
| melange_coniferes | 0.70 | 0.00 | 0.01 | 0.53 |
| douglas | 0.40 | 0.01 | 0.00 | 1.50 |
| robinier | 0.10 | 0.00 | 0.00 | 1.46 |
| autres_pins | 0.50 | 0.00 | 0.00 | 0.35 |
| meleze | 0.30 | 0.00 | 0.00 | 0.00 |

### Composition : substrat

Part moyenne de chaque classe dans les cercles (observations et fond), et valeur attribuée par la règle.

|  | valeur_regle | part_observations | part_fond | ratio |
|---|---|---|---|---|
| detritique_mixte | 1.00 | 0.45 | 0.31 | 1.43 |
| calcaire | 0.60 | 0.21 | 0.28 | 0.76 |
| marno_calcaire | 0.70 | 0.17 | 0.18 | 0.92 |
| alluvions_recentes | 0.40 | 0.09 | 0.13 | 0.66 |
| siliceux | 1.00 | 0.07 | 0.07 | 1.10 |
| indetermine | 0.70 | 0.01 | 0.03 | 0.48 |

## Météo à la date d'observation

Score M calculé avec la météo historique (Open-Meteo, ERA5-Land et ERA5), à l'altitude médiane des forêts du cercle, comparé aux autres jours de la saison au même endroit.

![Météo](meteo.png)

- AUC temporelle : 0.60 (faible)
- Sous-scores moyens le jour observé : pluie_15j 0.79, tmoy_7j 0.86, amplitude_7j 0.97, saison 0.95, gel 0.98

Valeurs des indicateurs les jours d'observation (déciles 10 et 90, médiane), comparées aux seuils du trapèze de la règle :

|  | seuils_regle | p10 | mediane | p90 | sous_score_moyen | jours_a_zero_pct |
|---|---|---|---|---|---|---|
| pluie_15j | 20 / 35 / 150 / 300 | 18.75 | 43.40 | 89.21 | 0.79 | 11.11 |
| tmoy_7j | 8 / 12 / 20 / 25 | 9.69 | 14.61 | 18.79 | 0.86 | 3.89 |
| amplitude_7j | 4 / 8 / 14 / 20 | 6.98 | 9.50 | 11.13 | 0.97 | 0.00 |

## Règles à revoir

- Habitat : AUC 0.56, le modèle distingue mal les zones observées du fond.
- Météo : AUC temporelle 0.60, les jours observés ne sont pas nettement mieux notés que les autres jours.
