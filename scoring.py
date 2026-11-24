def score_label(score: int) -> str:
    if score >= 85:
        return "Coup de cœur"
    if score >= 70:
        return "Très bonne option"
    if score >= 55:
        return "Bonne option"
    return "Option à considérer"
