import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import timedelta
import re
import unicodedata
import math

st.set_page_config(page_title="En Train Alain", page_icon="🚆", layout="wide")

DATA = Path(__file__).parent / "data"

# ------------------------------------------------------------
# Chargement des données
# ------------------------------------------------------------

@st.cache_data(show_spinner="Chargement des données SNCF…")
def load_data():
    stations = pd.read_csv(DATA / "stations.csv")
    routes = pd.read_csv(DATA / "routes.csv")
    cal = pd.read_csv(
        DATA / "calendar_dates.csv",
        dtype={"service_id": str, "date": str},
    )
    trips = pd.read_csv(DATA / "trip_stops.csv.gz", compression="gzip")

    def canonical_service_id(value):
        if pd.isna(value):
            return ""
        s = str(value).strip()
        return str(int(s)) if s.isdigit() else s

    cal["service_id"] = cal["service_id"].map(canonical_service_id)
    trips["service_id"] = trips["service_id"].map(canonical_service_id)

    trips["trip_id"] = trips["trip_id"].astype(str)
    trips["station_id"] = trips["station_id"].astype(str)
    trips["route_type"] = (
        pd.to_numeric(trips["route_type"], errors="coerce")
        .fillna(0)
        .astype(int)
    )

    # On rattache les informations de ligne aux passages.
    route_cols = [c for c in ["route_id", "route_short_name", "route_long_name", "route_type"] if c in routes.columns]
    if "route_id" in route_cols:
        routes_small = routes[route_cols].drop_duplicates("route_id")
        trips = trips.merge(routes_small, on="route_id", how="left", suffixes=("", "_route"))

    return stations, routes, cal, trips


@st.cache_data
def load_fares():
    p = DATA / "tarifs-tgv-inoui-ouigo.csv"
    if not p.exists():
        return pd.DataFrame()
    return pd.read_csv(p, sep=None, engine="python", dtype=str)


# ------------------------------------------------------------
# Utilitaires
# ------------------------------------------------------------

