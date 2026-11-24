def deal_score(price, duration_hours, direct, budget, reference_price, appeal):
    # Score volontairement simple pour le prototype.
    price_ratio = max(0, min(1, (reference_price - price) / max(reference_price, 1)))
    budget_fit = max(0, min(1, (budget - price) / max(budget, 1)))
    duration_fit = max(0, min(1, 1 - (duration_hours - 1) / 7))
    direct_bonus = 1 if direct else 0.45
    appeal_fit = max(0, min(1, appeal / 10))

    score = (
        40 * price_ratio +
        20 * budget_fit +
        15 * duration_fit +
        10 * direct_bonus +
        15 * appeal_fit
    )
    return round(score)
