import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import date, timedelta
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

    # The SNCF GTFS export uses zero-padded service_id values in
    # calendar_dates.csv (e.g. "000013") but the trip table stores the
    # same service as "13". Canonicalise both sides before matching.
    def canonical_service_id(value):
        if pd.isna(value):
            return ""
        text = str(value).strip()
        if text.isdigit():
            return str(int(text))
        return text

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
    s = re.sub(r"\bHALL\s+\d+(?:\s*-\s*\d+)?\b", "", s)
    s = re.sub(r"[^A-Z0-9 ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def parse_gtfs_time(x):
    try:
        h, m, s = str(x).split(":")
        return int(h)*60 + int(m)
    except Exception:
        return np.nan

def fmt_duration(minutes):
    minutes = int(round(minutes))
    return f"{minutes//60} h {minutes%60:02d}"

def fmt_time(x):
    if pd.isna(x):
        return ""
    m = int(x)
    return f"{(m//60)%24:02d}:{m%60:02d}"

def active_services(cal, d):
    ds = d.strftime("%Y%m%d")
    x = cal[cal["date"] == ds]
    return set(x.loc[x["exception_type"] == 1, "service_id"]) - set(x.loc[x["exception_type"] == 2, "service_id"])

def station_options(stations):
    paris = ["Paris (toutes les gares)"] + sorted(stations["station_name"].dropna().unique().tolist())
    return paris

def station_ids_for_choice(choice, stations):
    if choice == "Paris (toutes les gares)":
        return set(stations.loc[stations["station_name"].str.contains(r"^Paris\b", case=False, na=False), "station_id"])
    return set(stations.loc[stations["station_name"] == choice, "station_id"])

def direct_journeys(trips, services, origin_ids, destination_ids=None, dep_start=300, dep_end=900, max_duration=600):
    # Select active rail rows at the origin.
    base = trips[(trips["service_id"].isin(services)) &
                 (trips["route_type"] == 2) &
                 (trips["station_id"].isin(origin_ids))].copy()
    if base.empty:
        return pd.DataFrame()
    base["dep_min"] = base["departure_time"].map(parse_gtfs_time)
    base = base[(base["dep_min"] >= dep_start) & (base["dep_min"] <= dep_end)]
    if base.empty:
        return pd.DataFrame()

    # Pull complete trips for the matching trip IDs, then keep downstream stops.
    ids = base["trip_id"].unique()
    full = trips[trips["trip_id"].isin(ids)][
        ["trip_id", "station_id", "station_name", "stop_sequence", "arrival_time", "trip_headsign"]
    ].copy()
    origins = base[["trip_id","stop_sequence","departure_time","dep_min","station_id"]].rename(
        columns={
            "stop_sequence": "origin_seq",
            "departure_time": "origin_departure_time",
            "station_id": "origin_station_id",
        }
    )
    full = full.merge(
        origins[["trip_id","origin_seq","origin_departure_time","dep_min","origin_station_id"]],
        on="trip_id",
        how="inner",
    )
    full["arr_min"] = full["arrival_time"].map(parse_gtfs_time)
    full = full[full["stop_sequence"] > full["origin_seq"]]
    full = full[full["station_id"].notna()]
    if destination_ids is not None:
        full = full[full["station_id"].isin(destination_ids)]
    full = full[(full["arr_min"] >= full["dep_min"]) & ((full["arr_min"]-full["dep_min"]) <= max_duration)]
    # One result per trip + destination station: earliest arrival.
    full = full.sort_values(["trip_id","station_id","arr_min"]).drop_duplicates(["trip_id","station_id"])
    full = full.rename(columns={"origin_departure_time": "departure_time"})
    return full[["trip_id","station_id","station_name","departure_time","arrival_time","dep_min","arr_min","origin_station_id","trip_headsign"]]

def return_options(trips, services, origin_ids, destination_id, dep_start=600, dep_end=1500, max_duration=600):
    # Search destination -> origin on return date.
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
    vals = pd.to_numeric(f["Prix minimum"], errors="coerce")
    return vals.min(), pd.to_numeric(f["Prix maximum"], errors="coerce").max()

stations, routes, cal, trips = load_data()
fares = load_fares()
if not fares.empty:
    fares["_o"] = fares["Gare origine"].map(norm)
    fares["_d"] = fares["Gare destination"].map(norm)

st.title("🚆 En Train Alain")
st.caption("Tu as un budget, on cherche où partir. — V5 : vrais horaires SNCF")

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
    dep_window = st.selectbox("Départ aller", ["Toute la journée", "Matin (05h–12h)", "Après-midi (12h–18h)", "Soir (18h–23h)"])
    vibe = st.selectbox("Ambiance", ["Peu importe", "Week-end", "Culture", "Nature", "Soleil", "Gastronomie"])
    search = st.button("🔎 Trouver où partir", type="primary", use_container_width=True)

st.markdown("### Où peux-tu partir ?")
st.info("Cette version utilise les horaires SNCF réels. Les prix affichés quand disponibles sont des **tarifs indicatifs de référence**, pas le prix en temps réel.")

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

    if not out_services:
        st.warning("Aucun service SNCF n'est renseigné pour cette date dans le fichier GTFS.")
        st.stop()

    with st.spinner("Recherche des trajets réels…"):
        outbound_trips = direct_journeys(trips, out_services, origin_ids, dep_start=dep_start, dep_end=dep_end, max_duration=max_duration)

        if outbound_trips.empty:
            st.warning("Aucun trajet ferroviaire direct trouvé avec ces critères.")
            st.caption("Les horaires SNCF ont bien été chargés, mais aucun train direct ne correspond à cette combinaison de date, départ, plage horaire et durée.")
            st.stop()

        # Keep the best outbound per destination.
        dests = []
        for station_id, g in outbound_trips.groupby("station_id"):
            g = g.sort_values(["arr_min","dep_min"])
            row = g.iloc[0].copy()
            ret = return_options(trips, in_services, origin_ids, station_id, dep_start=600, dep_end=1500, max_duration=max_duration)
            if not ret.empty:
                rr = ret.sort_values(["dep_min","arr_min"]).iloc[0]
                row["return_departure"] = rr["departure_time"]
                row["return_arrival"] = rr["arrival_time"]
                row["return_duration"] = rr["arr_min"] - rr["dep_min"]
                row["return_trip_id"] = rr["trip_id"]
            else:
                row["return_departure"] = np.nan
                row["return_arrival"] = np.nan
                row["return_duration"] = np.nan
                row["return_trip_id"] = np.nan
            dests.append(row)

        results = pd.DataFrame(dests)
        results = results[results["return_trip_id"].notna()].copy()
        if results.empty:
            st.warning("Des allers ont été trouvés, mais aucun retour direct compatible n'a été trouvé.")
            st.stop()

        # Reference fare estimate when station names match the SNCF fare dataset.
        if not fares.empty:
            origin_for_fare = "PARIS"
            if origin != "Paris (toutes les gares)":
                origin_for_fare = origin
            fare_mins = []
            for _, r in results.iterrows():
                mn, mx = fare_lookup(fares, origin_for_fare, r["station_name"])
                fare_mins.append(mn)
            results["fare_min"] = fare_mins
            results["fare_ar"] = results["fare_min"] * 2
        else:
            results["fare_min"] = np.nan
            results["fare_ar"] = np.nan

        # Score: duration + schedule + budget when a reference fare exists.
        results["out_duration"] = results["arr_min"] - results["dep_min"]
        results["total_duration"] = results["out_duration"] + results["return_duration"]
        results["schedule_score"] = np.clip(1 - np.abs(results["dep_min"] - 510) / 600, 0, 1)
        results["time_score"] = np.clip(1 - results["total_duration"] / (max_duration*2), 0, 1)
        if results["fare_ar"].notna().any():
            budget_score = np.where(results["fare_ar"].notna(), np.clip(1 - results["fare_ar"]/budget, 0, 1), 0.5)
        else:
            budget_score = np.full(len(results), 0.5)
        results["score"] = (0.45*budget_score + 0.35*results["time_score"] + 0.20*results["schedule_score"])*100
        results = results.sort_values(["score","out_duration"], ascending=[False,True]).head(30)

        st.success(f"{len(results)} destinations avec un aller + retour direct trouvées.")
        st.caption(f"Services actifs : {len(out_services)} à l'aller · {len(in_services)} au retour")

        for _, r in results.iterrows():
            fare_text = f"≈ {r['fare_ar']:.0f} € A/R" if pd.notna(r["fare_ar"]) else "prix à vérifier"
            with st.container(border=True):
                c1, c2 = st.columns([3,1])
                with c1:
                    st.subheader(str(r["station_name"]).title())
                    st.write(
                        f"**Aller :** {fmt_time(r['dep_min'])} → {fmt_time(r['arr_min'])} · {fmt_duration(r['out_duration'])}  \n"
                        f"**Retour :** {fmt_time(r['return_departure'])} → {fmt_time(r['return_arrival'])} · {fmt_duration(r['return_duration'])}"
                    )
                    st.caption(f"{fare_text} · score {r['score']:.0f}/100 · {r['trip_headsign']}")
                with c2:
                    st.metric("Deal Score", f"{r['score']:.0f}/100")

else:
    st.markdown("""
    **Exemple :** choisis Paris, un week-end et un budget de 100 €.

    En Train Alain va chercher dans les données SNCF les destinations réellement desservies,
    puis vérifier qu'un trajet retour existe aussi.
    """)
