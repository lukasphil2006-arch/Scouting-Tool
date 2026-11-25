"""Einstiegspunkt:  python -m scout.main --config config.yaml --out output"""
import argparse
import datetime as dt
import os

import yaml

from . import ai, enrich, mailer, output, report, scoring, sources
from . import master as ms
from . import state as st
from .net import Fetcher, domain_of, host_only


def load_blocklist(path: str):
    if not os.path.exists(path):
        return set()
    with open(path, encoding="utf-8") as f:
        return {l.strip().lower() for l in f if l.strip() and not l.startswith("#")}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--out", default="output")
    ap.add_argument("--dry-run", action="store_true", help="kein Merkzettel-Update, kein Mailversand")
    ap.add_argument("--recheck", action="store_true",
                    help="alle Einträge der Gesamtliste mit den aktuellen Regeln (und KI) neu prüfen, keine neuen Quellen, keine Mail")
    args = ap.parse_args(argv)

    with open(args.config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    run = cfg["run"]
    today = dt.date.today()

    fetcher = Fetcher(run["user_agent"], run["request_delay_s"])
    state = st.load(run["state_file"])
    purged = st.purge(state, today, run["retention_days"])
    blocked = load_blocklist(run["blocklist_file"])
    print(f"Merkzettel: {len(state['seen'])} Einträge ({purged} wegen Löschfrist entfernt), Sperrliste: {len(blocked)}")

    master_path = run.get("master_file", "data/gesamtliste.xlsx")
    master = ms.load(master_path)
    recheck_domains = set()
    if args.recheck:
        rows = list(master["startups"].values()) + list(master["review"].values())
        candidates = [{"url": r["url"], "source": r.get("quelle") or "Gesamtliste", "name_hint": ""} for r in rows if r.get("url")]
        recheck_domains = {r["domain"] for r in rows}
        state["seen"] = {d: v for d, v in state["seen"].items() if d not in recheck_domains}
        print(f"Neu-Prüfung: {len(candidates)} Einträge aus der Gesamtliste")
        run["max_candidates"] = max(run["max_candidates"], len(candidates))
        run["max_focus"] = run["max_other"] = run["max_review"] = 10_000
    else:
        candidates = sources.collect(cfg, fetcher)

    # 1) Kandidaten sammeln und bereinigen
    todo, seen_now = [], set()
    for c in candidates:
        d = domain_of(c["url"])
        h = host_only(d)
        if not d or d in seen_now or d in state["seen"]:
            continue
        seen_now.add(d)
        if any(h == b or h.endswith("." + b) for b in blocked):
            continue
        todo.append(c)
    # reihum über die Quellen verteilen, damit eine große Quelle nicht alle anderen verdrängt
    by_src = {}
    for c in todo:
        by_src.setdefault(c["source"], []).append(c)
    stats = {k: {"neu": len(v), "geprüft": 0, "geliefert": 0} for k, v in by_src.items()}
    todo, queues = [], list(by_src.values())
    while queues and len(todo) < run["max_candidates"]:
        for q in list(queues):
            if q:
                todo.append(q.pop(0))
            if not q:
                queues.remove(q)
            if len(todo) >= run["max_candidates"]:
                break
    print(f"{len(todo)} neue Kandidaten werden geprüft")

    # 2) Anreichern und bewerten
    results = []
    for c in todo:
        info = enrich.analyze_site(fetcher, c["url"], cfg, c.get("name_hint", ""))
        if not info:
            st.mark(state, domain_of(c["url"]), "unreachable", today)
            continue
        info["source"], info["source_url"] = c["source"], c.get("source_url", "")
        info["strict"] = c.get("strict", False)
        stats[c["source"]]["geprüft"] += 1
        scoring.evaluate(info, cfg, today)
        results.append(info)
        print(f"  {info['name'][:30]:30} score={info['score']:>2} bucket={info['bucket']} {info['reject_reason']}")

    # 2b) Optional: KI prüft die vorgefilterten Kandidaten (Startup ja/nein, Name, Beschreibung, Ort)
    checker = ai.Checker(cfg)
    pending = [r for r in results if r["bucket"]]
    if checker.enabled and pending:
        print(f"KI-Prüfung für {len(pending)} vorgefilterte Kandidaten ({checker.model}) …")
        for r, verdict in zip(pending, checker.check(pending)):
            ai.apply(r, verdict, cfg, today.year)
            r["region"] = scoring.classify_region(r.get("plz", ""), cfg["regions"], r.get("country", ""))["name"]
            if verdict is not None:
                print(f"  {r['name'][:30]:30} -> {r['bucket'] or 'raus'}  {r.get('ai_note', '')[:80]}")

    focus, other, review = scoring.select(results, cfg)
    delivered = {r["domain"] for r in focus + other}
    for r in focus + other:
        stats[r["source"]]["geliefert"] += 1
    print("\nQuellen-Bilanz (neu / geprüft / geliefert):")
    for k, v in sorted(stats.items(), key=lambda kv: -kv[1]["geliefert"]):
        print(f"  {k[:40]:40} {v['neu']:>4} / {v['geprüft']:>4} / {v['geliefert']:>3}")
    if review:
        print(f"{len(review)} unsichere Einträge kommen ins Blatt 'Prüfen':")
        for r in review:
            print(f"  {r['name'][:30]:30} {r['review_notes']}")

    # 3) Gesamtliste (Backup) fortschreiben
    retention = run.get("master_retention_days", run["retention_days"])
    dropped = ms.purge(master, today, retention)
    if recheck_domains:  # was jetzt kein Startup mehr ist, fliegt aus der Gesamtliste
        keep = {r["domain"] for r in focus + other + review}
        removed = [d for d in recheck_domains if d not in keep]
        for sheet in master.values():
            for d in removed:
                sheet.pop(d, None)
        print(f"Neu-Prüfung: {len(removed)} Einträge entfernt, {len(keep)} bleiben")
    for bereich, rows in (("Fokus", focus), ("Weitere", other)):
        for r in rows:
            ms.upsert(master, "startups", ms.to_row(r, bereich, scoring.primary_category(r, cfg), today))
    for r in review:
        bereich = "Fokus" if r.get("review_of") == "focus" else "Weitere"
        ms.upsert(master, "review", ms.to_row(r, bereich, scoring.primary_category(r, cfg), today))
    print(f"Gesamtliste: {len(master['startups'])} Startups, {len(master['review'])} zum Prüfen "
          f"({dropped} wegen Löschfrist entfernt)")

    # 4) Ausgabe: interaktiver HTML-Bericht + Excel-Gesamtliste (+ optional PDF)
    meta = {"date": today.strftime("%d.%m.%Y"), "checked": len(results), "retention": retention}
    base = os.path.join(args.out, f"startup-scouting_{today.isoformat()}")
    html_path, xlsx_path = base + ".html", base + "_gesamtliste.xlsx"
    recs = report.write_html(html_path, master, meta, today.isoformat(), cfg)
    ms.save(xlsx_path, master, meta)
    attachments = [html_path, xlsx_path]
    if run.get("attach_pdf"):
        output.write_pdf(base + ".pdf", focus, other, meta)
        attachments.append(base + ".pdf")
    print(f"Bericht geschrieben: {html_path} + {xlsx_path}  (neu: Fokus {len(focus)}, Weitere {len(other)}, "
          f"Prüfen {len(review)})")

    if not args.dry_run:
        mail_ok = True
        if args.recheck:
            print("Neu-Prüfung: keine Mail. Bericht und Gesamtliste liegen im Archiv des Laufs.")
        elif focus or other or review:
            try:
                mailer.send(f"Startup-Scouting {meta['date']}: {len(focus)} neue Fokus-Treffer",
                            output.mail_text(focus, other, review, master, meta, recs), attachments)
            except Exception as exc:  # Mail fehlgeschlagen: Liste bleibt als Datei erhalten, Merkzettel nicht updaten
                mail_ok = False
                print(f"::error::Mailversand fehlgeschlagen: {exc}")
                print("Die Liste liegt trotzdem als Datei vor. Merkzettel und Gesamtliste werden nicht aktualisiert, "
                      "damit die Treffer beim nächsten Lauf erneut erscheinen.")
        if mail_ok:
            review_d = {r["domain"] for r in review}
            for r in results:
                status = "delivered" if r["domain"] in delivered else ("review" if r["domain"] in review_d else "rejected")
                st.mark(state, r["domain"], status, today)
            st.save(run["state_file"], state)
            ms.save(master_path, master, meta)


if __name__ == "__main__":
    main()
