# En Train Alain — V9

V9 recentre la recherche sur de vraies destinations d'escapade et compare plusieurs horaires aller/retour.

## Ce qui change

- Les 3 423 gares SNCF ne sont plus toutes considérées comme des destinations finales.
- Le moteur utilise `data/destinations.csv` comme catalogue éditorial de destinations pertinentes.
- Pour chaque destination, plusieurs trajets directs aller sont analysés.
- Plusieurs trajets directs retour sont analysés.
- Le moteur compare les combinaisons aller/retour et choisit celle qui obtient le meilleur Deal Score.
- Les autres horaires intéressants sont accessibles dans « Voir d'autres horaires ».
- Les vraies gares de départ et d'arrivée sont affichées.
- La recherche est faite en lots : une recherche aller pour les destinations puis une recherche retour pour toutes les destinations, au lieu de lancer une recherche séparée pour chaque gare.

## Choix volontaire de cette V9

Les correspondances ne sont pas utilisées dans cette version. C'est volontaire : la V8.x montrait que le moteur de correspondances pouvait produire des résultats peu pertinents (gares intermédiaires, itinéraires absurdes) et ralentir fortement la recherche.

La prochaine étape pourra réintroduire les correspondances avec un moteur dédié et optimisé, après validation de la logique « destination + plusieurs horaires ».

## Données

À conserver dans `data/` :

- `stations.csv`
- `routes.csv`
- `calendar_dates.csv`
- `trip_stops.csv.gz`
- `tarifs-tgv-inoui-ouigo.csv`
- `destinations.csv`

Les prix restent indicatifs jusqu'au branchement d'une API commerciale temps réel.

## Déploiement

Remplacer :

- `app.py`
- `README.md`
- `requirements.txt`

et conserver les fichiers de données déjà présents dans `data/`.
