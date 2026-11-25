"""Website eines Kandidaten auswerten: Beschreibung, Gründungsjahr, Standort,
generische Kontaktadresse. Persönliche E-Mail-Adressen werden NIE gespeichert."""
import datetime as dt
import re
import warnings
from urllib.parse import urljoin

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

from .net import domain_of, host_only
from .startup_check import founded_fallback
from . import clean

LEGAL_PAGE = re.compile(r"impressum|imprint|legal[- ]?notice|kontakt|contact", re.I)
ABOUT_PAGE = re.compile(r"über[- ]?uns|ueber[- ]?uns|about|mission|unternehmen|company", re.I)
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
PLZ_RE = re.compile(r"\b(\d{5})\s+([A-ZÄÖÜ][a-zäöüßA-ZÄÖÜ\-]+(?:[ \-][A-ZÄÖÜ][a-zäöüß\-]+)?)")
FOUNDED_RES = [
    re.compile(r"gegründet\s*(?:im|in|:)?\s*(?:jahr\s*)?((?:19|20)\d{2})", re.I),
    re.compile(r"founded\s*(?:in|:)?\s*((?:19|20)\d{2})", re.I),
    re.compile(r"gegr\.?\s*((?:19|20)\d{2})", re.I),
    re.compile(r"gründungsjahr:?\s*((?:19|20)\d{2})", re.I),
]
LEGAL_FORMS = [("gGmbH", r"\bgGmbH\b"), ("UG", r"\bUG\s*\(haftungsbeschränkt\)|\bUG\b"),
               ("GmbH", r"\bGmbH\b"), ("AG", r"\bAG\b"), ("e.V.", r"\be\.\s?V\.")]


def _deobfuscate(text: str) -> str:
    return re.sub(r"\s*[\[\(]\s*(?:at|ät)\s*[\]\)]\s*", "@", text, flags=re.I)


def _clean_text(soup: BeautifulSoup) -> str:
    for t in soup(["script", "style", "noscript", "svg"]):
        t.decompose()
    return re.sub(r"\s+", " ", soup.get_text(" ")).strip()


def _subpages(soup, base_url: str, pattern, limit: int):
    host = host_only(domain_of(base_url))
    found = []
    for a in soup.find_all("a", href=True):
        label = (a.get_text(" ") or "") + " " + a["href"]
        if not pattern.search(label):
            continue
        url = urljoin(base_url, a["href"]).split("#")[0]
        if host_only(domain_of(url)) != host or url in found or url.rstrip("/") == base_url.rstrip("/"):
            continue
        found.append(url)
        if len(found) >= limit:
            break
    return found


def _generic_emails(texts, soups, site_domain, cfg):
    prefixes = [p.lower() for p in cfg["generic_email_prefixes"]]
    need_match = cfg["run"].get("require_email_domain_match", True)
    host = host_only(site_domain)
    cands = set()
    for s in soups:
        for a in s.find_all("a", href=True):
            if a["href"].lower().startswith("mailto:"):
                cands.update(EMAIL_RE.findall(a["href"][7:].split("?")[0]))
    for t in texts:
        cands.update(EMAIL_RE.findall(_deobfuscate(t)))
    keep = []
    for mail in cands:
        local, _, dom = mail.lower().partition("@")
        if local not in prefixes:
            continue  # persönliche Adresse -> wird verworfen, nicht gespeichert
        if need_match and not (dom == host or dom.endswith("." + host) or host.endswith("." + dom)):
            continue
        keep.append(mail.lower())
    keep.sort(key=lambda m: prefixes.index(m.split("@")[0]))
    return keep


def analyze_site(fetcher, url: str, cfg: dict, name_hint: str = ""):
    home = fetcher.get(url)
    if not home:
        return None
    html, final_url = home
    soup = BeautifulSoup(html, "html.parser")
    domain = domain_of(final_url)

    title = (soup.title.string or "").strip() if soup.title and soup.title.string else ""
    og = soup.find("meta", property="og:site_name")
    og_site = og["content"].strip() if og and og.get("content") else ""
    desc_tag = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", property="og:description")
    description = clean.clean_description(desc_tag.get("content", "") if desc_tag else "")
    headings = " ".join(h.get_text(" ", strip=True) for h in soup.find_all(["h1", "h2"])[:8])

    legal_urls = _subpages(soup, final_url, LEGAL_PAGE, 2)
    about_urls = _subpages(soup, final_url, ABOUT_PAGE, 1)
    pages_soups, legal_text = [soup], ""
    legal_page_url = ""
    extra_text = ""
    for u in legal_urls:
        r = fetcher.get(u)
        if r:
            s = BeautifulSoup(r[0], "html.parser")
            pages_soups.append(s)
            legal_text += " " + _clean_text(BeautifulSoup(r[0], "html.parser"))
            if not legal_page_url and re.search(r"impressum|imprint|legal", u, re.I):
                legal_page_url = u
    if not legal_page_url and legal_urls:
        legal_page_url = legal_urls[0]
    for u in about_urls:
        r = fetcher.get(u)
        if r:
            extra_text += " " + _clean_text(BeautifulSoup(r[0], "html.parser"))

    # E-Mails vor dem Bereinigen aus allen Seiten (mailto-Links brauchen das Soup)
    body_text = _clean_text(BeautifulSoup(html, "html.parser"))
    emails = _generic_emails([body_text, legal_text], pages_soups, domain, cfg)

    all_text = " ".join([title, description, headings, body_text[:15000], extra_text[:8000]])
    scan = " ".join([body_text, legal_text, extra_text])

    founded = None
    for rx in FOUNDED_RES:
        m = rx.search(scan)
        if m:
            y = int(m.group(1))
            if 1950 <= y <= dt.date.today().year:
                founded = y
                break
    if founded is None:
        y = founded_fallback(scan)
        if y and 1900 <= y <= dt.date.today().year:
            founded = y

    if founded is None:
        founded = clean.age_hint(scan, dt.date.today().year)

    plz, city = clean.plz_city(legal_text, body_text)
    country = clean.country_of(domain, legal_text or body_text[-3000:], bool(plz))
    if country and country != "Deutschland":
        plz = ""  # ausländische Postleitzahlen nicht als deutsche Region werten
    name = clean.pick_name(title, og_site, legal_text, domain, name_hint)

    legal_form = ""
    for label, rx in LEGAL_FORMS:
        if re.search(rx, scan):
            legal_form = label
            break

    return {
        "name": name[:80], "url": final_url, "domain": domain, "description": description,
        "about_text": (" ".join([description, headings, body_text[:2500], extra_text[:2000]]))[:5000],
        "text": all_text, "legal_text": legal_text[:8000], "emails": emails, "legal_page": legal_page_url or final_url,
        "founded": founded, "plz": plz, "city": city, "country": country, "legal_form": legal_form,
    }
