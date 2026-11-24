def deal_score(price, budget, duration_hours, vibe_bonus=0):
    """
    Utility kept separate for future iterations.
    The current engine uses the same principles:
    affordability + short travel time + user preference.
    """
    price_part = max(0, 35 - (price / max(budget, 1)) * 25)
    duration_part = max(0, 25 - duration_hours * 5)
    return round(min(100, 35 + price_part + duration_part + vibe_bonus))
