# Calibrage – Morille

Généré le 23/10/2026. Taxons : Morchella.

> **Rapport de diagnostic.** Les règles de `config/especes/morille.yaml` ne sont pas modifiées automatiquement.
> **Provisoire** : habitat calculé sans la carte géologique BRGM (serveur indisponible) : rapports à régénérer après son intégration.

## Données

| | Nombre |
|---|---:|
| Observations GBIF dans le département (≥ 2005, CC0 / CC BY) | 27 |
| … datées au jour près (phénologie) | 27 |
| … localisées à ≤ 3000 m (habitat, météo) | 24 |
| Fond « target-group » : observations de champignons localisées | 24163 |

Principaux jeux de données (GBIF) :

- f43dadbd-df8d-4db2-95f4-e69872c4384c : 5
- 0155b886-98a0-4d3e-88b2-9fd0513e647e : 5
- 96cb0072-426e-4c30-875d-9201aecc15ff : 5
- 26dfdca2-d8a1-4135-a03a-b669b67eb187 : 4
- 50c9509d-22c7-4a22-a47d-8c48425ef4a7 : 2
- 794521f5-7fc1-4d91-9464-0d56e6a23725 : 2

Requête GBIF : https://api.gbif.org/v1/occurrence/search?hasCoordinate=true&hasGeospatialIssue=false&occurrenceStatus=PRESENT&decimalLatitude=44.6959,45.8834&decimalLongitude=4.7420,6.3593&year=2005,2026&license=CC0_1_0,CC_BY_4_0

## Phénologie

![Phénologie](phenologie.png)

Observations hors de la fenêtre saisonnière du modèle : **0 %**.

## Habitat

L'habitat est moyenné dans le cercle d'incertitude de chaque observation, puis comparé au même calcul sur le fond.

![Habitat](habitat.png)

- AUC observations / fond : 0.47 (faible)
- Indice de Boyce continu : -0.22 (faible)

### Composition : essences

Part moyenne de chaque classe dans les cercles (observations et fond), et valeur attribuée par la règle.

|  | valeur_regle | part_observations | part_fond | ratio |
|---|---|---|---|---|
| melange_feuillus | 0.70 | 0.41 | 0.37 | 1.11 |
| sapin_epicea | 0.80 | 0.26 | 0.27 | 0.96 |
| chataignier | 0.20 | 0.10 | 0.08 | 1.21 |
| mixte_feuillus | 0.50 | 0.06 | 0.07 | 0.79 |
| mixte_coniferes | 0.70 | 0.08 | 0.06 | 1.49 |
| chenes_decidus | 0.40 | 0.05 | 0.05 | 1.04 |
| foret_ouverte | 0.60 | 0.00 | 0.02 | 0.12 |
| hetre | 0.30 | 0.01 | 0.02 | 0.26 |
| autres_feuillus | 0.80 | 0.03 | 0.02 | 1.33 |
| pin_sylvestre | 0.30 | 0.00 | 0.01 | 0.12 |
| peupleraie | 0.80 | 0.00 | 0.01 | 0.21 |
| melange_coniferes | 0.70 | 0.00 | 0.01 | 0.22 |
| douglas | 0.10 | 0.00 | 0.00 | 0.16 |
| robinier | 0.30 | 0.00 | 0.00 | 0.00 |
| autres_pins | 0.30 | 0.00 | 0.00 | 0.00 |
| meleze | 0.80 | 0.00 | 0.00 | 0.00 |

## Météo à la date d'observation

Score M calculé avec la météo historique (Open-Meteo, ERA5-Land et ERA5), à l'altitude médiane des forêts du cercle, comparé aux autres jours de la saison au même endroit.

![Météo](meteo.png)

- AUC temporelle : 0.66 (correct)
- Sous-scores moyens le jour observé : pluie_15j 0.80, tmoy_7j 0.84, amplitude_7j 0.99, saison 1.00, gel 0.88

Valeurs des indicateurs les jours d'observation (déciles 10 et 90, médiane), comparées aux seuils du trapèze de la règle :

|  | seuils_regle | p10 | mediane | p90 | sous_score_moyen | jours_a_zero_pct |
|---|---|---|---|---|---|---|
| pluie_15j | 15 / 30 / 120 / 250 | 14.50 | 46.75 | 104.30 | 0.80 | 16.67 |
| tmoy_7j | 6 / 9 / 15 / 20 | 6.61 | 10.37 | 12.51 | 0.84 | 4.17 |
| amplitude_7j | 4 / 8 / 15 / 20 | 7.65 | 9.55 | 12.51 | 0.99 | 0.00 |

## Règles à revoir

- Habitat : AUC 0.47, le modèle distingue mal les zones observées du fond.
