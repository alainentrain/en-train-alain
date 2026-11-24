"""
Data-source adapters for En Train Alain.

V1 intentionally runs in DEMO mode so the Streamlit deployment works
without credentials or paid API access.

Next step:
- connect SNCF open-data datasets for stations, schedules, real-time data,
  reference fares and MAX availability;
- add a Tictactrip adapter for current retail prices, availability and
  booking/redirection.

Do not put API secrets directly in this file. Use Streamlit secrets or
environment variables in production.
"""

import os

SNCF_API_TOKEN = os.getenv("SNCF_API_TOKEN", "")
TICTACTRIP_API_KEY = os.getenv("TICTACTRIP_API_KEY", "")
