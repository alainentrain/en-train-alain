from datetime import date
import pandas as pd
from scoring import deal_score

def load_demo_data():
    return pd.DataFrame([
        ["Paris","Lille","Hauts-de-France",1.05,29,"direct","culture","city"],
        ["Paris","Reims","Grand Est",0.75,25,"direct","culture","week-end"],
        ["Paris","Rouen","Normandie",1.45,22,"direct","culture","week-end"],
        ["Paris","Amiens","Hauts-de-France",1.25,20,"direct","culture","week-end"],
        ["Paris","Orléans","Centre-Val de Loire",1.10,20,"direct","culture","week-end"],
        ["Paris","Dijon","Bourgogne",1.40,35,"direct","culture","week-end"],
        ["Paris","Strasbourg","Grand Est",1.85,39,"direct","culture","week-end"],
        ["Paris","Nantes","Pays de la Loire",2.15,49,"direct","culture","week-end"],
        ["Paris","Rennes","Bretagne",1.55,39,"direct","week-end","culture"],
        ["Paris","Tours","Centre-Val de Loire",1.15,25,"direct","culture","week-end"],
        ["Paris","Bordeaux","Nouvelle-Aquitaine",2.10,49,"direct","week-end","romantique"],
        ["Paris","Lyon","Auvergne-Rhône-Alpes",2.05,45,"direct","culture","week-end"],
        ["Paris","Marseille","Provence-Alpes-Côte d'Azur",3.20,55,"direct","mer","soleil"],
        ["Paris","Montpellier","Occitanie",3.25,49,"direct","mer","soleil"],
        ["Paris","Avignon","Provence-Alpes-Côte d'Azur",2.75,45,"direct","culture","week-end"],
        ["Paris","Annecy","Auvergne-Rhône-Alpes",4.05,55,"direct","nature","romantique"],
        ["Paris","La Rochelle","Nouvelle-Aquitaine",2.55,45,"direct","mer","week-end"],
        ["Paris","Bruxelles","Belgique",1.45,39,"direct","culture","week-end"],
        ["Paris","Luxembourg","Luxembourg",2.15,39,"direct","culture","week-end"],
        ["Paris","Londres","Royaume-Uni",2.25,59,"direct","culture","week-end"],
    ], columns=["origin","destination","region","duration","price","direct","vibe1","vibe2"])

def search_destinations(origin, budget, departure, max_duration, vibes):
    df = load_demo_data()
    origin_norm = origin.strip().lower()

    # Demo mode: if the origin is not Paris, keep the same discovery set
    # but adjust the label so the prototype remains usable.
    df = df[(df.price <= budget) & (df.duration <= max_duration)].copy()

    def score_row(row):
        vibe_bonus = 0
        if vibes:
            for v in vibes:
                if v in {row["vibe1"], row["vibe2"]}:
                    vibe_bonus += 5
        base = deal_score(row["price"], row["duration"], row["direct"])
        return min(100, base + vibe_bonus)

    df["score"] = df.apply(score_row, axis=1)
    df["reason"] = df.apply(lambda r: reason(r, vibes), axis=1)
    df = df.sort_values(["score", "price"], ascending=[False, True]).head(20)

    return df.to_dict("records")

def reason(row, vibes):
    if vibes:
        for v in vibes:
            if v in {row["vibe1"], row["vibe2"]}:
                return f"Parfait pour {v}"
    if row["price"] <= 30:
        return "Petit budget"
    if row["duration"] <= 1.5:
        return "Rapide à rejoindre"
    return "Bon rapport trajet/prix"
