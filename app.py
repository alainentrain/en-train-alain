import streamlit as st
from datetime import date, timedelta

from data_sources import get_live_sncF_fares
from engine import find_destinations

st.set_page_config(
    page_title="En Train Alain",
    page_icon="🚂",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
.block-container {max-width: 760px; padding-top: 1.2rem; padding-bottom: 3rem;}
.eta-card {
    border: 1px solid #e7e7e7; border-radius: 18px; padding: 18px;
    margin: 12px 0; background: white;
}
.score {font-size: 1.45rem; font-weight: 800;}
.destination {font-size: 1.25rem; font-weight: 800;}
.muted {color: #666;}
.price {font-size: 1.1rem; font-weight: 700;}
</style>
""", unsafe_allow_html=True)

st.title("🚂 En Train Alain")
st.subheader("Tu as un budget. On trouve où partir.")
st.caption("V2 — tarifs SNCF open data + moteur de découverte")

with st.container():
    departure = st.text_input("📍 Départ", value="Paris")
    budget = st.slider("💶 Budget maximum", 10, 200, 50, 5)
    trip_date = st.date_input(
        "📅 Date de départ",
        value=date.today() + timedelta(days=7),
        min_value=date.today(),
    )
    max_duration = st.slider("⏱️ Durée maximale du trajet", 1.0, 8.0, 3.0, 0.5)
    vibe = st.selectbox(
        "✨ Envie",
        ["Peu importe", "Culture", "Mer", "Nature", "Soleil", "Week-end"],
    )

search = st.button("🔎 Trouve-moi une destination", use_container_width=True, type="primary")

if search:
    with st.spinner("Je cherche les destinations compatibles…"):
        fares, source_status = get_live_sncF_fares(departure)

    if source_status == "live":
        results = find_destinations(
            fares=fares,
            departure=departure,
            budget=budget,
            trip_date=trip_date,
            max_duration=max_duration,
            vibe=vibe,
        )
        st.success("Tarifs issus du jeu de données officiel SNCF Open Data.")
    else:
        results = find_destinations(
            fares=fares,
            departure=departure,
            budget=budget,
            trip_date=trip_date,
            max_duration=max_duration,
            vibe=vibe,
        )
        st.warning(
            "La source SNCF n'est pas accessible pour le moment. "
            "Le prototype utilise les données de secours intégrées au projet."
        )

    st.divider()

    if not results:
        st.info(
            "Aucune destination ne correspond aux critères. "
            "Essaie d'augmenter le budget ou la durée maximale."
        )
    else:
        st.subheader("Tes meilleures options")
        for r in results[:10]:
            st.markdown(f"""
            <div class="eta-card">
                <div style="display:flex;justify-content:space-between;gap:15px;">
                    <div>
                        <div class="destination">{r['destination']}</div>
                        <div class="muted">{departure} → {r['destination']} · {r['transporteur']}</div>
                    </div>
                    <div class="score">{r['score']}/100</div>
                </div>
                <div style="margin-top:10px;">
                    <span class="price">≈ {r['prix_min']} €</span>
                    · {r['description']}
                </div>
                <div class="muted" style="margin-top:7px;">
                    Tarif indicatif · {r['date']}
                </div>
            </div>
            """, unsafe_allow_html=True)

        st.caption(
            "Important : ce prix est un tarif indicatif issu de l'open data SNCF. "
            "Il ne garantit ni le prix disponible à cette date, ni la disponibilité du train. "
            "La prochaine étape est la vérification commerciale en temps réel."
        )
else:
    st.info(
        "Exemple : « J'ai 40 €, je pars de Paris ce week-end ». "
        "Lance une recherche pour voir le moteur fonctionner."
    )
