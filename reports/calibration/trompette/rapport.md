# Calibrage – Trompette de la mort

Généré le 23/10/2026. Taxons : Craterellus cornucopioides.

> **Rapport de diagnostic.** Les règles de `config/especes/trompette.yaml` ne sont pas modifiées automatiquement.
> **Provisoire** : habitat calculé sans la carte géologique BRGM (serveur indisponible) : rapports à régénérer après son intégration.

## Données

| | Nombre |
|---|---:|
| Observations GBIF dans le département (≥ 2005, CC0 / CC BY) | 65 |
| … datées au jour près (phénologie) | 65 |
| … localisées à ≤ 3000 m (habitat, météo) | 64 |
| Fond « target-group » : observations de champignons localisées | 24163 |

Principaux jeux de données (GBIF) :

- 0155b886-98a0-4d3e-88b2-9fd0513e647e : 34
- 130d809d-87a5-4d74-a113-0fbf30d33e45 : 11
- 26dfdca2-d8a1-4135-a03a-b669b67eb187 : 6
- f43dadbd-df8d-4db2-95f4-e69872c4384c : 4
- d96a57d7-72ff-49af-a186-2e0aa74ea527 : 3
- f3a30e56-c548-44b5-83e9-d85ac61d9bbe : 2

Requête GBIF : https://api.gbif.org/v1/occurrence/search?hasCoordinate=true&hasGeospatialIssue=false&occurrenceStatus=PRESENT&decimalLatitude=44.6959,45.8834&decimalLongitude=4.7420,6.3593&year=2005,2026&license=CC0_1_0,CC_BY_4_0

## Phénologie

![Phénologie](phenologie.png)

Observations hors de la fenêtre saisonnière du modèle : **11 %**.

## Habitat

L'habitat est moyenné dans le cercle d'incertitude de chaque observation, puis comparé au même calcul sur le fond.

![Habitat](habitat.png)

- AUC observations / fond : 0.51 (faible)
- Indice de Boyce continu : 0.01 (faible)

### Composition : essences

Part moyenne de chaque classe dans les cercles (observations et fond), et valeur attribuée par la règle.

|  | valeur_regle | part_observations | part_fond | ratio |
|---|---|---|---|---|
| melange_feuillus | 0.90 | 0.45 | 0.37 | 1.22 |
| sapin_epicea | 0.40 | 0.26 | 0.27 | 0.95 |
| chataignier | 0.50 | 0.08 | 0.08 | 1.00 |
| mixte_feuillus | 0.90 | 0.07 | 0.07 | 0.88 |
| mixte_coniferes | 0.60 | 0.04 | 0.06 | 0.64 |
| chenes_decidus | 0.80 | 0.02 | 0.05 | 0.44 |
| foret_ouverte | 0.30 | 0.02 | 0.02 | 0.73 |
| hetre | 1.00 | 0.03 | 0.02 | 1.15 |
| autres_feuillus | 0.70 | 0.03 | 0.02 | 1.18 |
| pin_sylvestre | 0.10 | 0.01 | 0.01 | 0.43 |
| peupleraie | 0.10 | 0.01 | 0.01 | 0.87 |
| melange_coniferes | 0.20 | 0.00 | 0.01 | 0.12 |
| douglas | 0.10 | 0.00 | 0.00 | 0.46 |
| robinier | 0.10 | 0.01 | 0.00 | 3.32 |
| autres_pins | 0.00 | 0.00 | 0.00 | 0.52 |
| meleze | 0.00 | 0.00 | 0.00 | 0.00 |

## Météo à la date d'observation

Score M calculé avec la météo historique (Open-Meteo, ERA5-Land et ERA5), à l'altitude médiane des forêts du cercle, comparé aux autres jours de la saison au même endroit.

![Météo](meteo.png)

- AUC temporelle : 0.64 (correct)
- Sous-scores moyens le jour observé : pluie_15j 0.66, tmoy_7j 0.91, saison 0.87, gel 0.96

Valeurs des indicateurs les jours d'observation (déciles 10 et 90, médiane), comparées aux seuils du trapèze de la règle :

|  | seuils_regle | p10 | mediane | p90 | sous_score_moyen | jours_a_zero_pct |
|---|---|---|---|---|---|---|
| pluie_15j | 25 / 60 / 200 / 350 | 24.16 | 54.40 | 107.55 | 0.66 | 10.94 |
| tmoy_7j | 5 / 9 / 17 / 22 | 8.37 | 13.39 | 17.34 | 0.91 | 3.12 |

## Règles à revoir

- Phénologie : 11 % des observations hors saison du modèle (janv., avr., juil., déc.).
- Habitat : AUC 0.51, le modèle distingue mal les zones observées du fond.
- Essence « chenes_decidus » : sous-représentée près des observations (× 0.4) mais notée 0.8.
