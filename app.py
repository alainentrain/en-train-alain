import streamlit as st
from datetime import date, timedelta
from engine import find_destinations

st.set_page_config(
    page_title="En Train Alain",
    page_icon="🚂",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
.block-container {max-width: 720px; padding-top: 1.5rem;}
h1 {font-size: 2.1rem !important; margin-bottom: .2rem;}
.eta-card {padding: 1rem 1.1rem; border: 1px solid #e8e8e8; border-radius: 18px; margin-bottom: .8rem; background: white;}
.score {font-weight: 800; font-size: 1.15rem;}
.small {color:#666; font-size:.85rem;}
</style>
""", unsafe_allow_html=True)

st.title("🚂 En Train Alain")
st.subheader("Tu as un budget. On trouve où partir.")
st.caption("Prototype V1 — moteur de découverte ferroviaire")

col1, col2 = st.columns(2)
with col1:
    depart = st.text_input("📍 Départ", "Paris")
with col2:
    budget = st.number_input("💶 Budget max", min_value=10, max_value=1000, value=80, step=5)

col3, col4 = st.columns(2)
with col3:
    dep_date = st.date_input("📅 Date de départ", date.today() + timedelta(days=4))
with col4:
    max_duration = st.number_input("⏱️ Durée max", min_value=1, max_value=12, value=5, step=1)

flex = st.selectbox("🗓️ Flexibilité", ["Date précise", "± 1 jour", "Week-end", "± 3 jours"])
vibe = st.selectbox(
    "✨ Tu cherches plutôt…",
    ["Peu importe", "Mer", "Ville", "Nature", "Culture", "Soleil"],
)

if st.button("🔎 Trouve-moi une destination", use_container_width=True, type="primary"):
    results = find_destinations(
        depart=depart,
        budget=budget,
        departure_date=dep_date,
        max_duration=max_duration,
        flexibility=flex,
        vibe=vibe,
    )

    st.divider()
    st.markdown("### Tes meilleures options")

    if not results:
        st.warning("Aucune destination ne correspond à ces critères dans le prototype.")
    else:
        for r in results:
            st.markdown(f"""
            <div class="eta-card">
                <div style="display:flex;justify-content:space-between;gap:10px;">
                    <div>
                        <div style="font-size:1.25rem;font-weight:800;">{r['destination']}</div>
                        <div class="small">{r['route']} · {r['duration']} · {r['type']}</div>
                    </div>
                    <div class="score">{r['score']}/100</div>
                </div>
                <div style="margin-top:.7rem;font-size:1.05rem;">
                    <b>≈ {r['price']} €</b> · {r['reason']}
                </div>
                <div class="small" style="margin-top:.35rem;">
                    {r['date_label']} · {r['direct']}
                </div>
            </div>
            """, unsafe_allow_html=True)

        st.caption("Prototype : les prix affichés sont indicatifs et ne constituent pas une disponibilité commerciale en temps réel.")

st.divider()
st.caption("En Train Alain — chercher où partir avant de chercher comment réserver.")
