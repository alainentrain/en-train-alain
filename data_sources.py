from dataclasses import dataclass
from typing import Dict, List

@dataclass
class Route:
    destination: str
    operator: str
    outbound_h: float
    return_h: float
    base_price_ar: float
    vibes: Dict[str, float]
    reason: str

# Données de démonstration.
# Les scores de vibe sont volontairement séparés : une même destination
# peut être excellente pour la culture ET pour la gastronomie, par exemple.
DEMO_ROUTES: List[Route] = [
    Route(
        "Le Mans", "OUIGO TRAIN CLASSIQUE", 2.2, 2.2, 24,
        {"Week-end": 9, "Culture": 7, "Nature": 6, "Soleil": 3, "Gastronomie": 7},
        "Petit budget et trajet simple pour une escapade sans prise de tête."
    ),
    Route(
        "Reims", "TGV INOUI", 0.8, 0.8, 36,
        {"Week-end": 9, "Culture": 9, "Nature": 5, "Soleil": 4, "Gastronomie": 9},
        "Très facile depuis Paris, idéale pour une escapade courte."
    ),
    Route(
        "Nantes", "OUIGO", 2.2, 2.2, 38,
        {"Week-end": 9, "Culture": 8, "Nature": 8, "Soleil": 5, "Gastronomie": 8},
        "Bonne option pour un vrai week-end sans trop exploser le temps de trajet."
    ),
    Route(
        "Dijon", "TGV INOUI", 1.7, 1.7, 42,
        {"Week-end": 8, "Culture": 10, "Nature": 7, "Soleil": 4, "Gastronomie": 10},
        "Très bon compromis entre patrimoine, gastronomie et temps de trajet."
    ),
    Route(
        "La Rochelle", "TGV INOUI", 2.7, 2.7, 52,
        {"Week-end": 10, "Culture": 7, "Nature": 9, "Soleil": 9, "Gastronomie": 8},
        "Une vraie sensation d'évasion, particulièrement intéressante aux beaux jours."
    ),
    Route(
        "Bordeaux", "TGV INOUI", 2.1, 2.1, 58,
        {"Week-end": 9, "Culture": 9, "Nature": 7, "Soleil": 8, "Gastronomie": 10},
        "Un gros potentiel pour un week-end : culture, gastronomie et dépaysement."
    ),
    Route(
        "Nîmes", "TGV INOUI", 2.9, 2.9, 60,
        {"Week-end": 8, "Culture": 9, "Nature": 8, "Soleil": 10, "Gastronomie": 8},
        "Très intéressante pour chercher du soleil et un vrai changement d'ambiance."
    ),
]

def get_routes() -> List[Route]:
    return DEMO_ROUTES
