import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import timedelta
import re
import unicodedata

st.set_page_config(page_title="En Train Alain", page_icon="🚆", layout="wide")
DATA = Path(__file__).parent / "data"

MAX_OPTIONS = 4
MAX_ALTERNATIVES = 3

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
    trips["dep_min"] = trips["departure_time"].map(parse_gtfs_time)
    trips["arr_min"] = trips["arrival_time"].map(parse_gtfs_time)
    return stations, routes, cal, trips

@st.cache_data
def load_destinations():
    return pd.read_csv(DATA / "destinations.csv")

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
            ].astype(str)
        )
    return set(stations.loc[stations["station_name"] == choice, "station_id"].astype(str))

def build_destination_map(stations, destinations):
    s = stations.copy()
    s["_norm"] = s["station_name"].map(norm)
    mapping = {}
    station_to_destination = {}
    for _, d in destinations.iterrows():
        target = norm(d["match"])
        mask = (s["_norm"] == target) | s["_norm"].str.startswith(target + " ")
        ids = set(s.loc[mask, "station_id"].astype(str))
        if ids:
            mapping[d["destination"]] = {"station_ids": ids, "row": d}
            for sid in ids:
                station_to_destination[sid] = d["destination"]
    return mapping, station_to_destination

def rail_rows(trips, services):
    return trips[
        trips["service_id"].isin(services) & (trips["route_type"] == 2)
    ]

def direct_journeys(trips, services, origin_ids, destination_ids=None,
                    dep_start=300, dep_end=1380, max_duration=600):
    base = rail_rows(trips, services)
    base = base[base["station_id"].isin(origin_ids)].copy()
    if base.empty:
        return pd.DataFrame()

    base = base[base["dep_min"].between(dep_start, dep_end)].dropna(subset=["dep_min"])
    if base.empty:
        return pd.DataFrame()

    ids = base["trip_id"].unique()
    full = trips[trips["trip_id"].isin(ids)][
        ["trip_id", "station_id", "station_name", "stop_sequence",
         "arrival_time", "arr_min", "trip_headsign"]
    ].copy()

    origins = base[
        ["trip_id", "stop_sequence", "departure_time", "dep_min", "station_id"]
    ].rename(columns={
        "stop_sequence": "origin_seq",
        "departure_time": "origin_departure_time",
        "station_id": "origin_station_id",
    })

    full = full.merge(origins, on="trip_id", how="inner")
    full = full[
        (full["stop_sequence"] > full["origin_seq"])
        & full["station_id"].notna()
        & full["arr_min"].notna()
    ]
    if destination_ids is not None:
        full = full[full["station_id"].isin(destination_ids)]
    if full.empty:
        return pd.DataFrame()

    full["duration"] = full["arr_min"] - full["dep_min"]
    full = full[(full["duration"] >= 0) & (full["duration"] <= max_duration)]
    full = full.sort_values(["trip_id", "station_id", "arr_min"]).drop_duplicates(
        ["trip_id", "station_id"]
    )
    return full.rename(columns={"origin_departure_time": "departure_time"})[
        ["trip_id", "station_id", "station_name", "departure_time",
         "arrival_time", "dep_min", "arr_min", "origin_station_id",
         "trip_headsign", "duration"]
    ]

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

def pick_options(df, n=MAX_OPTIONS):
    if df.empty:
        return df
    # Keep a spread of departures rather than four almost-identical trains.
    x = df.sort_values(["dep_min", "duration", "arr_min"]).copy()
    picked = []
    for _, row in x.iterrows():
        if all(abs(float(row["dep_min"]) - float(p["dep_min"])) >= 45 for p in picked):
            picked.append(row)
        if len(picked) >= n:
            break
    if len(picked) < n:
        seen = {str(p["trip_id"]) for p in picked}
        for _, row in x.iterrows():
            if str(row["trip_id"]) not in seen:
                picked.append(row)
                seen.add(str(row["trip_id"]))
            if len(picked) >= n:
                break
    return pd.DataFrame(picked)

