"""Einstiegspunkt:  python -m scout.main --config config.yaml --out output"""
import argparse
import datetime as dt
import os

import yaml

from . import enrich, mailer, output, scoring, sources
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

    # 1) Kandidaten sammeln und bereinigen
    todo, seen_now = [], set()
    for c in sources.collect(cfg, fetcher):
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
        stats[c["source"]]["geprüft"] += 1
        scoring.evaluate(info, cfg, today)
        results.append(info)
        print(f"  {info['name'][:30]:30} score={info['score']:>2} bucket={info['bucket']} {info['reject_reason']}")

    focus, other = scoring.select(results, cfg)
    delivered = {r["domain"] for r in focus + other}
    for r in focus + other:
        stats[r["source"]]["geliefert"] += 1
    print("\nQuellen-Bilanz (neu / geprüft / geliefert):")
    for k, v in sorted(stats.items(), key=lambda kv: -kv[1]["geliefert"]):
        print(f"  {k[:40]:40} {v['neu']:>4} / {v['geprüft']:>4} / {v['geliefert']:>3}")

    # 3) Ausgabe
    meta = {"date": today.strftime("%d.%m.%Y"), "checked": len(results), "retention": run["retention_days"]}
    base = os.path.join(args.out, f"startup-scouting_{today.isoformat()}")
    xlsx_path, pdf_path = base + ".xlsx", base + ".pdf"
    output.write_xlsx(xlsx_path, focus, other, meta)
    output.write_pdf(pdf_path, focus, other, meta)
    print(f"Liste geschrieben: {pdf_path} + {xlsx_path}  (Fokus: {len(focus)}, Weitere: {len(other)})")

    if not args.dry_run:
        mail_ok = True
        if focus or other:
            try:
                mailer.send(f"Startup-Scouting {meta['date']}: {len(focus)} Fokus-Treffer",
                            output.mail_text(focus, other, meta), [pdf_path, xlsx_path])
            except Exception as exc:  # Mail fehlgeschlagen: Liste bleibt als Datei erhalten, Merkzettel nicht updaten
                mail_ok = False
                print(f"::error::Mailversand fehlgeschlagen: {exc}")
                print("Die Liste liegt trotzdem als Datei vor. Merkzettel wird nicht aktualisiert, "
                      "damit die Treffer beim nächsten Lauf erneut erscheinen.")
        if mail_ok:
            for r in results:
                st.mark(state, r["domain"], "delivered" if r["domain"] in delivered else "rejected", today)
            st.save(run["state_file"], state)


if __name__ == "__main__":
    main()
