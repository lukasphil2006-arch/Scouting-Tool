"""Merkzettel: speichert NUR Domain, Datum und Status – keine Kontaktdaten."""
import datetime as dt
import json
import os


def load(path: str) -> dict:
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {"seen": {}}


def save(path: str, state: dict):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=1, sort_keys=True, ensure_ascii=False)


def purge(state: dict, today: dt.date, retention_days: int) -> int:
    limit = today - dt.timedelta(days=retention_days)
    old = [d for d, v in state["seen"].items() if dt.date.fromisoformat(v["first_seen"]) < limit]
    for d in old:
        del state["seen"][d]
    return len(old)


def mark(state: dict, domain: str, status: str, today: dt.date):
    state["seen"][domain] = {"first_seen": today.isoformat(), "status": status}
