# generator/generator.py
import time, requests, random, datetime as dt, os

API = os.getenv("API_URL", "http://localhost:8000")
TOKEN = os.getenv("INGEST_TOKEN", "DEV_INGEST_TOKEN")
DEVICES = ["TF-SIG-101","TF-DRN-022","TF-SEN-317","TF-SIG-077","TF-EVC-005"]

def send_once():
    payload = {
        "event": "signal_state",
        "state": random.choice(["G","Y","R"]),
        "speed": random.randint(0,70),
        "lat": 39.28 + random.random()/100,
        "lon": -76.61 + random.random()/100
    }
    body = {
        "device_id": random.choice(DEVICES),
        "payload": payload,
        "ts_utc": dt.datetime.utcnow().isoformat(timespec="seconds")+"Z"
    }
    try:
        r = requests.post(f"{API}/v1/ingest", json=body,
                          headers={"X-TF-Key": TOKEN}, timeout=3)
        print(r.status_code, r.json() if r.ok else r.text)
    except Exception as e:
        print("error:", e)

if __name__ == "__main__":
    while True:
        send_once()
        time.sleep(2)
