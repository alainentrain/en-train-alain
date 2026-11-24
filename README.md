# 🚂 En Train Alain — prototype V1

> Tu as un budget. On trouve où partir.

Prototype mobile-first construit avec Streamlit.

## Déploiement Streamlit

- Repository : `alainentrain/en-train-alain`
- Branch : `main`
- Main file path : `app.py`

## Fonctionnement actuel

Le prototype utilise un jeu de données local pour fonctionner immédiatement sans clé API.

Le moteur :
1. reçoit un départ, un budget, une date, une durée maximale et une envie ;
2. filtre les destinations ;
3. calcule un **Deal Score** ;
4. affiche les meilleures options.

Les prix sont **indicatifs** : ils ne représentent pas une disponibilité commerciale temps réel.

## Prochaine étape

Brancher :
- les données ouvertes SNCF pour le réseau et les horaires ;
- une source commerciale pour vérifier prix/disponibilité ;
- la redirection réservation.

Architecture visée :

`Utilisateur → moteur de découverte → données ouvertes → candidats → score → vérification temps réel → réservation`

## Lancer localement

```bash
pip install -r requirements.txt
streamlit run app.py
```
