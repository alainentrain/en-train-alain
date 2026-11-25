# En Train Alain — V11.1

Prototype Streamlit basé sur V10.

## V11.1
- Horaires SNCF réels via GTFS.
- Allers et retours affichés séparément.
- Trajets directs conservés.
- Ajout de trajets à 1 correspondance.
- Directs et correspondances sont mélangés dans le classement des destinations.
- Budget et durée restent des critères de scoring indicatifs.
- Les prix restent des tarifs de référence, pas des prix temps réel.

## Données
Conserver le dossier `data/` déjà présent dans le projet avec les 5 fichiers :
`calendar_dates.csv`, `routes.csv`, `stations.csv`, `tarifs-tgv-inoui-ouigo.csv`, `trip_stops.csv.gz`.

## Déploiement
Remplacer uniquement `app.py` et `README.md`. Conserver `requirements.txt` et le dossier `data/` existants.
