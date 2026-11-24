# En Train Alain — V10

Prototype Streamlit basé sur les horaires SNCF GTFS réels.

## V10
- Plusieurs horaires d’aller par destination.
- Plusieurs horaires de retour par destination.
- Les horaires sont présentés séparément : aucune combinaison aller × retour n’est imposée dans l’interface.
- Les destinations restent classées par Deal Score.
- Les prix sont des tarifs indicatifs de référence, pas des prix temps réel.

## Fichiers de données requis
Dans `data/` :
- `stations.csv`
- `routes.csv`
- `calendar_dates.csv`
- `trip_stops.csv.gz`
- `tarifs-tgv-inoui-ouigo.csv`

## Déploiement
Le fichier principal est `app.py`. Installer les dépendances avec `requirements.txt`.
