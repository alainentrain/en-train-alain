# En Train Alain — V13

Prototype de découverte de destinations en train depuis Paris.

## V13
- horaires SNCF réels issus du GTFS
- destinations présentées sous forme de cartes
- allers et retours affichés séparément
- suppression du doublon « Allers disponibles »
- correspondances d'un trajet seulement lorsque nécessaire
- tarifs indicatifs lorsqu'une référence est disponible

## Données
Conserver dans `data/` les fichiers SNCF déjà utilisés par la version précédente :
- `stations.csv`
- `routes.csv`
- `calendar_dates.csv`
- `trip_stops.csv.gz`
- `tarifs-tgv-inoui-ouigo.csv`
