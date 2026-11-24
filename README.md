# En Train Alain — V5

Prototype utilisant le GTFS SNCF fourni par l'utilisateur.

## Ce que fait V5
- gares SNCF réelles
- services actifs selon la date
- trajets ferroviaires réels
- horaires aller et retour
- durée réelle
- recherche de destinations accessibles directement
- tarif de référence quand une correspondance avec le dataset tarifaire SNCF est possible

Les prix ne sont pas temps réel. Le booking/commercial API viendra ensuite.

## Lancer
```bash
pip install -r requirements.txt
streamlit run app.py
```
