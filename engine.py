from datetime import date
from scoring import deal_score
from data_sources import DEMO_DESTINATIONS

def find_destinations(depart, budget, departure_date, max_duration, flexibility, vibe):
    candidates = []
    for item in DEMO_DESTINATIONS:
        if depart.strip().lower() not in ["paris", "paris gare de lyon", "paris gare du nord", "paris est", "paris montparnasse"]:
            # Prototype : les données démo sont construites pour un départ de Paris.
            continue
        if item["duration_hours"] > max_duration:
            continue
        if item["price"] > budget:
            continue
        if vibe != "Peu importe" and vibe not in item["vibes"]:
            continue

        score = deal_score(
            price=item["price"],
            duration_hours=item["duration_hours"],
            direct=item["direct"],
            budget=budget,
            reference_price=item["reference_price"],
            appeal=item["appeal"],
        )
        candidates.append({
            **item,
            "score": score,
            "date_label": departure_date.strftime("%d/%m/%Y"),
        })

    candidates.sort(key=lambda x: (-x["score"], x["price"]))
    return candidates[:8]
