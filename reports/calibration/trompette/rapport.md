# Calibrage – Trompette de la mort

Généré le 31/10/2026. Taxons : Craterellus cornucopioides.

> **Rapport de diagnostic.** Les règles de `config/especes/trompette.yaml` ne sont pas modifiées automatiquement.

## Données

| | Nombre |
|---|---:|
| Observations GBIF dans le département (≥ 2005, CC0, CC BY, CC BY-NC) | 69 |
| … datées au jour près (phénologie) | 69 |
| … localisées à ≤ 3000 m (habitat, météo) | 68 |
| Fond « target-group » : observations de champignons localisées | 25125 |

Principaux jeux de données (GBIF) :

- 0155b886-98a0-4d3e-88b2-9fd0513e647e : 34
- 130d809d-87a5-4d74-a113-0fbf30d33e45 : 11
- 26dfdca2-d8a1-4135-a03a-b669b67eb187 : 6
- 50c9509d-22c7-4a22-a47d-8c48425ef4a7 : 5
- f43dadbd-df8d-4db2-95f4-e69872c4384c : 4
- d96a57d7-72ff-49af-a186-2e0aa74ea527 : 3

Requête GBIF : https://api.gbif.org/v1/occurrence/search?hasCoordinate=true&hasGeospatialIssue=false&occurrenceStatus=PRESENT&decimalLatitude=44.6959,45.8834&decimalLongitude=4.7420,6.3593&year=2005,2026&license=CC0_1_0,CC_BY_4_0,CC_BY_NC_4_0

## Phénologie

![Phénologie](phenologie.png)

Observations hors de la fenêtre saisonnière du modèle : **6 %**.

## Habitat

L'habitat est moyenné dans le cercle d'incertitude de chaque observation, puis comparé au même calcul sur le fond.

![Habitat](habitat.png)

- AUC observations / fond : 0.54 (faible)
- Indice de Boyce continu : -0.25 (faible)

### Composition : essences

Part moyenne de chaque classe dans les cercles (observations et fond), et valeur attribuée par la règle.

|  | valeur_regle | part_observations | part_fond | ratio |
|---|---|---|---|---|
| melange_feuillus | 0.90 | 0.43 | 0.36 | 1.18 |
| sapin_epicea | 0.40 | 0.28 | 0.27 | 1.02 |
| chataignier | 0.50 | 0.07 | 0.08 | 0.98 |
| mixte_feuillus | 0.90 | 0.07 | 0.08 | 0.90 |
| mixte_coniferes | 0.60 | 0.04 | 0.06 | 0.73 |
| chenes_decidus | 0.50 | 0.02 | 0.05 | 0.43 |
| autres_feuillus | 0.70 | 0.03 | 0.02 | 1.10 |
| foret_ouverte | 0.30 | 0.02 | 0.02 | 0.71 |
| hetre | 1.00 | 0.02 | 0.02 | 1.11 |
| pin_sylvestre | 0.10 | 0.01 | 0.01 | 0.40 |
| peupleraie | 0.10 | 0.01 | 0.01 | 0.83 |
| melange_coniferes | 0.20 | 0.00 | 0.01 | 0.13 |
| douglas | 0.10 | 0.00 | 0.00 | 0.45 |
| robinier | 0.10 | 0.01 | 0.00 | 3.21 |
| autres_pins | 0.00 | 0.00 | 0.00 | 0.48 |
| meleze | 0.00 | 0.00 | 0.00 | 0.00 |

### Composition : substrat

Part moyenne de chaque classe dans les cercles (observations et fond), et valeur attribuée par la règle.

|  | valeur_regle | part_observations | part_fond | ratio |
|---|---|---|---|---|
| detritique_mixte | 0.80 | 0.35 | 0.31 | 1.13 |
| calcaire | 1.00 | 0.32 | 0.28 | 1.14 |
| marno_calcaire | 1.00 | 0.14 | 0.18 | 0.77 |
| alluvions_recentes | 0.60 | 0.14 | 0.13 | 1.08 |
| siliceux | 0.60 | 0.03 | 0.07 | 0.46 |
| indetermine | 0.70 | 0.01 | 0.03 | 0.50 |

## Météo à la date d'observation

Score M calculé avec la météo historique (Open-Meteo, ERA5-Land et ERA5), à l'altitude médiane des forêts du cercle, comparé aux autres jours de la saison au même endroit.

![Météo](meteo.png)

- AUC temporelle : 0.68 (correct)
- Sous-scores moyens le jour observé : pluie_15j 0.82, tmoy_7j 0.91, saison 0.93, gel 0.97

Valeurs des indicateurs les jours d'observation (déciles 10 et 90, médiane), comparées aux seuils du trapèze de la règle :

|  | seuils_regle | p10 | mediane | p90 | sous_score_moyen | jours_a_zero_pct |
|---|---|---|---|---|---|---|
| pluie_15j | 25 / 40 / 200 / 350 | 27.04 | 56.60 | 111.43 | 0.82 | 10.29 |
| tmoy_7j | 5 / 9 / 17 / 22 | 8.30 | 13.14 | 17.21 | 0.91 | 2.94 |

## Règles à revoir

- Habitat : AUC 0.54, le modèle distingue mal les zones observées du fond.
