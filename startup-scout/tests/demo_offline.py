"""Offline-Demo: Fake-Startups und ein Fake-Feed laufen lokal, der komplette Ablauf wird getestet.
Start:  python tests/demo_offline.py"""
import functools
import http.server
import os
import shutil
import sys
import threading

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO = os.path.join(ROOT, ".demo")
sys.path.insert(0, ROOT)

SITES = {
    8101: ("Gruenstrom Aachen", """<html><head><title>Gruenstrom Aachen | Solarstrom und Wasserstoff</title>
<meta name="description" content="Wir entwickeln Wasserstoff-Speicher und Photovoltaik-Lösungen für die Energiewende."></head>
<body><h1>Klimaneutrale Energie für Gewerbe</h1><p>Gegründet 2022 als Ausgründung der RWTH. EXIST-Gründungsstipendium, Seed-Runde 2024.
Energiespeicher, erneuerbare Energien, Dekarbonisierung.</p><a href="/impressum.html">Impressum</a></body></html>""",
     "<html><body>Gruenstrom Aachen GmbH, Jülicher Str. 1, 52062 Aachen. Kontakt: info@gruenstrom-demo.example, "
     "Geschäftsführerin Anna Beispiel (anna.beispiel@gruenstrom-demo.example)</body></html>"),
    8102: ("Quantenwerk", """<html><head><title>Quantenwerk - Photonik Startup</title>
<meta name="description" content="Deep-Tech Sensorik auf Basis von Photonik und Quantentechnologie."></head>
<body><h1>Quantum Sensorik</h1><p>Founded in 2021. Pre-Seed, Prototyp verfügbar. Spin-off der Universität.</p>
<a href="/imprint.html">Imprint</a></body></html>""",
     "<html><body>Quantenwerk UG (haftungsbeschränkt), Torstr. 5, 10115 Berlin. hello [at] quantenwerk-demo.example</body></html>"),
    8103: ("Kaffeebox", """<html><head><title>Kaffeebox - Kaffee im Abo</title>
<meta name="description" content="Kaffee-Abo für Büros."></head><body><h1>Kaffee im Abo</h1>
<p>Gegründet 2023. Seed-Finanzierung durch Business Angel. Software-Plattform für Büro-Logistik.</p><a href="/impressum.html">Impressum</a></body></html>""",
     "<html><body>Kaffeebox GmbH, Hohenzollernring 3, 50667 Köln. office@kaffeebox-demo.example</body></html>"),
    8104: ("AltBau", """<html><head><title>AltBau AG - Bauunternehmen</title>
<meta name="description" content="Bauunternehmen, nachhaltig bauen."></head><body><h1>Seit Jahrzehnten</h1>
<p>Gegründet 1987. Nachhaltig, Recycling.</p><a href="/impressum.html">Impressum</a></body></html>""",
     "<html><body>AltBau AG, Hauptstr. 9, 80331 München. max.mustermann@altbau-demo.example</body></html>"),
    8105: ("SocialLift", """<html><head><title>SocialLift - Impact Startup</title>
<meta name="description" content="Social Entrepreneurship für Teilhabe und Inklusion, B Corp zertifiziert."></head>
<body><h1>Social Impact</h1><p>Gegründet 2020. Gemeinwohl, Sustainable Development Goals. Pre-Seed.</p>
<a href="/impressum.html">Impressum</a></body></html>""",
     "<html><body>SocialLift gGmbH, Marienplatz 1, 80331 München. Kontakt: jonas.k@sociallift-demo.example, info@sociallift-demo.example</body></html>"),
    8106: ("Institut", """<html><head><title>Institut für Solare Systeme</title>
<meta name="description" content="Forschung zu Photovoltaik und Wasserstoff."></head><body><h1>Spin-offs und Forschung</h1>
<p>Gegründet 2019. Ausgründung, Photovoltaik, erneuerbare Energien, Wasserstoff, Pre-Seed.</p><a href="/impressum.html">Impressum</a></body></html>""",
     "<html><body>Fraunhofer-Gesellschaft zur Förderung der angewandten Forschung e.V., Hansastr. 27c, 80686 München. info@institut-demo.example</body></html>"),
    8107: ("Netzwerk", """<html><head><title>Greentech Hub Rheinland</title>
<meta name="description" content="Wir unterstützen Startups aus Greentech und Cleantech."></head><body><h1>Unsere Startups</h1>
<p>Gegründet 2021. Accelerator-Programm für Klimaschutz, Energiewende, Kreislaufwirtschaft. Seed-Runde.</p><a href="/impressum.html">Impressum</a></body></html>""",
     "<html><body>Greentech Hub GmbH, Domstr. 1, 50667 Köln. kontakt@hub-demo.example</body></html>"),
}

