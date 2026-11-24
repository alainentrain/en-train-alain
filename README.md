# En Train Alain — prototype V3

## Ce que cette version corrige

- recherche avec **date d'aller**
- recherche avec **date de retour**
- budget interprété comme **budget maximum A/R**
- durée maximale appliquée à l'aller **et** au retour
- le moteur recalcule les tarifs indicatifs selon les mois sélectionnés
- les résultats sont explicitement présentés comme **indicatifs**, et non comme des prix disponibles en temps réel

## Important

Cette V3 n'est pas encore connectée à un inventaire commercial en temps réel.

Le jeu `DEMO_ROUTES` sert à tester le comportement du moteur et de l'interface.

### Architecture cible

```text
Utilisateur
   ↓
Critères : départ + aller + retour + budget + durée + envie
   ↓
Moteur En Train Alain
   ↓
SNCF Open Data / autres données ouvertes
   ↓
candidats
   ↓
Deal Score
   ↓
20 meilleures destinations
   ↓
Tictactrip
   ↓
prix + disponibilité réellement vérifiés
   ↓
redirection réservation
```

## Lancer localement

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Déployer sur Streamlit Community Cloud

1. Mettre ces fichiers dans un dépôt GitHub public ou accessible à Streamlit.
2. Ouvrir Streamlit Community Cloud.
3. Choisir le dépôt.
4. Choisir `app.py` comme fichier principal.
5. Deploy.

## Prochaine étape technique

Remplacer progressivement `DEMO_ROUTES` par des données réelles :

- réseau / gares / horaires : Open Data SNCF
- tarifs de référence : Open Data SNCF
- prix et disponibilité commerciaux : Tictactrip

Ne jamais présenter un tarif Open Data comme une disponibilité garantie pour une date donnée.
