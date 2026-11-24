"""
Couche de données.

V3 utilise volontairement un petit jeu de données de démonstration afin que
l'application fonctionne immédiatement sur Streamlit.

La prochaine couche à brancher est :
1. SNCF Open Data pour le réseau / horaires / tarifs de référence.
2. Tictactrip pour la vérification commerciale du prix + disponibilité.
"""

DEMO_ROUTES = [
    {
        "origin": "Paris",
        "destination": "Reims",
        "outbound_operator": "TGV INOUI",
        "outbound_duration": 0.75,
        "return_duration": 0.75,
        "outbound_reference_price": 8,
        "return_reference_price": 8,
        "vibes": ["Week-end", "Culture", "Gastronomie"],
        "description": "Très facile depuis Paris, idéal pour une escapade courte.",
        "seasonal_factors": {12: 1.10, 1: 0.95, 2: 0.95, 3: 1.00, 4: 1.00, 5: 1.05, 6: 1.10, 7: 1.15, 8: 1.15, 9: 1.00, 10: 1.00, 11: 1.00},
        "return_factors": {12: 1.10, 1: 0.95, 2: 0.95, 3: 1.00, 4: 1.00, 5: 1.05, 6: 1.10, 7: 1.15, 8: 1.15, 9: 1.00, 10: 1.00, 11: 1.00},
    },
    {
        "origin": "Paris",
        "destination": "Nantes",
        "outbound_operator": "OUIGO",
        "outbound_duration": 2.25,
        "return_duration": 2.25,
        "outbound_reference_price": 8,
        "return_reference_price": 8,
        "vibes": ["Week-end", "Culture", "Gastronomie"],
        "description": "Bonne option pour un vrai week-end sans trop exploser le temps de trajet.",
        "seasonal_factors": {12: 1.15, 1: 0.95, 2: 0.95, 3: 1.00, 4: 1.05, 5: 1.05, 6: 1.10, 7: 1.20, 8: 1.20, 9: 1.00, 10: 1.00, 11: 1.00},
        "return_factors": {12: 1.15, 1: 0.95, 2: 0.95, 3: 1.00, 4: 1.05, 5: 1.05, 6: 1.10, 7: 1.20, 8: 1.20, 9: 1.00, 10: 1.00, 11: 1.00},
    },
    {
        "origin": "Paris",
        "destination": "Dijon",
        "outbound_operator": "TGV INOUI",
        "outbound_duration": 1.75,
        "return_duration": 1.75,
        "outbound_reference_price": 13,
        "return_reference_price": 13,
        "vibes": ["Week-end", "Culture", "Gastronomie"],
        "description": "Très bon compromis entre prix, temps de trajet et dépaysement.",
        "seasonal_factors": {12: 1.05, 1: 0.95, 2: 0.95, 3: 1.00, 4: 1.00, 5: 1.05, 6: 1.10, 7: 1.15, 8: 1.15, 9: 1.00, 10: 1.00, 11: 1.00},
        "return_factors": {12: 1.05, 1: 0.95, 2: 0.95, 3: 1.00, 4: 1.00, 5: 1.05, 6: 1.10, 7: 1.15, 8: 1.15, 9: 1.00, 10: 1.00, 11: 1.00},
    },
    {
        "origin": "Paris",
        "destination": "Le Mans",
        "outbound_operator": "OUIGO TRAIN CLASSIQUE",
        "outbound_duration": 2.25,
        "return_duration": 2.25,
        "outbound_reference_price": 5,
        "return_reference_price": 5,
        "vibes": ["Week-end", "Culture"],
        "description": "Petit budget et trajet simple pour une escapade sans prise de tête.",
        "seasonal_factors": {12: 1.10, 1: 0.95, 2: 0.95, 3: 1.00, 4: 1.00, 5: 1.05, 6: 1.10, 7: 1.15, 8: 1.15, 9: 1.00, 10: 1.00, 11: 1.00},
        "return_factors": {12: 1.10, 1: 0.95, 2: 0.95, 3: 1.00, 4: 1.00, 5: 1.05, 6: 1.10, 7: 1.15, 8: 1.15, 9: 1.00, 10: 1.00, 11: 1.00},
    },
    {
        "origin": "Paris",
        "destination": "Nîmes",
        "outbound_operator": "OUIGO",
        "outbound_duration": 2.9,
        "return_duration": 2.9,
        "outbound_reference_price": 10,
        "return_reference_price": 10,
        "vibes": ["Week-end", "Culture", "Soleil", "Gastronomie"],
        "description": "Un gros dépaysement pour un trajet qui reste sous trois heures.",
        "seasonal_factors": {12: 1.10, 1: 0.95, 2: 0.95, 3: 1.00, 4: 1.05, 5: 1.10, 6: 1.15, 7: 1.25, 8: 1.25, 9: 1.10, 10: 1.00, 11: 1.00},
        "return_factors": {12: 1.10, 1: 0.95, 2: 0.95, 3: 1.00, 4: 1.05, 5: 1.10, 6: 1.15, 7: 1.25, 8: 1.25, 9: 1.10, 10: 1.00, 11: 1.00},
    },
    {
        "origin": "Paris",
        "destination": "La Rochelle",
        "outbound_operator": "OUIGO",
        "outbound_duration": 2.75,
        "return_duration": 2.75,
        "outbound_reference_price": 11,
        "return_reference_price": 11,
        "vibes": ["Week-end", "Nature", "Gastronomie"],
        "description": "Très bon potentiel d'escapade, surtout quand le tarif reste bas.",
        "seasonal_factors": {12: 1.05, 1: 0.95, 2: 0.95, 3: 1.00, 4: 1.05, 5: 1.10, 6: 1.20, 7: 1.30, 8: 1.30, 9: 1.15, 10: 1.00, 11: 1.00},
        "return_factors": {12: 1.05, 1: 0.95, 2: 0.95, 3: 1.00, 4: 1.05, 5: 1.10, 6: 1.20, 7: 1.30, 8: 1.30, 9: 1.15, 10: 1.00, 11: 1.00},
    },
    {
        "origin": "Paris",
        "destination": "Bordeaux",
        "outbound_operator": "OUIGO",
        "outbound_duration": 2.25,
        "return_duration": 2.25,
        "outbound_reference_price": 16,
        "return_reference_price": 16,
        "vibes": ["Week-end", "Culture", "Gastronomie"],
        "description": "Destination très attractive pour un week-end, mais plus sensible au budget.",
        "seasonal_factors": {12: 1.10, 1: 0.95, 2: 0.95, 3: 1.00, 4: 1.05, 5: 1.10, 6: 1.15, 7: 1.25, 8: 1.25, 9: 1.10, 10: 1.00, 11: 1.00},
        "return_factors": {12: 1.10, 1: 0.95, 2: 0.95, 3: 1.00, 4: 1.05, 5: 1.10, 6: 1.15, 7: 1.25, 8: 1.25, 9: 1.10, 10: 1.00, 11: 1.00},
    },
]
