# En Train Alain — V10

Prototype Streamlit de découverte de destinations ferroviaires.

## V10

- utilise les horaires SNCF réels présents dans `data/`
- filtre les destinations trop proches de Paris pour éviter que les résultats soient dominés par les gares RER / Transilien
- conserve les trajets directs et peut utiliser 1 correspondance comme solution de secours
- affiche plusieurs **allers disponibles**
- affiche plusieurs **retours disponibles**
- ne fabrique pas de combinaison aller × retour
- les tarifs sont des références indicatives, pas des prix temps réel
- le Deal Score sert à classer les destinations, pas à annoncer un prix garanti

## Fichiers de données attendus

`data/`
- `stations.csv`
- `routes.csv`
- `calendar_dates.csv`
- `trip_stops.csv.gz`
- `tarifs-tgv-inoui-ouigo.csv`

## Déploiement

Remplacer `app.py`, `requirements.txt` et `README.md` dans le dépôt GitHub.
Conserver le dossier `data/` actuel.

Streamlit Cloud relancera ensuite l'application depuis le nouveau `app.py`.
