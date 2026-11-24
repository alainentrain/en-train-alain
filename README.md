# 🚂 En Train Alain — prototype V2

> **Tu as un budget. On trouve où partir.**

Prototype Streamlit mobile-first.

## Ce qui change dans la V2

Le moteur ne repose plus uniquement sur le jeu de données fictif de la V1.

Il interroge le jeu officiel **SNCF Open Data — Tarifs TGV INOUI et OUIGO** lorsqu'il est accessible.

Ce jeu contient des **prix minimum / maximum par origine-destination et profil tarifaire**. Il est mis à jour annuellement. Il ne s'agit donc pas d'un prix temps réel pour un train donné.

Source officielle :
https://ressources.data.sncf.com/explore/dataset/tarifs-tgv-inoui-ouigo/

Pour les horaires et le temps réel, SNCF publie également des données GTFS/GTFS-RT et une API SNCF.

## Architecture

Utilisateur
→ moteur de découverte
→ données SNCF Open Data
→ candidats
→ Deal Score
→ vérification commerciale temps réel
→ réservation

## Lancer

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Déploiement Streamlit

- Repository : `alainentrain/en-train-alain`
- Branch : `main`
- Main file : `app.py`

## Prochaine étape

Connecter une source commerciale (par exemple Tictactrip) pour vérifier :
- prix réellement disponibles à la date demandée ;
- disponibilité ;
- itinéraire précis ;
- lien de réservation.

**Ne jamais présenter le prix Open Data comme un prix garanti ou temps réel.**
