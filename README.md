# 🚆 En Train Alain — prototype V1

> Tu as un budget. On trouve où partir.

Prototype mobile-first de **En Train Alain**, un moteur de découverte de destinations en train.

## Lancer localement

```bash
pip install -r requirements.txt
streamlit run app.py
```

Puis ouvrir l'URL indiquée par Streamlit.

## Déployer gratuitement sur Streamlit Community Cloud

1. Créer un dépôt GitHub, par exemple `en-train-alain`.
2. Mettre **les fichiers du projet à la racine du dépôt**.
3. Aller sur Streamlit Community Cloud.
4. Connecter le compte GitHub.
5. Choisir le dépôt `en-train-alain`.
6. Choisir `app.py` comme fichier principal.
7. Déployer.

L'application démarre immédiatement en **mode démo**, sans clé API.

## Architecture

```text
Utilisateur
   ↓
Recherche budget / départ / date / durée / envie
   ↓
Moteur En Train Alain
   ↓
Données ouvertes / horaires / tarifs de référence / MAX
   ↓
Candidats destinations
   ↓
Deal Score
   ↓
Top destinations
   ↓
API commerciale (ex. Tictactrip)
   ↓
Prix + disponibilité actuels
   ↓
Redirection / réservation
```

## Important

Les prix du prototype sont **indicatifs**. Ils ne sont pas des prix de vente en temps réel.

La prochaine étape consiste à remplacer progressivement les données de démonstration par :
- open data SNCF pour la couverture ferroviaire et les horaires ;
- données tarifaires de référence ;
- disponibilité MAX lorsque pertinente ;
- API commerciale pour vérifier le prix réel et la disponibilité avant affichage d'une offre réservable.

## Structure

- `app.py` : interface Streamlit
- `engine.py` : recherche et génération des destinations
- `scoring.py` : calcul du Deal Score
- `data_sources.py` : futurs connecteurs API
- `requirements.txt` : dépendances
