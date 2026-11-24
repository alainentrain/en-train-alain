
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

    merged = merged.merge(
        second.rename(columns={
            "trip_id": "second_trip_id",
            "station_id": "transfer_station_id",
            "station_name": "transfer_station_name",
        }),
        on="transfer_station_id",
        how="inner",
    )
    merged = merged[merged["second_trip_id"] != merged["first_trip_id"]]
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
st.caption("Tu as un budget, on cherche où partir. — V8 : plusieurs horaires")

with st.sidebar:
    st.header("Ton escapade")
    origin = st.selectbox("Départ", station_options(stations), index=0)
    min_date = pd.to_datetime(cal["date"], format="%Y%m%d").min().date()
    max_date = pd.to_datetime(cal["date"], format="%Y%m%d").max().date()
    outbound = st.date_input("Date aller", value=min_date, min_value=min_date, max_value=max_date)
    return_default = min(outbound + timedelta(days=2), max_date)
    inbound = st.date_input("Date retour", value=return_default, min_value=outbound, max_value=max_date)
    budget = st.slider("Budget maximum A/R (€)", 20, 300, 100, 5)
    max_leg = st.slider("Durée max par trajet", 1, 8, 4, 1)
    dep_window = st.selectbox(
        "Départ aller",
        ["Toute la journée", "Matin (05h–12h)", "Après-midi (12h–18h)", "Soir (18h–23h)"]
    )
    vibe = st.selectbox(
        "Ambiance", ["Peu importe", "Week-end", "Culture", "Nature", "Soleil", "Gastronomie"]
    )
    search = st.button("🔎 Trouver où partir", type="primary", use_container_width=True)

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
        # On cherche les horaires indépendamment : pas de multiplication artificielle
        # des combinaisons aller x retour. Chaque destination expose ses options.
        direct_out = direct_journeys(
            trips, out_services, origin_ids,
            dep_start=dep_start, dep_end=dep_end, max_duration=max_duration
        )

        if direct_out.empty:
            st.warning("Aucun trajet ferroviaire direct trouvé avec ces critères.")
            st.stop()

        candidates = []
        for station_id, out_group in direct_out.groupby("station_id"):
            out_group = out_group.sort_values(["dep_min", "arr_min"]).copy()
            # Garder plusieurs horaires distincts, pas seulement le premier train.
            out_options = out_group.drop_duplicates(["dep_min", "arr_min"]).head(5)

            ret = return_options_direct(
                trips, in_services, station_id, origin_ids,
                dep_start=600, dep_end=1500, max_duration=max_duration
            )
            if ret.empty:
                continue

            ret = ret.sort_values(["dep_min", "arr_min"]).drop_duplicates(
                ["dep_min", "arr_min"]
            ).head(5)

            # Le score de destination reste indépendant des combinaisons :
            # on utilise les meilleures caractéristiques disponibles côté aller
            # et côté retour, puis on expose les horaires séparément.
            best_out = out_options.sort_values("duration").iloc[0]
            best_ret = ret.sort_values("duration").iloc[0]
            row = best_out.copy()
            row["return_duration"] = best_ret["duration"]
            row["return_departure"] = best_ret["departure_time"]
            row["return_arrival"] = best_ret["arrival_time"]
            row["out_options"] = out_options.to_dict("records")
            row["return_options"] = ret.to_dict("records")
            row["journey_type"] = "Direct"
            candidates.append(row)

        results = pd.DataFrame(candidates)
        if results.empty:
            st.warning("Des allers ont été trouvés, mais aucun retour direct compatible n'a été trouvé.")
            st.stop()

        origin_for_fare = "PARIS" if origin == "Paris (toutes les gares)" else origin
        results["fare_min"] = [
            fare_lookup(fares, origin_for_fare, name)
            for name in results["station_name"]
        ]
        results["fare_ar"] = results["fare_min"] * 2
        results["out_duration"] = pd.to_numeric(results["duration"], errors="coerce")
        results["return_duration"] = pd.to_numeric(results["return_duration"], errors="coerce")
        results["total_duration"] = results["out_duration"] + results["return_duration"]

        schedule_score = np.clip(
            1 - np.abs(pd.to_numeric(results["dep_min"], errors="coerce") - 510) / 600,
            0, 1
        ).fillna(0)
        time_score = np.clip(
            1 - results["total_duration"] / (max_duration * 2), 0, 1
        ).fillna(0)
        if results["fare_ar"].notna().any():
            budget_score = np.where(
                results["fare_ar"].notna(),
                np.clip(1 - results["fare_ar"] / budget, 0, 1), 0.5
            )
        else:
            budget_score = np.full(len(results), 0.5)

        results["score"] = (
            0.45 * budget_score + 0.35 * time_score + 0.20 * schedule_score
        ) * 100
        results = results.replace([np.inf, -np.inf], np.nan)
        results = results.dropna(subset=["out_duration", "return_duration"])
        results = results.sort_values(["score", "total_duration"], ascending=[False, True]).head(30)

        st.success(f"{len(results)} destinations avec plusieurs horaires disponibles.")
        st.caption(
            f"Services actifs : {len(out_services)} à l'aller · {len(in_services)} au retour · V8"
        )

        for _, r in results.iterrows():
            fare_text = f"≈ {r['fare_ar']:.0f} € A/R" if pd.notna(r["fare_ar"]) else "prix à vérifier"
            out_opts = r["out_options"]
            ret_opts = r["return_options"]

            with st.container(border=True):
                c1, c2 = st.columns([4, 1])
                with c1:
                    st.subheader(str(r["station_name"]).title())
                    st.caption(f"{fare_text} · score {r['score']:.0f}/100")

                    st.markdown("**🚆 Allers disponibles**")
                    for o in out_opts:
                        st.write(
                            f"{fmt_time(o['dep_min'])} → {fmt_time(o['arr_min'])} · "
                            f"{fmt_duration(o['duration'])}"
                        )

                    st.markdown("**↩️ Retours disponibles**")
                    for rr in ret_opts:
                        st.write(
                            f"{fmt_time(rr['dep_min'])} → {fmt_time(rr['arr_min'])} · "
                            f"{fmt_duration(rr['duration'])}"
                        )

                    st.caption("Les allers et retours sont présentés séparément : à toi de choisir la combinaison qui te convient.")
                with c2:
                    st.metric("Deal Score", f"{r['score']:.0f}/100")

else:
    st.markdown("""
    **Exemple :** choisis Paris, un week-end et un budget de 100 €.

    En Train Alain cherche des destinations réellement desservies,
    puis affiche plusieurs possibilités d'aller et de retour pour chacune.
    """)
