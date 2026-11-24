import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import timedelta
import re
import unicodedata

st.set_page_config(page_title="En Train Alain", page_icon="🚆", layout="wide")

DATA = Path(__file__).parent / "data"


@st.cache_data(show_spinner="Chargement des données SNCF…")
def load_data():
    stations = pd.read_csv(DATA / "stations.csv")
    routes = pd.read_csv(DATA / "routes.csv")
    cal = pd.read_csv(DATA / "calendar_dates.csv", dtype={"service_id": str, "date": str})
    trips = pd.read_csv(DATA / "trip_stops.csv.gz", compression="gzip")

    def canonical_service_id(value):
        if pd.isna(value):
            return ""
        text = str(value).strip()
        return str(int(text)) if text.isdigit() else text

    cal["service_id"] = cal["service_id"].map(canonical_service_id)
    trips["service_id"] = trips["service_id"].map(canonical_service_id)
    trips["trip_id"] = trips["trip_id"].astype(str)
    trips["station_id"] = trips["station_id"].astype(str)
    trips["route_type"] = trips["route_type"].fillna(0).astype(int)
    return stations, routes, cal, trips


@st.cache_data
def load_fares():
    p = DATA / "tarifs-tgv-inoui-ouigo.csv"
    if not p.exists():
        return pd.DataFrame()
    return pd.read_csv(p, sep=";", dtype=str)


