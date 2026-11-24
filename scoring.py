def deal_score(
    roundtrip_price,
    budget,
    outbound_duration,
    return_duration,
    vibe,
    destination_vibes,
):
    # Prix : plus le billet consomme peu du budget, meilleur est le score.
    price_ratio = roundtrip_price / max(budget, 1)
    price_score = max(0, 40 * (1 - price_ratio))

    # Temps : pénalise les trajets longs, tout en restant compatible
    # avec une escapade.
    avg_duration = (outbound_duration + return_duration) / 2
    duration_score = max(0, 30 * (1 - avg_duration / 6))

    # Adéquation avec l'envie.
    vibe_score = 0
    if vibe == "Peu importe":
        vibe_score = 15
    elif vibe in destination_vibes:
        vibe_score = 20
    else:
        vibe_score = 5

    # Petit bonus pour un trajet simple.
    simplicity_score = 10

    return round(min(100, price_score + duration_score + vibe_score + simplicity_score))


def explain_score(roundtrip_price, budget, outbound_duration, return_duration):
    return (
        f"{roundtrip_price:.0f} € A/R pour environ "
        f"{outbound_duration:.1f} h à l'aller et {return_duration:.1f} h au retour."
    )
