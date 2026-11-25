"""Kandidaten sammeln: News-Feeds (RSS/Atom) und eigene CSV-Listen."""
import csv
import datetime as dt
import json
import email.utils
import os
import re
import xml.etree.ElementTree as ET
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .net import domain_of, host_only


# Domains, die erfahrungsgemäß keine Startups sind (zusätzlich zu ignore_link_domains aus der config)
BUILTIN_IGNORE = {"stateofeuropeantech.com", "atomico.com", "sifted.eu", "tech.eu", "forbes.com", "reuters.com",
                  "bloomberg.com", "handelsblatt.com", "spiegel.de", "zeit.de", "wsj.com", "ft.com",
                  "amazon.com", "amazon.de", "microsoft.com", "wikipedia.org", "creativecommons.org", "wordpress.org",
                  "wordpress.com", "paypal.com", "whatsapp.com", "t.me", "pinterest.com", "reddit.com", "slack.com"}


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _parse_feed(xml_text: str):
    """Liefert Liste von dicts: title, link, html, date."""
    try:
        root = ET.fromstring(xml_text.encode("utf-8", errors="replace"))
    except ET.ParseError:
        return []
    items = []
    for el in root.iter():
        if _local(el.tag) not in ("item", "entry"):
            continue
        d = {"title": "", "link": "", "html": "", "date": None}
        for ch in el:
            t = _local(ch.tag)
            if t == "title":
                d["title"] = (ch.text or "").strip()
            elif t == "link":
                d["link"] = (ch.attrib.get("href") or ch.text or "").strip() or d["link"]
            elif t in ("description", "encoded", "content", "summary"):
                d["html"] += " " + (ch.text or "")
            elif t in ("pubDate", "published", "updated"):
                try:
                    d["date"] = email.utils.parsedate_to_datetime(ch.text)
                except (TypeError, ValueError):
                    try:
                        d["date"] = dt.datetime.fromisoformat((ch.text or "").replace("Z", "+00:00"))
                    except ValueError:
                        pass
        items.append(d)
    return items


def _external_links(html: str, base_url: str, ignore: set, limit: int):
    soup = BeautifulSoup(html, "html.parser")
    base = domain_of(base_url)
    found, seen = [], set()
    for a in soup.find_all("a", href=True):
        href = urljoin(base_url, a["href"])
        if not href.startswith(("http://", "https://")):
            continue
        dom = domain_of(href)
        host = dom.split(":")[0]
        if not dom or dom == base or dom in seen:
            continue
        if any(host == ig or host.endswith("." + ig) for ig in ignore):
            continue
        seen.add(dom)
        found.append(href.split("#")[0])
        if len(found) >= limit:
            break
    return found


def from_rss(feed: dict, cfg: dict, fetcher):
    out = []
    res = fetcher.get(feed["url"])
    if not res:
        print(f"  ! Feed nicht lesbar: {feed['name']}")
        return out
    ignore = set(cfg["sources"].get("ignore_link_domains", [])) | BUILTIN_IGNORE
    limit = cfg["sources"].get("links_per_article", 3)
    max_age = cfg["run"].get("max_item_age_days", 45)
    now = dt.datetime.now(dt.timezone.utc)
    for it in _parse_feed(res[0]):
        d = it["date"]
        if d is not None:
            if d.tzinfo is None:
                d = d.replace(tzinfo=dt.timezone.utc)
            if (now - d).days > max_age:
                continue
        links = _external_links(it["html"], it["link"] or feed["url"], ignore, limit)
        if not links and it["link"]:
            page = fetcher.get(it["link"])
            if page:
                links = _external_links(page[0], page[1], ignore, limit)
        for url in links:
            out.append({"url": url, "source": feed["name"], "source_url": it["link"]})
    return out


def from_page(entry, cfg: dict, fetcher):
    """Verzeichnis-/Portfolio-/Ausstellerseite: alle externen Links darauf werden Kandidaten.
    entry: URL-String oder {name: ..., url: ...}"""
    url = entry if isinstance(entry, str) else entry["url"]
    name = domain_of(url) if isinstance(entry, str) else entry.get("name", domain_of(url))
    res = fetcher.get(url)
    if not res:
        print(f"  ! Seite nicht lesbar: {url}")
        return []
    ignore = set(cfg["sources"].get("ignore_link_domains", [])) | BUILTIN_IGNORE
    limit = cfg["sources"].get("page_links_limit", 80)
    return [{"url": u, "source": name, "source_url": url} for u in _external_links(res[0], res[1], ignore, limit)]


URL_RE = re.compile(r"https?://[^\s\"'<>\\]+")


def _walk_strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _walk_strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk_strings(v)


def _records(data, list_path):
    for key in (list_path or "").split("."):
        if key:
            data = data.get(key, []) if isinstance(data, dict) else []
    return data if isinstance(data, list) else []


