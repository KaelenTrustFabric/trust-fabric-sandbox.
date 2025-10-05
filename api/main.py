# api/main.py
# Trust-Fabric Sandbox API (compact)
import os, json, time, uuid, base64, hashlib, sqlite3, statistics, datetime as dt
from typing import Optional, List
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from nacl.signing import SigningKey
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# ---------- Config ----------
DB_PATH       = os.getenv("DB_PATH", "./tf.db")
INGEST_TOKEN  = os.getenv("INGEST_TOKEN", "DEV_INGEST_TOKEN")
BLOCK_SIZE    = int(os.getenv("BLOCK_SIZE", "25"))
PRIVATE_KEY   = os.getenv("PRIVATE_KEY")  # base64 seed (32 bytes)
if not PRIVATE_KEY:  # dev-friendly auto key
    PRIVATE_KEY = base64.b64encode(SigningKey.generate()._seed).decode()

SIGNING_KEY = SigningKey(base64.b64decode(PRIVATE_KEY))

# ---------- DB ----------
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
conn.row_factory = sqlite3.Row

def init_db():
    cur = conn.cursor()
    cur.execute("""
      CREATE TABLE IF NOT EXISTS events(
        id TEXT PRIMARY KEY,
        device_id TEXT NOT NULL,
        payload TEXT NOT NULL,
        ts_utc TEXT NOT NULL,
        hash TEXT NOT NULL,
        sig TEXT NOT NULL,
        ledger_ref TEXT,
        trust_score REAL NOT NULL,
        verified INTEGER NOT NULL,
        created_at TEXT NOT NULL
      )
    """)
    cur.execute("""
      CREATE TABLE IF NOT EXISTS blocks(
        block_id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        root_hash TEXT NOT NULL,
        events_count INTEGER NOT NULL
      )
    """)
    conn.commit()
init_db()

# ---------- Models ----------
class IngestBody(BaseModel):
    device_id: str
    payload: dict
    ts_utc: str  # ISO 8601, e.g. 2025-10-05T12:00:00Z

# ---------- Helpers ----------
latencies: List[float] = []

def sha256_str(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()

def attestation_hash(device_id: str, ts_utc: str, payload: dict) -> str:
    canon = json.dumps(payload, sort_keys=True, separators=(',', ':'))
    return sha256_str(f"{device_id}|{ts_utc}|{canon}")

def sign_hex(h: str) -> str:
    sig = SIGNING_KEY.sign(bytes.fromhex(h)).signature
    return base64.b64encode(sig).decode()

def trust_score(device_id: str, ts_utc: str) -> float:
    # simple demo scoring
    try:
        t = dt.datetime.fromisoformat(ts_utc.replace("Z", "+00:00"))
        skew = abs((dt.datetime.now(dt.timezone.utc) - t).total_seconds())
    except Exception:
        skew = 9999
    score = 0.986
    if not device_id.startswith("TF-"): score -= 0.02
    if skew > 5: score -= 0.02
    return max(0.0, min(1.0, score))

def total_events() -> int:
    return conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]

def build_block_if_needed():
    total = total_events()
    if total == 0 or total % BLOCK_SIZE != 0:
        return None
    # take last BLOCK_SIZE hashes and create a pseudo-root
    rows = conn.execute(
        "SELECT hash FROM events ORDER BY created_at DESC LIMIT ?", (BLOCK_SIZE,)
    ).fetchall()
    concat = "".join([r["hash"] for r in rows])
    root = sha256_str(concat)
    now = dt.datetime.utcnow().isoformat() + "Z"
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO blocks(created_at, root_hash, events_count) VALUES(?,?,?)",
        (now, root, BLOCK_SIZE),
    )
    block_id = cur.lastrowid
    # mark those events with the ledger ref
    cur.execute("""
      WITH last AS (
        SELECT id FROM events ORDER BY created_at DESC LIMIT ?
      )
      UPDATE events SET ledger_ref=? WHERE id IN (SELECT id FROM last)
    """, (BLOCK_SIZE, f"block_{block_id}"))
    conn.commit()
    return block_id

# ---------- App ----------
app = FastAPI(title="Trust-Fabric Sandbox API", version="0.1")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

@app.middleware("http")
async def add_eval_header(request, call_next):
    resp = await call_next(request)
    if isinstance(resp, JSONResponse):
        resp.headers["X-TF-License"] = "Evaluation-Only"
    return resp

# ---------- Routes ----------
@app.get("/v1/health")
def health():
    p95 = int(statistics.quantiles(latencies, n=20)[18]) if len(latencies) >= 20 else (int(latencies[-1]) if latencies else 0)
    tot = total_events()
    ver = conn.execute("SELECT COUNT(*) FROM events WHERE verified=1").fetchone()[0] if tot else 0
    return {"status": "ok", "verified_rate": (ver / tot) * 100 if tot else 0.0, "p95_latency_ms": p95}

@app.get("/v1/events")
def list_events(limit: int = 50):
    rows = conn.execute("""
      SELECT id, device_id, payload, ts_utc, hash, sig, ledger_ref, trust_score, verified, created_at
      FROM events ORDER BY created_at DESC LIMIT ?
    """, (min(max(limit, 1), 500),)).fetchall()
    return [dict(r) for r in rows]

@app.get("/v1/blocks")
def list_blocks(limit: int = 10):
    rows = conn.execute("""
      SELECT block_id, created_at, root_hash, events_count
      FROM blocks ORDER BY block_id DESC LIMIT ?
    """, (min(max(limit, 1), 100),)).fetchall()
    return [dict(r) for r in rows]

@app.post("/v1/ingest")
def ingest(body: IngestBody, x_tf_key: Optional[str] = Header(None)):
    if x_tf_key != INGEST_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")
    start = time.perf_counter()

    h = attestation_hash(body.device_id, body.ts_utc, body.payload)
    sig = sign_hex(h)
    score = trust_score(body.device_id, body.ts_utc)

    ev_id = str(uuid.uuid4())
    now = dt.datetime.utcnow().isoformat() + "Z"
    conn.execute("""
      INSERT INTO events(id, device_id, payload, ts_utc, hash, sig, ledger_ref, trust_score, verified, created_at)
      VALUES(?,?,?,?,?,?,?,?,1,?)
    """, (ev_id, body.device_id, json.dumps(body.payload, separators=(',', ':')), body.ts_utc, h, sig, None, score, now))
    conn.commit()

    block_id = build_block_if_needed()
    latency_ms = (time.perf_counter() - start) * 1000
    latencies.append(latency_ms)

    return {
        "event_id": ev_id,
        "hash": f"sha256:{h}",
        "sig": f"ed25519:{sig}",
        "ledger_ref": f"block_{block_id}" if block_id else None,
        "trust_score": round(score, 3),
        "verified": True
    }
