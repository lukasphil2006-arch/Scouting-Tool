# Startup-Scout

Regelbasiertes Startup-Scouting **ohne KI zur Laufzeit, ohne Abo, ohne Bindung an einen Rechner**.
Einmal im Monat (am 1.) sammelt ein Skript neue Startup-Websites aus News-Feeds und eigenen Listen,
prüft, ob es wirklich Startups sind, bewertet sie nach Greentech / Impact / Deeptech, filtert nach
Region, Alter und Phase und schickt einen **interaktiven HTML-Bericht** plus eine **Excel-Gesamtliste**
an einen Verteiler.

## Was in der Mail ankommt
- **`startup-scouting_DATUM.html`** – per Doppelklick im Browser öffnen (läuft offline, keine Installation).
  Karten pro Startup, Filter nach Kategorie (Greentech, Impact, Deeptech, Weitere), Phase, Region,
  Gründungsjahr, Volltextsuche, „nur neue“. Gefilterte Auswahl als CSV speichern, „Drucken / PDF“ für Papier.
  Der Bericht zeigt alle Startups der letzten 180 Tage; neue Treffer dieses Laufs tragen ein „NEU“.
  Ganz oben stehen die **Empfehlungen fürs Startup Village**: die 10 Startups, die nach Region, Phase,
  Thema und Sektor am besten passen, mit dem passenden Programm (Incubator/Accelerator). Gewichtung und
  Programm-Zuordnung stehen in `config.yaml` unter `empfehlungen`.
- **`…_gesamtliste.xlsx`** – Backup mit allen Infos:
  - Blatt **Startups**: alle gelieferten Startups (ein Eintrag pro Domain).
  - Blatt **Prüfen**: unsichere Fälle (wirkt wie Förderer/Netzwerk/Event oder Konzern) mit Prüfhinweis.
    Diese stehen bewusst *nicht* im HTML-Bericht.
  - Spalten **Kontaktstatus** und **Notiz** gehören euch und werden nie überschrieben.

## Wie „nur Startups“ sichergestellt wird (`startup_check` in config.yaml)
1. **Hart raus**: Domains von Hochschulen, Forschungsinstituten (Fraunhofer, Helmholtz, Max-Planck, Leibniz …),
   Behörden (.bund.de, .nrw, .edu …), Banken, Kammern und Förderern; dazu Impressum-Angaben wie
   „Körperschaft des öffentlichen Rechts“ oder „Fraunhofer-Gesellschaft zur Förderung …“.
2. **Zum Prüfen**: klingt nach Netzwerk/Förderer/Event („wir unterstützen Startups“) oder Konzern
   („Mitarbeiter weltweit“, „Tochtergesellschaft der“), Rechtsform e.V., AG ohne Gründungsjahr.
3. **Startup-Signale** sind eng gefasst (EXIST-Stipendium, Pre-Seed, Finanzierungsrunde, Ausgründung …),
   damit Institute nicht über Wörter wie „Förderung“ oder „Universität“ durchrutschen.
4. **Gründungsjahr** wird auch aus „seit 1983“ / „since 1983“ gelesen, damit alte Firmen rausfallen.

Rutscht trotzdem etwas durch: Domain in `blocklist.txt` (einmalig, nie wieder) oder in
`startup_check.exclude_domains` eintragen – direkt im Browser auf GitHub, ohne Code.

## Was gespeichert wird (und was nicht)
- Gespeichert: Firmenname, Website, **generische** Firmenadresse (info@, kontakt@ …), Eckdaten.
- **Nie gespeichert:** persönliche E-Mail-Adressen und Namen von Personen (werden beim Auslesen verworfen).
- Merkzettel (`data/state.json`): nur Domain, Datum, Status. Wird nach `retention_days` gelöscht.
- Gesamtliste (`data/gesamtliste.xlsx`): Firmendaten der gelieferten Startups. Einträge, die länger als
  `retention_days` nicht mehr gesehen wurden, werden gelöscht. **Das Repo muss deshalb privat bleiben.**
- Sperrliste: Domain in `blocklist.txt` eintragen, dann taucht sie nie wieder auf.
- Das Skript **versendet keine Werbemails** an Startups. Es erzeugt nur die Liste.
- Es beachtet `robots.txt` und wartet zwischen Anfragen.

## Einrichten (einmalig, ca. 15 Minuten)
1. Neues **privates** GitHub-Repo anlegen (am besten unter einer Organisation) und diesen Ordner hochladen.
2. In `config.yaml` unter `run.user_agent` eure echte Kontaktadresse eintragen.
3. Unter *Settings → Secrets and variables → Actions* diese Secrets anlegen:
   `SMTP_HOST`, `SMTP_PORT` (z. B. 587), `SMTP_USER`, `SMTP_PASS`, `MAIL_FROM`, `MAIL_TO` (= der Verteiler).
   Empfehlung: ein eigenes Absender-Konto (z. B. scouting@eure-domain.de), nicht ein privates Postfach.
4. Unter *Actions → Startup Scouting → Run workflow* einmal manuell starten. Danach läuft es am 1. jedes Monats.
5. Ergebnis: Mail mit HTML-Bericht und Excel-Gesamtliste. Zusätzlich liegen beide 30 Tage als Archiv im Lauf
   (nur für Repo-Mitglieder). Das alte PDF gibt es weiterhin mit `run.attach_pdf: true`.

## Anpassen (alles in `config.yaml`)
- Themen-Stichwörter: `themes` (greentech, impact, deeptech)
- Region, Alter, Phase: `regions`, `filters`, `phases`
- Menge pro Lauf: `max_candidates` (geprüfte Websites, 600 ≈ 1,5 Std.), `max_focus`, `max_other`
- Empfehlungen: `empfehlungen`
- Startup-Prüfung: `startup_check`
- Quellen: `sources.rss` (News-Feeds) und `sources.csv` (eigene Listen, z. B. Förderlisten oder Ausstellerlisten)

## Lokal testen (ohne Internet)
```
pip install -r requirements.txt
python tests/demo_offline.py
```
Startet Fake-Startups, ein Fake-Institut, ein Fake-Netzwerk und einen Fake-Feed lokal und prüft den kompletten
Ablauf (Institut fliegt raus, Netzwerk landet in „Prüfen“, Startups im Bericht).

## Bekannte Grenzen
- Die Feed-URLs in `config.yaml` sind Startwerte und sollten beim ersten Lauf geprüft werden.
- News-Feeds liefern Rauschen (verlinkte Investoren, Unis, Konzerne). Der Startup-Signal-Filter fängt vieles ab, nicht alles.
- Gründungsjahr und Standort werden aus dem Website-Text gelesen und sind nicht immer vorhanden.
- Eine Vorab-Prüfung durch euren Datenschutzbeauftragten ist vor dem Echtbetrieb sinnvoll.