def norm(s):
    if pd.isna(s):
        return ""
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    s = s.upper().replace("'", " ").replace("-", " ")
    s = re.sub(r"[^A-Z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def parse_gtfs_time(x):
    try:
        h, m, s = str(x).split(":")
        return int(h) * 60 + int(m)
    except Exception:
        return np.nan


def fmt_duration(minutes):
    if pd.isna(minutes):
        return "durée inconnue"
    try:
        minutes = int(round(float(minutes)))
    except (TypeError, ValueError):
        return "durée inconnue"
    return f"{minutes // 60} h {minutes % 60:02d}"


def fmt_time(x):
    """Format a GTFS time safely, including values above 24:00."""
    if pd.isna(x):
        return ""
    try:
        m = int(float(x))
    except (TypeError, ValueError):
        # Defensive fallback if a raw HH:MM:SS value reaches the formatter.
        parsed = parse_gtfs_time(x)
        if pd.isna(parsed):
            return str(x)
        m = int(parsed)
    return f"{(m // 60) % 24:02d}:{m % 60:02d}"


def active_services(cal, d):
    ds = d.strftime("%Y%m%d")
    x = cal[cal["date"] == ds]
    return (
        set(x.loc[x["exception_type"] == 1, "service_id"])
        - set(x.loc[x["exception_type"] == 2, "service_id"])
    )


def station_options(stations):
    names = sorted(stations["station_name"].dropna().unique().tolist())
    return ["Paris (toutes les gares)"] + names


def station_ids_for_choice(choice, stations):
    if choice == "Paris (toutes les gares)":
        return set(
            stations.loc[
                stations["station_name"].str.contains(
                    r"^Paris\b", case=False, na=False
                ),
                "station_id",
            ]
        )
    return set(stations.loc[stations["station_name"] == choice, "station_id"])


def prepare_trips(trips):
    """Add numeric times once. GTFS permits >24h times, so do not modulo here."""
    t = trips.copy()
    t["dep_min"] = t["departure_time"].map(parse_gtfs_time)
    t["arr_min"] = t["arrival_time"].map(parse_gtfs_time)
    t = t[t["route_type"] == 2].copy()  # rail: TER, TGV, Intercités, etc.
    return t


def direct_journeys(trips, services, origin_ids, destination_ids=None,
                    dep_start=300, dep_end=1380, max_duration=600):
    """Find direct journeys on one train from origin to downstream stations."""
    base = trips[
        trips["service_id"].isin(services)
        & trips["station_id"].isin(origin_ids)
    ].copy()

    base = base[
        base["dep_min"].between(dep_start, dep_end)
        & base["dep_min"].notna()
    ]
    if base.empty:
        return pd.DataFrame()

    ids = base["trip_id"].unique()
    full = trips[
        trips["trip_id"].isin(ids)
        & trips["station_id"].notna()
    ][
        ["trip_id", "station_id", "station_name", "stop_sequence",
         "arrival_time", "arr_min", "trip_headsign"]
    ].copy()

    origins = base[
        ["trip_id", "stop_sequence", "departure_time", "dep_min", "station_id"]
    ].rename(
        columns={
            "stop_sequence": "origin_seq",
            "departure_time": "origin_departure_time",
            "station_id": "origin_station_id",
        }
    )

    full = full.merge(
        origins,
        on="trip_id",
        how="inner",
    )
    full = full[full["stop_sequence"] > full["origin_seq"]]

    if destination_ids is not None:
        full = full[full["station_id"].isin(destination_ids)]

    full = full[
        full["arr_min"].notna()
        & (full["arr_min"] >= full["dep_min"])
        & ((full["arr_min"] - full["dep_min"]) <= max_duration)
    ]

    return (
        full.sort_values(["trip_id", "station_id", "arr_min"])
        .drop_duplicates(["trip_id", "station_id"])
        .rename(columns={"origin_departure_time": "departure_time"})
        [[
            "trip_id", "station_id", "station_name",
            "departure_time", "arrival_time",
            "dep_min", "arr_min", "origin_station_id",
            "trip_headsign",
        ]]
    )


def one_connection_journeys(trips, services, origin_ids,
                             dep_start=300, dep_end=1380,
                             max_duration=600, min_transfer=10,
                             max_connections=3):
    """
    Build a small one-connection network:
    origin -> transfer -> destination.

    We keep only a few fastest candidate first legs per transfer station,
    then search the next train from that transfer point.
    """
    base = trips[
        trips["service_id"].isin(services)
        & trips["station_id"].isin(origin_ids)
        & trips["dep_min"].notna()
    ].copy()
    base = base[base["dep_min"].between(dep_start, dep_end)]
    if base.empty:
        return pd.DataFrame()

    # First leg: origin -> every downstream stop.
    ids = base["trip_id"].unique()
    first = trips[
        trips["trip_id"].isin(ids)
        & trips["station_id"].notna()
    ][
        ["trip_id", "station_id", "station_name", "stop_sequence",
         "arr_min", "arrival_time", "trip_headsign"]
    ].copy()

    origins = base[
        ["trip_id", "stop_sequence", "departure_time", "dep_min", "station_id"]
    ].rename(
        columns={
            "stop_sequence": "origin_seq",
            "station_id": "origin_station_id",
        }
    )
    first = first.merge(origins, on="trip_id", how="inner")
    first = first[first["stop_sequence"] > first["origin_seq"]]
    first = first[first["arr_min"].notna()]
    first["first_duration"] = first["arr_min"] - first["dep_min"]
    first = first[
        (first["first_duration"] > 0)
        & (first["first_duration"] <= max_duration)
    ]

    if first.empty:
        return pd.DataFrame()

    # Avoid thousands of tiny transfer candidates.
    first = (
        first.sort_values(["station_id", "arr_min"])
        .drop_duplicates(["station_id", "trip_id"])
    )
    first = first.groupby("station_id", group_keys=False).head(max_connections)

    transfer_ids = first["station_id"].unique()

    # Second leg candidates from transfer stations.
    second_base = trips[
        trips["service_id"].isin(services)
        & trips["station_id"].isin(transfer_ids)
        & trips["dep_min"].notna()
    ][
        ["trip_id", "station_id", "stop_sequence", "departure_time",
         "dep_min", "trip_headsign"]
    ].copy()

    if second_base.empty:
        return pd.DataFrame()

    second_ids = second_base["trip_id"].unique()
    second = trips[
        trips["trip_id"].isin(second_ids)
        & trips["station_id"].notna()
        & trips["arr_min"].notna()
    ][
        ["trip_id", "station_id", "station_name", "stop_sequence",
         "arrival_time", "arr_min", "trip_headsign"]
    ].copy()

    second = second.merge(
        second_base.rename(columns={"station_id": "transfer_id",
                                    "stop_sequence": "transfer_seq"}),
        on="trip_id",
        how="inner",
    )
    second = second[second["station_id"] != second["transfer_id"]]
    second = second[second["stop_sequence"] > second["transfer_seq"]]

    # Join first-leg arrivals to second-leg departures at the same transfer.
    # Keep the two departure timestamps explicitly named to avoid pandas
    # suffixes and NaN values when calculating the total journey duration.
    first_small = first[
        ["station_id", "trip_id", "departure_time", "dep_min",
         "arr_min", "arrival_time", "origin_station_id"]
    ].rename(columns={
        "station_id": "transfer_id",
        "trip_id": "first_trip_id",
        "dep_min": "first_dep_min",
        "arr_min": "transfer_arr_min",
        "arrival_time": "transfer_arrival_time",
    })

    second = second.merge(first_small, on="transfer_id", how="inner")
    second["wait"] = second["dep_min"] - second["transfer_arr_min"]
    second["total_elapsed"] = second["arr_min"] - second["first_dep_min"]

    second = second[
        second["wait"].between(min_transfer, 120)
        & second["total_elapsed"].between(1, max_duration)
        & second["first_dep_min"].notna()
        & second["arr_min"].notna()
    ]

    if second.empty:
        return pd.DataFrame()

    out = second[
        ["station_id", "station_name", "departure_time",
         "first_dep_min", "arr_min", "arrival_time",
         "origin_station_id", "first_trip_id", "trip_id",
         "transfer_id", "transfer_arr_min", "trip_headsign",
         "total_elapsed"]
    ].copy()
    out = out.rename(columns={
        "trip_id": "second_trip_id",
        "total_elapsed": "journey_duration",
    })
    return out


def return_options(trips, services, destination_id, origin_ids,
                   dep_start=600, dep_end=1500, max_duration=600):
    return direct_journeys(
        trips, services, {destination_id}, origin_ids,
        dep_start=dep_start, dep_end=dep_end, max_duration=max_duration
    )


def fare_lookup(fares, origin_name, dest_name):
    if fares.empty:
        return np.nan, np.nan

    o, d = norm(origin_name), norm(dest_name)
    f = fares[(fares["_o"] == o) & (fares["_d"] == d)]
    if f.empty:
        f = fares[(fares["_o"] == d) & (fares["_d"] == o)]
    if f.empty:
        return np.nan, np.nan

    lo = pd.to_numeric(f["Prix minimum"], errors="coerce").min()
    hi = pd.to_numeric(f["Prix maximum"], errors="coerce").max()
    return lo, hi


stations, routes, cal, trips = load_data()
trips = prepare_trips(trips)

fares = load_fares()
if not fares.empty:
    fares["_o"] = fares["Gare origine"].map(norm)
    fares["_d"] = fares["Gare destination"].map(norm)

st.title("🚆 En Train Alain")
st.caption("Tu as un budget, on cherche où partir. — V6 : directs d'abord, correspondances ensuite")

with st.sidebar:
    st.header("Ton escapade")

    origin = st.selectbox(
        "Départ",
        station_options(stations),
        index=0,
    )

    min_date = pd.to_datetime(cal["date"], format="%Y%m%d").min().date()
    max_date = pd.to_datetime(cal["date"], format="%Y%m%d").max().date()

    outbound = st.date_input(
        "Date aller",
        value=min_date,
        min_value=min_date,
        max_value=max_date,
    )

    return_default = min(outbound + timedelta(days=2), max_date)
    inbound = st.date_input(
        "Date retour",
        value=return_default,
        min_value=outbound,
        max_value=max_date,
    )

    budget = st.slider("Budget maximum A/R (€)", 20, 300, 100, 5)
    max_leg = st.slider("Durée max par trajet", 1, 8, 4, 1)

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
        ["Peu importe", "Week-end", "Culture", "Nature", "Soleil", "Gastronomie"],
    )

    search = st.button(
        "🔎 Trouver où partir",
        type="primary",
        use_container_width=True,
    )

