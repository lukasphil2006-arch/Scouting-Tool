# Startup-Scout (Prototyp)

Regelbasiertes Startup-Scouting **ohne KI zur Laufzeit, ohne Abo, ohne Bindung an einen Rechner**.
Alle 2 Wochen sammelt ein Skript neue Startup-Websites aus News-Feeds und eigenen Listen,
bewertet sie nach Greentech / Impact / Deeptech, filtert nach Region, Alter und Phase und
schickt eine Excel-Liste an einen Verteiler.

## Was gespeichert wird (und was nicht)
- Gespeichert: Firmenname, Website, **generische** Firmenadresse (info@, kontakt@ …), Eckdaten.
- **Nie gespeichert:** persönliche E-Mail-Adressen und Namen von Personen (werden beim Auslesen verworfen).
- Merkzettel (`data/state.json`): nur Domain, Datum, Status. Wird nach `retention_days` gelöscht.
- Sperrliste: Domain in `blocklist.txt` eintragen, dann taucht sie nie wieder auf.
- Das Skript **versendet keine Werbemails** an Startups. Es erzeugt nur die Liste.
- Es beachtet `robots.txt` und wartet zwischen Anfragen.

## Einrichten (einmalig, ca. 15 Minuten)
1. Neues **privates** GitHub-Repo anlegen (am besten unter einer Organisation) und diesen Ordner hochladen.
2. In `config.yaml` unter `run.user_agent` eure echte Kontaktadresse eintragen.
3. Unter *Settings → Secrets and variables → Actions* diese Secrets anlegen:
   `SMTP_HOST`, `SMTP_PORT` (z. B. 587), `SMTP_USER`, `SMTP_PASS`, `MAIL_FROM`, `MAIL_TO` (= der Verteiler).
   Empfehlung: ein eigenes Absender-Konto (z. B. scouting@eure-domain.de), nicht ein privates Postfach.
4. Unter *Actions → Startup Scouting → Run workflow* einmal manuell starten. Danach läuft es am 1. und 15. jedes Monats.
5. Ergebnis: Mail mit Excel-Anhang. Zusätzlich liegt die Liste 30 Tage als Archiv im Lauf (nur für Repo-Mitglieder).

## Anpassen (alles in `config.yaml`)
- Themen-Stichwörter: `themes` (greentech, impact, deeptech)
- Region, Alter, Phase: `regions`, `filters`, `phases`
- Menge pro Lauf: `max_focus`, `max_other`
- Quellen: `sources.rss` (News-Feeds) und `sources.csv` (eigene Listen, z. B. Förderlisten oder Ausstellerlisten)

## Lokal testen (ohne Internet)
```
pip install -r requirements.txt
python tests/demo_offline.py
```
Startet fünf Fake-Startups und einen Fake-Feed lokal und prüft den kompletten Ablauf.

## Bekannte Grenzen
- Die Feed-URLs in `config.yaml` sind Startwerte und sollten beim ersten Lauf geprüft werden.
- News-Feeds liefern Rauschen (verlinkte Investoren, Unis, Konzerne). Der Startup-Signal-Filter fängt vieles ab, nicht alles.
- Gründungsjahr und Standort werden aus dem Website-Text gelesen und sind nicht immer vorhanden.
- Eine Vorab-Prüfung durch euren Datenschutzbeauftragten ist vor dem Echtbetrieb sinnvoll.
