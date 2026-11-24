import streamlit as st
from datetime import date, timedelta

from engine import search_destinations
from data_sources import DEMO_ROUTES

st.set_page_config(
    page_title="En Train Alain",
    page_icon="🚂",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
.block-container { max-width: 760px; padding-top: 1.5rem; }
h1 { margin-bottom: .2rem; }
.eta-card {
    border: 1px solid #e5e7eb; border-radius: 16px;
    padding: 18px; margin: 12px 0; background: white;
}
.score { float:right; font-size: 1.15rem; font-weight: 700; }
.price { font-size: 1.2rem; font-weight: 700; margin-top: 8px; }
.meta { color:#666; font-size:.92rem; }
.note { color:#777; font-size:.78rem; }
</style>
""", unsafe_allow_html=True)

st.title("🚂 En Train Alain")
st.subheader("Tu as un budget. On trouve où partir.")
st.caption("Prototype V3 — moteur de découverte avec aller + retour")

with st.form("search"):
    departure = st.text_input("📍 Départ", value="Paris")

    c1, c2 = st.columns(2)
    with c1:
        departure_date = st.date_input(
            "📅 Aller",
            value=date.today() + timedelta(days=14),
            min_value=date.today()
        )
    with c2:
        return_date = st.date_input(
            "↩️ Retour",
            value=date.today() + timedelta(days=16),
            min_value=date.today()
        )

    c3, c4 = st.columns(2)
    with c3:
        budget = st.number_input(
            "💶 Budget maximum A/R",
            min_value=5, max_value=500, value=40, step=5
        )
    with c4:
        max_duration = st.slider(
            "⏱️ Durée max par trajet",
            min_value=1.0, max_value=6.0, value=3.0, step=0.5
        )

    vibe = st.selectbox(
        "✨ Envie",
        ["Peu importe", "Week-end", "Culture", "Nature", "Soleil", "Gastronomie"]
    )

    submitted = st.form_submit_button(
        "🔎 Trouve-moi une destination",
        use_container_width=True
    )

if submitted:
    if return_date < departure_date:
        st.error("La date de retour doit être après la date de départ.")
        st.stop()

    results = search_destinations(
        departure=departure,
        departure_date=departure_date,
        return_date=return_date,
        budget=float(budget),
        max_duration=float(max_duration),
        vibe=vibe,
        routes=DEMO_ROUTES,
    )

    st.divider()
    st.markdown(
        f"### Tes meilleures options"
    )
    st.caption(
        f"{departure} → aller {departure_date.strftime('%d/%m/%Y')} · "
        f"retour {return_date.strftime('%d/%m/%Y')} · "
        f"budget A/R ≤ {budget:.0f} € · ≤ {max_duration:g} h par trajet"
    )

    if not results:
        st.warning(
            "Aucune destination ne rentre dans ces critères avec les données de démonstration. "
            "Essaie d'augmenter le budget ou la durée."
        )
    else:
        for r in results:
            st.markdown(f"""
<div class="eta-card">
<div class="score">{r['score']}/100</div>
<h3 style="margin-bottom:4px">{r['destination']}</h3>
<div class="meta">{r['outbound_operator']} · aller ≈ {r['outbound_duration']:.1f} h</div>
<div class="meta">retour ≈ {r['return_duration']:.1f} h</div>
<div class="price">≈ {r['roundtrip_reference_price']:.0f} € A/R</div>
<div class="meta">{r['reason']}</div>
<div class="note">Tarif indicatif issu des données du prototype — ce n'est pas une disponibilité commerciale en temps réel.</div>
</div>
""", unsafe_allow_html=True)

st.divider()
st.caption(
    "V3 : le budget porte sur l'aller-retour et la recherche possède désormais une vraie date d'aller et une vraie date de retour. "
    "Les tarifs affichés ici restent indicatifs tant que l'API commerciale n'est pas branchée."
)