def from_json(entry: dict, cfg: dict, fetcher):
    """JSON-Liste (z.B. yc-oss, WordPress-REST). Pro Eintrag wird die Webseite aus `website_field`
    gelesen; fehlt das Feld, wird die erste fremde URL im Eintrag genommen.
    Optional: pages (Seitenzahl bei WordPress ?page=N), name_field."""
    name = entry.get("name", domain_of(entry["url"]))
    own = host_only(domain_of(entry["url"]))
    ignore = set(cfg["sources"].get("ignore_link_domains", [])) | BUILTIN_IGNORE
    out, pages = [], int(entry.get("pages", 1))
    for n in range(1, pages + 1):
        url = entry["url"] if pages == 1 else entry["url"] + ("&" if "?" in entry["url"] else "?") + f"page={n}"
        res = fetcher.get(url)
        if not res:
            break
        try:
            data = json.loads(res[0])
        except ValueError:
            print(f"  ! kein JSON: {url}")
            break
        recs = _records(data, entry.get("list_path"))
        if not recs:
            break
        for rec in recs:
            site = rec.get(entry["website_field"]) if entry.get("website_field") and isinstance(rec, dict) else None
            if not site:
                for s_ in _walk_strings(rec):
                    for u in URL_RE.findall(s_):
                        h = host_only(domain_of(u))
                        if h and h != own and not any(h == i or h.endswith("." + i) for i in ignore):
                            site = u
                            break
                    if site:
                        break
            if site:
                hint = rec.get(entry.get("name_field", "name"), "") if isinstance(rec, dict) else ""
                out.append({"url": site if site.startswith("http") else "https://" + site, "source": name,
                            "source_url": entry["url"], "name_hint": hint if isinstance(hint, str) else ""})
    return out


def from_sitemap(entry: dict, cfg: dict, fetcher):
    """Sitemap -> Profilseiten -> erste fremde Webseite pro Profil (z.B. Portfolio-Seiten von Investoren).
    Pro Lauf wird nur ein Ausschnitt (max_pages) gelesen; er wandert bei jedem Lauf weiter,
    so wird mit der Zeit das ganze Portfolio abgedeckt."""
    name = entry.get("name", domain_of(entry["url"]))
    res = fetcher.get(entry["url"])
    if not res:
        print(f"  ! Sitemap nicht lesbar: {entry['url']}")
        return []
    needle = entry.get("url_contains", "")
    locs = [m.strip() for m in re.findall(r"<loc>([^<]+)</loc>", res[0]) if needle in m]
    if not locs:
        return []
    per = int(entry.get("max_pages", 40))
    step = (dt.date.today().toordinal() // 14) * per
    start = step % len(locs)
    pick = (locs[start:] + locs[:start])[:per]
    ignore = set(cfg["sources"].get("ignore_link_domains", [])) | BUILTIN_IGNORE | set(entry.get("ignore", []))
    out = []
    for u in pick:
        page = fetcher.get(u)
        if not page:
            continue
        links = _external_links(page[0], page[1], ignore, 1)
        if links:
            out.append({"url": links[0], "source": name, "source_url": u})
    return out


def from_csv(path: str):
    out = []
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            url = (row.get("website") or "").strip()
            if not url:
                continue
            if not re.match(r"https?://", url):
                url = "https://" + url
            out.append({"url": url, "source": (row.get("source") or os.path.basename(path)).strip(),
                        "source_url": "", "name_hint": (row.get("name") or "").strip()})
    return out


def _tag(cands, entry):
    """Quellen mit status (z.B. 'ungeprüft') werden in Liste und Bilanz gekennzeichnet."""
    st = entry.get("status") if isinstance(entry, dict) else None
    if isinstance(entry, dict) and entry.get("streng"):
        for c in cands:
            c["strict"] = True
    if st:
        for c in cands:
            c["source"] = f"{c['source']} [{st}]"
    return cands


def collect(cfg: dict, fetcher):
    cands = []
    for feed in cfg["sources"].get("rss", []):
        print(f"Feed: {feed['name']}")
        cands += _tag(from_rss(feed, cfg, fetcher), feed)
    for entry in cfg["sources"].get("pages", []) or []:
        print(f"Seite: {entry if isinstance(entry, str) else entry.get('name', entry['url'])}")
        cands += _tag(from_page(entry, cfg, fetcher), entry)
    for entry in cfg["sources"].get("json", []) or []:
        print(f"JSON: {entry.get('name', entry['url'])}")
        cands += _tag(from_json(entry, cfg, fetcher), entry)
    for entry in cfg["sources"].get("sitemaps", []) or []:
        print(f"Sitemap: {entry.get('name', entry['url'])}")
        cands += _tag(from_sitemap(entry, cfg, fetcher), entry)
    for path in cfg["sources"].get("csv", []):
        cands += from_csv(path)
    return cands
