# generator/simulate_nodes.py
# Trust-Fabric simulator — sends signed telemetry to your API.

import os, time, uuid, random, json, requests
from datetime import datetime, timezone

# --- CONFIG (edit these two if needed) ---
API_BASE   = "https://trust-fabric-sandbox.onrender.com"
INGEST_KEY = "DEV_INGEST_TOKEN"   # or your new long random token
DELAY_S    = 15                   # seconds between sends
PER_DEVICE = 1                    # packets per device per cycle

# Demo devices
DEVICES = [
    ("TF-SIG-101", "Traffic Signal", "Pratt & Light St"),
    ("TF-CV-201",  "Connected Vehicle", "I-95 EB MP 53"),
    ("TF-UAS-301", "UAS Node", "Port Perimeter"),
]
# generator/simulate_nodes.py
# Trust-Fabric simulator: gets a JWT, then posts signed-ish demo events to /v1/ingest

import os, time, uuid, random, json, requests
from datetime import datetime, timezone

API_BASE    = os.getenv("API_URL", "https://trust-fabric-sandbox.onrender.com")
INGEST_KEY  = os.getenv("INGEST_TOKEN", "<PUT_INGEST_TOKEN_HERE>")  # or set in Render/locally
JWT_CLIENT  = os.getenv("JWT_CLIENT", "kaelen-demo")
DELAY_S     = float(os.getenv("DELAY_S", "10"))      # seconds between rounds
PER_DEVICE  = int(os.getenv("PER_DEVICE", "2"))      # events per device each round

DEVICES = [
    ("TF-SIG-101", "Traffic Signal", "Pratt & Light St"),
    ("TF-CV-201",  "Connected Vehicle", "Inner Harbor"),
    ("TF-UAS-301", "UAS Node", "Port Perimeter"),
]

def iso_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def get_token():
    url = f"{API_BASE}/v1/dev-token"
    r = requests.post(url, json={"client": JWT_CLIENT, "key": INGEST_KEY}, timeout=10)
    r.raise_for_status()
    j = r.json()
    print(f"[auth] JWT ok (expires_in={j.get('expires_in','?')}s)")
    return j["access_token"]

def payload_for(device_id: str):
    if device_id.startswith("TF-SIG"):
        return {"state": random.choice([0,1,2]), "lat": 39.289, "lon": -76.612}
    if device_id.startswith("TF-UAS"):
        return {"alt_m": random.randint(30,120), "speed": random.randint(0,20)}
    # default CV
    return {"speed": random.randint(0,65),
            "lat": 39.29 + random.random()/1000,
            "lon": -76.61 - random.random()/1000}

def send_event(token: str, device_id: str):
    body = {
        "device_id": device_id,
        "payload": payload_for(device_id),
        "ts_utc": iso_now() + "Z",
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-TF-Nonce": str(uuid.uuid4()),   # anti-replay header (your API can enforce)
    }
    r = requests.post(f"{API_BASE}/v1/ingest", headers=headers, json=body, timeout=12)
    status = r.status_code
    try:
        j = r.json()
    except Exception:
        j = {"text": r.text[:160]}
    print(f"[{device_id}] {status} -> {j}")
    return status

def main():
    token = get_token()
    while True:
        for device_id, _, _ in DEVICES:
            for _ in range(PER_DEVICE):
                send_event(token, device_id)
        time.sleep(DELAY_S)

if __name__ == "__main__":
    print(f"Target API: {API_BASE}")
    main()
