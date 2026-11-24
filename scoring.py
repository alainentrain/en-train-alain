def deal_score(price, duration, direct):
    # Prototype heuristic. In production this should combine:
    # current price vs reference price, duration, directness,
    # flexibility, availability and destination appeal.
    price_score = max(0, 50 - price * 0.45)
    duration_score = max(0, 30 - duration * 4)
    direct_score = 20 if direct == "direct" else 8
    return int(max(0, min(100, price_score + duration_score + direct_score)))
