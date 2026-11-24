import requests
import pandas as pd
from pathlib import Path

SNCF_DATASET_URL = (
    "https://ressources.data.sncf.com/api/explore/v2.1/catalog/datasets/"
    "tarifs-tgv-inoui-ouigo/records"
)

FALLBACK = Path(__file__).parent / "data" / "fallback_fares.csv"

def _normalise_station(value: str) -> str:
    value = (value or "").strip().upper()
    value = value.replace("PARIS", "PARIS")
    return value

def get_live_sncF_fares(departure: str):
    """
    Returns (DataFrame, status).
    The SNCF dataset contains annual min/max fare ranges by origin/destination,
    not date-specific live inventory.
    """
    dep = _normalise_station(departure)
    where = f"search(gare_origine, '{dep}')"

    params = {
        "limit": 100,
        "where": where,
        "select": (
            "transporteur,gare_origine,gare_destination,"
            "prix_minimum,prix_maximum"
        ),
    }

    try:
        r = requests.get(SNCF_DATASET_URL, params=params, timeout=12)
        r.raise_for_status()
        data = r.json().get("results", [])
        if data:
            return pd.DataFrame(data), "live"
    except Exception:
        pass

    return pd.read_csv(FALLBACK), "fallback"