st.markdown("### Où peux-tu partir ?")
st.info(
    "Horaires issus des données SNCF chargées dans l'application. "
    "Les prix affichés sont des **tarifs indicatifs de référence** quand une "
    "correspondance tarifaire existe ; ils ne sont pas les prix en temps réel."
)

if search:
    if inbound < outbound:
        st.error("La date retour doit être après la date aller.")
        st.stop()

    if dep_window == "Matin (05h–12h)":
        dep_start, dep_end = 300, 720
    elif dep_window == "Après-midi (12h–18h)":
        dep_start, dep_end = 720, 1080
    elif dep_window == "Soir (18h–23h)":
        dep_start, dep_end = 1080, 1380
    else:
        dep_start, dep_end = 300, 1380

    max_duration = max_leg * 60
    out_services = active_services(cal, outbound)
    in_services = active_services(cal, inbound)
    origin_ids = station_ids_for_choice(origin, stations)

    if not out_services or not in_services:
        st.warning("Aucun service SNCF n'est renseigné pour l'une des deux dates.")
        st.stop()

    with st.spinner("Recherche des escapades…"):
        # 1) Direct first — this remains the cleanest product result.
        direct_out = direct_journeys(
            trips, out_services, origin_ids,
            dep_start=dep_start, dep_end=dep_end,
            max_duration=max_duration,
        )

        direct_candidates = []
        if not direct_out.empty:
            for station_id, g in direct_out.groupby("station_id"):
                g = g.sort_values(["arr_min", "dep_min"])
                row = g.iloc[0].copy()
                ret = return_options(
                    trips, in_services, station_id, origin_ids,
                    dep_start=600, dep_end=1500,
                    max_duration=max_duration,
                )
                if not ret.empty:
                    rr = ret.sort_values(["dep_min", "arr_min"]).iloc[0]
                    row["return_departure"] = rr["departure_time"]
                    row["return_arrival"] = rr["arrival_time"]
                    row["return_dep_min"] = rr["dep_min"]
                    row["return_arr_min"] = rr["arr_min"]
                    row["return_duration"] = rr["arr_min"] - rr["dep_min"]
                    row["journey_type"] = "Direct"
                    row["transfer"] = ""
                    direct_candidates.append(row)

        results = pd.DataFrame(direct_candidates)

        # 2) If the direct pool is too small, add one-connection outbound trips.
        if len(results) < 30:
            conn_out = one_connection_journeys(
                trips, out_services, origin_ids,
                dep_start=dep_start, dep_end=dep_end,
                max_duration=max_duration,
            )

            conn_candidates = []
            if not conn_out.empty:
                # Keep one best outbound per destination.
                for station_id, g in conn_out.groupby("station_id"):
                    g = g.sort_values(["journey_duration", "dep_min"])
                    row = g.iloc[0].copy()

                    ret = return_options(
                        trips, in_services, station_id, origin_ids,
                        dep_start=600, dep_end=1500,
                        max_duration=max_duration,
                    )
                    if not ret.empty:
                        rr = ret.sort_values(["dep_min", "arr_min"]).iloc[0]
                        row["return_departure"] = rr["departure_time"]
                        row["return_arrival"] = rr["arrival_time"]
                        row["return_dep_min"] = rr["dep_min"]
                        row["return_arr_min"] = rr["arr_min"]
                        row["return_duration"] = rr["arr_min"] - rr["dep_min"]
                        row["out_duration"] = row["journey_duration"]
                        row["journey_type"] = "1 correspondance"
                        row["transfer"] = str(row["transfer_id"])
                        conn_candidates.append(row)

            if conn_candidates:
                conn_df = pd.DataFrame(conn_candidates)
                results = pd.concat([results, conn_df], ignore_index=True, sort=False)

        if results.empty:
            st.warning(
                "Aucune escapade avec aller + retour compatible n'a été trouvée "
                "avec ces critères."
            )
            st.stop()

        # Direct results already have out_duration; connected ones use journey_duration.
        if "out_duration" not in results.columns:
            results["out_duration"] = np.nan
        results["out_duration"] = results["out_duration"].fillna(
            results.get("journey_duration", np.nan)
        )

        results["return_duration"] = pd.to_numeric(
            results["return_duration"], errors="coerce"
        )

        # Never let incomplete journey rows crash the UI or contaminate the score.
        results["out_duration"] = pd.to_numeric(results["out_duration"], errors="coerce")
        results = results[
            results["out_duration"].notna()
            & results["return_duration"].notna()
        ].copy()

        if results.empty:
            st.warning("Aucune escapade complète avec des durées valides n'a été trouvée.")
            st.stop()

        results["fare_min"] = np.nan
        results["fare_max"] = np.nan

        for idx, r in results.iterrows():
            lo, hi = fare_lookup(
                fares,
                origin,
                str(r["station_name"]),
            )
            results.loc[idx, "fare_min"] = lo
            results.loc[idx, "fare_max"] = hi

        # The fare dataset is one-way/reference data. Use the minimum reference
        # fare x 2 as a rough A/R estimate, and keep the label explicit.
        results["fare_ar"] = results["fare_min"] * 2

        results["budget_score"] = np.where(
            results["fare_ar"].notna(),
            np.clip(1 - results["fare_ar"] / budget, 0, 1),
            0.45,
        )
        results["time_score"] = np.clip(
            1 - (
                results["out_duration"] + results["return_duration"]
            ) / (max_duration * 2),
            0,
            1,
        )
        results["schedule_score"] = np.clip(
            1 - np.abs(
                pd.to_numeric(results["dep_min"], errors="coerce") - 510
            ) / 600,
            0,
            1,
        )

        # Until a real destination taxonomy exists, vibe is deliberately neutral
        # in V6 rather than pretending that a station name proves a vibe.
        results["score"] = (
            0.50 * results["budget_score"]
            + 0.35 * results["time_score"]
            + 0.15 * results["schedule_score"]
        ) * 100

        results = (
            results.sort_values(
                ["score", "journey_type", "out_duration"],
                ascending=[False, True, True],
            )
            .drop_duplicates("station_id")
            .head(30)
        )

        direct_count = int((results["journey_type"] == "Direct").sum())
        conn_count = int((results["journey_type"] != "Direct").sum())

        st.success(
            f"{len(results)} destinations trouvées · "
            f"{direct_count} directes · {conn_count} avec 1 correspondance"
        )

        st.caption(
            f"Services actifs : {len(out_services)} à l'aller · "
            f"{len(in_services)} au retour · "
            "TER/TGV/Intercités inclus lorsqu'ils sont présents dans le GTFS ferroviaire."
        )

        if vibe != "Peu importe":
            st.caption(
                f"Ambiance « {vibe} » : le classement thématique sera branché "
                "sur une vraie base destination dans l'étape suivante."
            )

        for _, r in results.iterrows():
            fare_text = (
                f"≈ {r['fare_ar']:.0f} € A/R (référence)"
                if pd.notna(r["fare_ar"])
                else "prix à vérifier"
            )

            with st.container(border=True):
                c1, c2 = st.columns([3, 1])

                with c1:
                    st.subheader(str(r["station_name"]).title())

                    journey_label = r["journey_type"]
                    transfer_text = ""
                    if journey_label != "Direct":
                        transfer_text = " · 1 correspondance"

                    st.write(
                        f"**Aller :** {fmt_time(r['dep_min'])} → "
                        f"{fmt_time(r['arr_min'])} · "
                        f"{fmt_duration(r['out_duration'])}{transfer_text}  \n"
                        f"**Retour :** {fmt_time(r['return_dep_min'])} → "
                        f"{fmt_time(r['return_arr_min'])} · "
                        f"{fmt_duration(r['return_duration'])}"
                    )

                    st.caption(
                        f"{fare_text} · score {r['score']:.0f}/100 · "
                        f"{journey_label}"
                    )

                with c2:
                    st.metric("Deal Score", f"{r['score']:.0f}/100")

else:
    st.markdown(
        """
        **Exemple :** Paris → week-end → 100 € A/R.

        En Train Alain cherche d'abord les destinations accessibles **sans
        correspondance**, puis élargit la recherche à **1 correspondance**
        lorsque cela permet de trouver davantage d'escapades.
        """
    )
