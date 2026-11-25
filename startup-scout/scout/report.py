"""Interaktiver HTML-Bericht: eine einzige Datei, läuft offline in jedem Browser.
Zeigt alle Startups aus der Gesamtliste (Fokus + Weitere), neue Treffer dieses Laufs sind markiert."""
import html
import json
import os
from pathlib import Path

from .master import rows_sorted
from .scoring import region_path

TEMPLATE = Path(__file__).with_name("report_template.html")
FIELDS = ("kategorie", "name", "url", "email", "impressum", "themen", "sektor", "ort", "region", "gegruendet",
          "phase", "rechtsform", "score", "beschreibung", "quelle", "erstmals", "land", "warum", "ki")
LEGACY_REGION = {"Deutschland (übrige)": "Deutschland"}


def fit(r: dict, cfg: dict, today_year: int):
    """Passung fürs Startup Village: (Punkte, Gründe, passendes Programm)."""
    e = cfg.get("empfehlungen", {})
    p = e.get("punkte", {})
    pts, why = 0, []

    def add(n, label):
        nonlocal pts
        if n:
            pts += n
            why.append(label)

    add(p.get("region", {}).get(r.get("region"), 0), r.get("region"))
    add(p.get("phase", {}).get(r.get("phase"), 0), r.get("phase"))
    cats = dict.fromkeys([r.get("kategorie")] + [t.strip() for t in str(r.get("themen") or "").split(",")])
    for c in cats:
        add(p.get("kategorie", {}).get(c, 0), c)
    for sec in [x.strip() for x in str(r.get("sektor") or "").split(",") if x.strip()]:
        add(p.get("sektor", {}).get(sec, 0), sec)
    try:
        if today_year - int(r.get("gegruendet")) <= 3:
            add(p.get("junges_startup", 0), f'gegründet {r.get("gegruendet")}')
    except (TypeError, ValueError):
        pass
    if r.get("email"):
        pts += p.get("email_vorhanden", 0)
    return pts, why, e.get("programm", {}).get(r.get("phase"), "")


def _allowed(d: dict, cfg: dict) -> bool:
    e = cfg.get("empfehlungen", {})
    p = e.get("pflicht", {})
    if e.get("ohne_kontaktstatus", True) and d.get("kontaktstatus"):
        return False
    if p.get("email") and not d.get("email"):
        return False
    if p.get("standort_deutschland") and "Deutschland" not in d.get("regionen", []):
        return False
    if p.get("gruendung_oder_phase") and not d.get("gegruendet") and d.get("phase") in ("", "unbekannt"):
        return False
    if p.get("ki_bestaetigt") and d.get("ki") and not str(d["ki"]).startswith("Startup"):
        return False
    return True


def recommendations(rows: list, cfg: dict):
    e = cfg.get("empfehlungen", {})
    cand = [d for d in rows if d["fit"] > 0 and _allowed(d, cfg)]
    cand.sort(key=lambda d: ((d["neu"] if e.get("neue_zuerst", True) else 0), d["fit"], +(d.get("score") or 0)), reverse=True)
    return [d["domain"] for d in cand[: e.get("anzahl", 10)]]


def build_rows(master_data: dict, cfg: dict, today_iso: str):
    year = int(today_iso[:4])
    rows = []
    for r in rows_sorted(master_data["startups"].values()):
        d = {f: ("" if r.get(f) is None else r.get(f)) for f in FIELDS}
        d["domain"], d["kontaktstatus"] = r.get("domain", ""), r.get("kontaktstatus") or ""
        d["neu"] = str(r.get("erstmals")) == today_iso
        d["region"] = LEGACY_REGION.get(d["region"], d["region"]) or "Unbekannt"
        d["regionen"] = region_path(d["region"], cfg["regions"])
        d["fit"], d["fit_gruende"], d["programm"] = fit(d, cfg, year)
        rows.append(d)
    recs = recommendations(rows, cfg)
    for d in rows:
        d["empfohlen"] = recs.index(d["domain"]) + 1 if d["domain"] in recs else 0
    return rows


def region_tree(regions: list):
    """Regionen als Baum in Anzeige-Reihenfolge: Deutschland > NRW > Aachen, dann Ausland, Unbekannt."""
    kids = {}
    for r in regions:
        kids.setdefault(r.get("teil_von"), []).append(r["name"])
    out = []

    def walk(name, depth):
        out.append({"name": name, "depth": depth})
        for k in kids.get(name, []):
            walk(k, depth + 1)
    for top in kids.get(None, []):
        walk(top, 0)
    return out


def write_html(path: str, master_data: dict, meta: dict, today_iso: str, cfg: dict):
    rows = build_rows(master_data, cfg, today_iso)
    data = json.dumps(rows, ensure_ascii=False, default=str).replace("</", "<\\/")
    page = (TEMPLATE.read_text(encoding="utf-8")
            .replace("{{TITLE}}", "Startup-Scouting")
            .replace("{{RUN_DATE}}", html.escape(meta["date"]))
            .replace("{{RETENTION}}", str(meta["retention"]))
            .replace("{{KI}}", html.escape(meta.get("ki", "")))
            .replace("{{REGIONS}}", json.dumps(region_tree(cfg["regions"]), ensure_ascii=False))
            .replace("{{PHASES}}", json.dumps([p["name"] for p in reversed(cfg["phases"])] + ["unbekannt"], ensure_ascii=False))
            .replace("{{DATA}}", data))
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    Path(path).write_text(page, encoding="utf-8")
    return sorted([d for d in rows if d["empfohlen"]], key=lambda d: d["empfohlen"])
