# En Train Alain — V5.1

Prototype Streamlit basé sur les horaires SNCF GTFS réels.

## Données locales
- `data/stations.csv` : gares / points d'arrêt ferroviaires
- `data/routes.csv` : lignes SNCF
- `data/calendar_dates.csv` : dates de circulation
- `data/trip_stops.csv.gz` : horaires des arrêts et trajets
- `data/tarifs-tgv-inoui-ouigo.csv` : tarifs indicatifs TGV INOUI / OUIGO

## V5.1 — corrections
- normalisation des `service_id` entre `calendar_dates.csv` et `trip_stops.csv.gz` (le calendrier utilise des identifiants avec zéros en tête) ;
- conservation correcte de l'heure de départ à la gare d'origine lors de la construction d'un trajet ;
- recherche ferroviaire basée sur les trajets `route_type = 2`, ce qui inclut les services ferroviaires régionaux présents dans le GTFS ;
- lorsqu'aucun tarif ouvert n'est disponible, le résultat reste affichable avec « prix à vérifier » au lieu d'être supprimé.

Les prix affichés ne sont pas des prix de vente en temps réel.