def stay_minutes(out_dep, out_arr, ret_dep, same_day):
    if same_day:
        return ret_dep - out_arr
    return (24 * 60 - out_arr) + ret_dep

def score_pair(out_row, ret_row, fare_ar, budget, max_duration, vibe_score, same_day):
    stay = stay_minutes(out_row["dep_min"], out_row["arr_min"], ret_row["dep_min"], same_day)
    if stay <= 0:
        return -1
    total_travel = float(out_row["duration"]) + float(ret_row["duration"])
    time_score = np.clip(1 - total_travel / (max_duration * 2), 0, 1)
    # A pleasant departure window, without making 6am trains impossible.
    schedule_score = np.clip(1 - abs(float(out_row["dep_min"]) - 510) / 600, 0, 1)
    stay_target = 8 * 60 if same_day else 24 * 60
    stay_score = np.clip(stay / stay_target, 0, 1)
    budget_score = 0.5 if pd.isna(fare_ar) else np.clip(1 - fare_ar / budget, 0, 1)
    return (0.38 * vibe_score + 0.27 * budget_score + 0.18 * time_score
            + 0.10 * schedule_score + 0.07 * stay_score) * 100

def find_best_pairs(out_options, return_options, fare_ar, budget, max_duration,
                    vibe_score, same_day):
    pairs = []
    for _, o in out_options.iterrows():
        for _, r in return_options.iterrows():
            if same_day and float(r["dep_min"]) <= float(o["arr_min"]):
                continue
            score = score_pair(o, r, fare_ar, budget, max_duration, vibe_score, same_day)
            if score < 0:
                continue
            pairs.append({"out": o, "ret": r, "score": score})
    pairs.sort(key=lambda p: p["score"], reverse=True)
    return pairs[:MAX_ALTERNATIVES + 1]

stations, routes, cal, trips = load_data()
fares = load_fares()
destinations = load_destinations()
destination_map, station_to_destination = build_destination_map(stations, destinations)
station_name_map = stations.set_index(stations["station_id"].astype(str))["station_name"].to_dict()
if not fares.empty:
    fares["_o"] = fares["Gare origine"].map(norm)
    fares["_d"] = fares["Gare destination"].map(norm)

