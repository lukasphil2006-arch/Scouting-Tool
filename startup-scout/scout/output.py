"""Ausgabe: optionales PDF und der Mailtext. HTML-Bericht: report.py, Excel-Gesamtliste: master.py."""
import os
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

GREEN = colors.HexColor("#2F6F4F")
LIGHT = colors.HexColor("#F3F7F4")
GREY = colors.HexColor("#5F6B64")
TAGCOL = {"Greentech": ("#DCEFE4", "#1D5A3C"), "Impact": ("#FBE8C8", "#7A4B00"), "Deeptech": ("#DCE6F7", "#1F3F7A")}


def _t(s) -> str:
    """Text PDF-sicher machen (Standardschrift kennt nur Latin-1/cp1252) und für XML escapen."""
    return escape(str(s or "").encode("cp1252", "replace").decode("cp1252"))


def _themes(r):
    return ", ".join(t.capitalize() for t in r["themes"])


def _meta(r):
    parts = [f'{r["city"]} ({r["plz"]})' if r["city"] else "", r["region"] if not r["city"] else "",
             f'gegründet {r["founded"]}' if r["founded"] else "", r["phase"] if r["phase"] != "unbekannt" else "",
             r["legal_form"]]
    return "  ·  ".join(p for p in parts if p)


# ------------------------------------------------------------------ PDF (schön)
def _styles():
    base = dict(fontName="Helvetica", textColor=colors.HexColor("#1F2A24"))
    return {
        "name": ParagraphStyle("name", fontName="Helvetica-Bold", fontSize=12.5, leading=15, textColor=GREEN),
        "score": ParagraphStyle("score", fontSize=8.5, leading=11, alignment=2, textColor=GREY, fontName="Helvetica"),
        "tags": ParagraphStyle("tags", fontSize=8.5, leading=13, **base),
        "meta": ParagraphStyle("meta", fontSize=8.5, leading=11.5, textColor=GREY, fontName="Helvetica"),
        "desc": ParagraphStyle("desc", fontSize=9.2, leading=12.5, **base),
        "contact": ParagraphStyle("contact", fontSize=8.8, leading=12, **base),
        "h1": ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=15, leading=19, textColor=GREEN, spaceBefore=6, spaceAfter=6),
        "p": ParagraphStyle("p", fontSize=9.5, leading=13.5, **base),
    }


def _card(r, st, width):
    tags = " ".join(
        f'<font backColor="{TAGCOL.get(t.capitalize(), ("#E8E8E8", "#333333"))[0]}" '
        f'color="{TAGCOL.get(t.capitalize(), ("#E8E8E8", "#333333"))[1]}">&nbsp;{_t(t.capitalize())}&nbsp;</font>' for t in r["themes"])
    if r["sectors"]:
        tags += "&nbsp;&nbsp;" + " ".join(f'<font backColor="#EEF0EE" color="#444444">&nbsp;{_t(s)}&nbsp;</font>' for s in r["sectors"])
    mail = (f'<link href="mailto:{_t(r["emails"][0])}" color="#0563C1">{_t(r["emails"][0])}</link>'
            if r["emails"] else '<font color="#888888">keine generische Adresse gefunden</font>')
    imp = f' &nbsp;|&nbsp; <link href="{_t(r["legal_page"])}" color="#0563C1">Impressum / Kontakt</link>' if r["legal_page"] else ""
    rows = [
        [Paragraph(f'<link href="{_t(r["url"])}" color="#2F6F4F">{_t(r["name"])}</link>', st["name"]),
         Paragraph(f'Score {r["score"]}', st["score"])],
        [Paragraph(tags or "&nbsp;", st["tags"]), ""],
        [Paragraph(_t(_meta(r)) or "&nbsp;", st["meta"]), ""],
        [Paragraph(_t(r["description"][:260]) or "&nbsp;", st["desc"]), ""],
        [Paragraph(f'<b>E-Mail:</b> {mail}{imp}', st["contact"]), ""],
        [Paragraph(f'<font color="#888888">Quelle: {_t(r["source"])}</font>', st["meta"]), ""],
    ]
    t = Table(rows, colWidths=[width - 24 * mm, 24 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT), ("LINEBEFORE", (0, 0), (0, -1), 3, GREEN),
        ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 2.2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2),
        ("TOPPADDING", (0, 0), (-1, 0), 7), ("BOTTOMPADDING", (0, -1), (-1, -1), 7),
        ("SPAN", (0, 1), (1, 1)), ("SPAN", (0, 2), (1, 2)), ("SPAN", (0, 3), (1, 3)),
        ("SPAN", (0, 4), (1, 4)), ("SPAN", (0, 5), (1, 5)), ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return KeepTogether([t, Spacer(1, 4.5 * mm)])


