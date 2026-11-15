# Contrat API TerraCI pour le frontend

Le backend expose `POST /api/terraci/recommend/`. Cet endpoint appelle le moteur TerraCI sans remplacer l'analyse existante `POST /api/plots/analyze/`.

## Configuration locale

Copier `.env.example` en `.env`, puis remplacer les valeurs d'exemple par une clé secrète et une URL de base PostgreSQL locales. `.env` est ignoré par Git; ne jamais y mettre des identifiants dans un fichier suivi.

## Requête

Envoyer un objet JSON avec :

- `latitude`, `longitude` : coordonnées WGS84.
- `donnees_environnementales` : tableau de `n` années, chaque année contenant exactement 12 mois, chaque mois contenant 4 nombres dans cet ordre : pluie mensuelle en mm, température en °C, humidité du sol en fraction de 0 à 1, NDVI de -1 à 1. Les valeurs doivent être finies.
- `source_donnees` : description exacte de l'origine des observations; elle est retournée dans la réponse.
- `local_data` (facultatif) : objet contenant notamment `mois_saison` (numéros de mois de 1 à 12) et `culture_actuelle` (culture précédente saisie par l'utilisateur).
- `priorites` (facultatif) : liste parmi `temoin`, `hydrique` et `regeneration`.

Exemple de structure :

```json
{
  "latitude": 7.689,
  "longitude": -5.0284,
  "donnees_environnementales": [
    [
      [80, 30, 0.2, 0.4],
      [80, 30, 0.2, 0.4],
      [80, 30, 0.2, 0.4],
      [80, 30, 0.2, 0.4],
      [80, 30, 0.2, 0.4],
      [80, 30, 0.2, 0.4],
      [80, 30, 0.2, 0.4],
      [80, 30, 0.2, 0.4],
      [80, 30, 0.2, 0.4],
      [80, 30, 0.2, 0.4],
      [80, 30, 0.2, 0.4],
      [80, 30, 0.2, 0.4]
    ]
  ],
  "source_donnees": "NASA POWER et relevés locaux, période à préciser",
  "local_data": {
    "mois_saison": [3, 4, 5, 6, 7],
    "culture_actuelle": "niebe"
  },
  "priorites": ["hydrique"]
}
```

Les valeurs numériques ci-dessus illustrent uniquement le format et ne sont pas des données observées.

## Réponse et limites

La réponse contient `statut`, `rotation_actuelle`, `qualite_donnees`, `avertissements` et `strategies_classement`. Les cultures et seuils du catalogue sont expérimentaux; les scores sont des indicateurs de comparaison, pas des probabilités de rendement ni des conseils agronomiques validés. Une culture maraîchère reconnue mais non scorée (par exemple tomate) renvoie `catalogue_incomplet` et ne reçoit pas de score.

La route exige des données environnementales explicites : elle ne génère pas de données simulées par défaut. Le frontend doit afficher les avertissements et distinguer l'origine des observations des hypothèses du catalogue.
