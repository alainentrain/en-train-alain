
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
        s = str(value).strip()
        return str(int(s)) if s.isdigit() else s

    cal["service_id"] = cal["service_id"].map(canonical_service_id)
    trips["service_id"] = trips["service_id"].map(canonical_service_id)
    trips["trip_id"] = trips["trip_id"].astype(str)
    trips["station_id"] = trips["station_id"].astype(str)
    trips["route_type"] = pd.to_numeric(trips["route_type"], errors="coerce").fillna(0).astype(int)
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
    s = re.sub(r"\bHALL\s+\d+(?:\s*-\s*\d+)?\b", "", s)
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
    minutes = int(round(float(minutes)))
    return f"{minutes // 60} h {minutes % 60:02d}"

def fmt_time(x):
    if pd.isna(x):
        return "—"
    m = int(round(float(x)))
    return f"{(m // 60) % 24:02d}:{m % 60:02d}"

def active_services(cal, d):
    ds = d.strftime("%Y%m%d")
    x = cal[cal["date"] == ds]
    return set(x.loc[x["exception_type"] == 1, "service_id"]) - set(
        x.loc[x["exception_type"] == 2, "service_id"]
    )

def station_options(stations):
    return ["Paris (toutes les gares)"] + sorted(
        stations["station_name"].dropna().unique().tolist()
    )

def station_ids_for_choice(choice, stations):
    if choice == "Paris (toutes les gares)":
        return set(
            stations.loc[
                stations["station_name"].str.contains(r"^Paris\b", case=False, na=False),
                "station_id",
            ]
        )
    return set(stations.loc[stations["station_name"] == choice, "station_id"])

def rail_rows(trips, services):
    return trips[
        trips["service_id"].isin(services) & (trips["route_type"] == 2)
    ].copy()

def direct_journeys(trips, services, origin_ids, destination_ids=None,
                    dep_start=300, dep_end=1380, max_duration=600):
    base = rail_rows(trips, services)
    base = base[base["station_id"].isin(origin_ids)].copy()
    if base.empty:
        return pd.DataFrame()

    base["dep_min"] = base["departure_time"].map(parse_gtfs_time)
    base = base[base["dep_min"].between(dep_start, dep_end)]
    base = base.dropna(subset=["dep_min"])
    if base.empty:
        return pd.DataFrame()

    ids = base["trip_id"].unique()
    full = trips[trips["trip_id"].isin(ids)][
        ["trip_id", "station_id", "station_name", "stop_sequence",
         "arrival_time", "trip_headsign"]
    ].copy()

    origins = base[
        ["trip_id", "stop_sequence", "departure_time", "dep_min", "station_id"]
    ].rename(columns={
        "stop_sequence": "origin_seq",
        "departure_time": "origin_departure_time",
        "station_id": "origin_station_id",
    })

    full = full.merge(
        origins,
        on="trip_id",
        how="inner",
        suffixes=("", "_origin"),
    )
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
        (full["duration"] >= 0) & (full["duration"] <= max_duration)
    ]
    full = (
        full.sort_values(["trip_id", "station_id", "arr_min"])
        .drop_duplicates(["trip_id", "station_id"])
    )
    return full.rename(columns={"origin_departure_time": "departure_time"})[
        ["trip_id", "station_id", "station_name", "departure_time",
         "arrival_time", "dep_min", "arr_min", "origin_station_id",
         "trip_headsign", "duration"]
    ]