FEED = """<?xml version="1.0"?><rss version="2.0"><channel><title>Demo</title>
<item><title>Aachener Startup sammelt Geld ein</title><link>http://localhost:8100/a1.html</link>
<pubDate>{d}</pubDate><description>&lt;p&gt;Gruenstrom: &lt;a href="http://localhost:8101/"&gt;Website&lt;/a&gt; und
&lt;a href="https://www.linkedin.com/company/x"&gt;LinkedIn&lt;/a&gt;&lt;/p&gt;</description></item>
<item><title>Berlin: Quantenwerk</title><link>http://localhost:8100/a2.html</link><pubDate>{d}</pubDate><description>kurz</description></item>
<item><title>Kaffee im Abo</title><link>http://localhost:8100/a3.html</link><pubDate>{d}</pubDate><description>&lt;a href="http://localhost:8103/"&gt;Kaffeebox&lt;/a&gt;</description></item>
<item><title>Uralt-Artikel</title><link>http://localhost:8100/a4.html</link><pubDate>Mon, 01 Jan 2024 10:00:00 +0000</pubDate><description>&lt;a href="http://localhost:8104/"&gt;AltBau&lt;/a&gt;</description></item>
</channel></rss>"""


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def serve(port, directory):
    h = functools.partial(Quiet, directory=directory)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def build():
    import email.utils
    import datetime as dt
    shutil.rmtree(DEMO, ignore_errors=True)
    os.makedirs(DEMO)
    for port, (_, home, legal) in SITES.items():
        d = os.path.join(DEMO, f"s{port}")
        os.makedirs(d)
        open(os.path.join(d, "index.html"), "w", encoding="utf-8").write(home)
        for n in ("impressum.html", "imprint.html"):
            open(os.path.join(d, n), "w", encoding="utf-8").write(legal)
    feed = os.path.join(DEMO, "feed")
    os.makedirs(feed)
    now = email.utils.format_datetime(dt.datetime.now(dt.timezone.utc))
    open(os.path.join(feed, "feed.xml"), "w", encoding="utf-8").write(FEED.format(d=now))
    open(os.path.join(feed, "a2.html"), "w", encoding="utf-8").write(
        '<html><body><p>Mehr:</p><a href="http://localhost:8102/">Quantenwerk</a></body></html>')
    open(os.path.join(feed, "directory.html"), "w", encoding="utf-8").write(
        '<html><body><a href="http://localhost:8105/">SocialLift</a> <a href="http://localhost:8101/">Gruenstrom</a>'
        ' <a href="http://localhost:8106/">Institut</a> <a href="http://localhost:8107/">Hub</a>'
        ' <a href="https://www.linkedin.com/x">LinkedIn</a></body></html>')
    open(os.path.join(feed, "list.json"), "w", encoding="utf-8").write(
        '{"items":[{"name":"Quantenwerk","website":"http://localhost:8102/"},{"name":"X","other":{"u":"http://localhost:8103/"}}]}')
    open(os.path.join(feed, "sitemap.xml"), "w", encoding="utf-8").write(
        "<urlset><url><loc>http://localhost:8100/portfolio/p1.html</loc></url><url><loc>http://localhost:8100/blog/x.html</loc></url></urlset>")
    os.makedirs(os.path.join(feed, "portfolio"))
    open(os.path.join(feed, "portfolio", "p1.html"), "w", encoding="utf-8").write(
        '<html><body><a href="http://localhost:8105/">Unternehmenswebsite</a></body></html>')
    with open(os.path.join(DEMO, "extra.csv"), "w", encoding="utf-8") as f:
        f.write("name,website,source,note\nSocialLift,http://localhost:8105/,Förderliste,\nAltBau,http://localhost:8104/,Förderliste,\n")


