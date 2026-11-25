"""Höflicher HTTP-Abruf: robots.txt beachten, Pause pro Host, Größenlimit."""
import time
import urllib.parse
import urllib.robotparser

import requests

MAX_BYTES = 2_000_000


def domain_of(url: str) -> str:
    """Host inkl. Port (falls vorhanden), ohne 'www.'."""
    try:
        netloc = urllib.parse.urlparse(url).netloc.lower()
    except ValueError:
        return ""
    return netloc[4:] if netloc.startswith("www.") else netloc


def host_only(domain: str) -> str:
    return domain.split(":")[0]


class Fetcher:
    def __init__(self, user_agent: str, delay: float = 2.0, timeout: int = 15):
        self.ua = user_agent
        self.delay = delay
        self.timeout = timeout
        self._robots = {}
        self._last = {}
        self.session = requests.Session()
        self.session.headers["User-Agent"] = user_agent

    def _robots_for(self, base: str):
        if base not in self._robots:
            rp = urllib.robotparser.RobotFileParser()
            try:
                r = self.session.get(base + "/robots.txt", timeout=self.timeout)
                rp.parse(r.text.splitlines() if r.status_code == 200 else [])
            except requests.RequestException:
                rp.parse([])
            rp.modified()  # sonst verweigert can_fetch() alles
            self._robots[base] = rp
        return self._robots[base]

    def allowed(self, url: str) -> bool:
        p = urllib.parse.urlparse(url)
        if p.scheme not in ("http", "https"):
            return False
        return self._robots_for(f"{p.scheme}://{p.netloc}").can_fetch(self.ua, url)

    def get(self, url: str):
        """Gibt (Text, finale URL) zurück oder None."""
        if not self.allowed(url):
            return None
        host = urllib.parse.urlparse(url).netloc
        wait = self.delay - (time.time() - self._last.get(host, 0))
        if wait > 0:
            time.sleep(wait)
        self._last[host] = time.time()
        try:
            r = self.session.get(url, timeout=self.timeout, stream=True)
            ctype = r.headers.get("Content-Type", "")
            if r.status_code != 200 or not any(t in ctype for t in ("html", "xml", "text")):
                return None
            buf = b""
            for chunk in r.iter_content(65536):
                buf += chunk
                if len(buf) > MAX_BYTES:
                    break
            enc = r.encoding if r.encoding and "charset" in ctype.lower() else "utf-8"
            return buf.decode(enc, errors="replace"), r.url
        except requests.RequestException:
            return None
