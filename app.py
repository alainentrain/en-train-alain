import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import timedelta
import re
import unicodedata
import math

st.set_page_config(page_title="En Train Alain", page_icon="🚆", layout="wide")

VERSION = "V10"
DATA = Path(__file__).parent / "data"

# -------------------------------------------------------------------
# Data
# -------------------------------------------------------------------

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

    return stations, routes, cal, trips


@st.cache_data
def load_fares():
    path = DATA / "tarifs-tgv-inoui-ouigo.csv"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, sep=None, engine="python", dtype=str)


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

def norm(value):
    if pd.isna(value):
        return ""
    value = (
        unicodedata.normalize("NFKD", str(value))
        .encode("ascii", "ignore")
        .decode()
    )
    value = value.upper().replace("'", " ").replace("-", " ")
    value = re.sub(r"\bHALL\s+\d+(?:\s*-\s*\d+)?\b", "", value)
    value = re.sub(r"[^A-Z0-9 ]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def parse_gtfs_time(value):
    try:
        h, m, s = str(value).split(":")
        return int(h) * 60 + int(m)
    except Exception:
        return np.nan


def fmt_time(value):
    if pd.isna(value):
        return "—"
    s = str(value).strip()
    if ":" in s:
        try:
            parts = s.split(":")
            return f"{int(parts[0]) % 24:02d}:{int(parts[1]):02d}"
        except Exception:
            return "—"
    try:
        total = int(round(float(s)))
        return f"{(total // 60) % 24:02d}:{total % 60:02d}"
    except Exception:
        return "—"


def fmt_duration(minutes):
    if pd.isna(minutes):
        return "durée inconnue"
    minutes = int(round(float(minutes)))
    return f"{minutes // 60} h {minutes % 60:02d}"


def active_services(cal, date_value):
    date_str = date_value.strftime("%Y%m%d")
    rows = cal[cal["date"] == date_str]
    added = set(rows.loc[rows["exception_type"] == 1, "service_id"])
    removed = set(rows.loc[rows["exception_type"] == 2, "service_id"])
    return added - removed


def is_paris_station_name(name):
    n = norm(name)
    patterns = (
        "PARIS GARE DE LYON",
        "PARIS MONTPARNASSE",
        "PARIS GARE DU NORD",
        "PARIS GARE DE L EST",
        "PARIS SAINT LAZARE",
        "PARIS AUSTERLITZ",
        "PARIS BERCY",
    )
    return n == "PARIS" or any(n.startswith(p) for p in patterns)


def station_options(stations):
    return ["Paris (toutes les gares)"] + sorted(
        stations["station_name"].dropna().unique().tolist()
    )


def station_ids_for_choice(choice, stations):
    if choice == "Paris (toutes les gares)":
        mask = stations["station_name"].map(is_paris_station_name)
        return set(stations.loc[mask, "station_id"].astype(str))
    return set(
        stations.loc[
            stations["station_name"] == choice, "station_id"
        ].astype(str)
    )


# -------------------------------------------------------------------
# Destination filtering
# -------------------------------------------------------------------

PARIS_LAT = 48.8566
PARIS_LON = 2.3522
MIN_DESTINATION_DISTANCE_KM = 50

# This is intentionally a discovery filter, not a claim about the
# administrative Île-de-France boundary. It prevents RER / Transilien
# suburbs from becoming the main "travel destinations".
IDF_TERMS = (
    "RER",
    "TRANSILIEN",
    "VAL D EUROPE",
    "MARNE LA VALLEE",
    "MASSY",
    "VERSAILLES",
    "SAINT QUENTIN EN YVELINES",
    "AEROPORT CDG",
    "ROISSY",
    "ORLY",
    "CERGY",
    "MELUN",
    "FONTAINEBLEAU",
    "CORBEIL",
    "EVRY",
    "MANTES LA JOLIE",
    "MEAUX",
    "MITRY",
    "LAGNY",
    "CHELLES",
    "CREIL",
    "ORRY LA VILLE",
)


def haversine_km(lat, lon):
    lat1 = math.radians(PARIS_LAT)
    lon1 = math.radians(PARIS_LON)
    lat2 = np.radians(pd.to_numeric(lat, errors="coerce"))
    lon2 = np.radians(pd.to_numeric(lon, errors="coerce"))

    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = (
        np.sin(dlat / 2) ** 2
        + math.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    )
    return 6371.0 * 2 * np.arcsin(np.sqrt(a))


def destination_mask(stations):
    distance = haversine_km(stations["lat"], stations["lon"])
    name_norm = stations["station_name"].fillna("").map(norm)
    term_mask = name_norm.map(
        lambda name: any(term in name for term in IDF_TERMS)
    )
    return (
        (distance >= MIN_DESTINATION_DISTANCE_KM)
        & (~term_mask)
        & (~stations["station_name"].map(is_paris_station_name))
    )


# -------------------------------------------------------------------
# Journey search
# -------------------------------------------------------------------

def rail_rows(trips, services):
    return trips[
        trips["service_id"].isin(services)
        & (trips["route_type"] == 2)
    ].copy()


def direct_journeys(
    trips,
    services,
    origin_ids,
    destination_ids=None,
    dep_start=300,
    dep_end=1380,
    max_duration=600,
):
    base = rail_rows(trips, services)
    base = base[base["station_id"].isin(origin_ids)].copy()

    if base.empty:
        return pd.DataFrame()

    base["dep_min"] = base["departure_time"].map(parse_gtfs_time)
    base = base[
        base["dep_min"].between(dep_start, dep_end)
        & base["dep_min"].notna()
    ]

    if base.empty:
        return pd.DataFrame()

    trip_ids = base["trip_id"].unique()

    full = trips[
        trips["trip_id"].isin(trip_ids)
    ][
        [
            "trip_id",
            "station_id",
            "station_name",
            "stop_sequence",
            "arrival_time",
            "trip_headsign",
        ]
    ].copy()

    origins = base[
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

    full = full.merge(origins, on="trip_id", how="inner")
    full["arr_min"] = full["arrival_time"].map(parse_gtfs_time)

    full = full[
        (full["stop_sequence"] > full["origin_seq"])
        & full["station_id"].notna()
        & full["arr_min"].notna()
    ]

    if destination_ids is not None:
        full = full[full["station_id"].isin(destination_ids)]

    full["duration"] = full["arr_min"] - full["dep_min"]
    full = full[
        (full["duration"] >= 0)
        & (full["duration"] <= max_duration)
    ]

    full = (
        full.sort_values(
            ["trip_id", "station_id", "arr_min"]
        )
        .drop_duplicates(["trip_id", "station_id"])
    )

    return full.rename(
        columns={"origin_departure_time": "departure_time"}
    )[
        [
            "trip_id",
            "station_id",
            "station_name",
            "departure_time",
            "arrival_time",
            "dep_min",
            "arr_min",
            "origin_station_id",
            "trip_headsign",
            "duration",
        ]
    ]


def one_connection_journeys(
    trips,
    services,
    origin_ids,
    dep_start=300,
    dep_end=1380,
    max_duration=600,
    min_transfer=5,
    max_transfer=90,
    max_results_per_destination=3,
):
    """
    O -> X -> D using two real GTFS trips.

    Used only as a fallback when direct destinations are too few.
    Importantly, V10 never pairs a specific outbound train with a
    specific return train.
    """
    rail = rail_rows(trips, services)
    if rail.empty:
        return pd.DataFrame()

    origin = rail[rail["station_id"].isin(origin_ids)].copy()
    origin["dep_min"] = origin["departure_time"].map(parse_gtfs_time)
    origin = origin[
        origin["dep_min"].between(dep_start, dep_end)
        & origin["dep_min"].notna()
    ]

    if origin.empty:
        return pd.DataFrame()

    first_ids = origin["trip_id"].unique()

    first = trips[
        trips["trip_id"].isin(first_ids)
    ][
        [
            "trip_id",
            "station_id",
            "station_name",
            "stop_sequence",
            "arrival_time",
            "trip_headsign",
        ]
    ].copy()

    first = first.merge(
        origin[
            [
                "trip_id",
                "stop_sequence",
                "dep_min",
                "departure_time",
                "station_id",
            ]
        ].rename(
            columns={
                "stop_sequence": "origin_seq",
                "station_id": "origin_station_id",
                "departure_time": "origin_departure_time",
            }
        ),
        on="trip_id",
        how="inner",
    )

    first["transfer_arr"] = first["arrival_time"].map(parse_gtfs_time)
    first = first[
        (first["stop_sequence"] > first["origin_seq"])
        & first["transfer_arr"].notna()
    ].copy()

    first["first_duration"] = (
        first["transfer_arr"] - first["dep_min"]
    )
    first = first[
        (first["first_duration"] > 0)
        & (first["first_duration"] < max_duration)
    ]

    if first.empty:
        return pd.DataFrame()

    second = rail[
        [
            "trip_id",
            "station_id",
            "station_name",
            "stop_sequence",
            "departure_time",
            "trip_headsign",
        ]
    ].copy()
    second["second_dep"] = second["departure_time"].map(parse_gtfs_time)
    second = second[second["second_dep"].notna()]

    merged = first[
        [
            "trip_id",
            "origin_station_id",
            "dep_min",
            "origin_departure_time",
            "station_id",
            "station_name",
            "stop_sequence",
            "transfer_arr",
            "first_duration",
        ]
    ].rename(
        columns={
            "trip_id": "first_trip_id",
            "station_id": "transfer_station_id",
            "station_name": "transfer_station_name",
            "stop_sequence": "transfer_seq",
        }
    )

    merged = merged.merge(
        second.rename(
            columns={
                "trip_id": "second_trip_id",
                "station_id": "transfer_station_id",
            }
        ),
        on="transfer_station_id",
        how="inner",
        suffixes=("", "_second"),
    )

    merged = merged[
        merged["second_trip_id"] != merged["first_trip_id"]
    ]

    merged["wait"] = (
        merged["second_dep"] - merged["transfer_arr"]
    )
    merged = merged[
        merged["wait"].between(min_transfer, max_transfer)
    ]

    if merged.empty:
        return pd.DataFrame()

    second_ids = merged["second_trip_id"].unique()

    downstream = trips[
        trips["trip_id"].isin(second_ids)
    ][
        [
            "trip_id",
            "station_id",
            "station_name",
            "stop_sequence",
            "arrival_time",
            "trip_headsign",
        ]
    ].copy()

    downstream = downstream.merge(
        merged[
            [
                "second_trip_id",
                "first_trip_id",
                "origin_station_id",
                "dep_min",
                "origin_departure_time",
                "transfer_station_id",
                "transfer_station_name",
                "transfer_seq",
                "wait",
            ]
        ],
        left_on="trip_id",
        right_on="second_trip_id",
        how="inner",
    )

    downstream["arr_min"] = downstream["arrival_time"].map(
        parse_gtfs_time
    )

    downstream = downstream[
        downstream["arr_min"].notna()
        & (downstream["stop_sequence"] > downstream["transfer_seq"])
        & (downstream["station_id"] != downstream["origin_station_id"])
        & (downstream["station_id"] != downstream["transfer_station_id"])
    ].copy()

    downstream["total_duration"] = (
        downstream["arr_min"] - downstream["dep_min"]
    )

    downstream = downstream[
        (downstream["total_duration"] > 0)
        & (downstream["total_duration"] <= max_duration)
    ]

    if downstream.empty:
        return pd.DataFrame()

    downstream["transfer_text"] = (
        downstream["transfer_station_name"].fillna("correspondance")
        + " · "
        + downstream["wait"].round().astype(int).astype(str)
        + " min"
    )

    downstream = (
        downstream.sort_values(
            ["station_id", "total_duration", "dep_min"]
        )
        .drop_duplicates(
            ["station_id", "first_trip_id", "second_trip_id"]
        )
    )

    out = downstream[
        [
            "first_trip_id",
            "second_trip_id",
            "station_id",
            "station_name",
            "origin_departure_time",
            "dep_min",
            "arrival_time",
            "arr_min",
            "total_duration",
            "transfer_station_name",
            "wait",
            "transfer_text",
            "trip_headsign",
        ]
    ].copy()

    return (
        out.sort_values(
            ["station_id", "total_duration", "dep_min"]
        )
        .groupby("station_id", group_keys=False)
        .head(max_results_per_destination)
    )


# -------------------------------------------------------------------
# Reference fares
# -------------------------------------------------------------------

def fare_lookup(fares, origin_name, destination_name):
    if fares.empty:
        return np.nan

    o = norm(origin_name)
    d = norm(destination_name)

    direct = fares[
        (fares["_o"] == o)
        & (fares["_d"] == d)
    ]

    if direct.empty:
        direct = fares[
            (fares["_o"] == d)
            & (fares["_d"] == o)
        ]

    if direct.empty:
        return np.nan

    return pd.to_numeric(
        direct["Prix minimum"], errors="coerce"
    ).min()


# -------------------------------------------------------------------
# App
# -------------------------------------------------------------------

stations, routes, cal, trips = load_data()

fares = load_fares()
if not fares.empty:
    fares["_o"] = fares["Gare origine"].map(norm)
    fares["_d"] = fares["Gare destination"].map(norm)

st.title("🚆 En Train Alain")
st.caption(
    "Tu as un budget, on cherche où partir. — "
    f"{VERSION} : allers et retours disponibles séparément"
)

with st.sidebar:
    st.header("Ton escapade")

    origin = st.selectbox(
        "Départ",
        station_options(stations),
        index=0,
    )

    min_date = (
        pd.to_datetime(cal["date"], format="%Y%m%d")
        .min()
        .date()
    )
    max_date = (
        pd.to_datetime(cal["date"], format="%Y%m%d")
        .max()
        .date()
    )

    outbound = st.date_input(
        "Date aller",
        value=min_date,
        min_value=min_date,
        max_value=max_date,
    )

    return_default = min(
        outbound + timedelta(days=2),
        max_date,
    )

    inbound = st.date_input(
        "Date retour",
        value=return_default,
        min_value=outbound,
        max_value=max_date,
    )

    budget = st.slider(
        "Budget indicatif A/R (€)",
        20,
        300,
        100,
        5,
    )

    max_leg = st.slider(
        "Durée max par trajet",
        1,
        8,
        4,
        1,
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

    search = st.button(
        "🔎 Trouver où partir",
        type="primary",
        use_container_width=True,
    )

st.markdown("### Où peux-tu partir ?")

st.info(
    "Les horaires viennent des données SNCF. "
    "Les prix affichés sont des **tarifs indicatifs de référence** "
    "quand une relation tarifaire est disponible, pas des prix en temps réel."
)

st.caption(
    "💡 Les horaires d'aller et de retour sont volontairement "
    "**présentés séparément**. En Train Alain ne choisit pas à ta place "
    "une combinaison précise de trains."
)

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

    if not out_services:
        st.warning(
            "Aucun service SNCF n'est renseigné pour la date aller."
        )
        st.stop()

    if not in_services:
        st.warning(
            "Aucun service SNCF n'est renseigné pour la date retour."
        )
        st.stop()

    allowed_destination_ids = set(
        stations.loc[
            destination_mask(stations),
            "station_id",
        ].astype(str)
    )

    with st.spinner("Recherche des destinations réelles…"):

        # -----------------------------------------------------------
        # 1. ALLERS
        # -----------------------------------------------------------
        direct_out = direct_journeys(
            trips,
            out_services,
            origin_ids,
            destination_ids=allowed_destination_ids,
            dep_start=dep_start,
            dep_end=dep_end,
            max_duration=max_duration,
        )

        # Only use one-connection journeys as a fallback.
        direct_destinations = (
            direct_out["station_id"].nunique()
            if not direct_out.empty
            else 0
        )

        if direct_destinations < 30:
            one_out = one_connection_journeys(
                trips,
                out_services,
                origin_ids,
                dep_start=dep_start,
                dep_end=dep_end,
                max_duration=max_duration,
            )

            if not one_out.empty:
                one_out = one_out[
                    one_out["station_id"].isin(
                        allowed_destination_ids
                    )
                ]
        else:
            one_out = pd.DataFrame()

        outbound_by_destination = {}

        if not direct_out.empty:
            for station_id, group in direct_out.groupby(
                "station_id"
            ):
                outbound_by_destination[station_id] = {
                    "type": "Direct",
                    "options": group.sort_values(
                        ["dep_min", "duration"]
                    ).head(8),
                    "best_duration": group["duration"].min(),
                    "best_dep": group["dep_min"].min(),
                }

        if not one_out.empty:
            for station_id, group in one_out.groupby(
                "station_id"
            ):
                # Direct remains preferred when available.
                if station_id not in outbound_by_destination:
                    outbound_by_destination[station_id] = {
                        "type": "1 correspondance",
                        "options": group.sort_values(
                            ["dep_min", "total_duration"]
                        ).head(5),
                        "best_duration": group[
                            "total_duration"
                        ].min(),
                        "best_dep": group["dep_min"].min(),
                    }

        if not outbound_by_destination:
            st.warning(
                "Aucune destination hors Île-de-France ne correspond "
                "aux critères de trajet aller."
            )
            st.stop()

        # -----------------------------------------------------------
        # 2. RETOURS — searched independently.
        # -----------------------------------------------------------
        result_rows = []

        for station_id, out_info in outbound_by_destination.items():

            ret = direct_journeys(
                trips,
                in_services,
                {station_id},
                destination_ids=origin_ids,
                dep_start=300,
                dep_end=1380,
                max_duration=max_duration,
            )

            if ret.empty:
                # No direct return: keep the destination only if there
                # is at least a real return by one connection.
                ret_one = one_connection_journeys(
                    trips,
                    in_services,
                    {station_id},
                    dep_start=300,
                    dep_end=1380,
                    max_duration=max_duration,
                )

                if not ret_one.empty:
                    ret_one = ret_one[
                        ret_one["station_id"].isin(origin_ids)
                    ]

                if ret_one.empty:
                    continue

                return_type = "1 correspondance"
                return_options = ret_one.sort_values(
                    ["dep_min", "total_duration"]
                ).head(8)

                best_return_duration = return_options[
                    "total_duration"
                ].min()

            else:
                return_type = "Direct"
                return_options = ret.sort_values(
                    ["dep_min", "duration"]
                ).head(8)

                best_return_duration = return_options[
                    "duration"
                ].min()

            result_rows.append(
                {
                    "station_id": station_id,
                    "station_name": str(
                        out_info["options"].iloc[0]["station_name"]
                    ),
                    "out_type": out_info["type"],
                    "out_options": out_info["options"],
                    "out_duration": out_info["best_duration"],
                    "out_dep": out_info["best_dep"],
                    "return_type": return_type,
                    "return_options": return_options,
                    "return_duration": best_return_duration,
                }
            )

        if not result_rows:
            st.warning(
                "Des destinations sont accessibles à l'aller, "
                "mais aucune ne possède de retour correspondant "
                "à la durée maximale."
            )
            st.stop()

        results = pd.DataFrame(result_rows)

        # -----------------------------------------------------------
        # 3. DEAL SCORE
        # -----------------------------------------------------------
        results["fare_one_way"] = [
            fare_lookup(
                fares,
                "PARIS" if origin == "Paris (toutes les gares)" else origin,
                name,
            )
            for name in results["station_name"]
        ]

        results["fare_ar_reference"] = (
            results["fare_one_way"] * 2
        )

        results["total_best_duration"] = (
            results["out_duration"]
            + results["return_duration"]
        )

        schedule_score = np.clip(
            1
            - np.abs(
                pd.to_numeric(
                    results["out_dep"],
                    errors="coerce",
                )
                - 510
            )
            / 600,
            0,
            1,
        ).fillna(0)

        time_score = np.clip(
            1
            - results["total_best_duration"]
            / (max_duration * 2),
            0,
            1,
        ).fillna(0)

        budget_score = np.where(
            results["fare_ar_reference"].notna(),
            np.clip(
                1
                - results["fare_ar_reference"] / budget,
                0,
                1,
            ),
            0.5,
        )

        results["score"] = (
            0.45 * budget_score
            + 0.35 * time_score
            + 0.20 * schedule_score
        ) * 100

        results = (
            results.replace([np.inf, -np.inf], np.nan)
            .sort_values(
                ["score", "total_best_duration"],
                ascending=[False, True],
            )
            .head(30)
        )

        direct_out_count = int(
            (results["out_type"] == "Direct").sum()
        )
        connection_out_count = int(
            (results["out_type"] == "1 correspondance").sum()
        )

        st.success(
            f"{len(results)} destinations trouvées."
        )

        st.caption(
            f"{direct_out_count} allers directs · "
            f"{connection_out_count} allers avec 1 correspondance · "
            "retours recherchés indépendamment"
        )

        # -----------------------------------------------------------
        # 4. DISPLAY
        # -----------------------------------------------------------
        for _, r in results.iterrows():

            fare_text = (
                f"≈ {r['fare_ar_reference']:.0f} € A/R de référence"
                if pd.notna(r["fare_ar_reference"])
                else "prix à vérifier"
            )

            with st.container(border=True):

                c1, c2 = st.columns([4, 1])

                with c1:
                    st.subheader(
                        str(r["station_name"]).title()
                    )

                    st.caption(
                        f"{fare_text} · "
                        f"Deal Score {r['score']:.0f}/100"
                    )

                    st.markdown(
                        f"**🚆 Allers disponibles** "
                        f"({r['out_type']})"
                    )

                    out_lines = []

                    for _, option in r["out_options"].iterrows():
                        line = (
                            f"{fmt_time(option['dep_min'])} → "
                            f"{fmt_time(option['arr_min'])} · "
                            f"{fmt_duration(option.get('duration', option.get('total_duration')))}"
                        )

                        if r["out_type"] != "Direct":
                            line += (
                                f" · correspondance à "
                                f"{option['transfer_station_name']}"
                            )

                        out_lines.append(
                            f"- {line}"
                        )

                    st.markdown(
                        "\n".join(out_lines)
                    )

                    st.markdown(
                        f"**↩️ Retours disponibles** "
                        f"({r['return_type']})"
                    )

                    return_lines = []

                    for _, option in r["return_options"].iterrows():
                        duration = (
                            option["duration"]
                            if r["return_type"] == "Direct"
                            else option["total_duration"]
                        )

                        departure = (
                            option["dep_min"]
                            if r["return_type"] == "Direct"
                            else option["dep_min"]
                        )

                        arrival = option["arr_min"]

                        line = (
                            f"{fmt_time(departure)} → "
                            f"{fmt_time(arrival)} · "
                            f"{fmt_duration(duration)}"
                        )

                        if r["return_type"] != "Direct":
                            line += (
                                f" · correspondance à "
                                f"{option['transfer_station_name']}"
                            )

                        return_lines.append(
                            f"- {line}"
                        )

                    st.markdown(
                        "\n".join(return_lines)
                    )

                    st.caption(
                        "Les horaires aller et retour sont indépendants : "
                        "à toi de choisir la combinaison qui te convient."
                    )

                with c2:
                    st.metric(
                        "Deal Score",
                        f"{r['score']:.0f}/100",
                    )

else:
    st.markdown(
        """
        **Exemple :** choisis Paris, un week-end et un budget de 100 €.

        En Train Alain cherche des destinations ferroviaires réellement
        accessibles, puis affiche **les allers disponibles et les retours
        disponibles séparément**.

        Il ne choisit pas à ta place une combinaison de trains.
        """
    )

    st.caption(
        f"{VERSION} · données SNCF ouvertes · prototype de découverte"
    )
