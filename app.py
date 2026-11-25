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
    if choice == "Paris (toutes les gares)":
        # On prend uniquement les gares dont le nom commence par Paris.
        mask = stations["station_name"].astype(str).str.match(
            r"^Paris\b", case=False, na=False
        )
        return set(stations.loc[mask, "station_id"])

    return set(stations.loc[stations["station_name"] == choice, "station_id"])


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

    # On ne garde que les trips qui partent bien de l'origine.
    trip_ids = origin["trip_id"].unique()

    downstream_cols = [
        "trip_id",
        "station_id",
        "station_name",
        "stop_sequence",
        "arrival_time",
        "trip_headsign",
    ]

    downstream = trips[
        trips["trip_id"].isin(trip_ids)
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

    downstream = downstream.merge(
        origins,
        on="trip_id",
        how="inner",
    )

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

    downstream["duration"] = (
        downstream["arr_min"] - downstream["dep_min"]
    )

    downstream = downstream[
        (downstream["duration"] > 0)
        & (downstream["duration"] <= max_duration)
    ]

    # Un seul passage par train + destination.
    downstream = (
        downstream
        .sort_values(["trip_id", "station_id", "arr_min"])
        .drop_duplicates(["trip_id", "station_id"])
    )

    return downstream[
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
    ].rename(
        columns={"origin_departure_time": "departure_time"}
    )


# ------------------------------------------------------------
# Recherche de trajets à 1 correspondance
# ------------------------------------------------------------

def one_connection_journeys(
    trips,
    services,
    origin_ids,
    destination_ids=None,
    dep_start=300,
    dep_end=1380,
    max_duration=600,
    min_transfer=10,
    max_transfer=120,
    max_first_stops=12,
    max_second_options_per_transfer=3,
):
    """
    Cherche des trajets avec exactement 1 correspondance.

    La logique est volontairement conservatrice :
    - le 1er train part de l'origine ;
    - la correspondance se fait dans une gare desservie par ce train ;
    - le 2e train part 10 à 120 min plus tard ;
    - la destination est atteinte dans la durée maximale du trajet ;
    - on exclut les boucles et les changements sur le même train.

    Le calcul est fait par gare de correspondance avec searchsorted plutôt
    qu'avec un gros merge de tous les passages, afin de rester exploitable
    sur le GTFS complet.
    """
    rail = rail_rows(trips, services)
    if rail.empty:
        return pd.DataFrame()

    origin = rail[rail["station_id"].isin(origin_ids)].copy()
    if origin.empty:
        return pd.DataFrame()

    origin["dep_min"] = origin["departure_time"].map(parse_gtfs_time)
    origin = origin[
        origin["dep_min"].between(dep_start, dep_end)
        & origin["dep_min"].notna()
    ].copy()
    if origin.empty:
        return pd.DataFrame()

    origin = origin.rename(
        columns={
            "stop_sequence": "origin_seq",
            "station_id": "origin_station_id",
            "departure_time": "origin_departure_time",
        }
    )

    # Passages en aval des trains partant de l'origine : candidats
    # aux gares de correspondance.
    first_trip_ids = origin["trip_id"].unique()
    first_cols = [
        "trip_id", "station_id", "station_name", "stop_sequence",
        "arrival_time", "trip_headsign"
    ]
    first_downstream = trips[
        trips["trip_id"].isin(first_trip_ids)
    ][first_cols].copy()

    first_downstream = first_downstream.merge(
        origin[[
            "trip_id", "origin_seq", "origin_station_id",
            "origin_departure_time", "dep_min"
        ]],
        on="trip_id",
        how="inner",
    )
    first_downstream["transfer_arr_min"] = first_downstream["arrival_time"].map(parse_gtfs_time)
    first_downstream = first_downstream[
        (first_downstream["stop_sequence"] > first_downstream["origin_seq"])
        & first_downstream["station_id"].notna()
        & first_downstream["transfer_arr_min"].notna()
        & ((first_downstream["transfer_arr_min"] - first_downstream["dep_min"]) > 0)
    ].copy()

    if first_downstream.empty:
        return pd.DataFrame()

    # On ne regarde que les premiers arrêts raisonnables comme correspondances.
    first_downstream = first_downstream.sort_values(
        ["trip_id", "stop_sequence"]
    )
    first_downstream["_rank"] = first_downstream.groupby("trip_id").cumcount()
    first_downstream = first_downstream[
        first_downstream["_rank"] < max_first_stops
    ].copy()

    # Gares dans lesquelles un second train pourrait partir.
    transfer_stations = first_downstream["station_id"].unique()
    second_origins = rail[
        rail["station_id"].isin(transfer_stations)
    ][[
        "trip_id", "station_id", "station_name", "stop_sequence",
        "departure_time", "trip_headsign"
    ]].copy()
    second_origins["second_dep_min"] = second_origins["departure_time"].map(parse_gtfs_time)
    second_origins = second_origins[second_origins["second_dep_min"].notna()].copy()

    if second_origins.empty:
        return pd.DataFrame()

    # Index par gare pour trouver rapidement les départs après la correspondance.
    second_groups = {}
    for sid, grp in second_origins.groupby("station_id", sort=False):
        g = grp.sort_values("second_dep_min").reset_index(drop=True)
        second_groups[sid] = g

    selected = []

    for sid, first_grp in first_downstream.groupby("station_id", sort=False):
        second_grp = second_groups.get(sid)
        if second_grp is None or second_grp.empty:
            continue

        dep_values = second_grp["second_dep_min"].to_numpy()

        for _, f in first_grp.iterrows():
            lo = float(f["transfer_arr_min"]) + min_transfer
            hi = float(f["transfer_arr_min"]) + max_transfer
            left = dep_values.searchsorted(lo, side="left")
            right = dep_values.searchsorted(hi, side="right")

            if right <= left:
                continue

            candidates = second_grp.iloc[left:min(right, left + max_second_options_per_transfer)]
            for _, s in candidates.iterrows():
                if str(s["trip_id"]) == str(f["trip_id"]):
                    continue
                selected.append({
                    "first_trip_id": f["trip_id"],
                    "origin_station_id": f["origin_station_id"],
                    "origin_departure_time": f["origin_departure_time"],
                    "origin_dep_min": f["dep_min"],
                    "transfer_station_id": sid,
                    "transfer_station_name": f["station_name"],
                    "transfer_arr_min": f["transfer_arr_min"],
                    "second_trip_id": s["trip_id"],
                    "second_origin_seq": s["stop_sequence"],
                    "second_departure_time": s["departure_time"],
                    "second_dep_min": s["second_dep_min"],
                })

    if not selected:
        return pd.DataFrame()

    selected = pd.DataFrame(selected).drop_duplicates(
        ["first_trip_id", "transfer_station_id", "second_trip_id"]
    )

    # On déroule le 2e train jusqu'à ses destinations.
    second_trip_ids = selected["second_trip_id"].unique()
    downstream_cols = [
        "trip_id", "station_id", "station_name", "stop_sequence",
        "arrival_time", "trip_headsign"
    ]
    second_downstream = trips[
        trips["trip_id"].isin(second_trip_ids)
    ][downstream_cols].copy()

    second_downstream = second_downstream.merge(
        selected,
        left_on="trip_id",
        right_on="second_trip_id",
        how="inner",
    )

    second_downstream = second_downstream[
        second_downstream["stop_sequence"] > second_downstream["second_origin_seq"]
    ].copy()
    second_downstream["arr_min"] = second_downstream["arrival_time"].map(parse_gtfs_time)
    second_downstream = second_downstream[second_downstream["arr_min"].notna()].copy()

    if destination_ids is not None:
        second_downstream = second_downstream[
            second_downstream["station_id"].isin(destination_ids)
        ].copy()

    second_downstream["duration"] = (
        second_downstream["arr_min"] - second_downstream["origin_dep_min"]
    )
    second_downstream = second_downstream[
        (second_downstream["duration"] > 0)
        & (second_downstream["duration"] <= max_duration)
    ].copy()

    if second_downstream.empty:
        return pd.DataFrame()

    # Un seul itinéraire par destination / paire de trains.
    second_downstream = (
        second_downstream
        .sort_values(["station_id", "duration", "origin_dep_min"])
        .drop_duplicates(["first_trip_id", "second_trip_id", "station_id"])
    )

    return second_downstream[[
        "first_trip_id",
        "second_trip_id",
        "station_id",
        "station_name",
        "origin_station_id",
        "origin_departure_time",
        "arr_min",
        "origin_dep_min",
        "duration",
        "transfer_station_id",
        "transfer_station_name",
        "transfer_arr_min",
        "second_departure_time",
        "second_dep_min",
        "trip_headsign",
    ]].rename(columns={
        "origin_departure_time": "departure_time",
    })


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
    "Tu as un budget, on cherche où partir. — V10 : allers et retours disponibles"
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
    "Cette version utilise les horaires SNCF réels. "
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
        # 1. ALLERS DISPONIBLES : DIRECT + 1 CORRESPONDANCE
        # ====================================================

        outbound_direct = direct_journeys(
            trips,
            out_services,
            origin_ids,
            dep_start=dep_start,
            dep_end=dep_end,
            max_duration=max_duration,
        )

        outbound_connections = one_connection_journeys(
            trips,
            out_services,
            origin_ids,
            dep_start=dep_start,
            dep_end=dep_end,
            max_duration=max_duration,
        )

        if outbound_direct.empty and outbound_connections.empty:
            outbound_all = pd.DataFrame()
        else:
            out_parts = []
            if not outbound_direct.empty:
                d = outbound_direct.copy()
                d["journey_type"] = "direct"
                d["sort_type"] = 0
                out_parts.append(d)
            if not outbound_connections.empty:
                c = outbound_connections.copy()
                c["journey_type"] = "1 correspondance"
                c["sort_type"] = 1
                out_parts.append(c)
            outbound_all = pd.concat(out_parts, ignore_index=True, sort=False)

        # ====================================================
        # 2. RETOURS DISPONIBLES : DIRECT + 1 CORRESPONDANCE
        # ====================================================

        # On garde les allers et les retours indépendants. On ne fabrique
        # toujours PAS une paire aller/retour imposée.
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

            return_connections = one_connection_journeys(
                trips,
                in_services,
                possible_destination_ids,
                destination_ids=origin_ids,
                dep_start=600,
                dep_end=1500,
                max_duration=max_duration,
            )

            ret_parts = []
            if not return_direct.empty:
                d = return_direct.copy()
                d["journey_type"] = "direct"
                d["sort_type"] = 0
                ret_parts.append(d)
            if not return_connections.empty:
                c = return_connections.copy()
                # Pour un retour, le champ station_id correspond à l'origine
                # du trajet (la destination du week-end).
                c["origin_station_id"] = c["origin_station_id"]
                c["journey_type"] = "1 correspondance"
                c["sort_type"] = 1
                ret_parts.append(c)

            if ret_parts:
                return_all = pd.concat(ret_parts, ignore_index=True, sort=False)

        # Normalisation des colonnes pour que directs et correspondances
        # soient traités par le même moteur de classement / affichage.
        if not outbound_all.empty:
            if "origin_dep_min" in outbound_all.columns:
                outbound_all["dep_min"] = outbound_all["origin_dep_min"]
            if "departure_time" not in outbound_all.columns and "origin_departure_time" in outbound_all.columns:
                outbound_all["departure_time"] = outbound_all["origin_departure_time"]

        if not return_all.empty:
            if "origin_dep_min" in return_all.columns:
                return_all["dep_min"] = return_all["origin_dep_min"]
            if "departure_time" not in return_all.columns and "origin_departure_time" in return_all.columns:
                return_all["departure_time"] = return_all["origin_departure_time"]

            # Le moteur de correspondance retourne station_name pour la gare
            # finale. Pour un retour, la carte doit afficher le nom de la
            # destination de départ du week-end : on le récupère depuis l'aller.
            if "station_id" in return_all.columns and not outbound_all.empty:
                dest_names = (
                    outbound_all[["station_id", "station_name"]]
                    .dropna()
                    .drop_duplicates("station_id")
                    .set_index("station_id")["station_name"]
                    .to_dict()
                )
                return_all["station_name"] = return_all["origin_station_id"].map(dest_names)

        # ====================================================
        # 3. EXCLUSION DES DESTINATIONS DE PROXIMITÉ
        # ====================================================

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
                "Aucune destination avec un aller et un retour (direct ou avec 1 correspondance) "
                "ne correspond à ces critères."
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

        for station_id in common_destinations:

            out = outbound_all[
                outbound_all["station_id"] == station_id
            ].sort_values(["dep_min", "duration"])

            ret = return_all[
                return_all["origin_station_id"] == station_id
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

            station_name = str(
                best_out["station_name"]
            )

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
            f"{len(results)} destinations affichées · "
            f"direct + 1 correspondance"
        )

        # ====================================================
        # 5. AFFICHAGE
        # ====================================================

        st.caption("🚆 direct · 🔄 1 correspondance — les deux types de trajets sont classés ensemble.")

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
                        str(r["station_name"]).title()
                    )

                    st.caption(
                        f"{fare_text} · "
                        f"distance ≈ {r['distance_km']:.0f} km · "
                        f"score {r['score']:.0f}/100"
                    )

                    st.markdown("🚆 **Allers disponibles**")

                    out_lines = []
                    for _, x in out.iterrows():
                        out_lines.append(
                            f"- {fmt_time(x['dep_min'])} → "
                            f"{fmt_time(x['arr_min'])} · "
                            f"{fmt_duration(x['duration'])} · "
                            f"{x.get('journey_type', 'direct')}"
                        )

                    st.markdown("\n".join(out_lines))

                    st.markdown("↩️ **Retours disponibles**")

                    ret_lines = []
                    for _, x in ret.iterrows():
                        ret_lines.append(
                            f"- {fmt_time(x['dep_min'])} → "
                            f"{fmt_time(x['arr_min'])} · "
                            f"{fmt_duration(x['duration'])} · "
                            f"{x.get('journey_type', 'direct')}"
                        )

                    st.markdown("\n".join(ret_lines))

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