st.title("🚆 En Train Alain")
st.caption("Tu as un budget, on cherche où partir. — V9 : vraies destinations + plusieurs horaires")

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

    if not out_services or not in_services:
        st.warning("Aucun service SNCF n'est renseigné pour l'une des dates choisies dans le fichier GTFS.")
        st.stop()

    destination_ids = set(station_to_destination.keys())
    same_day = outbound == inbound

    with st.spinner("Recherche des escapades réelles…"):
        # One batched search for all editorial destinations, instead of a loop over 3,423 stations.
        out_all = direct_journeys(
            trips, out_services, origin_ids, destination_ids=destination_ids,
            dep_start=dep_start, dep_end=dep_end, max_duration=max_duration
        )
        if out_all.empty:
            st.warning("Aucune destination de notre sélection ne correspond aux critères aller.")
            st.stop()

        out_all["destination"] = out_all["station_id"].map(station_to_destination)
        out_all = out_all.dropna(subset=["destination"])

        # One batched return search for all destination stations back to the selected origin.
        return_origin_ids = set(out_all["station_id"].astype(str))
        ret_all = direct_journeys(
            trips, in_services, return_origin_ids, destination_ids=origin_ids,
            dep_start=600, dep_end=1500, max_duration=max_duration
        )
        if ret_all.empty:
            st.warning("Les destinations aller trouvées n'ont pas de retour direct correspondant aux critères.")
            st.stop()

        ret_all["destination"] = ret_all["origin_station_id"].map(station_to_destination)
        ret_all = ret_all.dropna(subset=["destination"])

        vibe_col = {"Culture": "culture", "Nature": "nature", "Soleil": "soleil", "Gastronomie": "gastronomie"}.get(vibe)
        vibe_map = destinations.set_index("destination")[vibe_col] if vibe_col else None

        result_rows = []
        for destination, og in out_all.groupby("destination"):
            station_ids = set(og["station_id"].astype(str))
            rg = ret_all[ret_all["origin_station_id"].astype(str).isin(station_ids)]
            if rg.empty:
                continue

            fare_min = fare_lookup(fares, "PARIS" if origin == "Paris (toutes les gares)" else origin, destination)
            fare_ar = fare_min * 2 if pd.notna(fare_min) else np.nan
            vs = float(vibe_map.get(destination, 0.5)) if vibe_map is not None else 0.70
            outs = pick_options(og, MAX_OPTIONS)
            rets = pick_options(rg, MAX_OPTIONS)
            pairs = find_best_pairs(outs, rets, fare_ar, budget, max_duration, vs, same_day)
            if not pairs:
                continue

            best = pairs[0]
            o, r = best["out"], best["ret"]
            result_rows.append({
                "destination": destination,
                "arrival_station": o["station_name"],
                "arrival_station_id": o["station_id"],
                "origin_station": o["origin_station_id"],
                "out": o,
                "ret": r,
                "alternatives": pairs[1:],
                "fare_ar": fare_ar,
                "score": best["score"],
                "vibe_score": vs,
            })

        results = pd.DataFrame(result_rows)
        if results.empty:
            st.warning("Aucun aller-retour direct ne correspond à ces critères.")
            st.stop()

        results = results.sort_values(["score", "destination"], ascending=[False, True]).head(30)

        st.success(f"{len(results)} destinations d'escapade · plusieurs horaires comparés pour chaque destination.")
        st.caption(
            f"Services actifs : {len(out_services)} à l'aller · {len(in_services)} au retour · "
            f"{len(out_all)} trajets aller analysés · V9"
        )

        for _, r in results.iterrows():
            o, ret = r["out"], r["ret"]
            fare_text = f"≈ {r['fare_ar']:.0f} € A/R" if pd.notna(r["fare_ar"]) else "prix à vérifier"
            out_station = str(o["station_name"])
            out_origin_station = str(station_name_map.get(str(o["origin_station_id"]), o["origin_station_id"]))
            ret_station = str(station_name_map.get(str(ret["origin_station_id"]), ret["origin_station_id"]))
            ret_arrival_station = str(ret["station_name"])
            with st.container(border=True):
                c1, c2 = st.columns([3, 1])
                with c1:
                    st.subheader(str(r["destination"]))
                    st.write(
                        f"**Aller — {out_origin_station} → {out_station} :** "
                        f"{fmt_time(o['dep_min'])} → {fmt_time(o['arr_min'])} · {fmt_duration(o['duration'])}"
                        f"  \n**Retour — {ret_station} → {ret_arrival_station} :** "
                        f"{fmt_time(ret['dep_min'])} → {fmt_time(ret['arr_min'])} · {fmt_duration(ret['duration'])}"
                    )
                    st.caption(f"Gare d'arrivée : **{out_station}** · trajet direct · {fare_text} · score {r['score']:.0f}/100")

                    alternatives = r["alternatives"]
                    if alternatives:
                        with st.expander("Voir d'autres horaires"):
                            for i, p in enumerate(alternatives, 1):
                                ao, ar = p["out"], p["ret"]
                                st.write(
                                    f"**Option {i}** · Aller {fmt_time(ao['dep_min'])} → {fmt_time(ao['arr_min'])} "
                                    f"({fmt_duration(ao['duration'])}) · Retour {fmt_time(ar['dep_min'])} → {fmt_time(ar['arr_min'])} "
                                    f"({fmt_duration(ar['duration'])}) · score {p['score']:.0f}/100"
                                )
                with c2:
                    st.metric("Deal Score", f"{r['score']:.0f}/100")
else:
    st.markdown("""
    **Exemple :** choisis Paris, un week-end et un budget de 100 €.

    En Train Alain part d'une **sélection de vraies destinations**, cherche plusieurs horaires aller et retour,
    puis te présente la combinaison la plus intéressante — avec les autres horaires disponibles en option.
    """)
