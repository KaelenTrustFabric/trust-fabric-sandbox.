# generator/simulate_nodes.py
import time, json, hmac, hashlib, random, requests
from datetime import datetime, timezone

API_BASE = "http://127.0.0.1:8000"  # <- change to your Render URL if deployed
ENDPOINT = f"{API_BASE}/attest"

# Two demo nodes with shared secrets (per-device key you'd provision in your identity registry)
NODES = {
    "TF-SIG-101": {"zone": "Pratt & Light St", "type": "Traffic Signal", "secret": b"sig101_secret"},
    "TF-SIG-077": {"zone": "Main & Granby",   "type": "Air Sensor",      "secret": b"sig077_secret"},
}

def sign(payload: dict, secret: bytes) -> str:
    """
    HMAC-SHA256 over a stable string of the important fields.
    Your API will recompute and compare this server-side.
    """
    canon = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    return hmac.new(secret, canon, hashlib.sha256).hexdigest()

def make_packet(node_id: str) -> dict:
    ts = datetime.now(timezone.utc).isoformat()
    # Example telemetry—customize for your devices
    sample = {
        "signal_status": random.choice(["green", "yellow", "red"]),
        "pm25": round(random.uniform(5, 40), 1),   # air quality example
        "temp_c": round(random.uniform(12, 35), 1)
    }
    pkt = {
        "node_id": node_id,
        "zone": NODES[node_id]["zone"],
        "type": NODES[node_id]["type"],
        "timestamp": ts,
        "payload": sample,
    }
    pkt["sig"] = sign(
        {k: pkt[k] for k in ["node_id", "timestamp", "payload"]},  # what we sign
        NODES[node_id]["secret"]
    )
    return pkt

def send_once(node_id: str):
    pkt = make_packet(node_id)
    try:
        r = requests.post(ENDPOINT, json=pkt, timeout=8)
        ok = "OK" if r.status_code < 300 else f"ERR {r.status_code}"
        rid = r.json().get("ledger_id", "—") if r.headers.get("content-type","").startswith("application/json") else "—"
        print(f"[{node_id}] {ok}  hash={pkt['sig'][:10]}…  ledger_id={rid}")
    except Exception as e:
        print(f"[{node_id}] FAIL {e}")

if __name__ == "__main__":
    print(f"Sending to {ENDPOINT}")
    while True:
        for node in NODES.keys():
            send_once(node)
        time.sleep(15)   # send every 15s
