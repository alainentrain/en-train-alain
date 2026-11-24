from datetime import date
from data_sources import get_routes, Route

VIBES = ["Peu importe", "Week-end", "Culture", "Nature", "Soleil", "Gastronomie"]

def seasonal_factor(d: date) -> float:
    # Démo uniquement : fait varier légèrement le tarif indicatif selon le mois.
    factors = {
        1: 1.00, 2: 0.96, 3: 0.98, 4: 1.02,
        5: 1.06, 6: 1.10, 7: 1.18, 8: 1.14,
        9: 1.04, 10: 0.99, 11: 0.96, 12: 1.03
    }
    return factors[d.month]

def price_for(route: Route, outbound: date, return_date: date) -> float:
    # Démo : moyenne des deux dates, sans prétendre reproduire les prix SNCF réels.
    factor = (seasonal_factor(outbound) + seasonal_factor(return_date)) / 2
    return route.base_price_ar * factor

def duration_score(hours: float, max_hours: float) -> float:
    if hours > max_hours:
        return 0
    # Plus le trajet est court, plus le score est favorable.
    return max(0, min(100, 100 - (hours / max_hours) * 45))

def budget_score(price: float, budget: float) -> float:
    if price > budget:
        return 0
    if budget <= 0:
        return 0
    # Un trajet très en-dessous du budget obtient un meilleur score.
    ratio = price / budget
    return 100 - ratio * 35

def vibe_score(route: Route, vibe: str) -> float:
    if vibe == "Peu importe":
        return 70
    return route.vibes.get(vibe, 0) * 10

def weekend_score(route: Route, outbound: date, return_date: date) -> float:
    days = (return_date - outbound).days
    score = route.vibes.get("Week-end", 0) * 10

    # Petit bonus si l'utilisateur part sur 2 jours ou 3 jours.
    if days in (1, 2, 3):
        score = min(100, score + 5)

    return score

def build_reason(route: Route, vibe: str) -> str:
    if vibe != "Peu importe":
        value = route.vibes.get(vibe, 0)
        if value >= 9:
            return f"Très bonne correspondance avec ton envie « {vibe.lower()} »."
        if value >= 7:
            return f"Bonne correspondance avec ton envie « {vibe.lower()} »."
        return f"Option possible si tu veux surtout respecter le budget et la durée."
    return route.reason

def search_destinations(
    departure: str,
    outbound: date,
    return_date: date,
    budget: float,
    max_duration: float,
    vibe: str,
):
    # V3.1 reste volontairement un prototype : les destinations sont encore
    # issues d'un petit jeu de données de démonstration.
    if departure.strip().lower() != "paris":
        # On conserve le comportement simple du prototype.
        # La prochaine étape remplacera cette logique par les vraies stations/réseaux.
        return []

    results = []

    for route in get_routes():
        price = price_for(route, outbound, return_date)

        if price > budget:
            continue
        if route.outbound_h > max_duration or route.return_h > max_duration:
            continue

        b = budget_score(price, budget)
        d = (
            duration_score(route.outbound_h, max_duration)
            + duration_score(route.return_h, max_duration)
        ) / 2
        v = vibe_score(route, vibe)
        w = weekend_score(route, outbound, return_date)

        # Pondération :
        # budget 35%, durée 25%, vibe 30%, week-end 10%.
        score = round(0.35 * b + 0.25 * d + 0.30 * v + 0.10 * w)

        results.append({
            "destination": route.destination,
            "operator": route.operator,
            "outbound_h": route.outbound_h,
            "return_h": route.return_h,
            "price": price,
            "score": score,
            "vibes": sorted(
                route.vibes.keys(),
                key=lambda k: route.vibes[k],
                reverse=True
            ),
            "reason": build_reason(route, vibe),
        })

    results.sort(key=lambda x: (-x["score"], x["price"]))
    return results[:10]
