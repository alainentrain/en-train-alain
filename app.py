import streamlit as st
from datetime import date, timedelta
from engine import find_best_options

st.set_page_config(page_title="En Train Alain", page_icon="🚆", layout="centered")

st.markdown('''
<style>
.block-container {max-width: 760px; padding-top: 2rem; padding-bottom: 4rem;}
.result-card {border:1px solid #e5e7eb;border-radius:18px;padding:20px 22px;margin:14px 0;background:white;}
.score {font-size:1.25rem;font-weight:700;}
.price {font-size:1.25rem;font-weight:700;margin:8px 0;}
.muted {color:#6b7280;font-size:.88rem;}
.tags span {display:inline-block;padding:4px 9px;margin:3px 5px 3px 0;border-radius:999px;background:#f3f4f6;font-size:.78rem;}
</style>
''', unsafe_allow_html=True)

st.title("🚆 En Train Alain")
st.subheader("Tu as un budget. On trouve où partir.")
st.caption("Prototype V4 — moteur de recommandation par destination")

with st.container(border=True):
    st.markdown("### ✨ Qu'est-ce qui te fait envie ?")
    vibe = st.selectbox("Vibe", ["Peu importe","Week-end","Culture","Nature","Soleil","Gastronomie"],
                        label_visibility="collapsed")
    c1, c2 = st.columns(2)
    with c1:
        departure = st.selectbox("📍 Départ", ["Paris"])
        outbound = st.date_input("📅 Aller", date.today() + timedelta(days=11))
    with c2:
        return_date = st.date_input("📅 Retour", outbound + timedelta(days=1))
        budget = st.number_input("💶 Budget maximum A/R", min_value=10, max_value=500, value=80, step=5)
    max_hours = st.slider("⏱️ Durée max par trajet", 1.0, 6.0, 3.0, 0.1)
    search = st.button("🔎 Trouve-moi une destination", type="primary", use_container_width=True)

if search:
    if return_date <= outbound:
        st.error("La date de retour doit être après la date d'aller.")
        st.stop()

    results = find_best_options(departure, outbound, return_date, budget, max_hours, vibe)

    st.markdown("## Tes meilleures options")
    st.caption(f"{departure} → aller {outbound.strftime('%d/%m/%Y')} · retour {return_date.strftime('%d/%m/%Y')} · budget A/R ≤ {budget:.0f} € · ≤ {max_hours:g} h par trajet")

    if not results:
        st.warning("Aucune destination ne correspond à tes contraintes. Essaie d'augmenter le budget ou la durée maximale.")
        st.stop()

    for r in results:
        tags = "".join(f"<span>{t}</span>" for t in r["tags"])
        vibe_line = (f"Très bonne correspondance avec ton envie « {vibe.lower()} »."
                     if vibe != "Peu importe" else r["reason"])
        st.markdown(f'''
        <div class="result-card">
          <div style="display:flex;justify-content:space-between;gap:20px;">
            <div><h2 style="margin:0;">{r["destination"]}</h2>
            <div class="muted">{r["operator"]} · aller ≈ {r["outbound_hours"]:.1f} h · retour ≈ {r["return_hours"]:.1f} h</div></div>
            <div class="score">{r["score"]}/100</div>
          </div>
          <div class="price">≈ {r["round_trip_price"]:.0f} € A/R</div>
          <div>{vibe_line}</div>
          <div class="tags">{tags}</div>
          <div class="muted" style="margin-top:10px;">Tarif indicatif issu des données du prototype — ce n'est pas une disponibilité commerciale en temps réel.</div>
        </div>
        ''', unsafe_allow_html=True)

    st.markdown("---")
    st.caption("V4 : les envies sont modélisées par des profils de destination à scores progressifs.")
else:
    st.info("Choisis tes contraintes et ton envie, puis lance la recherche.")
