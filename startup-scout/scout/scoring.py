"""Regelbasierte Bewertung und Filter – keine KI, nachvollziehbar und reproduzierbar."""
import re

_PATTERNS = {}

# Begriffe, die auf Investoren, Berichte oder Werbeseiten hindeuten (überschreibbar über config: exclude_markers)
DEFAULT_EXCLUDE = [
    "we invest in", "our portfolio", "portfolio companies", "portfolio-unternehmen", "venture capital firm",
    "venture capital fund", "investment firm", "we back founders", "werbeartikel", "werbegeschenk", "giveaway",
]


def _pattern(term: str):
    """Kurze Begriffe (<=5 Zeichen) müssen als ganzes Wort vorkommen ("exist" trifft nicht "existing").
    Längere Begriffe dürfen am Ende weitergehen ("nachhaltig" trifft "Nachhaltigkeit")."""
    t = term.strip().lower()
    if t not in _PATTERNS:
        end = r"(?!\w)" if len(t) <= 5 and t[-1:].isalnum() else ""
        _PATTERNS[t] = re.compile(r"(?<!\w)" + re.escape(t) + end)
    return _PATTERNS[t]


def _hits(text: str, terms):
    return [t for t in terms if _pattern(t).search(text)]


def theme_scores(text: str, themes: dict):
    t = text.lower()
    res = {}
    for name, spec in themes.items():
        strong = _hits(t, spec.get("strong", []))
        weak = _hits(t, spec.get("weak", []))
        res[name] = (2 * len(strong) + len(weak), strong + weak)
    return res


def classify_region(plz: str, regions: list):
    for r in regions:
        if not r["plz"] and not plz:
            return r
        if plz and any(plz.startswith(p) for p in r["plz"]):
            return r
    return regions[-1]


def detect_phase(text: str, phases: list) -> str:
    t = text.lower()
    for ph in phases:
        if _hits(t, ph["keywords"]):
            return ph["name"]
    return "unbekannt"


def evaluate(info: dict, cfg: dict, today):
    sc, flt = cfg["scoring"], cfg["filters"]
    text = info["text"].lower()
    th = theme_scores(text, cfg["themes"])
    focus_hit = [n for n in cfg["focus_themes"] if th[n][0] >= sc["theme_threshold"]]
    base = sum(min(th[n][0], sc["theme_cap"]) for n in focus_hit)

    info["themes"] = focus_hit
    info["hits"] = ", ".join(dict.fromkeys(h for n in focus_hit for h in th[n][1]))[:140]

    sector_counts = {s: len(_hits(text, kws)) for s, kws in cfg["sectors"].items()}
    info["sectors"] = [s for s, c in sorted(sector_counts.items(), key=lambda x: -x[1]) if c > 0][:3]

    info["phase"] = detect_phase(info["text"], cfg["phases"])
    funding = bool(_hits(text, cfg["signals"]["funding"]))
    spinoff = bool(_hits(text, cfg["signals"]["spinoff"]))
    info["funding"], info["spinoff"] = funding, spinoff

    region = classify_region(info.get("plz", ""), cfg["regions"])
    info["region"] = region["name"]

    founded = info.get("founded")
    age = today.year - founded if founded else None
    info["age"] = age

    reasons = []
    if _hits(text, cfg.get("exclude_markers", DEFAULT_EXCLUDE)):
        reasons.append("Investor/Werbeseite, kein Startup")
    if age is not None and (founded < flt["founded_from"] or age > flt["max_age_years"]):
        reasons.append("zu alt")
    if age is None and not flt["allow_unknown_founded"]:
        reasons.append("Gründungsjahr unbekannt")
    if info["phase"] == "unbekannt" and not flt["allow_unknown_phase"]:
        reasons.append("Phase unbekannt")
    if info["phase"] != "unbekannt" and info["phase"] not in flt["phases"]:
        reasons.append("Phase nicht gewünscht")
    if not region.get("include", True):
        reasons.append("Region ausgeschlossen")
    signal = (age is not None and age <= flt["max_age_years"]) or info["phase"] != "unbekannt" or funding or spinoff
    if flt["require_startup_signal"] and not signal:
        reasons.append("kein Startup-Signal")

    bonus = region["bonus"] + cfg["phase_bonus"].get(info["phase"], 0) + int(funding) + int(spinoff)
    if age is not None:
        bonus += sc["age_bonus_young"] if age <= 3 else (sc["age_bonus_ok"] if age <= 5 else 0)
    info["score"] = base + bonus

    info["bucket"] = None
    info["reject_reason"] = ", ".join(reasons)
    if reasons:
        return
    if focus_hit and info["score"] >= sc["min_score_focus"]:
        info["bucket"] = "focus"
    elif not focus_hit and flt["include_other"] and bonus >= sc["min_score_other"]:
        info["bucket"] = "other"


def select(results: list, cfg: dict):
    key = lambda r: (-r["score"], r["name"].lower())
    focus = sorted([r for r in results if r["bucket"] == "focus"], key=key)[: cfg["run"]["max_focus"]]
    other = sorted([r for r in results if r["bucket"] == "other"], key=key)[: cfg["run"]["max_other"]]
    return focus, other
