DESTINATION_PROFILES = {
    "Reims": {
        "operator":"TGV INOUI","outbound_hours":0.8,"return_hours":0.8,"base_round_trip_price":42,
        "tags":["Week-end","Culture","Gastronomie"],
        "vibes":{"Week-end":.90,"Culture":.82,"Gastronomie":.94,"Nature":.42,"Soleil":.28},
        "reason":"Très facile depuis Paris, idéale pour une escapade courte.",
        "season":{1:.92,2:.94,3:.98,4:1.02,5:1.05,6:1.08,7:1.10,8:1.08,9:1.04,10:1,11:.96,12:1.04}
    },
    "Dijon": {
        "operator":"TGV INOUI","outbound_hours":1.7,"return_hours":1.7,"base_round_trip_price":49,
        "tags":["Week-end","Culture","Gastronomie"],
        "vibes":{"Week-end":.91,"Culture":.90,"Gastronomie":.97,"Nature":.60,"Soleil":.36},
        "reason":"Excellent compromis entre patrimoine, gastronomie et temps de trajet.",
        "season":{1:.92,2:.93,3:.98,4:1,5:1.04,6:1.06,7:1.08,8:1.07,9:1.03,10:1,11:.95,12:1.05}
    },
    "Le Mans": {
        "operator":"OUIGO TRAIN CLASSIQUE","outbound_hours":2.2,"return_hours":2.2,"base_round_trip_price":29,
        "tags":["Week-end","Culture"],
        "vibes":{"Week-end":.78,"Culture":.55,"Gastronomie":.48,"Nature":.50,"Soleil":.30},
        "reason":"Petit budget et trajet simple pour une escapade sans prise de tête.",
        "season":{1:.90,2:.92,3:.96,4:1,5:1.02,6:1.05,7:1.08,8:1.08,9:1.02,10:.98,11:.93,12:1.03}
    },
    "Nantes": {
        "operator":"OUIGO","outbound_hours":2.2,"return_hours":2.2,"base_round_trip_price":45,
        "tags":["Week-end","Culture","Nature"],
        "vibes":{"Week-end":.93,"Culture":.76,"Gastronomie":.72,"Nature":.74,"Soleil":.44},
        "reason":"Bonne option pour un vrai week-end sans trop exploser le temps de trajet.",
        "season":{1:.90,2:.92,3:.96,4:1,5:1.04,6:1.08,7:1.12,8:1.10,9:1.03,10:.98,11:.93,12:1.04}
    },
    "La Rochelle": {
        "operator":"TGV INOUI","outbound_hours":2.7,"return_hours":2.7,"base_round_trip_price":68,
        "tags":["Week-end","Nature","Soleil"],
        "vibes":{"Week-end":.92,"Culture":.62,"Gastronomie":.76,"Nature":.88,"Soleil":.84},
        "reason":"Très bonne correspondance pour une escapade iodée et dépaysante.",
        "season":{1:.86,2:.88,3:.94,4:.98,5:1.02,6:1.08,7:1.15,8:1.16,9:1.06,10:.98,11:.91,12:.94}
    },
    "Nîmes": {
        "operator":"TGV INOUI","outbound_hours":2.9,"return_hours":2.9,"base_round_trip_price":76,
        "tags":["Week-end","Culture","Soleil","Gastronomie"],
        "vibes":{"Week-end":.88,"Culture":.82,"Gastronomie":.78,"Nature":.72,"Soleil":.94},
        "reason":"Plus loin, mais intéressante pour maximiser le dépaysement et la lumière.",
        "season":{1:.82,2:.86,3:.92,4:.98,5:1.02,6:1.08,7:1.13,8:1.12,9:1.05,10:.95,11:.88,12:.90}
    },
    "Bordeaux": {
        "operator":"TGV INOUI","outbound_hours":2.2,"return_hours":2.2,"base_round_trip_price":82,
        "tags":["Week-end","Culture","Gastronomie"],
        "vibes":{"Week-end":.96,"Culture":.88,"Gastronomie":.95,"Nature":.65,"Soleil":.62},
        "reason":"Très bon profil week-end, surtout si la gastronomie compte dans le choix.",
        "season":{1:.91,2:.93,3:.97,4:1.01,5:1.04,6:1.07,7:1.10,8:1.09,9:1.03,10:.99,11:.94,12:1.04}
    }
}
DEMO_ROUTES = DESTINATION_PROFILES
