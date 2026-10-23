# Calibrage – Pied-de-mouton

Généré le 23/10/2026. Taxons : Hydnum repandum.

> **Rapport de diagnostic.** Les règles de `config/especes/pied_de_mouton.yaml` ne sont pas modifiées automatiquement.
> **Provisoire** : habitat calculé sans la carte géologique BRGM (serveur indisponible) : rapports à régénérer après son intégration.

## Données

| | Nombre |
|---|---:|
| Observations GBIF dans le département (≥ 2005, CC0 / CC BY) | 56 |
| … datées au jour près (phénologie) | 56 |
| … localisées à ≤ 3000 m (habitat, météo) | 51 |
| Fond « target-group » : observations de champignons localisées | 24163 |

Principaux jeux de données (GBIF) :

- 0155b886-98a0-4d3e-88b2-9fd0513e647e : 26
- 96cb0072-426e-4c30-875d-9201aecc15ff : 6
- 130d809d-87a5-4d74-a113-0fbf30d33e45 : 5
- f43dadbd-df8d-4db2-95f4-e69872c4384c : 4
- 26dfdca2-d8a1-4135-a03a-b669b67eb187 : 3
- d96a57d7-72ff-49af-a186-2e0aa74ea527 : 3

Requête GBIF : https://api.gbif.org/v1/occurrence/search?hasCoordinate=true&hasGeospatialIssue=false&occurrenceStatus=PRESENT&decimalLatitude=44.6959,45.8834&decimalLongitude=4.7420,6.3593&year=2005,2026&license=CC0_1_0,CC_BY_4_0

## Phénologie

![Phénologie](phenologie.png)

Observations hors de la fenêtre saisonnière du modèle : **9 %**.

## Habitat

L'habitat est moyenné dans le cercle d'incertitude de chaque observation, puis comparé au même calcul sur le fond.

![Habitat](habitat.png)

- AUC observations / fond : 0.54 (faible)
- Indice de Boyce continu : 0.50 (faible)

### Composition : essences

Part moyenne de chaque classe dans les cercles (observations et fond), et valeur attribuée par la règle.

|  | valeur_regle | part_observations | part_fond | ratio |
|---|---|---|---|---|
| melange_feuillus | 0.90 | 0.36 | 0.37 | 0.98 |
| sapin_epicea | 0.90 | 0.28 | 0.27 | 1.04 |
| chataignier | 0.70 | 0.05 | 0.08 | 0.68 |
| mixte_feuillus | 1.00 | 0.09 | 0.07 | 1.20 |
| mixte_coniferes | 1.00 | 0.06 | 0.06 | 1.06 |
| chenes_decidus | 0.90 | 0.07 | 0.05 | 1.32 |
| foret_ouverte | 0.50 | 0.01 | 0.02 | 0.32 |
| hetre | 1.00 | 0.01 | 0.02 | 0.67 |
| autres_feuillus | 0.70 | 0.02 | 0.02 | 0.90 |
| pin_sylvestre | 0.60 | 0.03 | 0.01 | 2.06 |
| peupleraie | 0.10 | 0.00 | 0.01 | 0.36 |
| melange_coniferes | 0.80 | 0.01 | 0.01 | 0.98 |
| douglas | 0.40 | 0.01 | 0.00 | 2.84 |
| robinier | 0.20 | 0.00 | 0.00 | 0.45 |
| autres_pins | 0.50 | 0.00 | 0.00 | 0.67 |
| meleze | 0.40 | 0.00 | 0.00 | 0.00 |

## Météo à la date d'observation

Score M calculé avec la météo historique (Open-Meteo, ERA5-Land et ERA5), à l'altitude médiane des forêts du cercle, comparé aux autres jours de la saison au même endroit.

![Météo](meteo.png)

- AUC temporelle : 0.59 (faible)
- Sous-scores moyens le jour observé : pluie_15j 0.73, tmoy_7j 0.80, saison 0.92, gel 0.98

Valeurs des indicateurs les jours d'observation (déciles 10 et 90, médiane), comparées aux seuils du trapèze de la règle :

|  | seuils_regle | p10 | mediane | p90 | sous_score_moyen | jours_a_zero_pct |
|---|---|---|---|---|---|---|
| pluie_15j | 20 / 35 / 200 / 350 | 18.00 | 47.60 | 93.80 | 0.73 | 13.73 |
| tmoy_7j | 2 / 6 / 15 / 20 | 8.37 | 13.16 | 18.98 | 0.80 | 5.88 |

## Règles à revoir

- Habitat : AUC 0.54, le modèle distingue mal les zones observées du fond.
- Météo : AUC temporelle 0.59, les jours observés ne sont pas nettement mieux notés que les autres jours.
