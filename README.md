# En Train Alain — V14.2

## À ajouter au dépôt GitHub

- Remplacer `app.py` par celui fourni.
- Ajouter `data/destination_map.csv`.
- Ne pas supprimer ni remplacer les 5 fichiers de données SNCF déjà présents dans `data/`.

## Ce que change V14.2

- Sépare la couche éditoriale des destinations des données de transport.
- Les trajets continuent à utiliser les gares réelles pour calculer les itinéraires.
- Les gares peuvent être regroupées sous une destination éditoriale.
- Longueau est actuellement regroupée sous Amiens.
- Le reste des gares conserve par défaut son propre nom de destination : aucune classification éditoriale spéculative n'est ajoutée.
- Le moteur de correspondances évite désormais de rescanner tout le GTFS à chaque candidat de deuxième train.
- Le tarif de référence cherche d'abord la destination éditoriale, puis la gare réelle en secours.

## Important

Cette couche `destination_map.csv` est indépendante du fournisseur de transport. Elle pourra être conservée lorsque les prix et disponibilités viendront d'une API comme Tictactrip.
