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
    min_change=8,
    max_change=45,
    max_first_trips=160,
    max_transfer_stops_per_trip=10,
    max_second_trips_per_transfer=4,
):
    """Cherche des trajets à exactement 1 correspondance.

    Retourne les deux tronçons complets pour permettre un affichage
    compréhensible : départ -> correspondance -> arrivée.
    """
    rail = rail_rows(trips, services).copy()
    if rail.empty:
        return pd.DataFrame()

    rail["dep_min"] = rail["departure_time"].map(parse_gtfs_time)
    rail["arr_min"] = rail["arrival_time"].map(parse_gtfs_time)
    rail = rail[rail["dep_min"].notna() | rail["arr_min"].notna()].copy()

    # 1) Premiers trains au départ.
    first = rail[
        rail["station_id"].isin(origin_ids)
        & rail["dep_min"].between(dep_start, dep_end)
        & rail["dep_min"].notna()
    ].copy()

    if first.empty:
        return pd.DataFrame()

    # On garde un nombre raisonnable de départs répartis dans la journée.
    first = (
        first.sort_values(["dep_min", "trip_id", "stop_sequence"])
        .drop_duplicates(["trip_id", "station_id", "dep_min"])
    )
    if len(first) > max_first_trips:
        idx = np.linspace(0, len(first) - 1, max_first_trips).astype(int)
        first = first.iloc[np.unique(idx)].copy()

    # 2) Tous les arrêts suivants de ces premiers trains = points de correspondance possibles.
    first_origins = first[
        ["trip_id", "station_id", "stop_sequence", "dep_min", "departure_time"]
    ].rename(
        columns={
            "station_id": "origin_station_id",
            "stop_sequence": "origin_seq",
            "dep_min": "origin_dep_min",
            "departure_time": "origin_departure_time",
        }
    )

    first_stops = rail[
        rail["trip_id"].isin(first["trip_id"].unique())
    ][
        [
            "trip_id", "station_id", "station_name", "stop_sequence",
            "arrival_time", "arr_min", "trip_headsign"
        ]
    ].merge(first_origins, on="trip_id", how="inner")

    first_stops = first_stops[
        (first_stops["stop_sequence"] > first_stops["origin_seq"])
        & first_stops["arr_min"].notna()
        & (first_stops["station_id"] != first_stops["origin_station_id"])
    ].copy()

    if first_stops.empty:
        return pd.DataFrame()

    # Pour éviter des correspondances absurdes très loin sur le premier train,
    # on ne considère que les premiers points de correspondance de chaque train.
    first_stops = (
        first_stops.sort_values(
            ["trip_id", "stop_sequence"]
        )
        .groupby("trip_id", sort=False)
        .head(max_transfer_stops_per_trip)
    )

    # 3) Index des départs par gare de correspondance.
    second = rail[
        rail["dep_min"].notna()
    ][
        [
            "trip_id", "station_id", "station_name", "stop_sequence",
            "departure_time", "dep_min", "trip_headsign"
        ]
    ].copy()

    second = second.sort_values(["station_id", "dep_min", "trip_id"])
    dep_index = {}
    for sid, g in second.groupby("station_id", sort=False):
        dep_index[sid] = (
            g["dep_min"].to_numpy(),
            g.index.to_numpy(),
        )

    # Index des arrêts par train : évite de refaire rail[rail.trip_id == ...]
    # des milliers de fois.
    trip_rows = {
        tid: g
        for tid, g in rail.groupby("trip_id", sort=False)
    }

    destination_set = set(destination_ids) if destination_ids is not None else None
    candidates = []

    for row in first_stops.itertuples(index=False):
        idx_data = dep_index.get(row.station_id)
        if idx_data is None:
            continue

        dep_values, dep_indices = idx_data

        lo = np.searchsorted(
            dep_values,
            float(row.arr_min) + min_change,
            side="left",
        )
        hi = np.searchsorted(
            dep_values,
            float(row.arr_min) + max_change,
            side="right",
        )

        if hi <= lo:
            continue

        # Quelques deuxièmes trains suffisent pour découvrir les possibilités
        # sans transformer la recherche en générateur combinatoire.
        for pos in range(lo, min(hi, lo + max_second_trips_per_transfer)):
            sec_idx = dep_indices[pos]
            sec = second.loc[sec_idx]

            if str(sec["trip_id"]) == str(row.trip_id):
                continue

            sec_trip = trip_rows.get(sec["trip_id"])
            if sec_trip is None:
                continue

            dests = sec_trip[
                (sec_trip["stop_sequence"] > sec["stop_sequence"])
                & sec_trip["arr_min"].notna()
            ].copy()

            if destination_set is not None:
                dests = dests[dests["station_id"].isin(destination_set)]

            if dests.empty:
                continue

            dests = (
                dests.sort_values(["station_id", "arr_min"])
                .drop_duplicates(["station_id"])
            )

            for dest in dests.itertuples(index=False):
                total = float(dest.arr_min) - float(row.origin_dep_min)

                if total <= 0 or total > max_duration:
                    continue

                candidates.append(
                    {
                        "trip_id": f"{row.trip_id}__{sec['trip_id']}",
                        "station_id": str(dest.station_id),
                        "station_name": str(dest.station_name),
                        "dep_min": float(row.origin_dep_min),
                        "arr_min": float(dest.arr_min),
                        "origin_station_id": str(row.origin_station_id),
                        "departure_time": row.origin_departure_time,
                        "arrival_time": dest.arrival_time,
                        "duration": total,
                        "trip_headsign": f"{row.trip_headsign} / {sec['trip_headsign']}",
                        "journey_type": "1 correspondance",
                        "transfer_station_id": str(row.station_id),
                        "transfer_station_name": str(row.station_name),
                        "transfer_arr_min": float(row.arr_min),
                        "transfer_dep_min": float(sec["dep_min"]),
                        "change_duration": float(sec["dep_min"] - row.arr_min),
                        "first_leg_trip_id": str(row.trip_id),
                        "second_leg_trip_id": str(sec["trip_id"]),
                        "first_leg_departure_time": row.origin_departure_time,
                        "first_leg_arrival_time": row.arrival_time,
                        "second_leg_departure_time": sec["departure_time"],
                        "second_leg_arrival_time": dest.arrival_time,
                    }
                )

    if not candidates:
        return pd.DataFrame()

    out = pd.DataFrame(candidates)

    # On évite les doublons et les variantes moins bonnes.
    out = (
        out.sort_values(
            ["station_id", "duration", "change_duration", "dep_min"]
        )
        .drop_duplicates(
            [
                "origin_station_id",
                "station_id",
                "dep_min",
                "transfer_station_id",
                "transfer_dep_min",
                "arr_min",
            ]
        )
    )

    return out


