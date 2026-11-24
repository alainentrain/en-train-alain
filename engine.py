from datetime import date
import pandas as pd

VIBES = {
    "Culture": {"REIMS", "TOURS", "ROUEN", "LILLE", "STRASBOURG", "DIJON"},
    "Mer": {"LA ROCHELLE", "NANTES", "LE HAVRE", "SAINT-MALO"},
    "Nature": {"GRENOBLE", "ANNECY", "DIJON", "CHAMBERY"},
    "Soleil": {"AVIGNON", "NIMES", "MONTPELLIER", "MARSEILLE"},
    "Week-end": {"REIMS", "ROUEN", "TOURS", "LILLE", "AVIGNON"},
}

DURATION = {
    "REIMS": 0.77, "ROUEN": 1.50, "TOURS": 1.25, "LILLE": 1.15,
    "AVIGNON": 2.75, "NIMES": 2.85, "MONTPELLIER": 3.10,
    "MARSEILLE": 3.20, "DIJON": 1.65, "STRASBOURG": 1.90,
    "GRENOBLE": 3.00, "ANNECY": 3.75, "LA ROCHELLE": 2.75,
    "NANTES": 2.25, "LE HAVRE": 2.20, "SAINT-MALO": 2.50,
}

def _clean_city(name):
    name = str(name).upper()
    # Keep the station label readable but collapse common suffixes.
    for suffix in [" GARE SNCF", " RIVE DROITE", " VILLE", " STATION"]:
        name = name.replace(suffix, "")
    return name.title()

def find_destinations(fares, departure, budget, trip_date, max_duration, vibe):
    if fares is None or fares.empty:
        return []

    df = fares.copy()
    rename = {
        "gare_destination": "destination",
        "prix_minimum": "prix_min",
        "transporteur": "transporteur",
    }
    df = df.rename(columns=rename)

    for col in ["destination", "prix_min"]:
        if col not in df.columns:
            return []

    df["prix_min"] = (
        df["prix_min"].astype(str).str.replace("€", "", regex=False)
        .str.replace(",", ".", regex=False).astype(float)
    )
    df["destination_clean"] = df["destination"].map(_clean_city)

    rows = []
    for _, row in df.iterrows():
        city_key = str(row["destination"]).upper()
        city_key = city_key.replace(" GARE SNCF", "").replace(" VILLE", "")
        duration = DURATION.get(city_key, 4.0)

        if row["prix_min"] > budget or duration > max_duration:
            continue

        vibe_bonus = 0
        if vibe in VIBES and city_key in VIBES[vibe]:
            vibe_bonus = 12
        elif vibe == "Peu importe":
            vibe_bonus = 4

        price_score = max(0, 35 - (row["prix_min"] / max(budget, 1)) * 25)
        duration_score = max(0, 25 - duration * 5)
        score = round(min(100, 35 + price_score + duration_score + vibe_bonus))

        rows.append({
            "destination": row["destination_clean"],
            "prix_min": int(round(row["prix_min"])),
            "transporteur": row.get("transporteur", "SNCF"),
            "score": score,
            "date": trip_date.strftime("%d/%m/%Y"),
            "description": (
                "Très bon rapport budget / trajet"
                if score >= 70 else
                "Petit budget, départ simple"
                if row["prix_min"] <= 30 else
                "Option intéressante dans ton budget"
            ),
        })

    # Deduplicate destinations, keeping the cheapest.
    best = {}
    for r in rows:
        key = r["destination"]
        if key not in best or r["prix_min"] < best[key]["prix_min"]:
            best[key] = r

    return sorted(best.values(), key=lambda x: (-x["score"], x["prix_min"]))
