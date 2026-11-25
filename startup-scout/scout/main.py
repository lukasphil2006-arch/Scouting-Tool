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
    todo = todo[: run["max_candidates"]]
    print(f"{len(todo)} neue Kandidaten werden geprüft")

    # 2) Anreichern und bewerten
    results = []
    for c in todo:
        info = enrich.analyze_site(fetcher, c["url"], cfg, c.get("name_hint", ""))
        if not info:
            st.mark(state, domain_of(c["url"]), "unreachable", today)
            continue
        info["source"], info["source_url"] = c["source"], c.get("source_url", "")
        scoring.evaluate(info, cfg, today)
        results.append(info)
        print(f"  {info['name'][:30]:30} score={info['score']:>2} bucket={info['bucket']} {info['reject_reason']}")

    focus, other = scoring.select(results, cfg)
    delivered = {r["domain"] for r in focus + other}

    # 3) Ausgabe
    meta = {"date": today.strftime("%d.%m.%Y"), "checked": len(results), "retention": run["retention_days"]}
    path = os.path.join(args.out, f"startup-scouting_{today.isoformat()}.xlsx")
    output.write_xlsx(path, focus, other, meta)
    print(f"Liste geschrieben: {path}  (Fokus: {len(focus)}, Weitere: {len(other)})")

    if not args.dry_run:
        mail_ok = True
        if focus or other:
            try:
                mailer.send(f"Startup-Scouting {meta['date']}: {len(focus)} Fokus-Treffer",
                            output.mail_text(focus, other, meta), path)
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
