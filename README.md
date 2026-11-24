# En Train Alain — V6

V6 fait évoluer le prototype vers une logique de recherche d'escapades :

- horaires SNCF réels issus du GTFS déjà préparé ;
- TER / TGV / Intercités inclus lorsqu'ils sont présents comme services ferroviaires ;
- aller + retour ;
- recherche directe en priorité ;
- extension à 1 correspondance si le pool direct est insuffisant ;
- budget A/R ;
- durée maximale par trajet ;
- fenêtre de départ ;
- score de pertinence ;
- tarifs SNCF TGV INOUI / OUIGO affichés uniquement comme références, jamais comme prix temps réel.

## Installation

Conserver le dossier `data/` déjà utilisé par V5.1 à côté de `app.py` :

- `calendar_dates.csv`
- `routes.csv`
- `stations.csv`
- `tarifs-tgv-inoui-ouigo.csv`
- `trip_stops.csv.gz`

Puis déployer sur Streamlit Community Cloud avec `app.py` comme fichier principal.

## Important

V6 ne prétend pas encore connaître le prix réel disponible à une date donnée.
La prochaine brique commerciale sera le branchement de l'API de métarecherche
/ réservation (ex. Tictactrip) après génération des meilleures destinations.