def main():
    build()
    servers = [serve(8100, os.path.join(DEMO, "feed"))] + [serve(p, os.path.join(DEMO, f"s{p}")) for p in SITES]
    cfg = yaml.safe_load(open(os.path.join(ROOT, "config.yaml"), encoding="utf-8"))
    cfg["run"].update({"request_delay_s": 0, "state_file": os.path.join(DEMO, "state.json"),
                       "blocklist_file": os.path.join(DEMO, "blocklist.txt"), "require_email_domain_match": False,
                       "master_file": os.path.join(DEMO, "gesamtliste.xlsx"), "page_links_limit": 80})
    cfg["sources"]["rss"] = [{"name": "Demo-Feed", "url": "http://localhost:8100/feed.xml"}]
    cfg["sources"]["pages"] = [{"name": "Demo-Verzeichnis", "url": "http://localhost:8100/directory.html"}]
    cfg["sources"]["json"] = [{"name": "Demo-JSON", "url": "http://localhost:8100/list.json", "list_path": "items", "website_field": "website"}]
    cfg["sources"]["sitemaps"] = [{"name": "Demo-Portfolio", "url": "http://localhost:8100/sitemap.xml", "url_contains": "/portfolio/", "max_pages": 5}]
    cfg["sources"]["csv"] = [os.path.join(DEMO, "extra.csv")]
    cfg_path = os.path.join(DEMO, "config.yaml")
    yaml.safe_dump(cfg, open(cfg_path, "w", encoding="utf-8"), allow_unicode=True)

    from scout.main import main as run
    print("=== Lauf 1 ===")
    run(["--config", cfg_path, "--out", os.path.join(DEMO, "out")])
    print("\n=== Lauf 2 (nichts Neues erwartet) ===")
    run(["--config", cfg_path, "--out", os.path.join(DEMO, "out2")])
    for s in servers:
        s.shutdown()
    check(os.path.join(DEMO, "gesamtliste.xlsx"))


def check(master_path):
    """Prüft das Ergebnis: Institut raus, Netzwerk in "Prüfen", echte Startups in der Liste."""
    from scout import master as ms
    from scout.startup_check import domain_reason
    data = ms.load(master_path)
    names = {r["name"] for r in data["startups"].values()}
    review = {r["name"] for r in data["review"].values()}
    print("\nGesamtliste:", sorted(names), "| Prüfen:", sorted(review))
    assert {"Gruenstrom Aachen", "Quantenwerk", "SocialLift"} <= names, names
    assert not any("Institut" in n for n in names | review), "Institut hätte rausfliegen müssen"
    assert any("Hub" in n for n in review), "Netzwerk hätte in 'Prüfen' landen müssen"
    assert "AltBau AG" not in names
    sc = yaml.safe_load(open(os.path.join(ROOT, "config.yaml"), encoding="utf-8"))["startup_check"]
    for d in ["ise.fraunhofer.de", "kit.edu", "bmftr.bund.de", "sparkasse-aachen.de", "uni-koeln.de", "efre.nrw"]:
        assert domain_reason(d, sc), d
    for d in ["sunfire.de", "greenventory.de", "existence-startup.de", "naion.tech"]:
        assert not domain_reason(d, sc), d
    print("Alle Prüfungen bestanden.")


if __name__ == "__main__":
    main()