def write_pdf(path, focus, other, meta):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    st = _styles()
    W, H = A4
    margin = 18 * mm
    width = W - 2 * margin

    def first(c, d):
        c.saveState()
        c.setFillColor(GREEN)
        c.rect(0, H - 32 * mm, W, 32 * mm, stroke=0, fill=1)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 22)
        c.drawString(margin, H - 17 * mm, "Startup-Scouting")
        c.setFont("Helvetica", 10.5)
        c.drawString(margin, H - 24.5 * mm, f'Stand {meta["date"]}  ·  {len(focus)} Fokus-Treffer  ·  {len(other)} weitere')
        c.restoreState()
        later(c, d)

    def later(c, d):
        c.saveState()
        c.setFont("Helvetica", 7.5)
        c.setFillColor(GREY)
        c.drawString(margin, 10 * mm, "Nur Firmendaten und generische Firmenadressen. Intern behandeln, nicht ungefiltert weitergeben.")
        c.drawRightString(W - margin, 10 * mm, f"Seite {d.page}")
        c.restoreState()

    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=margin, rightMargin=margin, topMargin=14 * mm,
                            bottomMargin=17 * mm, title=f'Startup-Scouting {meta["date"]}', author="Startup-Scout")
    story = [Spacer(1, 22 * mm),
             Paragraph(f'Diesmal wurden {meta["checked"]} neue Websites geprüft. Die Liste ist nach Passung sortiert '
                       f'(Score: Themen-Treffer plus Bonus für Region, Alter, Phase und Förder-Signal). '
                       f'Die Tabelle mit allen Einträgen liegt zusätzlich als Excel bei.', st["p"]),
             Spacer(1, 3 * mm)]
    for title, rows, empty in (("Fokus: Greentech · Impact · Deeptech", focus, "Keine passenden Treffer in diesem Lauf."),
                               ("Weitere Startups", other, "Keine weiteren Treffer in diesem Lauf.")):
        story.append(Paragraph(title, st["h1"]))
        if rows:
            story += [_card(r, st, width) for r in rows]
        else:
            story += [Paragraph(empty, st["p"]), Spacer(1, 4 * mm)]
    doc.build(story, onFirstPage=first, onLaterPages=later)


def mail_text(focus, other, review, master, meta, recs=()):
    out = [f'Startup-Scouting vom {meta["date"]}', "",
           f'Neu in diesem Lauf: {len(focus)} Startups im Fokus (Greentech/Impact/Deeptech), {len(other)} weitere.',
           f'Insgesamt in der Liste: {len(master["startups"])} Startups der letzten {meta["retention"]} Tage.', "",
           "Im Anhang:",
           "- startup-scouting_….html: im Browser öffnen (Doppelklick) – filtern nach Kategorie, Phase, Region,",
           "  Gründungsjahr, Suche. Neue Treffer sind markiert. Funktioniert offline.",
           "- …_gesamtliste.xlsx: Backup mit allen Infos, inkl. Blatt 'Prüfen' für unsichere Fälle.", ""]
    if recs:
        out.append("Empfehlungen fürs Startup Village:")
        for d in recs:
            prog = f' → {d["programm"]}' if d.get("programm") else ""
            out.append(f'{d["empfohlen"]:>2}. {d["name"]} ({", ".join(d["fit_gruende"][:4])}){prog} – {d["url"]}')
        out.append("")
    if review:
        out += [f"{len(review)} Einträge waren nicht eindeutig (z. B. Netzwerk, Förderer oder Konzern) und stehen nur im "
                "Excel-Blatt 'Prüfen'.", ""]
    if meta.get("ki"):
        out += [meta["ki"], ""]
    out += ["Hinweis: Nur Firmendaten und generische Adressen. Bitte intern behandeln und nicht ungefiltert weitergeben."]
    return "\n".join(out)
