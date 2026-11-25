"""Aufräumen von Name, Beschreibung, Ort und Land – rein regelbasiert.
Die KI-Prüfung (ai.py) überschreibt diese Werte, wenn sie aktiv ist."""
import re

from .net import host_only

GENERIC_NAMES = {
    "home", "homepage", "startseite", "start", "welcome", "willkommen", "deutschland", "germany", "about", "about us",
    "über uns", "index", "website", "webseite", "news", "blog", "kontakt", "contact", "impressum", "imprint", "de", "en",
}
JUNK_DESC = re.compile(r"breadcrumb|cookie|javascript|lorem ipsum|bootstrap|html5 template|wordpress|"
                       r"404|page not found|seite nicht gefunden|just another", re.I)
LEGAL_NAME = re.compile(
    r"\b([A-ZÄÖÜ0-9][\w&.+\-]*(?:\s+[A-ZÄÖÜ0-9&][\w&.+\-]*){0,4})\s+"
    r"(GmbH\s*&\s*Co\.\s*KG|gGmbH|GmbH|UG\s*\(haftungsbeschränkt\)|UG|AG|SE|KG|e\.\s?V\.)")

# Länder: Domain-Endung -> Land, und Wörter im Text -> Land
TLD_COUNTRY = {
    "at": "Österreich", "ch": "Schweiz", "be": "Belgien", "nl": "Niederlande", "fr": "Frankreich", "it": "Italien",
    "es": "Spanien", "pt": "Portugal", "pl": "Polen", "cz": "Tschechien", "dk": "Dänemark", "se": "Schweden",
    "no": "Norwegen", "fi": "Finnland", "gr": "Griechenland", "lt": "Litauen", "lv": "Lettland", "ee": "Estland",
    "ie": "Irland", "uk": "Großbritannien", "lu": "Luxemburg", "hu": "Ungarn", "ro": "Rumänien", "il": "Israel",
}
COUNTRY_WORDS = [
    ("Deutschland", r"\bdeutschland\b|\bgermany\b|\bamtsgericht\b|\bhrb\s?\d|\bust-?id(?:nr)?\.?:?\s*de"),
    ("Österreich", r"\bösterreich\b|\baustria\b|\bfirmenbuch\b"),
    ("Schweiz", r"\bschweiz\b|\bswitzerland\b|\bsuisse\b|\bche-\d{3}"),
    ("Belgien", r"\bbelgien\b|\bbelgium\b|\bbelgique\b"),
    ("Niederlande", r"\bniederlande\b|\bnetherlands\b|\bkvk\b"),
    ("Frankreich", r"\bfrankreich\b|\bfrance\b|\bsiret\b"),
    ("Großbritannien", r"\bunited kingdom\b|\bengland\b|\bcompanies house\b"),
    ("USA", r"\busa\b|\bunited states\b|\bdelaware\b"),
]
PLZ_CITY = re.compile(r"\b(?:D-)?(\d{5})\s+([A-ZÄÖÜ][a-zäöüß]+(?:-[A-ZÄÖÜ]?[a-zäöüß]+)*"
                      r"(?:\s(?:am|an der|im|ob der|bei)\s[A-ZÄÖÜ][a-zäöüß]+|\s\(?[A-ZÄÖÜ][a-zäöüß]+\)?)?)")
CITY_STOP = {"Tel", "Telefon", "Fon", "Fax", "Phone", "Germany", "Deutschland", "Kontakt", "Contact", "E", "Mail",
             "Vertreten", "Vertretungsberechtigt", "Handelsregister", "Registergericht", "Geschäftsführer", "Email",
             "Ust", "USt", "Web", "Internet", "Mobil", "Sitz", "Amtsgericht", "Inhaber", "Germa"}


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9äöü]", "", s.lower())


def pick_name(title: str, og_site: str, legal_text: str, domain: str, hint: str = "") -> str:
    stem = _norm(host_only(domain).split(".")[-2] if "." in host_only(domain) else host_only(domain))
    parts = [p.strip(" -–—|•:·") for p in re.split(r"\s[|\-–—•:·]\s|\s[|•·]\s?", title or "") if p.strip()]
    cands = []
    if og_site and _norm(og_site) not in {_norm(g) for g in GENERIC_NAMES}:
        cands.append(og_site.strip())
    cands += parts
    if hint:
        cands.append(hint)
    # 1) Kandidat, der zum Domainnamen passt (z. B. "Gruenstrom" bei gruenstrom.de)
    hits = [c for c in cands if _norm(c) and stem and (stem in _norm(c) or _norm(c) in stem)
            and len(c) <= 60 and _norm(c) not in GENERIC_NAMES]
    if hits:  # exakter Treffer zuerst, sonst der kürzeste ("Aviant" statt "About Aviant")
        return min(hits, key=lambda c: (_norm(c) != stem, len(c)))
    # 2) Firmenname aus dem Impressum, der zum Domainnamen passt
    for m in LEGAL_NAME.finditer(legal_text or ""):
        base = m.group(1).strip()
        if stem and (stem[:5] in _norm(base) or _norm(base)[:5] in stem):
            return f"{base} {m.group(2)}".strip()
    # 3) og:site_name, sonst Domainname
    if cands and og_site and _norm(og_site) not in GENERIC_NAMES and len(og_site) <= 40:
        return og_site.strip()
    return (stem or host_only(domain)).capitalize() if stem else host_only(domain)


def clean_description(desc: str) -> str:
    d = re.sub(r"\s+", " ", desc or "").strip()
    if len(d) < 25 or JUNK_DESC.search(d):
        return ""
    return d[:300]


def country_of(domain: str, legal_text: str, plz_found: bool) -> str:
    tld = host_only(domain).rsplit(".", 1)[-1].lower()
    t = (legal_text or "").lower()
    for land, rx in COUNTRY_WORDS:
        if re.search(rx, t):
            return land
    if tld == "de":
        return "Deutschland"
    if tld in TLD_COUNTRY:
        return TLD_COUNTRY[tld]
    if plz_found and re.search(r"\bgmbh\b|\bug\b|haftungsbeschränkt", t):
        return "Deutschland"
    return ""


def plz_city(*texts):
    for text in texts:
        for m in PLZ_CITY.finditer(text or ""):
            city = m.group(2)
            first = city.split()[0].split("-")[0]
            if first in CITY_STOP:
                continue
            city = " ".join(w for w in city.split() if w.strip("()") not in CITY_STOP)
            return m.group(1), city
    return "", ""


_YEARS_AGO = re.compile(r"(?:seit\s+(?:über\s+|mehr\s+als\s+)?|for\s+(?:over\s+|more\s+than\s+)?)(\d{1,3})\s+"
                        r"(?:jahren|jahrzehnten|years|decades)(?![^.]{0,40}(?:erfahrung|experience))", re.I)
_GENERATION = re.compile(r"in\s+der\s+(?:zweiten|dritten|vierten|fünften|sechsten|siebten|\d\.)\s+generation", re.I)


def age_hint(text: str, this_year: int):
    """"seit 25 Jahren" -> ungefähres Gründungsjahr; "in der dritten Generation" -> sehr alt."""
    if _GENERATION.search(text or ""):
        return this_year - 60
    m = _YEARS_AGO.search(text or "")
    if m:
        n = int(m.group(1))
        if "jahrzehnt" in m.group(0).lower() or "decade" in m.group(0).lower():
            n *= 10
        if 3 <= n <= 200:
            return this_year - n
    return None