def merge_journey_types(direct, connections):
    frames = []

    if direct is not None and not direct.empty:
        d = direct.copy()
        d["journey_type"] = "direct"
        d["change_duration"] = np.nan
        d["transfer_station_id"] = ""
        d["transfer_station_name"] = ""
        frames.append(d)

    if connections is not None and not connections.empty:
        frames.append(connections.copy())

    if not frames:
        return pd.DataFrame()

    return pd.concat(frames, ignore_index=True, sort=False)


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
    "Tu as un budget, on cherche où partir. — V12 : trajets directs + correspondances qualitatives"
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
        st.warning("Aucun service SNCF n'est renseigné pour cette date aller dans le fichier GTFS.")
        st.stop()

    if not in_services:
        st.warning("Aucun service SNCF n'est renseigné pour cette date retour dans le fichier GTFS.")
        st.stop()

    with st.spinner("Recherche des destinations réelles…"):

        # ====================================================
        # 1. DIRECTS ALLER
        # ====================================================

        outbound_direct = direct_journeys(
            trips,
            out_services,
            origin_ids,
            dep_start=dep_start,
            dep_end=dep_end,
            max_duration=max_duration,
        )

        # ====================================================
        # 2. DIRECTS RETOUR
        # ====================================================

        # On commence par les destinations trouvées en direct à l'aller.
        # Puis les correspondances élargiront l'univers si nécessaire.
        direct_destinations = (
            set(outbound_direct["station_id"])
            if not outbound_direct.empty else set()
        )

        return_direct = direct_journeys(
            trips,
            in_services,
            direct_destinations if direct_destinations else set(),
            destination_ids=origin_ids,
            dep_start=300,
            dep_end=1500,
            max_duration=max_duration,
        ) if direct_destinations else pd.DataFrame()

        # ====================================================
        # 3. CORRESPONDANCES ALLER
        # ====================================================

        outbound_conn = one_connection_journeys(
            trips,
            out_services,
            origin_ids,
            destination_ids=None,
            dep_start=dep_start,
            dep_end=dep_end,
            max_duration=max_duration,
        )

        # Exclusion proximité avant de construire les retours.
        def keep_destination(df, destination_col="station_id"):
            if df.empty:
                return df
            return df[
                ~df[destination_col].map(
                    lambda x: is_suburban_or_idf_station(x, station_lookup)
                )
            ].copy()

        outbound_direct = keep_destination(outbound_direct, "station_id")
        outbound_conn = keep_destination(outbound_conn, "station_id")
        return_direct = (
            return_direct[
                ~return_direct["origin_station_id"].map(
                    lambda x: is_suburban_or_idf_station(x, station_lookup)
                )
            ].copy()
            if not return_direct.empty else return_direct
        )

        outbound_candidates = pd.concat(
            [outbound_direct, outbound_conn],
            ignore_index=True,
            sort=False,
        ) if not outbound_conn.empty or not outbound_direct.empty else pd.DataFrame()

        # ====================================================
        # 4. CORRESPONDANCES RETOUR
        # ====================================================

        candidate_destinations = (
            set(outbound_candidates["station_id"])
            if not outbound_candidates.empty else set()
        )

        # On cherche les retours directs supplémentaires pour les destinations
        # accessibles uniquement avec correspondance à l'aller.
        if candidate_destinations:
            missing_direct_return = direct_journeys(
                trips,
                in_services,
                candidate_destinations,
                destination_ids=origin_ids,
                dep_start=300,
                dep_end=1500,
                max_duration=max_duration,
            )
        else:
            missing_direct_return = pd.DataFrame()

        missing_direct_return = (
            missing_direct_return[
                ~missing_direct_return["origin_station_id"].map(
                    lambda x: is_suburban_or_idf_station(x, station_lookup)
                )
            ].copy()
            if not missing_direct_return.empty else missing_direct_return
        )

        return_direct = pd.concat(
            [return_direct, missing_direct_return],
            ignore_index=True,
            sort=False,
        ) if not missing_direct_return.empty else return_direct

        # Correspondance retour pour les destinations sans retour direct.
        direct_return_destinations = (
            set(return_direct["origin_station_id"])
            if not return_direct.empty else set()
        )
        need_return_conn = candidate_destinations - direct_return_destinations

        return_conn = one_connection_journeys(
            trips,
            in_services,
            need_return_conn,
            destination_ids=origin_ids,
            dep_start=300,
            dep_end=1500,
            max_duration=max_duration,
        ) if need_return_conn else pd.DataFrame()

        if not return_conn.empty:
            return_conn = return_conn[
                ~return_conn["origin_station_id"].map(
                    lambda x: is_suburban_or_idf_station(x, station_lookup)
                )
            ].copy()

        return_all = merge_journey_types(
            return_direct,
            return_conn,
        )
        outbound_all = merge_journey_types(
            outbound_direct,
            outbound_conn,
        )

        # ====================================================
        # 5. DESTINATIONS AVEC ALLER + RETOUR
        # ====================================================

        outbound_destinations = (
            set(outbound_all["station_id"])
            if not outbound_all.empty else set()
        )
        return_destinations = (
            set(return_all["origin_station_id"])
            if not return_all.empty else set()
        )

        common_destinations = outbound_destinations & return_destinations

        if not common_destinations:
            st.warning(
                "Aucune destination avec un aller et un retour exploitables "
                "ne correspond à ces critères."
            )
            st.stop()

        outbound_all = outbound_all[
            outbound_all["station_id"].isin(common_destinations)
        ].copy()
        return_all = return_all[
            return_all["origin_station_id"].isin(common_destinations)
        ].copy()

        # ====================================================
        # 6. SCORE DE PERTINENCE
        # ====================================================

        destination_rows = []

        for station_id in common_destinations:

            out = outbound_all[
                outbound_all["station_id"] == station_id
            ].copy()

            ret = return_all[
                return_all["origin_station_id"] == station_id
            ].copy()

            if out.empty or ret.empty:
                continue

            # Meilleur trajet pour évaluer la destination :
            # direct prioritaire, mais une correspondance correcte reste admissible.
            out["_connection_penalty"] = out["journey_type"].map(
                {"direct": 0, "1 correspondance": 10}
            ).fillna(20)
            ret["_connection_penalty"] = ret["journey_type"].map(
                {"direct": 0, "1 correspondance": 10}
            ).fillna(20)

            out = out.sort_values(
                ["_connection_penalty", "duration", "change_duration", "dep_min"]
            )
            ret = ret.sort_values(
                ["_connection_penalty", "duration", "change_duration", "dep_min"]
            )

            best_out = out.iloc[0]
            best_ret = ret.iloc[0]

            station_name = str(best_out["station_name"])

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

            # Qualité temporelle de l'escapade.
            total_travel = float(best_out["duration"]) + float(best_ret["duration"])
            time_score = np.clip(
                1 - total_travel / (max_duration * 2),
                0,
                1,
            )

            # Régularité de l'offre : plusieurs horaires = plus de liberté.
            option_score = np.clip(
                (min(len(out), 8) + min(len(ret), 8)) / 16,
                0,
                1,
            )

            # Une correspondance pénalise la destination, mais pas au point
            # de l'éliminer automatiquement.
            connection_penalty = 0
            if best_out["journey_type"] == "1 correspondance":
                connection_penalty += 7
            if best_ret["journey_type"] == "1 correspondance":
                connection_penalty += 7

            if pd.notna(best_out.get("change_duration", np.nan)):
                wait = float(best_out["change_duration"])
                if wait > 35:
                    connection_penalty += min(5, (wait - 35) / 5)

            if pd.notna(best_ret.get("change_duration", np.nan)):
                wait = float(best_ret["change_duration"])
                if wait > 35:
                    connection_penalty += min(5, (wait - 35) / 5)

            if pd.notna(fare_ar):
                budget_score = np.clip(
                    1 - fare_ar / budget,
                    0,
                    1,
                )
            else:
                # On ne prétend pas connaître le prix réel.
                budget_score = 0.5

            schedule_score = np.clip(
                1 - abs(float(best_out["dep_min"]) - 510) / 600,
                0,
                1,
            )

            score = (
                0.42 * budget_score
                + 0.30 * time_score
                + 0.16 * option_score
                + 0.12 * schedule_score
            ) * 100 - connection_penalty

            destination_rows.append(
                {
                    "station_id": station_id,
                    "station_name": station_name,
                    "out": out.drop(columns=["_connection_penalty"]),
                    "ret": ret.drop(columns=["_connection_penalty"]),
                    "fare_ar": fare_ar,
                    "score": score,
                    "distance_km": station_lookup.loc[
                        station_id, "_distance_paris_km"
                    ],
                    "best_out_type": best_out["journey_type"],
                    "best_ret_type": best_ret["journey_type"],
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

        direct_count = sum(
            1
            for _, r in results.iterrows()
            if r["best_out_type"] == "direct"
            and r["best_ret_type"] == "direct"
        )

        st.success(
            f"{len(results)} destinations pertinentes trouvées."
        )

        st.caption(
            f"Allers : {len(outbound_all)} options · "
            f"Retours : {len(return_all)} options · "
            f"{direct_count}/{len(results)} destinations avec direct recommandé "
            f"dans les deux sens."
        )

        # ====================================================
        # 7. AFFICHAGE
        # ====================================================

        for _, r in results.iterrows():

            out = (
                r["out"]
                .sort_values(["dep_min", "duration"])
                .drop_duplicates(
                    ["dep_min", "arr_min", "transfer_station_id"]
                )
                .head(8)
            )

            ret = (
                r["ret"]
                .sort_values(["dep_min", "duration"])
                .drop_duplicates(
                    ["dep_min", "arr_min", "transfer_station_id"]
                )
                .head(8)
            )

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

                    st.markdown(
                        "🚆 **Allers disponibles**"
                    )

                    out_lines = []

                    for _, x in out.iterrows():

                        if x["journey_type"] == "direct":

                            line = (
                                f"- **{fmt_time(x['dep_min'])} → "
                                f"{fmt_time(x['arr_min'])}** · "
                                f"{fmt_duration(x['duration'])} · "
                                f"direct · départ **{x['origin_station_id']}**"
                            )

                            # Remplace l'ID par le nom si possible.
                            try:
                                dep_name = station_lookup.loc[
                                    x["origin_station_id"], "station_name"
                                ]
                                line = (
                                    f"- **{fmt_time(x['dep_min'])} → "
                                    f"{fmt_time(x['arr_min'])}** · "
                                    f"{fmt_duration(x['duration'])} · direct · "
                                    f"🚉 {dep_name}"
                                )
                            except Exception:
                                pass

                        else:

                            try:
                                dep_name = station_lookup.loc[
                                    x["origin_station_id"], "station_name"
                                ]
                            except Exception:
                                dep_name = x["origin_station_id"]

                            line = (
                                f"- **{fmt_time(x['dep_min'])} → "
                                f"{fmt_time(x['arr_min'])}** · "
                                f"{fmt_duration(x['duration'])} · "
                                f"**1 correspondance à {x['transfer_station_name']}** · "
                                f"🚉 {dep_name} → "
                                f"{fmt_time(x['transfer_arr_min'])} / "
                                f"{fmt_time(x['transfer_dep_min'])} "
                                f"({fmt_duration(x['change_duration'])})"
                            )

                        out_lines.append(line)

                    st.markdown("\n".join(out_lines))

                    st.markdown(
                        "↩️ **Retours disponibles**"
                    )

                    ret_lines = []

                    for _, x in ret.iterrows():

                        if x["journey_type"] == "direct":

                            try:
                                dep_name = station_lookup.loc[
                                    x["origin_station_id"], "station_name"
                                ]
                            except Exception:
                                dep_name = x["origin_station_id"]

                            line = (
                                f"- **{fmt_time(x['dep_min'])} → "
                                f"{fmt_time(x['arr_min'])}** · "
                                f"{fmt_duration(x['duration'])} · direct · "
                                f"🚉 {dep_name}"
                            )

                        else:

                            try:
                                dep_name = station_lookup.loc[
                                    x["origin_station_id"], "station_name"
                                ]
                            except Exception:
                                dep_name = x["origin_station_id"]

                            line = (
                                f"- **{fmt_time(x['dep_min'])} → "
                                f"{fmt_time(x['arr_min'])}** · "
                                f"{fmt_duration(x['duration'])} · "
                                f"**1 correspondance à {x['transfer_station_name']}** · "
                                f"🚉 {dep_name} → "
                                f"{fmt_time(x['transfer_arr_min'])} / "
                                f"{fmt_time(x['transfer_dep_min'])} "
                                f"({fmt_duration(x['change_duration'])})"
                            )

                        ret_lines.append(line)

                    st.markdown("\n".join(ret_lines))

                    st.caption(
                        "Les horaires aller et retour restent volontairement "
                        "indépendants : à toi de choisir la combinaison qui te convient."
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
        puis affiche les horaires disponibles à l'aller et au retour.
        """
    )
