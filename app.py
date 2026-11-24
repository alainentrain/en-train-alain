import streamlit as st
from datetime import date, timedelta
from engine import search_destinations

st.set_page_config(
    page_title="En Train Alain",
    page_icon="🚆",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
.block-container {max-width: 760px; padding-top: 2rem; padding-bottom: 4rem;}
h1 {letter-spacing: -1px;}
.eta-card {padding: 18px; border-radius: 18px; border: 1px solid #e7e7e7; margin-bottom: 14px;}
.price {font-size: 1.35rem; font-weight: 800;}
.small {color:#666; font-size:.9rem;}
.badge {display:inline-block; padding:4px 9px; border-radius:999px; background:#f2f2f2; margin-right:5px; font-size:.78rem;}
</style>
""", unsafe_allow_html=True)

st.title("🚆 En Train Alain")
st.subheader("Tu as un budget. On trouve où partir.")

st.caption("Prototype V1 — moteur de découverte ferroviaire")

with st.form("search"):
    col1, col2 = st.columns(2)
    with col1:
        origin = st.text_input("📍 Départ", "Paris")
    with col2:
        budget = st.number_input("💶 Budget max", min_value=10, max_value=1000, value=80, step=5)

    col1, col2 = st.columns(2)
    with col1:
        departure = st.date_input("📅 Date de départ", date.today() + timedelta(days=3))
    with col2:
        max_duration = st.selectbox("⏱️ Durée max", [2, 3, 4, 5, 6, 8, 12], index=3,
                                    format_func=lambda x: f"{x} h")

    vibe = st.multiselect(
        "✨ J'ai envie de…",
        ["mer", "soleil", "culture", "nature", "week-end", "romantique"],
        default=["week-end"],
    )

    submitted = st.form_submit_button("🔎 Trouve-moi une destination", use_container_width=True)

if submitted:
    results = search_destinations(
        origin=origin,
        budget=float(budget),
        departure=departure,
        max_duration=max_duration,
        vibes=vibe,
    )

    st.markdown(f"### Tes meilleures options depuis {origin}")

    if not results:
        st.warning("Aucune destination ne correspond à ces critères dans le prototype.")
    else:
        for r in results:
            st.markdown(f"""
            <div class="eta-card">
                <div style="font-size:1.25rem;font-weight:800">{r['destination']}</div>
                <div class="small">{r['region']} · {r['duration']:.1f} h · {r['direct']}</div>
                <br>
                <span class="price">≈ {r['price']} €</span>
                <span class="badge">Deal Score {r['score']}/100</span>
                <span class="badge">{r['reason']}</span>
            </div>
            """, unsafe_allow_html=True)

            c1, c2 = st.columns(2)
            with c1:
                st.button(f"❤️ {r['destination']}", key=f"fav_{r['destination']}")
            with c2:
                st.button("Voir le trajet →", key=f"go_{r['destination']}")

st.divider()
st.caption("Prototype : les prix affichés sont indicatifs et ne constituent pas une disponibilité commerciale en temps réel.")
