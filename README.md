# En Train Alain — V12

V12 améliore le moteur d'escapade à partir de V10.

- horaires SNCF réels issus du GTFS ;
- trajets directs ;
- trajets à 1 correspondance ;
- gare de départ réelle affichée ;
- gare de correspondance et horaires des deux tronçons affichés ;
- temps de correspondance contrôlé ;
- allers et retours recherchés indépendamment ;
- classement des destinations privilégiant la qualité de l'escapade ;
- moins de dépendance à un quota artificiel de 30 résultats.

## Données

Conserver le dossier `data/` déjà présent dans le projet GitHub.

## Installation

```bash
pip install -r requirements.txt
streamlit run app.py
```

Les prix restent des tarifs indicatifs de référence tant que l'API commerciale n'est pas intégrée.
