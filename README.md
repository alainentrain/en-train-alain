# En Train Alain — V10 corrigée

Cette version :
- utilise les horaires SNCF GTFS réels ;
- affiche les allers et les retours séparément ;
- ne tente pas de fabriquer une combinaison aller/retour ;
- affiche plusieurs horaires disponibles pour chaque destination ;
- écarte les destinations à moins de 70 km du départ pour éviter les trajets locaux type RER/Transilien dans le MVP ;
- conserve les tarifs TGV INOUI/OUIGO comme tarifs indicatifs de référence ;
- corrige l'erreur pandas `The truth value of a DataFrame is ambiguous` observée dans la V8.

## Déploiement

Remplacer `app.py`, `requirements.txt` et `README.md` dans le dépôt GitHub.
Conserver le dossier `data/` avec ses 5 fichiers existants.

Puis attendre le redéploiement Streamlit.
