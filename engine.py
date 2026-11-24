from datetime import date
from scoring import deal_score


def search_destinations(
    departure,
    departure_date,
    return_date,
    budget,
    max_duration,
    vibe,
    routes,
):
    """
    Prototype de moteur.
    IMPORTANT : les prix du jeu de démonstration sont des prix de référence,
    pas des prix disponibles en temps réel.
    """
    results = []

    for route in routes:
        if route["origin"].lower() != departure.strip().lower():
            continue

        if route["outbound_duration"] > max_duration:
            continue
        if route["return_duration"] > max_duration:
            continue

        # Le budget est désormais explicitement un budget A/R.
        # On ajoute une petite marge saison/date uniquement pour montrer
        # que les dates entrent dans le calcul. Ce n'est PAS un prix réel.
        seasonal_factor = route.get("seasonal_factors", {}).get(
            departure_date.month, 1.0
        )
        return_factor = route.get("return_factors", {}).get(
            return_date.month, 1.0
        )

        outbound_price = route["outbound_reference_price"] * seasonal_factor
        return_price = route["return_reference_price"] * return_factor
        roundtrip = outbound_price + return_price

        if roundtrip > budget:
            continue

        score = deal_score(
            roundtrip_price=roundtrip,
            budget=budget,
            outbound_duration=route["outbound_duration"],
            return_duration=route["return_duration"],
            vibe=vibe,
            destination_vibes=route["vibes"],
        )

        results.append({
            **route,
            "roundtrip_reference_price": roundtrip,
            "score": score,
            "reason": route["description"],
            "departure_date": departure_date,
            "return_date": return_date,
        })

    return sorted(results, key=lambda x: x["score"], reverse=True)