def norm(value):
    if pd.isna(value):
        return ""
    s = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode()
    s = s.upper().replace("'", " ").replace("-", " ")
    s = re.sub(r"\bHALL\s+\d+(?:\s*-\s*\d+)?\b", "", s)
    s = re.sub(r"[^A-Z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def parse_gtfs_time(value):
    try:
        h, m, s = str(value).split(":")
        return int(h) * 60 + int(m)
    except Exception:
        return np.nan


def fmt_duration(minutes):
    if pd.isna(minutes):
        return "durée inconnue"
    minutes = int(round(float(minutes)))
    return f"{minutes // 60} h {minutes % 60:02d}"


def fmt_time(value):
    if pd.isna(value):
        return "—"
    s = str(value).strip()

    # GTFS HH:MM:SS
    if ":" in s:
        try:
            parts = s.split(":")
            return f"{int(parts[0]) % 24:02d}:{int(parts[1]):02d}"
        except Exception:
            return "—"

    # Minutes internes
    try:
        total = int(round(float(s)))
        return f"{(total // 60) % 24:02d}:{total % 60:02d}"
    except Exception:
        return "—"


def active_services(cal, d):
    ds = d.strftime("%Y%m%d")
    x = cal[cal["date"] == ds]

    added = set(x.loc[x["exception_type"] == 1, "service_id"])
    removed = set(x.loc[x["exception_type"] == 2, "service_id"])

    return added - removed


def station_options(stations):
    names = sorted(
        stations["station_name"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )
    return ["Paris (toutes les gares)"] + names


def station_ids_for_choice(choice, stations):
    road_mask = stations["station_name"].astype(str).str.contains(
        r"routière|routiere|car", case=False, na=False
    )

    if choice == "Paris (toutes les gares)":
        mask = stations["station_name"].astype(str).str.match(
            r"^Paris\b", case=False, na=False
        ) & ~road_mask
        return set(stations.loc[mask, "station_id"])

    mask = (stations["station_name"] == choice) & ~road_mask
    return set(stations.loc[mask, "station_id"])


def haversine_km(lat1, lon1, lat2, lon2):
    """Distance approximative entre deux coordonnées GPS."""
    r = 6371.0
    p1 = math.radians(float(lat1))
    p2 = math.radians(float(lat2))
    dp = math.radians(float(lat2) - float(lat1))
    dl = math.radians(float(lon2) - float(lon1))

    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def add_distance_from_paris(stations):
    s = stations.copy()

    def dist(row):
        try:
            return haversine_km(
                48.8566, 2.3522,
                row["lat"], row["lon"]
            )
        except Exception:
            return np.nan

    s["_distance_paris_km"] = s.apply(dist, axis=1)
    return s


def is_suburban_or_idf_station(station_id, station_lookup):
    """
    Pour En Train Alain, on évite les destinations de proximité
    typiquement assimilables à un trajet RER / Transilien.
    Seuil volontairement simple : < 55 km du centre de Paris.
    """
    try:
        d = float(station_lookup.loc[station_id, "_distance_paris_km"])
        return d < 55
    except Exception:
        return False


def rail_rows(trips, services):
    # route_type 2 = ferroviaire dans notre export SNCF.
    return trips[
        trips["service_id"].isin(services)
        & (trips["route_type"] == 2)
    ].copy()


# ------------------------------------------------------------
# Recherche de trajets DIRECTS
# ------------------------------------------------------------

def direct_journeys(
    trips,
    services,
    origin_ids,
    destination_ids=None,
    dep_start=300,
    dep_end=1380,
    max_duration=600,
):
    rail = rail_rows(trips, services)

    origin = rail[rail["station_id"].isin(origin_ids)].copy()
    if origin.empty:
        return pd.DataFrame()

    origin["dep_min"] = origin["departure_time"].map(parse_gtfs_time)
    origin = origin[
        origin["dep_min"].between(dep_start, dep_end)
        & origin["dep_min"].notna()
    ]

    if origin.empty:
        return pd.DataFrame()

    trip_ids = origin["trip_id"].unique()

    downstream_cols = [
        "trip_id",
        "station_id",
        "station_name",
        "stop_sequence",
        "arrival_time",
        "trip_headsign",
    ]

    downstream = rail[
        rail["trip_id"].isin(trip_ids)
    ][downstream_cols].copy()

    origins = origin[
        [
            "trip_id",
            "stop_sequence",
            "departure_time",
            "dep_min",
            "station_id",
        ]
    ].rename(
        columns={
            "stop_sequence": "origin_seq",
            "departure_time": "origin_departure_time",
            "station_id": "origin_station_id",
        }
    )

    downstream = downstream.merge(origins, on="trip_id", how="inner")
    downstream["arr_min"] = downstream["arrival_time"].map(parse_gtfs_time)

    downstream = downstream[
        (downstream["stop_sequence"] > downstream["origin_seq"])
        & downstream["station_id"].notna()
        & downstream["arr_min"].notna()
    ].copy()

    if destination_ids is not None:
        downstream = downstream[
            downstream["station_id"].isin(destination_ids)
        ]

    downstream["duration"] = downstream["arr_min"] - downstream["dep_min"]
    downstream = downstream[
        (downstream["duration"] > 0)
        & (downstream["duration"] <= max_duration)
    ]

    downstream = (
        downstream
        .sort_values(["trip_id", "station_id", "arr_min"])
        .drop_duplicates(["trip_id", "station_id"])
    )

    result = downstream[
        [
            "trip_id",
            "station_id",
            "station_name",
            "origin_departure_time",
            "arrival_time",
            "dep_min",
            "arr_min",
            "origin_station_id",
            "trip_headsign",
            "duration",
        ]
    ].rename(columns={"origin_departure_time": "departure_time"})
    result["connections"] = 0
    return result


def one_connection_journeys(
    trips,
    services,
    origin_ids,
    destination_ids=None,
    dep_start=300,
    dep_end=1380,
    max_duration=600,
    min_transfer=8,
    max_transfer=90,
    max_candidates=120,
):
    """
    Recherche de trajets avec exactement une correspondance.

    Important : cette fonction ne fabrique pas de combinaison aller/retour.
    Elle produit simplement des possibilités de trajet dans UN sens.
    Pour limiter le coût, on ne cherche les correspondances que si
    la recherche directe ne suffit pas.
    """
    rail = rail_rows(trips, services)

    first = rail[rail["station_id"].isin(origin_ids)].copy()
    if first.empty:
        return pd.DataFrame()

    first["dep_min"] = first["departure_time"].map(parse_gtfs_time)
    first = first[
        first["dep_min"].between(dep_start, dep_end)
        & first["dep_min"].notna()
    ].copy()

    if first.empty:
        return pd.DataFrame()

    # Index des départs par gare : permet de trouver rapidement
    # le prochain train après une arrivée de correspondance.
    dep_idx = rail[
        ["trip_id", "station_id", "station_name", "stop_sequence",
         "departure_time", "trip_headsign"]
    ].copy()
    dep_idx["dep_min"] = dep_idx["departure_time"].map(parse_gtfs_time)
    dep_idx = dep_idx[dep_idx["dep_min"].notna()].copy()

    # Pour chaque gare, les départs sont triés afin d'utiliser searchsorted.
    dep_groups = {}
    for sid, g in dep_idx.groupby("station_id", sort=False):
        dep_groups[sid] = g.sort_values("dep_min")

    # Stops de chaque premier train après son départ de l'origine.
    first_ids = first["trip_id"].unique()
    first_stops = rail[rail["trip_id"].isin(first_ids)].copy()
    first_stops["arr_min"] = first_stops["arrival_time"].map(parse_gtfs_time)
    first_stops = first_stops[
        first_stops["arr_min"].notna()
        & first_stops["station_id"].notna()
    ]

    origins = first[
        ["trip_id", "station_id", "stop_sequence", "dep_min", "departure_time"]
    ].rename(
        columns={
            "station_id": "origin_station_id",
            "stop_sequence": "origin_seq",
            "departure_time": "origin_departure_time",
        }
    )
    first_stops = first_stops.merge(origins, on="trip_id", how="inner")
    first_stops = first_stops[
        first_stops["stop_sequence"] > first_stops["origin_seq"]
    ]

    # Ne garder qu'un nombre raisonnable de trains de départ pour
    # empêcher une recherche massive inutile.
    first = (
        first.sort_values(["dep_min", "trip_id"])
        .drop_duplicates(["trip_id"])
        .head(max_candidates)
    )
    first_ids = set(first["trip_id"])
    first_stops = first_stops[first_stops["trip_id"].isin(first_ids)]

    results = []

    # Index mémoire des arrêts par train : évite de rescanner tout le GTFS
    # pour chaque candidat de correspondance.
    trip_stop_groups = {
        str(tid): g for tid, g in rail.groupby("trip_id", sort=False)
    }

    for _, leg1 in first_stops.iterrows():
        transfer_station = leg1["station_id"]
        arrival1 = float(leg1["arr_min"])
        first_departure = float(leg1["dep_min"])

        g = dep_groups.get(transfer_station)
        if g is None or g.empty:
            continue

        lo = arrival1 + min_transfer
        hi = arrival1 + max_transfer
        vals = g["dep_min"].to_numpy()

        left = int(np.searchsorted(vals, lo, side="left"))
        right = int(np.searchsorted(vals, hi, side="right"))

        candidates = g.iloc[left:right]

        for _, leg2 in candidates.head(8).iterrows():
            # Ne pas reprendre le même train.
            if str(leg2["trip_id"]) == str(leg1["trip_id"]):
                continue

            # La destination doit être après le départ de la correspondance.
            trip2 = trip_stop_groups.get(str(leg2["trip_id"]))
            if trip2 is None or trip2.empty:
                continue
            trip2 = trip2.copy()

            trip2 = trip2[
                trip2["stop_sequence"] > float(leg2["stop_sequence"])
            ].copy()
            if trip2.empty:
                continue

            trip2["arr_min"] = trip2["arrival_time"].map(parse_gtfs_time)
            trip2 = trip2[trip2["arr_min"].notna()]

            if destination_ids is not None:
                trip2 = trip2[trip2["station_id"].isin(destination_ids)]

            if trip2.empty:
                continue

            trip2["total_duration"] = (
                trip2["arr_min"] - first_departure
            )
            trip2 = trip2[
                (trip2["total_duration"] > 0)
                & (trip2["total_duration"] <= max_duration)
            ]

            if trip2.empty:
                continue

            for _, final in trip2.sort_values("arr_min").head(3).iterrows():
                results.append({
                    "trip_id": f"{leg1['trip_id']}__{leg2['trip_id']}",
                    "station_id": final["station_id"],
                    "station_name": final["station_name"],
                    "departure_time": leg1["origin_departure_time"],
                    "arrival_time": final["arrival_time"],
                    "dep_min": first_departure,
                    "arr_min": float(final["arr_min"]),
                    "origin_station_id": leg1["origin_station_id"],
                    "trip_headsign": (
                        f"{leg1['trip_headsign']} / {leg2['trip_headsign']}"
                    ),
                    "duration": float(final["total_duration"]),
                    "transfer_station_id": transfer_station,
                    "transfer_station_name": str(leg1["station_name"]),
                    "transfer_departure": leg2["departure_time"],
                    "transfer_arrival": leg1["arrival_time"],
                    "connections": 1,
                })

    if not results:
        return pd.DataFrame()

    out = pd.DataFrame(results)

    # Élimination des doublons d'affichage.
    return (
        out
        .sort_values(["station_id", "dep_min", "arr_min"])
        .drop_duplicates(["station_id", "dep_min", "arr_min"])
    )



# ------------------------------------------------------------
# Couche DESTINATION
# ------------------------------------------------------------

# Cette couche est volontairement séparée des données transport.
# Les fournisseurs nous donnent des gares / arrêts ; En Train Alain
# décide quelles gares appartiennent à une même destination éditoriale.
#
# Le fichier destination_map.csv est notre couche métier : on peut donc
# la conserver quand la source des trajets passera du GTFS à une API.
@st.cache_data
def load_destination_map():
    p = DATA / "destination_map.csv"
    if not p.exists():
        return pd.DataFrame(columns=[
            "station_id", "station_name", "destination_name", "destination_type"
        ])
    return pd.read_csv(p, dtype=str)


def destination_name_for_station(station_name, destination_map=None):
    """Retourne le nom de destination éditoriale pour une gare."""
    if destination_map is not None and not destination_map.empty:
        hit = destination_map[
            destination_map["station_name"].map(norm) == norm(station_name)
        ]
        if not hit.empty:
            return str(hit.iloc[0]["destination_name"])
    return str(station_name)

# ------------------------------------------------------------
# Tarifs indicatifs
# ------------------------------------------------------------

def fare_lookup(fares, origin_name, dest_name):
    if fares.empty:
        return np.nan

    o = norm(origin_name)
    d = norm(dest_name)

    f = fares[
        (fares["_o"] == o)
        & (fares["_d"] == d)
    ]

    if f.empty:
        f = fares[
            (fares["_o"] == d)
            & (fares["_d"] == o)
        ]

    if f.empty:
        return np.nan

    return pd.to_numeric(
        f["Prix minimum"],
        errors="coerce"
    ).min()


# ------------------------------------------------------------
# Chargement
# ------------------------------------------------------------

stations, routes, cal, trips = load_data()
destination_map = load_destination_map()
stations_geo = add_distance_from_paris(stations)
station_lookup = stations_geo.set_index("station_id")

fares = load_fares()

if not fares.empty:
    fares["_o"] = fares["Gare origine"].map(norm)
    fares["_d"] = fares["Gare destination"].map(norm)


# ------------------------------------------------------------
# Interface
# ------------------------------------------------------------

st.title("🚆 En Train Alain")
st.caption(
    "Tu as un budget, on cherche où partir. — V14.2 : couche destination séparée des données transport"
)

with st.sidebar:
    st.header("Ton escapade")

    origin = st.selectbox(
        "Départ",
        station_options(stations),
        index=0,
    )

    min_date = pd.to_datetime(
        cal["date"], format="%Y%m%d"
    ).min().date()

    max_date = pd.to_datetime(
        cal["date"], format="%Y%m%d"
    ).max().date()

    outbound = st.date_input(
        "Date aller",
        value=min_date,
        min_value=min_date,
        max_value=max_date,
    )

    return_default = min(
        outbound + timedelta(days=2),
        max_date
    )

    inbound = st.date_input(
        "Date retour",
        value=return_default,
        min_value=outbound,
        max_value=max_date,
    )

    budget = st.slider(
        "Budget maximum A/R (€)",
        20, 300, 100, 5
    )

    max_leg = st.slider(
        "Durée max par trajet",
        1, 8, 4, 1
    )

    dep_window = st.selectbox(
        "Départ aller",
        [
            "Toute la journée",
            "Matin (05h–12h)",
            "Après-midi (12h–18h)",
            "Soir (18h–23h)",
        ],
    )

    vibe = st.selectbox(
        "Ambiance",
        [
            "Peu importe",
            "Week-end",
            "Culture",
            "Nature",
            "Soleil",
            "Gastronomie",
        ],
    )

    search = st.button(
        "🔎 Trouver où partir",
        type="primary",
        use_container_width=True,
    )


st.markdown("### Où peux-tu partir ?")

st.info(
    "Cette version utilise les horaires SNCF réels et ne propose une correspondance que lorsqu'aucun trajet direct n'existe pour la destination. "
    "Les prix affichés quand disponibles sont des **tarifs indicatifs de référence**, "
    "pas le prix en temps réel. "
    "**Les allers et les retours sont affichés séparément : "
    "En Train Alain ne cherche pas encore à fabriquer une combinaison précise entre les deux.**"
)


# ------------------------------------------------------------
# Recherche
# ------------------------------------------------------------

if search:

    if inbound < outbound:
        st.error("La date retour doit être après la date aller.")
        st.stop()

    windows = {
        "Matin (05h–12h)": (300, 720),
        "Après-midi (12h–18h)": (720, 1080),
        "Soir (18h–23h)": (1080, 1380),
        "Toute la journée": (300, 1380),
    }

    dep_start, dep_end = windows[dep_window]
    max_duration = max_leg * 60

    out_services = active_services(cal, outbound)
    in_services = active_services(cal, inbound)
    origin_ids = station_ids_for_choice(origin, stations)

    if not origin_ids:
        st.error("Impossible d'identifier la gare de départ.")
        st.stop()

    if not out_services:
        st.warning(
            "Aucun service SNCF n'est renseigné pour cette date aller dans le fichier GTFS."
        )
        st.stop()

    if not in_services:
        st.warning(
            "Aucun service SNCF n'est renseigné pour cette date retour dans le fichier GTFS."
        )
        st.stop()

    with st.spinner("Recherche des destinations réelles…"):

        # ====================================================
        # 1. ALLERS DISPONIBLES
        # ====================================================

        # V11 : les directs restent prioritaires.
        # Les correspondances servent uniquement à élargir la découverte
        # lorsqu'il n'y a pas assez de destinations directes.
        outbound_direct = direct_journeys(
            trips,
            out_services,
            origin_ids,
            dep_start=dep_start,
            dep_end=dep_end,
            max_duration=max_duration,
        )

        if outbound_direct.empty or outbound_direct["station_id"].nunique() < 30:
            outbound_connections = one_connection_journeys(
                trips,
                out_services,
                origin_ids,
                dep_start=dep_start,
                dep_end=dep_end,
                max_duration=max_duration,
            )
        else:
            outbound_connections = pd.DataFrame()

        # Une correspondance n'est ajoutée que pour une destination
        # qui ne possède AUCUN trajet direct. Cela élimine les faux détours
        # du type Paris → Longueau → Amiens lorsqu'un direct existe.
        if not outbound_connections.empty and not outbound_direct.empty:
            direct_destinations = set(outbound_direct["station_id"])
            outbound_connections = outbound_connections[
                ~outbound_connections["station_id"].isin(direct_destinations)
            ].copy()

        outbound_all = pd.concat(
            [outbound_direct, outbound_connections],
            ignore_index=True,
        ) if not outbound_connections.empty else outbound_direct

        # ====================================================
        # 2. RETOURS DISPONIBLES
        # ====================================================

        # Même principe dans l'autre sens : les retours restent indépendants
        # des allers. On ne construit aucune combinaison A/R ici.
        return_all = pd.DataFrame()

        if not outbound_all.empty:
            possible_destination_ids = set(
                outbound_all["station_id"]
            )

            return_direct = direct_journeys(
                trips,
                in_services,
                possible_destination_ids,
                destination_ids=origin_ids,
                dep_start=600,
                dep_end=1500,
                max_duration=max_duration,
            )

            if return_direct.empty or return_direct["origin_station_id"].nunique() < 30:
                return_connections = one_connection_journeys(
                    trips,
                    in_services,
                    possible_destination_ids,
                    destination_ids=origin_ids,
                    dep_start=600,
                    dep_end=1500,
                    max_duration=max_duration,
                )
            else:
                return_connections = pd.DataFrame()

            # Même règle au retour : un détour n'est jamais affiché
            # lorsqu'un retour direct existe déjà pour cette destination.
            if not return_connections.empty and not return_direct.empty:
                direct_return_destinations = set(return_direct["origin_station_id"])
                return_connections = return_connections[
                    ~return_connections["origin_station_id"].isin(direct_return_destinations)
                ].copy()

            if not return_connections.empty:
                return_all = pd.concat(
                    [return_direct, return_connections],
                    ignore_index=True,
                )
            else:
                return_all = return_direct

        # ====================================================
        # 3. NETTOYAGE DES POINTS ROUTIERS + PROXIMITÉ
        # ====================================================

        # Le MVP est ferroviaire : on exclut les arrêts routiers/cars
        # (ex. « Paris-Austerlitz Routiere ») même s'ils apparaissent
        # dans le flux SNCF.
        road_station_ids = set(
            stations.loc[
                stations["station_name"].astype(str).str.contains(
                    r"routière|routiere|car", case=False, na=False
                ),
                "station_id",
            ]
        )

        if not outbound_all.empty:
            outbound_all = outbound_all[
                ~outbound_all["station_id"].isin(road_station_ids)
            ].copy()

        if not return_all.empty:
            return_all = return_all[
                ~return_all["origin_station_id"].isin(road_station_ids)
            ].copy()

        # Puis on évite les destinations de proximité typiquement
        # assimilables à un trajet RER / Transilien.
        if not outbound_all.empty:
            outbound_all = outbound_all[
                ~outbound_all["station_id"].map(
                    lambda x: is_suburban_or_idf_station(x, station_lookup)
                )
            ].copy()

        if not return_all.empty:
            return_all = return_all[
                ~return_all["origin_station_id"].map(
                    lambda x: is_suburban_or_idf_station(x, station_lookup)
                )
            ].copy()

        # On ne garde que les destinations pour lesquelles
        # un aller ET au moins un retour existent.
        outbound_destinations = set(
            outbound_all["station_id"]
        ) if not outbound_all.empty else set()

        return_destinations = set(
            return_all["origin_station_id"]
        ) if not return_all.empty else set()

        common_destinations = (
            outbound_destinations & return_destinations
        )

        outbound_all = outbound_all[
            outbound_all["station_id"].isin(common_destinations)
        ].copy()

        return_all = return_all[
            return_all["origin_station_id"].isin(common_destinations)
        ].copy()

        if not common_destinations:
            st.warning(
                "Aucune destination avec un aller et un retour direct ne correspond "
                "à ces critères."
            )
            st.caption(
                "Les trajets sont recherchés séparément : l'application ne tente "
                "pas de fabriquer une paire précise aller + retour."
            )
            st.stop()

        # ====================================================
        # 4. UNE CARTE PAR DESTINATION
        # ====================================================

        destination_rows = []

        # Une destination éditoriale peut regrouper plusieurs gares.
        # Exemple : LONGUEAU -> Amiens. On fusionne alors les horaires de
        # toutes les gares appartenant à la même destination.
        outbound_all["_destination_name"] = outbound_all["station_name"].map(
            lambda x: destination_name_for_station(x, destination_map)
        )
        return_station_names = return_all["origin_station_id"].map(
            station_lookup["station_name"]
        )
        return_all["_destination_name"] = return_station_names.map(
            lambda x: destination_name_for_station(x, destination_map)
        )

        common_destination_names = (
            set(outbound_all["_destination_name"])
            & set(return_all["_destination_name"])
        )

        for destination_name in common_destination_names:

            out = outbound_all[
                outbound_all["_destination_name"] == destination_name
            ].sort_values(["dep_min", "duration"])

            ret = return_all[
                return_all["_destination_name"] == destination_name
            ].sort_values(["dep_min", "duration"])

            if out.empty or ret.empty:
                continue

            # Pour le score, on utilise le meilleur aller et le meilleur retour.
            best_out = out.sort_values(
                ["duration", "dep_min"]
            ).iloc[0]

            best_ret = ret.sort_values(
                ["duration", "dep_min"]
            ).iloc[0]

            station_id = best_out["station_id"]
            station_name = str(best_out["station_name"])

            # On cherche d'abord le tarif de la destination éditoriale,
            # puis celui de la gare réelle. Cela permet à une gare secondaire
            # (ex. Longueau) de profiter du tarif de sa destination (Amiens)
            # lorsqu'il existe dans les données de référence.
            fare_min = fare_lookup(
                fares,
                "PARIS" if origin == "Paris (toutes les gares)" else origin,
                str(destination_name),
            )
            if pd.isna(fare_min) and norm(str(destination_name)) != norm(station_name):
                fare_min = fare_lookup(
                    fares,
                    "PARIS" if origin == "Paris (toutes les gares)" else origin,
                    station_name,
                )

            fare_ar = (
                fare_min * 2
                if pd.notna(fare_min)
                else np.nan
            )

            # Score = indication de potentiel, pas promesse de prix réel.
            time_score = np.clip(
                1 - (
                    float(best_out["duration"])
                    + float(best_ret["duration"])
                ) / (max_duration * 2),
                0,
                1,
            )

            if pd.notna(fare_ar):
                budget_score = np.clip(
                    1 - fare_ar / budget,
                    0,
                    1,
                )
            else:
                budget_score = 0.5

            schedule_score = np.clip(
                1 - abs(
                    float(best_out["dep_min"]) - 510
                ) / 600,
                0,
                1,
            )

            score = (
                0.45 * budget_score
                + 0.35 * time_score
                + 0.20 * schedule_score
            ) * 100

            destination_rows.append(
                {
                    "station_id": station_id,
                    "station_name": station_name,
                    "destination_name": destination_name,
                    "out": out,
                    "ret": ret,
                    "fare_ar": fare_ar,
                    "score": score,
                    "distance_km": station_lookup.loc[
                        station_id, "_distance_paris_km"
                    ],
                }
            )

        results = pd.DataFrame(destination_rows)

        if results.empty:
            st.warning(
                "Des trajets ont été trouvés, mais aucune destination "
                "ne possède à la fois des allers et des retours exploitables."
            )
            st.stop()

        results = results.sort_values(
            ["score", "distance_km"],
            ascending=[False, True],
        ).head(30)

        st.success(
            f"{len(results)} destinations avec des allers et des retours disponibles."
        )

        st.caption(
            f"Services actifs : {len(out_services)} à l'aller · "
            f"{len(in_services)} au retour · "
            f"{len(results)} destinations affichées"
        )

        st.caption(
            "Les gares sont regroupées selon la couche éditoriale En Train Alain : "
            "une gare peut donc être un arrêt secondaire d'une destination sans devenir "
            "une destination distincte."
        )

        # ====================================================
        # 5. AFFICHAGE
        # ====================================================

        for _, r in results.iterrows():

            out = r["out"].sort_values(
                ["dep_min", "duration"]
            ).drop_duplicates(
                ["dep_min", "arr_min"]
            ).head(8)

            ret = r["ret"].sort_values(
                ["dep_min", "duration"]
            ).drop_duplicates(
                ["dep_min", "arr_min"]
            ).head(8)

            fare_text = (
                f"≈ {r['fare_ar']:.0f} € A/R de référence"
                if pd.notna(r["fare_ar"])
                else "prix à vérifier"
            )

            with st.container(border=True):

                c1, c2 = st.columns([3, 1])

                with c1:
                    st.subheader(
                        str(r["destination_name"]).title()
                    )

                    st.caption(
                        f"{fare_text} · "
                        f"distance ≈ {r['distance_km']:.0f} km · "
                        f"score {r['score']:.0f}/100"
                    )

                    def journey_label(x):
                        conn = int(x.get("connections", 0))
                        if conn == 0:
                            return "direct"
                        transfer = str(x.get("transfer_station_name", "")).strip()
                        return (
                            f"1 correspondance à {transfer}"
                            if transfer and transfer != "nan"
                            else "1 correspondance"
                        )

                    def journey_route(x, destination):
                        try:
                            origin_name = str(
                                station_lookup.loc[x["origin_station_id"], "station_name"]
                            )
                        except Exception:
                            origin_name = str(x.get("origin_station_id", ""))
                        if int(x.get("connections", 0)) == 0:
                            return f"{origin_name} → {destination}"
                        transfer = str(x.get("transfer_station_name", "")).strip()
                        return f"{origin_name} → {transfer} → {destination}"

                    def render_journeys(frame, destination):
                        lines = []
                        for _, x in frame.iterrows():
                            lines.append(
                                f"- **{fmt_time(x['dep_min'])} → {fmt_time(x['arr_min'])}** · "
                                f"{fmt_duration(x['duration'])} · {journey_label(x)}"
                            )
                            if int(x.get("connections", 0)) > 0:
                                lines.append(f"  _{journey_route(x, destination)}_")
                        st.markdown("\n".join(lines))

                    # 4 horaires visibles, puis un menu pour les autres.
                    visible_out = out.head(4)
                    visible_ret = ret.head(4)
                    destination_label = str(r["destination_name"]).title()

                    st.markdown("🚆 **Allers disponibles**")
                    render_journeys(visible_out, destination_label)
                    if len(out) > len(visible_out):
                        with st.expander(
                            f"Autres horaires disponibles ({len(out) - len(visible_out)})"
                        ):
                            render_journeys(out.iloc[len(visible_out):], destination_label)

                    st.markdown("↩️ **Retours disponibles**")
                    render_journeys(visible_ret, destination_label)
                    if len(ret) > len(visible_ret):
                        with st.expander(
                            f"Autres horaires disponibles ({len(ret) - len(visible_ret)})"
                        ):
                            render_journeys(ret.iloc[len(visible_ret):], destination_label)

                    st.caption(
                        "Les horaires aller et retour sont volontairement "
                        "présentés séparément : à toi de choisir la combinaison "
                        "qui te convient."
                    )

                with c2:
                    st.metric(
                        "Deal Score",
                        f"{r['score']:.0f}/100"
                    )

else:
    st.markdown(
        """
        **Exemple :** choisis Paris, un week-end et un budget de 100 €.

        En Train Alain cherche les destinations réellement desservies,
        puis affiche séparément les horaires disponibles à l'aller et au retour.
        """
    )
