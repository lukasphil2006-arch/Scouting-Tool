from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
H=["Nr","Quelle","Art","Region","Thema","Menge (ca.)","Zugriff","Status im Tool","URL","Hinweis"]
R=[
# --- automatisch eingebaut
("YC-OSS Climate (Industrie)","Accelerator-Portfolio (JSON)","Weltweit (viel USA)","Greentech/Climate","53","JSON-API, sauber","AUTOMATISCH (getestet: Struktur geprüft)","https://yc-oss.github.io/api/industries/climate.json","Feld 'website' vorhanden; Alter über launched_at, im Tool über Webseite geprüft"),
("YC-OSS Tag climate","Accelerator-Portfolio (JSON)","Weltweit","Greentech/Climate","143","JSON-API","AUTOMATISCH","https://yc-oss.github.io/api/tags/climate.json","Überschneidet sich mit Industrie-Liste, Doppelte werden entfernt"),
("YC-OSS Tag climatetech","Accelerator-Portfolio (JSON)","Weltweit","Greentech","32","JSON-API","AUTOMATISCH","https://yc-oss.github.io/api/tags/climatetech.json",""),
("YC-OSS Tag renewable-energy","Accelerator-Portfolio (JSON)","Weltweit","Energie","21","JSON-API","AUTOMATISCH","https://yc-oss.github.io/api/tags/renewable-energy.json",""),
("YC-OSS Tag sustainability","Accelerator-Portfolio (JSON)","Weltweit","Impact","16","JSON-API","AUTOMATISCH","https://yc-oss.github.io/api/tags/sustainability.json",""),
("YC-OSS Tag carbon-capture","Accelerator-Portfolio (JSON)","Weltweit","Deeptech/Climate","13","JSON-API","AUTOMATISCH","https://yc-oss.github.io/api/tags/carbon-capture-and-removal.json",""),
("HTGF Portfolio (Sitemap 1)","VC-Portfolio (Frühphasen-Fonds)","Deutschland","Deeptech, Climate Tech, Digital, Medtech","ca. 500","Sitemap + Profilseiten (Firmenwebsite ist dort verlinkt)","AUTOMATISCH, rotierend (40 Profile pro Lauf) - Praxistest offen","https://www.htgf.de/portfolio-sitemap.xml","Profil enthält 'Unternehmenswebsite'. Viele Firmen sind älter/Exit, Filter im Tool sortiert sie aus"),
("HTGF Portfolio (Sitemap 2)","VC-Portfolio","Deutschland","wie oben","s.o.","Sitemap","AUTOMATISCH, rotierend - Praxistest offen","https://www.htgf.de/portfolio-sitemap2.xml",""),
("ESA BIC Startups (Europa)","Inkubator-Portfolio (WordPress-API)","Europa inkl. NRW (ESA BIC NRW Aachen/Herten)","Deeptech/Raumfahrt, Anwendungen","hunderte","WordPress-REST: /wp-json/wp/v2/esa-startups","AUTOMATISCH - Datenfelder ungeprüft, Tool nimmt erste fremde URL im Eintrag","https://commercialisation.esa.int/wp-json/wp/v2/esa-startups?per_page=100","Route existiert (geprüft). Ob Webseiten im Datensatz stehen, zeigt erst der erste Lauf (Quellen-Bilanz)"),
("Fraunhofer ISE Spin-offs","Forschungs-Ausgründungen","Deutschland (Freiburg)","Energie/Solar/Deeptech","ca. 10-20","Statische Seite","AUTOMATISCH [ungetestet]","https://www.ise.fraunhofer.de/de/ueber-uns/spin-offs.html","Seite ist lang, Links stehen weit hinten; evtl. page_links_limit erhöhen"),
("DWI Aachen Start-ups","Institut-Ausgründungen","Aachen","Biotech/Materialien","wenige","Statische Seite","AUTOMATISCH [ungetestet]","https://www.dwi.rwth-aachen.de/en/seite/startups","Nur kleine Liste, aber regional ideal"),
("EU-Startups / Deutsche Startups News","Nachrichten-Feed","DE/EU","alle","laufend","RSS","SCHON DRIN (Prototyp)","https://www.eu-startups.com/feed/","Hauptquelle des ersten Laufs, nur 3 Treffer = zu dünn allein"),
# --- Nur manuell/CSV
("SET100 Liste 2026 (dena)","Preisliste/Top-100","Weltweit","Energie/Climate","100","PDF ohne Webseiten (nur Name+Land)","MANUELL: Namen googeln, Website in inputs/manual_startups.csv","https://www.startup-energy-transition.com/app/uploads/2026/02/SET100-List-2026.pdf","Qualitäts-Signal! Quelle in CSV als 'SET100 2026' eintragen -> im Tool filterbar"),
("Global Cleantech 100 (2026)","Ranking","Weltweit (5 aus DE)","Greentech","100","Download nach Formular","MANUELL","https://cleantech.com/the-global-cleantech-100/","Qualitäts-Signal, meist schon groß/finanziert"),
("EIC Accelerator Gewinner","Förderung (EU)","Europa","Deeptech, alle","ca. 40 pro Runde","PDF-Liste pro Runde","MANUELL (PDF)","https://eic.ec.europa.eu/news/38-start-ups-and-smes-secure-eic-support-latest-round-eic-accelerator-2026-06-15_en","Qualitäts-Signal; PDF enthält evtl. keine Webseiten"),
("Grüne Gründungen.NRW (PtJ)","Förderung (NRW)","NRW","Greentech","15 (erste Runde)","Seite ohne Links","MANUELL: Firmenliste aus Pressemitteilung","https://www.ptj.de/veroeffentlichungen/aktuelles/gruene-gruendungen-nrw-14-innovative-start-ups-feiern-foerderzusage","Genau Ihre Zielgruppe. Namen: AirPnP/Layer Performance, heatbrAIn, vGreens, NUNOS, Calogy, OSPHIM, SECARA, offsee, Khoch3, production.AI, Willowprint, mechIC, Lamb Space Tec, Senlytics"),
("EXIST-Gründerstipendium/Forschungstransfer","Förderung (Bund)","Deutschland","alle, viele Deeptech","hunderte","Projektliste/Förderkatalog","EINGEBAUT, ungeprüft","https://www.exist.de","Förderkatalog des Bundes durchsuchbar, Zugriff nicht verifiziert"),
("Helmholtz Spin-off-Datenbank","Forschungs-Ausgründungen","Deutschland","Deeptech/Energie","450+","PDF-Download","EINGEBAUT (Seite), PDF manuell","https://www.helmholtz.de/en/transfer/examples-and-successes/spin-offs/","PDF ca. 1 MB, Forschungszentrum Jülich liegt direkt in Ihrer Region"),
("Fraunhofer Venture Ausgründungen","Forschungs-Ausgründungen","Deutschland","Deeptech","ca. 500 seit 2000","Seite je Institut","EINGEBAUT, ungeprüft","https://venture.fraunhofer.de","Pro Institut eigene Spin-off-Seiten, z.B. ISE, IGD"),
("RWTH Spin-off Award Gewinner","Hochschul-Ausgründungen","Aachen","alle, viel Deeptech","10 pro Halbjahr","Webseite Gewinnerlisten","EINGEBAUT, ungeprüft + manuell","https://www.rwth-innovation.de/de/gruender/awards/spin-off-award","Qualitäts-Signal + regional. Seite per pages eintragbar (Praxistest offen)"),
("digitalHUB Aachen Mitglieder","Hub-Mitgliederliste","Aachen","Digital (nicht Green)","350 Startups","Seite 'Members' ungeprüft, evtl. JS","EINGEBAUT, ungeprüft","https://www.aachen.digital/en/digitalhub-aachen/members/","Regional wichtig, viele Mitglieder"),
("de:hub Düsseldorf (digihub) Ignition","Hub/Accelerator","NRW","GreenTech","120+","Alumni-Seiten","EINGEBAUT, ungeprüft","https://www.de-hub.de/en/the-hubs/duesseldorf/","Ignition ist GreenTech-Accelerator für NRW-Teams"),
("Startup Village Jülich / ZEBRA Accelerator","Accelerator","Jülich/NRW","GreenTech","kleine Zahl","Webseite","EINGEBAUT, ungeprüft","https://startup-village-juelich.cobot.me","Eigene Region, ggf. Austausch direkt statt Scraping"),
("World Fund Portfolio","VC-Portfolio","Europa","Climate Tech","20+","Portfolio-Seite ungeprüft","EINGEBAUT, ungeprüft","https://www.worldfund.vc/portfolio",""),
("Extantia Portfolio","VC-Portfolio","Europa (Berlin)","Climate Tech/Deeptech","30+","ungeprüft","EINGEBAUT, ungeprüft","https://f4.fund/firms/extantia/portfolio","Drittseite listet Portfolio"),
("Planet A Ventures","VC-Portfolio","Europa","Climate","27","ungeprüft","EINGEBAUT, ungeprüft","https://funding.tech.eu/investors/Planet%20A%20Ventures",""),
("CORDIS (Horizon Europe) Bulk-CSV","EU-Projektdaten","Europa","alle, KMU filterbar","tausende","CSV/XML-Download (Open Data)","SPÄTER: eigener Importer","https://data.europa.eu/data/datasets/cordis-eu-research-projects-under-horizon-europe-2021-2027","Sehr viel Menge, KMU mit Webseite und Region filterbar; sinnvoll für 'Quantität'"),
("B Corp Verzeichnis / Impact-Daten","Zertifizierung","Weltweit","Impact","tausende","data.world braucht Anmeldung; bcorporation.net Nutzungsbedingungen prüfen","SPÄTER/MANUELL","https://www.bcorporation.net/find-a-b-corp","Nur nach Prüfung der Nutzungsbedingungen"),
# --- Nicht nutzbar
("Deutsche Startups Verzeichnis","Verzeichnis","DE","alle","gross","robots.txt sperrt Abruf","AUSGESCHLOSSEN","https://www.deutsche-startups.de","Sperre wird respektiert; nur RSS-Feed nutzbar"),
("startbase.de Datenbank","Verzeichnis","DE","alle","10.000+","Abruf scheiterte","AUSGESCHLOSSEN (aktuell)","https://www.startbase.de","Ggf. später Rücksprache/Export"),
("EIT InnoEnergy Portfolio","Portfolio","Europa","Energie","145-160","Seite lädt per JavaScript","AUSGESCHLOSSEN (nur manuell)","https://innoenergy.com/for-innovators/portfolio",""),
("Seedtable / VCBacked / Crunchbase-artige","kommerzielle DB","Weltweit","alle","gross","Paywall/AGB","AUSGESCHLOSSEN","https://seedtable.com","Nicht scrapen"),
("EU-Startups 36 Greentech-Liste","Artikel","DE","Greentech","36","enthält keine Links","MANUELL","https://www.eu-startups.com/36-top-greentech-startups-and-companies-in-germany","Nur als Namensquelle"),
]
wb=Workbook();ws=wb.active;ws.title="Quellenkatalog"
ws.append(H)
for i,r in enumerate(R,1): ws.append([i,*r])
for c in ws[1]:
    c.font=Font(bold=True,color="FFFFFF");c.fill=PatternFill("solid",fgColor="1F6F4A")
fills={"AUTOMATISCH":"DFF3E4","SCHON":"DFF3E4","MANUELL":"FFF4D6","TEILWEISE":"FFF4D6","EINGEBAUT":"E8EEF9","SPÄTER":"E8EEF9","AUSGESCHLOSSEN":"F6DADA"}
for row in ws.iter_rows(min_row=2):
    st=str(row[7].value)
    for k,v in fills.items():
        if st.startswith(k):
            row[7].fill=PatternFill("solid",fgColor=v);break
    for c in row: c.alignment=Alignment(wrap_text=True,vertical="top")
for i,w in enumerate([5,34,24,24,24,12,30,36,52,52],1): ws.column_dimensions[get_column_letter(i)].width=w
ws.auto_filter.ref=ws.dimensions;ws.freeze_panes="C2"
wb.save("docs/Quellenkatalog.xlsx")
