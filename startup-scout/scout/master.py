"""Gesamtliste (Excel) als Backup: sammelt alle gelieferten Startups über die Läufe hinweg.

- Ein Eintrag pro Domain. Wird ein Startup erneut gefunden, wird er aktualisiert, "Erstmals gefunden" bleibt.
- Spalten "Notiz" und "Kontaktstatus" sind für euch und werden nie überschrieben.
- Einträge älter als die Löschfrist werden entfernt (Datenminimierung).
- Blatt "Startups": Fokus + Weitere. Blatt "Prüfen": unsichere Fälle mit Prüfhinweis. Blatt "Info".
"""
import datetime as dt
import os

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

# (Spaltenüberschrift, Feldname, Breite)
COLUMNS = [
    ("Bereich", "bereich", 10), ("Kategorie", "kategorie", 12), ("Name", "name", 28), ("Website", "url", 32),
    ("E-Mail (generisch)", "email", 30), ("Impressum", "impressum", 14), ("Themen", "themen", 22),
    ("Sektor", "sektor", 26), ("Ort", "ort", 16), ("PLZ", "plz", 8), ("Region", "region", 18),
    ("Gegründet", "gegruendet", 10), ("Phase", "phase", 18), ("Rechtsform", "rechtsform", 11),
    ("Score", "score", 7), ("Kurzbeschreibung", "beschreibung", 60), ("Quelle", "quelle", 20),
    ("Prüfhinweis", "pruefhinweis", 40), ("Erstmals gefunden", "erstmals", 14), ("Zuletzt gesehen", "zuletzt", 14),
    ("Kontaktstatus", "kontaktstatus", 16), ("Notiz", "notiz", 30), ("Domain", "domain", 24),
]
USER_FIELDS = ("kontaktstatus", "notiz")
SHEETS = {"startups": "Startups", "review": "Prüfen"}


def _empty():
    return {"startups": {}, "review": {}}


def load(path: str) -> dict:
    data = _empty()
    if not os.path.exists(path):
        return data
    wb = load_workbook(path)
    by_head = {h: f for h, f, _ in COLUMNS}
    for key, title in SHEETS.items():
        if title not in wb.sheetnames:
            continue
        ws = wb[title]
        rows = ws.iter_rows(values_only=True)
        header = next(rows, None) or []
        fields = [by_head.get(h) for h in header]
        for row in rows:
            rec = {f: v for f, v in zip(fields, row) if f}
            if rec.get("domain"):
                data[key][rec["domain"]] = rec
    return data


def to_row(r: dict, bereich: str, kategorie: str, today: dt.date) -> dict:
    return {
        "bereich": bereich, "kategorie": kategorie, "name": r["name"], "url": r["url"],
        "email": r["emails"][0] if r["emails"] else "", "impressum": r.get("legal_page", ""),
        "themen": ", ".join(t.capitalize() for t in r["themes"]), "sektor": ", ".join(r["sectors"]),
        "ort": r.get("city", ""), "plz": r.get("plz", ""), "region": r.get("region", ""),
        "gegruendet": r.get("founded") or "", "phase": r.get("phase", ""), "rechtsform": r.get("legal_form", ""),
        "score": r.get("score", ""), "beschreibung": r.get("description", ""), "quelle": r.get("source", ""),
        "pruefhinweis": r.get("review_notes", ""), "erstmals": today.isoformat(), "zuletzt": today.isoformat(),
        "domain": r["domain"],
    }


def upsert(data: dict, sheet: str, row: dict):
    """Neuen Eintrag anlegen oder bestehenden aktualisieren (Notiz/Kontaktstatus/Erstmals bleiben)."""
    for other in SHEETS:
        if other != sheet and row["domain"] in data[other]:
            old = data[other].pop(row["domain"])
            for f in USER_FIELDS + ("erstmals",):
                row[f] = old.get(f) or row.get(f)
    old = data[sheet].get(row["domain"])
    if old:
        for f in USER_FIELDS + ("erstmals",):
            row[f] = old.get(f) or row.get(f)
    data[sheet][row["domain"]] = row


def purge(data: dict, today: dt.date, retention_days: int) -> int:
    limit = (today - dt.timedelta(days=retention_days)).isoformat()
    n = 0
    for sheet in data.values():
        for d in [d for d, r in sheet.items() if str(r.get("zuletzt") or r.get("erstmals") or "") < limit]:
            del sheet[d]
            n += 1
    return n


def rows_sorted(rows):
    return sorted(rows, key=lambda r: (str(r.get("erstmals") or ""), r.get("score") or 0), reverse=True)


def save(path: str, data: dict, meta: dict):
    wb = Workbook()
    wb.remove(wb.active)
    for key, title in SHEETS.items():
        ws = wb.create_sheet(title)
        ws.append([h for h, _, _ in COLUMNS])
        for i, (_, _, w) in enumerate(COLUMNS, 1):
            ws.column_dimensions[get_column_letter(i)].width = w
            c = ws.cell(row=1, column=i)
            c.font = Font(bold=True, color="FFFFFF")
            c.fill = PatternFill("solid", fgColor="2F6F4F" if key == "startups" else "B7791F")
        for r in rows_sorted(data[key].values()):
            ws.append([r.get(f, "") for _, f, _ in COLUMNS])
        link_cols = [i for i, (_, f, _) in enumerate(COLUMNS) if f in ("url", "impressum")]
        for row in ws.iter_rows(min_row=2):
            for c in row:
                c.alignment = Alignment(vertical="top", wrap_text=COLUMNS[c.column - 1][1] in ("beschreibung", "pruefhinweis"))
            for i in link_cols:
                c = row[i]
                if isinstance(c.value, str) and c.value.startswith("http"):
                    c.hyperlink, c.font = c.value, Font(color="0563C1", underline="single")
        ws.freeze_panes = "D2"
        ws.auto_filter.ref = ws.dimensions

    info = wb.create_sheet("Info")
    for line in [
        ("Startup-Scouting – Gesamtliste", f'Stand {meta["date"]}'),
        ("Startups", f'{len(data["startups"])} Einträge (Fokus + Weitere)'),
        ("Prüfen", f'{len(data["review"])} unsichere Einträge – bitte kurz ansehen, bevor ihr sie nutzt'),
        ("Kontaktstatus / Notiz", "Diese Spalten gehören euch und werden bei späteren Läufen nicht überschrieben."),
        ("Kein Startup?", "Domain in blocklist.txt (Repo) eintragen – dann taucht sie nie wieder auf."),
        ("Datenschutz", "Nur Firmendaten und generische Firmenadressen. Intern behandeln, nicht ungefiltert weitergeben."),
        ("Löschfrist", f'Einträge, die länger als {meta["retention"]} Tage nicht mehr gesehen wurden, werden gelöscht.'),
    ]:
        info.append(list(line))
    info.column_dimensions["A"].width = 30
    info.column_dimensions["B"].width = 110
    for c in info["A"]:
        c.font = Font(bold=True)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    wb.save(path)
