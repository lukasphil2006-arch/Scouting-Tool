"""Ist das wirklich ein Startup? Regelbasierte Prüfung gegen Institute, Hochschulen, Behörden,
Banken, Förderer, Verbände, Medien und Konzerne.

Ergebnis:
  hard  -> Grund, warum der Eintrag sicher KEIN Startup ist (fliegt raus)
  soft  -> Liste von Hinweisen, die einen Blick wert sind (Eintrag landet in "Prüfen" statt in der Liste)
Alle Listen stehen in config.yaml unter `startup_check` und können ohne Code ergänzt werden.
"""
import re

from .net import host_only


def _labels(host: str):
    return host.split(".")


def domain_reason(domain: str, sc: dict) -> str:
    host = host_only(domain).lower()
    if not host:
        return ""
    for d in sc.get("exclude_domains", []):
        d = d.lower().strip()
        if host == d or host.endswith("." + d):
            return f"bekannte Nicht-Startup-Domain ({d})"
    for suf in sc.get("exclude_domain_suffixes", []):
        if host.endswith(suf.lower()):
            return f"öffentliche Einrichtung ({suf})"
    for part in sc.get("exclude_domain_contains", []):
        if part.lower() in host:
            return f"Institution/Bank/Förderer ({part})"
    for pre in sc.get("exclude_domain_starts", []):
        if any(lbl.startswith(pre.lower()) for lbl in _labels(host)):
            return f"Hochschule/Institution ({pre}…)"
    return ""


def _find(text: str, terms):
    return [t for t in terms if t.lower() in text]


def check(info: dict, sc: dict):
    """Gibt (hard_reason, soft_reasons) zurück."""
    hard = domain_reason(info.get("domain", ""), sc)
    if hard:
        return hard, []

    legal = (info.get("legal_text") or "").lower()
    hits = _find(legal, sc.get("legal_operator_markers", []))
    if hits:
        return f"Betreiber ist Institution/Behörde ({hits[0]})", []

    text = (info.get("text") or "").lower()
    soft = []
    org = _find(text, sc.get("support_org_markers", []))
    if org:
        soft.append(f"wirkt wie Förderer/Netzwerk/Event („{org[0]}“)")
    other = _find(text + " " + legal, sc.get("no_startup_markers", []))
    if other:
        soft.append(f"wirkt wie Dienstleister/Medium/Bildungsträger („{other[0]}“)")
    big = _find(text + " " + legal, sc.get("large_company_markers", []))
    if big:
        soft.append(f"wirkt wie etabliertes Unternehmen („{big[0]}“)")
    lf = info.get("legal_form", "")
    if lf in sc.get("review_legal_forms", []):
        soft.append(f"Rechtsform {lf}")
    if lf == "AG" and not info.get("founded"):
        soft.append("AG ohne bekanntes Gründungsjahr")
    return "", soft


_YEAR = re.compile(r"(?:seit|since|est\.?|established)\s*(?:dem\s+jahr\s*|in\s*)?((?:19|20)\d{2})\b", re.I)


def founded_fallback(text: str):
    """"seit 1983" / "since 1983" als Ersatz, wenn kein "gegründet" gefunden wurde."""
    m = _YEAR.search(text)
    return int(m.group(1)) if m else None
