import requests, time, random, datetime, json

API_URL = "https://trust-fabric-sandbox.onrender.com/v1/events"

DEVICE_ID = "TF-SIG-101"

while True:
    payload = {
        "device_id": DEVICE_ID,
        "state": random.randint(0, 1),
        "speed": round(random.uniform(10, 60), 2),
        "lat": 39.289,
        "lon": -76.612,
        "ts_utc": datetime.datetime.utcnow().isoformat() + "Z"
    }

    try:
        res = requests.post(API_URL, json=payload)
        print(f"[{datetime.datetime.now()}] Sent event → {res.status_code}")
    except Exception as e:
        print("Error:", e)

    time.sleep(5)
