# dashboard/streamlit_app.py
import os, requests, pandas as pd, streamlit as st

API = st.secrets.get("API_URL", os.getenv("API_URL","http://localhost:8000"))

st.set_page_config(page_title="Trust-Fabric Sandbox", layout="wide")
st.markdown(
    "<h2 style='margin-bottom:0'>TRUST-FABRIC — DATA VERIFICATION ENGINE (sandbox)</h2>"
    "<span style='color:#9ea7b3'>Evaluation Use Only — © Trust-Fabric</span>",
    unsafe_allow_html=True
)

col1, col2, col3 = st.columns(3)
events = requests.get(f"{API}/v1/events?limit=100").json()
blocks = requests.get(f"{API}/v1/blocks?limit=5").json()
health = requests.get(f"{API}/v1/health").json()

col1.metric("Verified Events", sum(1 for e in events if e["verified"]))
avg_trust = sum(e["trust_score"] for e in events)/len(events) if events else 0
col2.metric("Trust Score (avg)", f"{avg_trust:.3f}")
col3.metric("p95 Latency", f"{health.get('p95_latency_ms',0)} ms")

st.subheader("Attestation Flow — Latest Events")
df = pd.DataFrame(events)
if not df.empty:
    df_view = df[["device_id","ts_utc","hash","sig","ledger_ref","trust_score"]]
    st.dataframe(df_view, use_container_width=True, height=360)
else:
    st.info("No events yet — start the generator.")

left, right = st.columns(2)
with left:
    st.subheader("Ledger Snapshot — Recent Blocks")
    st.json(blocks)
with right:
    st.subheader("Identity Registry (demo)")
    st.table(pd.DataFrame({
        "device_id":["TF-SIG-101","TF-DRN-022","TF-SEN-317","TF-SIG-077","TF-EVC-005"],
        "status":["active"]*5
    }))

st.markdown("---")
st.caption("Identity → Attestation → Ledger → Dashboard → Micropayment (mock counters)")
