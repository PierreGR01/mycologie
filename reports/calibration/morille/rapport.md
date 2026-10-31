# Calibrage – Morille

Généré le 31/10/2026. Taxons : Morchella.

> **Rapport de diagnostic.** Les règles de `config/especes/morille.yaml` ne sont pas modifiées automatiquement.

## Données

| | Nombre |
|---|---:|
| Observations GBIF dans le département (≥ 2005, CC0, CC BY, CC BY-NC) | 40 |
| … datées au jour près (phénologie) | 40 |
| … localisées à ≤ 3000 m (habitat, météo) | 31 |
| Fond « target-group » : observations de champignons localisées | 25125 |

Principaux jeux de données (GBIF) :

- 50c9509d-22c7-4a22-a47d-8c48425ef4a7 : 15
- 96cb0072-426e-4c30-875d-9201aecc15ff : 5
- 0155b886-98a0-4d3e-88b2-9fd0513e647e : 5
- f43dadbd-df8d-4db2-95f4-e69872c4384c : 5
- 26dfdca2-d8a1-4135-a03a-b669b67eb187 : 4
- 258c29cc-51f6-43f5-b702-3a833921a008 : 2

Requête GBIF : https://api.gbif.org/v1/occurrence/search?hasCoordinate=true&hasGeospatialIssue=false&occurrenceStatus=PRESENT&decimalLatitude=44.6959,45.8834&decimalLongitude=4.7420,6.3593&year=2005,2026&license=CC0_1_0,CC_BY_4_0,CC_BY_NC_4_0

## Phénologie

![Phénologie](phenologie.png)

Observations hors de la fenêtre saisonnière du modèle : **0 %**.

## Habitat

L'habitat est moyenné dans le cercle d'incertitude de chaque observation, puis comparé au même calcul sur le fond.

![Habitat](habitat.png)

- AUC observations / fond : 0.51 (faible)
- Indice de Boyce continu : 0.30 (faible)

### Composition : essences

Part moyenne de chaque classe dans les cercles (observations et fond), et valeur attribuée par la règle.

|  | valeur_regle | part_observations | part_fond | ratio |
|---|---|---|---|---|
| melange_feuillus | 0.70 | 0.42 | 0.36 | 1.16 |
| sapin_epicea | 0.80 | 0.29 | 0.27 | 1.07 |
| chataignier | 0.20 | 0.07 | 0.08 | 0.96 |
| mixte_feuillus | 0.50 | 0.06 | 0.08 | 0.83 |
| mixte_coniferes | 0.70 | 0.07 | 0.06 | 1.16 |
| chenes_decidus | 0.40 | 0.04 | 0.05 | 0.82 |
| autres_feuillus | 0.80 | 0.03 | 0.02 | 1.07 |
| foret_ouverte | 0.60 | 0.00 | 0.02 | 0.10 |
| hetre | 0.30 | 0.00 | 0.02 | 0.20 |
| pin_sylvestre | 0.30 | 0.00 | 0.01 | 0.09 |
| peupleraie | 0.80 | 0.00 | 0.01 | 0.17 |
| melange_coniferes | 0.70 | 0.01 | 0.01 | 1.11 |
| douglas | 0.10 | 0.00 | 0.00 | 0.26 |
| robinier | 0.30 | 0.00 | 0.00 | 0.00 |
| autres_pins | 0.30 | 0.00 | 0.00 | 0.00 |
| meleze | 0.80 | 0.00 | 0.00 | 0.00 |

### Composition : substrat

Part moyenne de chaque classe dans les cercles (observations et fond), et valeur attribuée par la règle.

|  | valeur_regle | part_observations | part_fond | ratio |
|---|---|---|---|---|
| detritique_mixte | 0.80 | 0.34 | 0.31 | 1.08 |
| calcaire | 0.90 | 0.35 | 0.28 | 1.22 |
| marno_calcaire | 0.90 | 0.15 | 0.18 | 0.85 |
| alluvions_recentes | 1.00 | 0.11 | 0.13 | 0.83 |
| siliceux | 0.50 | 0.00 | 0.07 | 0.06 |
| indetermine | 0.60 | 0.05 | 0.03 | 1.92 |

## Météo à la date d'observation

Score M calculé avec la météo historique (Open-Meteo, ERA5-Land et ERA5), à l'altitude médiane des forêts du cercle, comparé aux autres jours de la saison au même endroit.

![Météo](meteo.png)

- AUC temporelle : 0.59 (faible)
- Sous-scores moyens le jour observé : pluie_15j 0.81, tmoy_7j 0.75, amplitude_7j 0.99, saison 1.00, gel 0.84

Valeurs des indicateurs les jours d'observation (déciles 10 et 90, médiane), comparées aux seuils du trapèze de la règle :

|  | seuils_regle | p10 | mediane | p90 | sous_score_moyen | jours_a_zero_pct |
|---|---|---|---|---|---|---|
| pluie_15j | 15 / 30 / 120 / 250 | 14.50 | 47.20 | 104.30 | 0.81 | 16.13 |
| tmoy_7j | 6 / 9 / 15 / 20 | 5.91 | 10.07 | 12.24 | 0.75 | 19.35 |
| amplitude_7j | 4 / 8 / 15 / 20 | 7.96 | 9.61 | 11.53 | 0.99 | 0.00 |

## Règles à revoir

- Habitat : AUC 0.51, le modèle distingue mal les zones observées du fond.
- Météo : AUC temporelle 0.59, les jours observés ne sont pas nettement mieux notés que les autres jours.
