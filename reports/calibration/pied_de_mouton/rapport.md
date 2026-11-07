# Calibrage – Pied-de-mouton

Généré le 07/11/2026. Taxons : Hydnum repandum.

> **Rapport de diagnostic.** Les règles de `config/especes/pied_de_mouton.yaml` ne sont pas modifiées automatiquement.

## Données

| | Nombre |
|---|---:|
| Observations GBIF dans les départements (≥ 2005, CC0, CC BY, CC BY-NC) | 59 |
| … datées au jour près (phénologie) | 59 |
| … localisées à ≤ 3000 m (habitat, météo) | 52 |
| Fond « target-group » : observations de champignons localisées | 30199 |

Principaux jeux de données (GBIF) :

- 0155b886-98a0-4d3e-88b2-9fd0513e647e : 26
- 96cb0072-426e-4c30-875d-9201aecc15ff : 6
- 130d809d-87a5-4d74-a113-0fbf30d33e45 : 5
- f43dadbd-df8d-4db2-95f4-e69872c4384c : 4
- 26dfdca2-d8a1-4135-a03a-b669b67eb187 : 3
- d96a57d7-72ff-49af-a186-2e0aa74ea527 : 3

Requête GBIF : https://api.gbif.org/v1/occurrence/search?hasCoordinate=true&hasGeospatialIssue=false&occurrenceStatus=PRESENT&decimalLatitude=44.6959,45.8834&decimalLongitude=3.0822,6.3593&year=2005,2026&license=CC0_1_0,CC_BY_4_0,CC_BY_NC_4_0

## Phénologie

![Phénologie](phenologie.png)

Observations hors de la fenêtre saisonnière du modèle : **10 %**.

## Habitat

L'habitat est moyenné dans le cercle d'incertitude de chaque observation, puis comparé au même calcul sur le fond.

![Habitat](habitat.png)

- AUC observations / fond : 0.56 (faible)
- Indice de Boyce continu : 0.13 (faible)

### Composition : essences

Part moyenne de chaque classe dans les cercles (observations et fond), et valeur attribuée par la règle.

|  | valeur_regle | part_observations | part_fond | ratio |
|---|---|---|---|---|
| melange_feuillus | 0.90 | 0.36 | 0.36 | 0.98 |
| sapin_epicea | 0.90 | 0.28 | 0.26 | 1.11 |
| mixte_feuillus | 1.00 | 0.09 | 0.08 | 1.16 |
| chataignier | 0.70 | 0.05 | 0.07 | 0.77 |
| mixte_coniferes | 1.00 | 0.06 | 0.06 | 0.98 |
| chenes_decidus | 0.90 | 0.07 | 0.04 | 1.45 |
| autres_feuillus | 0.70 | 0.02 | 0.03 | 0.69 |
| pin_sylvestre | 0.60 | 0.03 | 0.02 | 1.07 |
| foret_ouverte | 0.50 | 0.01 | 0.02 | 0.31 |
| hetre | 1.00 | 0.01 | 0.02 | 0.68 |
| melange_coniferes | 0.80 | 0.01 | 0.01 | 0.39 |
| peupleraie | 0.10 | 0.00 | 0.01 | 0.40 |
| douglas | 0.40 | 0.01 | 0.00 | 2.83 |
| robinier | 0.20 | 0.00 | 0.00 | 0.50 |
| autres_pins | 0.50 | 0.00 | 0.00 | 0.70 |
| meleze | 0.40 | 0.00 | 0.00 | 0.00 |

### Composition : substrat

Part moyenne de chaque classe dans les cercles (observations et fond), et valeur attribuée par la règle.

|  | valeur_regle | part_observations | part_fond | ratio |
|---|---|---|---|---|
| detritique_mixte | 0.90 | 0.52 | 0.40 | 1.30 |
| calcaire | 1.00 | 0.18 | 0.20 | 0.91 |
| siliceux | 0.80 | 0.04 | 0.17 | 0.21 |
| marno_calcaire | 1.00 | 0.19 | 0.15 | 1.25 |
| alluvions_recentes | 0.60 | 0.06 | 0.07 | 0.83 |
| indetermine | 0.80 | 0.02 | 0.02 | 1.03 |

## Météo à la date d'observation

Météo historique non évaluée.

## Règles à revoir

- Phénologie : 10 % des observations hors saison du modèle (févr., avr., juin).
- Habitat : AUC 0.56, le modèle distingue mal les zones observées du fond.
- Substrat « siliceux » : sous-représentée près des observations (× 0.2) mais notée 0.8.
