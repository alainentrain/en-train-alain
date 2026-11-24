# En Train Alain — V10

V10 est la version propre du prototype SNCF réel.

## Ce que fait V10

- utilise les horaires SNCF GTFS réels présents dans `data/`
- cherche des destinations ferroviaires hors du bassin parisien immédiat
- affiche plusieurs **allers disponibles**
- affiche plusieurs **retours disponibles**
- ne fabrique pas une combinaison aller/retour imposée
- accepte les trajets directs et, si nécessaire, les trajets avec 1 correspondance
- garde les tarifs SNCF comme **références indicatives**, pas comme prix temps réel
- affiche clairement la version V10

## Données attendues

Conserver dans `data/` les fichiers déjà présents dans le dépôt :

- `stations.csv`
- `routes.csv`
- `calendar_dates.csv`
- `trip_stops.csv.gz`
- `tarifs-tgv-inoui-ouigo.csv`

## Installation

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Important

V10 ne connaît toujours pas les prix de vente en temps réel. La prochaine étape commerciale/technique reste le branchement d'une API tarifaire/availability (par exemple Tictactrip) sur les destinations prometteuses.
