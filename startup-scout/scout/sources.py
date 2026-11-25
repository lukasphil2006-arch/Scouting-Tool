"""Kandidaten sammeln: News-Feeds (RSS/Atom) und eigene CSV-Listen."""
import csv
import datetime as dt
import email.utils
import os
import re
import xml.etree.ElementTree as ET
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .net import domain_of


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
    ignore = set(cfg["sources"].get("ignore_link_domains", []))
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


def collect(cfg: dict, fetcher):
    cands = []
    for feed in cfg["sources"].get("rss", []):
        print(f"Feed: {feed['name']}")
        cands += from_rss(feed, cfg, fetcher)
    for path in cfg["sources"].get("csv", []):
        cands += from_csv(path)
    return cands
