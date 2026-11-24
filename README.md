# En Train Alain — V7

Prototype Streamlit basé sur les données GTFS SNCF locales.

### V7
- trajets directs à l'aller et au retour ;
- trajets avec une correspondance possible à l'aller ;
- retour direct ou avec une correspondance ;
- contrôle de la durée totale ;
- correction du crash `NaN` lors de l'affichage des durées ;
- conservation des 5 fichiers de données existants dans `data/`.

### Installation
```bash
pip install -r requirements.txt
streamlit run app.py
```

### Données attendues
Conserver dans `data/` :
- `calendar_dates.csv`
- `routes.csv`
- `stations.csv`
- `tarifs-tgv-inoui-ouigo.csv`
- `trip_stops.csv.gz`

Les prix affichés sont des tarifs indicatifs de référence, pas des prix temps réel.