def one_connection_journeys(trips, services, origin_ids,
                            dep_start=300, dep_end=1380,
                            max_duration=600, min_transfer=5,
                            max_transfer=90, max_results_per_destination=3):
    """
    Build O -> X -> D journeys from two real GTFS trips.
    The first leg starts at the chosen origin. The second leg starts
    at the first leg's downstream stop. We keep sensible transfer times
    and a total journey duration <= max_duration.
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

    # First-leg candidates: every downstream stop that can serve as a transfer.
    first_ids = origin["trip_id"].unique()
    first = trips[trips["trip_id"].isin(first_ids)][
        ["trip_id", "station_id", "station_name", "stop_sequence",
         "arrival_time", "trip_headsign"]
    ].copy()
    first = first.merge(
        origin[["trip_id", "stop_sequence", "dep_min", "departure_time",
                "station_id"]].rename(columns={
                    "stop_sequence": "origin_seq",
                    "station_id": "origin_station_id",
                    "departure_time": "origin_departure_time",
                }),
        on="trip_id",
        how="inner",
    )
    first["transfer_arr"] = first["arrival_time"].map(parse_gtfs_time)
    first = first[
        (first["stop_sequence"] > first["origin_seq"])
        & first["transfer_arr"].notna()
    ].copy()
    first["first_duration"] = first["transfer_arr"] - first["dep_min"]
    first = first[
        (first["first_duration"] > 0)
        & (first["first_duration"] < max_duration)
    ]

    if first.empty:
        return pd.DataFrame()

    # Second-leg departures from transfer stations. Limit the working set
    # to a reasonable time window after each transfer to avoid a huge join.
    second = rail[
        ["trip_id", "station_id", "station_name", "stop_sequence",
         "departure_time", "trip_headsign"]
    ].copy()
    second["second_dep"] = second["departure_time"].map(parse_gtfs_time)
    second = second[second["second_dep"].notna()].copy()

    # Only use second trips that are not the same physical trip.
    # Merge on transfer station; this is the key connection.
    merged = first[
        ["trip_id", "origin_station_id", "dep_min", "origin_departure_time",
         "station_id", "station_name", "transfer_arr", "first_duration"]
    ].rename(columns={
        "trip_id": "first_trip_id",
        "station_id": "transfer_station_id",
        "station_name": "transfer_station_name",
    })

    # Important: transfer_station_name already exists on the left side
    # (the first leg). Do not rename the second leg's station_name to the
    # same column name, otherwise pandas creates transfer_station_name_x/y
    # and the later code cannot find transfer_station_name.
    merged = merged.merge(
        second.rename(columns={
            "trip_id": "second_trip_id",
            "station_id": "transfer_station_id",
        }),
        on="transfer_station_id",
        how="inner",
    )
    merged = merged[merged["second_trip_id"] != merged["first_trip_id"]]

    if "transfer_station_name" not in merged.columns:
        st.error("Erreur interne : la gare de correspondance n'a pas pu être identifiée.")
        return pd.DataFrame()

    merged["wait"] = merged["second_dep"] - merged["transfer_arr"]
    merged = merged[
        merged["wait"].between(min_transfer, max_transfer)
    ]
    merged["remaining"] = max_duration - (
        merged["first_duration"] + merged["wait"]
    )
    merged = merged[merged["remaining"] > 0]

    if merged.empty:
        return pd.DataFrame()

    # Find destinations downstream of each selected second trip.
    second_ids = merged["second_trip_id"].unique()
    downstream = trips[trips["trip_id"].isin(second_ids)][
        ["trip_id", "station_id", "station_name", "stop_sequence",
         "arrival_time", "trip_headsign"]
    ].copy()

    downstream = downstream.merge(
        merged[[
            "second_trip_id", "first_trip_id", "origin_station_id",
            "dep_min", "origin_departure_time", "transfer_station_id",
            "transfer_station_name", "transfer_arr", "second_dep",
            "wait", "first_duration"
        ]],
        left_on="trip_id",
        right_on="second_trip_id",
        how="inner",
    )
    downstream["arr_min"] = downstream["arrival_time"].map(parse_gtfs_time)
    downstream = downstream[
        downstream["arr_min"].notna()
        & (downstream["station_id"] != downstream["origin_station_id"])
        & (downstream["station_id"] != downstream["transfer_station_id"])
    ].copy()
    downstream["total_duration"] = downstream["arr_min"] - downstream["dep_min"]
    downstream = downstream[
        (downstream["total_duration"] > 0)
        & (downstream["total_duration"] <= max_duration)
    ]

    if downstream.empty:
        return pd.DataFrame()

    downstream["transfer_text"] = (
        downstream["transfer_station_name"].fillna("correspondance")
        + " · " + downstream["wait"].round().astype(int).astype(str) + " min"
    )

    # Keep the quickest connection(s) for each destination.
    downstream = downstream.sort_values(
        ["station_id", "total_duration", "dep_min"]
    ).drop_duplicates(
        ["station_id", "first_trip_id", "second_trip_id"]
    )

    out = downstream[
        ["first_trip_id", "second_trip_id", "station_id", "station_name",
         "origin_departure_time", "dep_min", "arrival_time", "arr_min",
         "total_duration", "transfer_station_name", "wait", "transfer_text",
         "trip_headsign"]
    ].copy()

    out = (
        out.sort_values(["station_id", "total_duration", "dep_min"])
        .groupby("station_id", group_keys=False)
        .head(max_results_per_destination)
    )

    return out

def return_options_direct(trips, services, destination_id, origin_ids,
                          dep_start=600, dep_end=1500, max_duration=600):
    return direct_journeys(
        trips, services, {destination_id}, origin_ids,
        dep_start=dep_start, dep_end=dep_end, max_duration=max_duration
    )

def fare_lookup(fares, origin_name, dest_name):
    if fares.empty:
        return np.nan
    o, d = norm(origin_name), norm(dest_name)
    f = fares[(fares["_o"] == o) & (fares["_d"] == d)]
    if f.empty:
        f = fares[(fares["_o"] == d) & (fares["_d"] == o)]
    if f.empty:
        return np.nan
    return pd.to_numeric(f["Prix minimum"], errors="coerce").min()

stations, routes, cal, trips = load_data()
fares = load_fares()
if not fares.empty:
    fares["_o"] = fares["Gare origine"].map(norm)
    fares["_d"] = fares["Gare destination"].map(norm)

st.title("🚆 En Train Alain")
st.caption("Tu as un budget, on cherche où partir. — V7 : directs + 1 correspondance")

with st.sidebar:
    st.header("Ton escapade")
    origin = st.selectbox("Départ", station_options(stations), index=0)

    min_date = pd.to_datetime(cal["date"], format="%Y%m%d").min().date()
    max_date = pd.to_datetime(cal["date"], format="%Y%m%d").max().date()
    outbound = st.date_input(
        "Date aller", value=min_date, min_value=min_date, max_value=max_date
    )
    return_default = min(outbound + timedelta(days=2), max_date)
    inbound = st.date_input(
        "Date retour", value=return_default,
        min_value=outbound, max_value=max_date
    )

    budget = st.slider("Budget maximum A/R (€)", 20, 300, 100, 5)
    max_leg = st.slider("Durée max par trajet", 1, 8, 4, 1)
    dep_window = st.selectbox(
        "Départ aller",
        ["Toute la journée", "Matin (05h–12h)",
         "Après-midi (12h–18h)", "Soir (18h–23h)"]
    )
    vibe = st.selectbox(
        "Ambiance",
        ["Peu importe", "Week-end", "Culture",
         "Nature", "Soleil", "Gastronomie"]
    )
    search = st.button(
        "🔎 Trouver où partir", type="primary", use_container_width=True
    )

st.markdown("### Où peux-tu partir ?")
st.info(
    "Cette version utilise les horaires SNCF réels. Les prix affichés quand disponibles "
    "sont des **tarifs indicatifs de référence**, pas le prix en temps réel."
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
        st.warning("Aucun service SNCF n'est renseigné pour cette date dans le fichier GTFS.")
        st.stop()
    if not in_services:
        st.warning("Aucun service SNCF n'est renseigné pour la date retour dans le fichier GTFS.")
        st.stop()

    with st.spinner("Recherche des escapades réelles…"):
        # 1) Direct outbound.
        direct_out = direct_journeys(
            trips, out_services, origin_ids,
            dep_start=dep_start, dep_end=dep_end,
            max_duration=max_duration
        )

        # 2) One-connection outbound.
        one_out = one_connection_journeys(
            trips, out_services, origin_ids,
            dep_start=dep_start, dep_end=dep_end,
            max_duration=max_duration
        )

        candidates = []

        if not direct_out.empty:
            for station_id, g in direct_out.groupby("station_id"):
                row = g.sort_values(["duration", "dep_min"]).iloc[0].copy()
                row["journey_type"] = "Direct"
                row["transfer_station_name"] = np.nan
                row["wait"] = np.nan
                row["transfer_text"] = ""
                candidates.append(row)

        if not one_out.empty:
            # Add connection candidates only when they are faster/better than
            # the direct candidate, or when no direct exists.
            for station_id, g in one_out.groupby("station_id"):
                row = g.sort_values(["total_duration", "dep_min"]).iloc[0].copy()
                row["journey_type"] = "1 correspondance"
                row["duration"] = row["total_duration"]
                candidates.append(row)

        if not candidates:
            st.warning(
                "Aucun trajet aller direct ou avec 1 correspondance ne correspond "
                "à ces critères."
            )
            st.stop()

        out_df = pd.DataFrame(candidates)

        # Prefer direct, but keep a connection when it is the only viable option.
        out_df = (
            out_df.sort_values(
                ["station_id", "journey_type", "duration", "dep_min"],
                key=lambda s: s.map({"Direct": 0, "1 correspondance": 1})
                if s.name == "journey_type" else s
            )
            .drop_duplicates("station_id", keep="first")
        )

        # Return: direct OR one connection.
        result_rows = []
        for _, row in out_df.iterrows():
            station_id = row["station_id"]

            ret_direct = return_options_direct(
                trips, in_services, station_id, origin_ids,
                dep_start=600, dep_end=1500, max_duration=max_duration
            )

            ret_choice = None
            ret_type = None
            if not ret_direct.empty:
                ret_choice = ret_direct.sort_values(
                    ["duration", "dep_min"]
                ).iloc[0]
                ret_type = "Direct"

            # If no direct return exists, try one connection.
            if ret_choice is None:
                # Search from the destination station. The return journey's
                # "origin" is this destination, while Paris is the target.
                ret_one = one_connection_journeys(
                    trips, in_services, {station_id},
                    dep_start=600, dep_end=1500,
                    max_duration=max_duration
                )
                if not ret_one.empty:
                    ret_one = ret_one[
                        ret_one["station_id"].isin(origin_ids)
                    ]
                    if not ret_one.empty:
                        ret_choice = ret_one.sort_values(
                            ["total_duration", "dep_min"]
                        ).iloc[0]
                        ret_type = "1 correspondance"

            if ret_choice is None:
                continue

            r = row.copy()
            r["return_type"] = ret_type
            r["return_departure"] = ret_choice["departure_time"] if ret_type == "Direct" else ret_choice["origin_departure_time"]
            r["return_arrival"] = ret_choice["arrival_time"] if ret_type == "Direct" else ret_choice["arrival_time"]
            r["return_duration"] = ret_choice["duration"] if ret_type == "Direct" else ret_choice["total_duration"]
            r["return_transfer"] = (
                "" if ret_type == "Direct"
                else str(ret_choice["transfer_text"])
            )
            result_rows.append(r)

        results = pd.DataFrame(result_rows)

        if results.empty:
            st.warning(
                "Des trajets aller ont été trouvés, mais aucun retour direct ou "
                "avec 1 correspondance ne correspond à la durée maximale."
            )
            st.stop()

        # Reference fare estimate.
        origin_for_fare = "PARIS" if origin == "Paris (toutes les gares)" else origin
        results["fare_min"] = [
            fare_lookup(fares, origin_for_fare, name)
            for name in results["station_name"]
        ]
        results["fare_ar"] = results["fare_min"] * 2

        results["out_duration"] = pd.to_numeric(
            results["duration"], errors="coerce"
        )
        results["return_duration"] = pd.to_numeric(
            results["return_duration"], errors="coerce"
        )
        results["total_duration"] = (
            results["out_duration"] + results["return_duration"]
        )

        # Safe scoring: NaN never reaches int()/formatting.
        schedule_score = np.clip(
            1 - np.abs(pd.to_numeric(results["dep_min"], errors="coerce") - 510) / 600,
            0, 1
        ).fillna(0)

        time_score = np.clip(
            1 - results["total_duration"] / (max_duration * 2),
            0, 1
        ).fillna(0)

        if results["fare_ar"].notna().any():
            budget_score = np.where(
                results["fare_ar"].notna(),
                np.clip(1 - results["fare_ar"] / budget, 0, 1),
                0.5
            )
        else:
            budget_score = np.full(len(results), 0.5)

        results["score"] = (
            0.45 * budget_score
            + 0.35 * time_score
            + 0.20 * schedule_score
        ) * 100

        results = results.replace([np.inf, -np.inf], np.nan)
        results = results.dropna(subset=["out_duration", "return_duration"])
        results = results.sort_values(
            ["score", "total_duration"], ascending=[False, True]
        ).head(30)

        direct_count = int((results["journey_type"] == "Direct").sum())
        connection_count = int(
            (results["journey_type"] == "1 correspondance").sum()
        )

        st.success(
            f"{len(results)} escapades trouvées · "
            f"{direct_count} départs directs · {connection_count} départs avec 1 correspondance."
        )
        st.caption(
            f"Services actifs : {len(out_services)} à l'aller · "
            f"{len(in_services)} au retour · V7"
        )

        for _, r in results.iterrows():
            fare_text = (
                f"≈ {r['fare_ar']:.0f} € A/R"
                if pd.notna(r["fare_ar"])
                else "prix à vérifier"
            )
            out_transfer = (
                ""
                if r["journey_type"] == "Direct"
                else f" · correspondance à {r['transfer_station_name']} ({r['wait']:.0f} min)"
            )
            ret_transfer = (
                ""
                if not r["return_transfer"]
                else f" · correspondance à {r['return_transfer']}"
            )

            with st.container(border=True):
                c1, c2 = st.columns([3, 1])
                with c1:
                    st.subheader(str(r["station_name"]).title())
                    st.write(
                        f"**Aller :** {fmt_time(r['dep_min'])} → "
                        f"{fmt_time(r['arr_min'])} · {fmt_duration(r['out_duration'])}"
                        f"{out_transfer}  \n"
                        f"**Retour :** {fmt_time(r['return_departure'])} → "
                        f"{fmt_time(r['return_arrival'])} · "
                        f"{fmt_duration(r['return_duration'])}"
                        f"{ret_transfer}"
                    )
                    st.caption(
                        f"{fare_text} · score {r['score']:.0f}/100 · "
                        f"{r['journey_type']} aller"
                    )
                with c2:
                    st.metric("Deal Score", f"{r['score']:.0f}/100")

else:
    st.markdown("""
    **Exemple :** choisis Paris, un week-end et un budget de 100 €.

    En Train Alain cherche des destinations réellement desservies,
    puis vérifie qu'un trajet retour existe aussi — en direct ou avec
    une correspondance.
    """)
