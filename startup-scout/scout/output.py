"""Excel-Liste und Mail-Text erzeugen."""
import os

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

COLUMNS = [
    ("Score", 7), ("Name", 28), ("Website", 30), ("E-Mail (generisch)", 28), ("Impressum / Kontakt", 26),
    ("Themen", 18), ("Sektor", 26), ("Standort", 22), ("Region", 18), ("Gegründet", 10), ("Alter", 7),
    ("Phase", 20), ("Rechtsform", 11), ("Förder-/Ausgründungs-Signal", 22), ("Kurzbeschreibung", 60),
    ("Treffer-Begriffe", 36), ("Quelle", 20), ("Quell-Artikel", 30),
]


def _row(r: dict):
    sig = ", ".join(x for x, f in (("Förderung/Finanzierung", r["funding"]), ("Ausgründung", r["spinoff"])) if f)
    return [
        r["score"], r["name"], r["url"], r["emails"][0] if r["emails"] else "(nicht gefunden – siehe Impressum)",
        r["legal_page"], ", ".join(t.capitalize() for t in r["themes"]), ", ".join(r["sectors"]),
        f'{r["plz"]} {r["city"]}'.strip(), r["region"], r["founded"] or "", r["age"] if r["age"] is not None else "",
        r["phase"], r["legal_form"], sig, r["description"], r["hits"], r["source"], r["source_url"],
    ]


def _sheet(ws, rows):
    ws.append([c for c, _ in COLUMNS])
    for i, (_, w) in enumerate(COLUMNS, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
        cell = ws.cell(row=1, column=i)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="2F6F4F")
    for r in rows:
        ws.append(_row(r))
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=cell.column in (15, 16))
        for idx in (2, 4, 17):  # Website, Impressum, Quell-Artikel als Link
            c = row[idx]
            if isinstance(c.value, str) and c.value.startswith("http"):
                c.hyperlink = c.value
                c.font = Font(color="0563C1", underline="single")
    ws.freeze_panes = "C2"
    ws.auto_filter.ref = ws.dimensions


def write_xlsx(path, focus, other, meta: dict):
    wb = Workbook()
    ws = wb.active
    ws.title = "Fokus"
    _sheet(ws, focus)
    ws2 = wb.create_sheet("Weitere")
    _sheet(ws2, other)
    info = wb.create_sheet("Info")
    lines = [
        ("Startup-Scouting", meta["date"]),
        ("Neu geprüfte Websites", meta["checked"]),
        ("In Liste 'Fokus'", len(focus)),
        ("In Liste 'Weitere'", len(other)),
        ("", ""),
        ("Datenschutz-Hinweis", "Die Liste enthält nur Firmendaten und generische Firmenadressen (info@, kontakt@ …)."),
        ("", "Persönliche Adressen werden nicht erfasst. Bitte Liste nicht ungefiltert weitergeben."),
        ("Speicherdauer", f'Merkzettel (nur Domain + Datum) wird nach {meta["retention"]} Tagen gelöscht.'),
        ("Widerspruch", "Wer nicht kontaktiert werden möchte: Domain in blocklist.txt eintragen."),
        ("Score", "Themen-Treffer (Greentech/Impact/Deeptech) + Bonus für Region, Alter, Phase, Förder-Signal."),
    ]
    for l in lines:
        info.append(list(l))
    info.column_dimensions["A"].width = 26
    info.column_dimensions["B"].width = 100
    for c in info["A"]:
        c.font = Font(bold=True)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    wb.save(path)


def mail_text(focus, other, meta):
    out = [f'Startup-Scouting vom {meta["date"]}',
           f'{len(focus)} Treffer im Fokus (Greentech/Impact/Deeptech), {len(other)} weitere. Details: Excel im Anhang.', ""]
    for r in focus[:10]:
        out.append(f'- {r["name"]} ({", ".join(t.capitalize() for t in r["themes"])}; {r["region"]}; Score {r["score"]})')
        out.append(f'  {r["url"]}  |  {r["emails"][0] if r["emails"] else "keine generische Adresse gefunden"}')
    if len(focus) > 10:
        out.append(f"  … und {len(focus) - 10} weitere in der Excel-Datei.")
    out += ["", "Hinweis: Nur Firmendaten und generische Adressen. Bitte intern behandeln und nicht ungefiltert weitergeben."]
    return "\n".join(out)
