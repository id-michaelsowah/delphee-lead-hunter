"""
Lightweight usage tracker — persists monthly token counts.
Storage backend:
  - DB_BACKEND=firestore  → Firestore collection "usage"
  - DB_BACKEND=sql (default) → usage.json file in project root
"""
import json
import os
import logging
from datetime import datetime
from threading import Lock

logger = logging.getLogger(__name__)

_USAGE_FILE = os.path.join(os.path.dirname(__file__), "..", "usage.json")
_lock = Lock()

# Pricing per 1M tokens (USD)
_PRICES = {
    "claude_input":  3.00,   # Claude Sonnet 4.6 input
    "claude_output": 15.00,  # Claude Sonnet 4.6 output
    "gemini_input":  0.075,  # Gemini 2.5 Flash input
    "gemini_output": 0.30,   # Gemini 2.5 Flash output
}

_USE_FIRESTORE = os.environ.get("DB_BACKEND", "sql").strip().lower() == "firestore"


# ── Firestore backend ─────────────────────────────────────────────────────────

def _firestore_increment(month: str, service: str, input_tokens: int, output_tokens: int):
    from google.cloud import firestore
    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    db = firestore.Client(project=project)
    ref = db.collection("usage").document(month)
    db.run_transaction(
        lambda tx: _apply_increment(tx, ref, service, input_tokens, output_tokens)
    )


def _apply_increment(transaction, ref, service: str, input_tokens: int, output_tokens: int):
    snapshot = ref.get(transaction=transaction)
    data = snapshot.to_dict() or {} if snapshot.exists else {}
    svc = data.get(service, {})
    svc["input_tokens"]  = svc.get("input_tokens",  0) + input_tokens
    svc["output_tokens"] = svc.get("output_tokens", 0) + output_tokens
    svc["calls"]         = svc.get("calls",          0) + 1
    data[service] = svc
    transaction.set(ref, data)


def _firestore_get(month: str) -> dict:
    from google.cloud import firestore
    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    db = firestore.Client(project=project)
    doc = db.collection("usage").document(month).get()
    return doc.to_dict() or {} if doc.exists else {}


def _firestore_all_months() -> list[str]:
    from google.cloud import firestore
    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    db = firestore.Client(project=project)
    return sorted(d.id for d in db.collection("usage").list_documents())


# ── File backend ──────────────────────────────────────────────────────────────

def _file_load() -> dict:
    try:
        if os.path.exists(_USAGE_FILE):
            with open(_USAGE_FILE) as f:
                return json.load(f)
    except Exception as e:
        logger.warning("Could not read usage.json: %s", e)
    return {}


def _file_save(data: dict):
    try:
        with open(_USAGE_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.warning("Could not write usage.json: %s", e)


# ── Public API ────────────────────────────────────────────────────────────────

def _current_month() -> str:
    return datetime.utcnow().strftime("%Y-%m")


def record_gemini(input_tokens: int, output_tokens: int):
    try:
        month = _current_month()
        if _USE_FIRESTORE:
            _firestore_increment(month, "gemini", input_tokens, output_tokens)
        else:
            with _lock:
                data = _file_load()
                g = data.setdefault(month, {}).setdefault("gemini", {})
                g["input_tokens"]  = g.get("input_tokens",  0) + input_tokens
                g["output_tokens"] = g.get("output_tokens", 0) + output_tokens
                g["calls"]         = g.get("calls",          0) + 1
                _file_save(data)
    except Exception as e:
        logger.warning("Usage tracking error (gemini): %s", e)


def record_claude(input_tokens: int, output_tokens: int):
    try:
        month = _current_month()
        if _USE_FIRESTORE:
            _firestore_increment(month, "claude", input_tokens, output_tokens)
        else:
            with _lock:
                data = _file_load()
                c = data.setdefault(month, {}).setdefault("claude", {})
                c["input_tokens"]  = c.get("input_tokens",  0) + input_tokens
                c["output_tokens"] = c.get("output_tokens", 0) + output_tokens
                c["calls"]         = c.get("calls",          0) + 1
                _file_save(data)
    except Exception as e:
        logger.warning("Usage tracking error (claude): %s", e)


def get_summary(month: str | None = None) -> dict:
    month = month or _current_month()

    if _USE_FIRESTORE:
        m = _firestore_get(month)
        all_months = _firestore_all_months()
        history_data = {mo: _firestore_get(mo) for mo in all_months}
    else:
        data = _file_load()
        m = data.get(month, {})
        all_months = sorted(data.keys())
        history_data = data

    g = m.get("gemini", {})
    c = m.get("claude", {})

    g_in, g_out = g.get("input_tokens", 0), g.get("output_tokens", 0)
    c_in, c_out = c.get("input_tokens", 0), c.get("output_tokens", 0)

    gemini_cost = (g_in * _PRICES["gemini_input"] + g_out * _PRICES["gemini_output"]) / 1_000_000
    claude_cost = (c_in * _PRICES["claude_input"] + c_out * _PRICES["claude_output"]) / 1_000_000

    def _month_cost(v: dict) -> float:
        gi = v.get("gemini", {})
        ci = v.get("claude", {})
        return round((
            gi.get("input_tokens",  0) * _PRICES["gemini_input"] +
            gi.get("output_tokens", 0) * _PRICES["gemini_output"] +
            ci.get("input_tokens",  0) * _PRICES["claude_input"] +
            ci.get("output_tokens", 0) * _PRICES["claude_output"]
        ) / 1_000_000, 4)

    return {
        "month": month,
        "gemini": {
            "calls": g.get("calls", 0),
            "input_tokens": g_in,
            "output_tokens": g_out,
            "estimated_cost_usd": round(gemini_cost, 4),
        },
        "claude": {
            "calls": c.get("calls", 0),
            "input_tokens": c_in,
            "output_tokens": c_out,
            "estimated_cost_usd": round(claude_cost, 4),
        },
        "total_estimated_cost_usd": round(gemini_cost + claude_cost, 4),
        "history": [
            {"month": mo, "total_estimated_cost_usd": _month_cost(history_data.get(mo, {}))}
            for mo in all_months
        ],
    }
