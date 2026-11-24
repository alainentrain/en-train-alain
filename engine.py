from data_sources import DESTINATION_PROFILES

def seasonal_price(base_price, month, factors):
    return base_price * factors.get(month, 1.0)

def vibe_match(profile, vibe):
    return 0.70 if vibe == "Peu importe" else profile["vibes"].get(vibe, 0.0)

def score_destination(profile, price, budget, total_hours, max_hours, vibe):
    budget_ratio = max(0.0, min(1.0, 1 - (price / max(budget, 1)) * 0.55))
    time_ratio = max(0.0, min(1.0, 1 - (total_hours / max(max_hours * 2, 1)) * 0.45))
    vibe_ratio = vibe_match(profile, vibe)
    if vibe == "Peu importe":
        score = 100 * (0.48 * budget_ratio + 0.32 * time_ratio + 0.20 * vibe_ratio)
    else:
        score = 100 * (0.52 * vibe_ratio + 0.28 * budget_ratio + 0.20 * time_ratio)
    return round(max(0, min(100, score)))

def find_best_options(departure, outbound, return_date, budget, max_hours, vibe):
    if departure != "Paris":
        return []
    results = []
    for destination, profile in DESTINATION_PROFILES.items():
        if profile["outbound_hours"] > max_hours or profile["return_hours"] > max_hours:
            continue
        out_price = seasonal_price(profile["base_round_trip_price"]/2, outbound.month, profile["season"])
        return_price = seasonal_price(profile["base_round_trip_price"]/2, return_date.month, profile["season"])
        round_trip_price = out_price + return_price
        if round_trip_price > budget:
            continue
        total_hours = profile["outbound_hours"] + profile["return_hours"]
        score = score_destination(profile, round_trip_price, budget, total_hours, max_hours, vibe)
        results.append({
            "destination":destination,"operator":profile["operator"],
            "outbound_hours":profile["outbound_hours"],"return_hours":profile["return_hours"],
            "round_trip_price":round_trip_price,"score":score,
            "tags":profile["tags"],"reason":profile["reason"]
        })
    results.sort(key=lambda x:(-x["score"],x["round_trip_price"],x["destination"]))
    return results
