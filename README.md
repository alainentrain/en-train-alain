# En Train Alain — V12

Base officielle : V10, avec la logique de correspondances de V11 conservée puis corrigée.

## V12
- Les trajets directs sont toujours prioritaires.
- Une correspondance n'est proposée que lorsqu'aucun trajet direct n'existe vers la destination.
- Les faux détours du type Paris → Longueau → Amiens alors qu'un direct existe sont éliminés.
- Les correspondances affichent désormais clairement la gare de correspondance et le parcours.
- Les points d'arrêt routiers/cars sont exclus du MVP ferroviaire, notamment « Paris-Austerlitz Routiere ».
- Les 4 premiers horaires sont visibles et les suivants sont accessibles via « Autres horaires disponibles ».
- Allers et retours restent indépendants : aucune combinaison A/R n'est imposée.

## Données
Conserver dans `data/` les 5 fichiers SNCF déjà utilisés :
- `stations.csv`
- `routes.csv`
- `calendar_dates.csv`
- `trip_stops.csv.gz`
- `tarifs-tgv-inoui-ouigo.csv`
