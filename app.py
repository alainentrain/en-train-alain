import streamlit as st
from datetime import date, timedelta
from engine import search_destinations

st.set_page_config(
    page_title="En Train Alain",
    page_icon="🚂",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
    .block-container { max-width: 760px; padding-top: 2rem; }
    .result-card {
        border: 1px solid #e7e7e7;
        border-radius: 16px;
        padding: 1.1rem 1.2rem;
        margin: 0.8rem 0;
        background: white;
    }
    .score { font-size: 1.1rem; font-weight: 700; float: right; }
    .price { font-size: 1.45rem; font-weight: 750; margin: .45rem 0; }
    .muted { color: #6b7280; font-size: .88rem; }
    .tag {
        display: inline-block; padding: .18rem .5rem; border-radius: 999px;
        background: #f3f4f6; font-size: .78rem; margin-right: .25rem;
    }
</style>
""", unsafe_allow_html=True)

st.title("🚂 En Train Alain")
st.subheader("Tu as un budget. On trouve où partir.")
st.caption("Prototype V3.1 — moteur de découverte avec préférences de destination.")

with st.form("search"):
    departure = st.text_input("📍 Départ", value="Paris")

    c1, c2 = st.columns(2)
    with c1:
        outbound = st.date_input(
            "🗓️ Aller",
            value=date.today() + timedelta(days=11),
            min_value=date.today(),
            format="DD/MM/YYYY",
        )
    with c2:
        return_date = st.date_input(
            "↩️ Retour",
            value=date.today() + timedelta(days=12),
            min_value=date.today(),
            format="DD/MM/YYYY",
        )

    budget = st.number_input(
        "💶 Budget maximum A/R",
        min_value=10,
        max_value=500,
        value=80,
        step=5,
    )

    duration = st.slider(
        "⏱️ Durée max par trajet",
        min_value=1.0,
        max_value=6.0,
        value=3.0,
        step=0.5,
        format="%.1f h",
    )

    vibe = st.selectbox(
        "✨ Qu'est-ce qui te fait envie ?",
        ["Peu importe", "Week-end", "Culture", "Nature", "Soleil", "Gastronomie"],
    )

    submitted = st.form_submit_button(
        "🔎 Trouve-moi une destination",
        use_container_width=True,
    )

if submitted:
    if return_date < outbound:
        st.error("La date de retour doit être après la date d'aller.")
        st.stop()

    results = search_destinations(
        departure=departure,
        outbound=outbound,
        return_date=return_date,
        budget=budget,
        max_duration=duration,
        vibe=vibe,
    )

    st.markdown("## Tes meilleures options")
    st.caption(
        f"{departure} → aller {outbound.strftime('%d/%m/%Y')} · "
        f"retour {return_date.strftime('%d/%m/%Y')} · "
        f"budget A/R ≤ {budget} € · ≤ {duration:g} h par trajet"
    )

    if not results:
        st.warning("Aucune destination ne correspond à ces critères dans le prototype.")
        st.stop()

    for r in results:
        tags = " ".join(
            f'<span class="tag">{x}</span>' for x in r["vibes"][:3]
        )
        st.markdown(f"""
        <div class="result-card">
            <div class="score">{r["score"]}/100</div>
            <h3 style="margin-bottom:.2rem;">{r["destination"]}</h3>
            <div class="muted">{r["operator"]} · aller ≈ {r["outbound_h"]:.1f} h · retour ≈ {r["return_h"]:.1f} h</div>
            <div class="price">≈ {r["price"]:.0f} € A/R</div>
            <div>{r["reason"]}</div>
            <div style="margin-top:.55rem;">{tags}</div>
            <div class="muted" style="margin-top:.65rem;">
                Tarif indicatif issu des données du prototype — ce n'est pas une disponibilité commerciale en temps réel.
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.caption(
        "V3.1 : le choix de vibe influence désormais réellement le classement. "
        "Les prix restent indicatifs jusqu'à l'intégration de données tarifaires en temps réel."
    )
