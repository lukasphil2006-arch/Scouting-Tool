"""Optionale KI-Prüfung der vorgefilterten Kandidaten (OpenAI-kompatible Schnittstelle, Standard: Mistral).

- Läuft nur, wenn in config.yaml `ai.enabled: true` steht UND der API-Schlüssel als Umgebungsvariable
  (GitHub-Secret, Standard: AI_API_KEY) gesetzt ist. Sonst bleibt alles regelbasiert.
- Geschickt wird nur öffentlicher Text von Startseite / "Über uns" (kein Impressum, keine Personennamen).
- Fällt die KI aus (Limit, Netzwerk, Fehler), läuft der Scout regelbasiert weiter.
"""
import json
import os
import re
import time

import requests

SYSTEM = """Du prüfst Firmen-Websites für das Startup-Scouting eines Gründerzentrums.
Antworte ausschließlich mit JSON im Format {"results": [...]}, ein Objekt pro Firma, gleiche Reihenfolge, mit:
  "id": die übergebene id,
  "ist_startup": true nur bei einem jungen, innovativen, wachstumsorientierten Unternehmen (in der Regel jünger als
     10 Jahre, eigenes Produkt/Technologie). false bei: etablierten Firmen/Konzernen, Agenturen, Beratungen, Kanzleien,
     Handwerk/Fertigung im Kundenauftrag, Forschungsinstituten, Hochschulen, Behörden, Verbänden, Netzwerken,
     Inkubatoren/Acceleratoren, Investoren, Medien, Events, Bildungsträgern, Shops ohne eigene Innovation, Spam,
  "sicherheit": "hoch", "mittel" oder "niedrig",
  "grund": ein kurzer deutscher Satz, warum (max. 20 Wörter),
  "name": der Firmen- bzw. Produktname, wie er sich selbst nennt (ohne Slogan, ohne Rechtsform),
  "beschreibung": 1–2 sachliche deutsche Sätze, was die Firma anbietet und für wen (max. 40 Wörter, keine Werbesprache),
  "kategorie": "Greentech", "Impact", "Deeptech" oder "Weitere",
  "land": Land des Firmensitzes auf Deutsch oder "" wenn unklar,
  "stadt": Stadt des Firmensitzes oder "" wenn unklar,
  "gruendungsjahr": Zahl oder null, wenn nicht erkennbar.
Greentech = Klima, Energie, Kreislaufwirtschaft, Umwelt. Impact = gesellschaftlicher/sozialer Mehrwert als Kern.
Deeptech = wissenschaftlich-technische Innovation (Materialien, Photonik, Quanten, Biotech, Robotik, Raumfahrt …).
Erfinde nichts: wenn etwas nicht im Text steht, leer lassen bzw. null."""


class AIUnavailable(Exception):
    pass


class Checker:
    def __init__(self, cfg: dict):
        a = cfg.get("ai", {}) or {}
        self.cfg = a
        self.key = os.environ.get(a.get("key_env", "AI_API_KEY"), "")
        self.enabled = bool(a.get("enabled")) and bool(self.key)
        self.url = a.get("base_url", "https://api.mistral.ai/v1/chat/completions")
        self.model = a.get("model", "mistral-small-latest")
        self.batch = int(a.get("batch_size", 6))
        self.chars = int(a.get("max_chars_per_site", 2500))
        self.delay = float(a.get("delay_s", 1.5))
        self.max_calls = int(a.get("max_calls", 120))
        self.calls = 0
        self.failed = False
        if a.get("enabled") and not self.key:
            print(f"KI-Prüfung übersprungen: Secret {a.get('key_env', 'AI_API_KEY')} ist nicht gesetzt.")

    def _post(self, messages):
        body = {"model": self.model, "messages": messages, "temperature": 0.1,
                "response_format": {"type": "json_object"}}
        headers = {"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"}
        for attempt in range(4):
            time.sleep(self.delay)
            try:
                r = requests.post(self.url, headers=headers, json=body, timeout=90)
            except requests.RequestException as exc:
                err = str(exc)
            else:
                if r.status_code == 200:
                    return r.json()["choices"][0]["message"]["content"]
                err = f"HTTP {r.status_code}: {r.text[:200]}"
                if r.status_code in (401, 403, 404):
                    raise AIUnavailable(err)
            time.sleep(5 * (attempt + 1))  # 429 / 5xx / Netzwerk: kurz warten, dann nochmal
        raise AIUnavailable(err)

    def _payload(self, items):
        out = []
        for i, it in enumerate(items):
            txt = re.sub(r"\s+", " ", it.get("about_text") or it.get("text") or "")[: self.chars]
            out.append({"id": i, "website": it["domain"], "seitentitel_name": it["name"],
                        "ort_laut_regeln": " ".join(x for x in (it.get("plz"), it.get("city")) if x),
                        "land_laut_regeln": it.get("country", ""), "text": txt})
        return out

    def check(self, items):
        """Gibt pro Eintrag ein dict (oder None) zurück. Bricht nie den Lauf ab."""
        results = [None] * len(items)
        if not self.enabled or self.failed:
            return results
        for start in range(0, len(items), self.batch):
            if self.calls >= self.max_calls:
                print(f"KI-Prüfung: Höchstzahl von {self.max_calls} Anfragen erreicht, Rest bleibt regelbasiert.")
                break
            chunk = items[start:start + self.batch]
            msgs = [{"role": "system", "content": SYSTEM},
                    {"role": "user", "content": json.dumps({"firmen": self._payload(chunk)}, ensure_ascii=False)}]
            try:
                self.calls += 1
                data = json.loads(self._post(msgs))
            except AIUnavailable as exc:
                print(f"::warning::KI-Prüfung nicht verfügbar ({exc}). Der Lauf geht regelbasiert weiter.")
                self.failed = True
                break
            except (ValueError, KeyError, TypeError) as exc:
                print(f"KI-Antwort nicht lesbar ({exc}), dieser Block bleibt regelbasiert.")
                continue
            res = data.get("results", data if isinstance(data, list) else [])
            for j, r in enumerate(res if isinstance(res, list) else []):
                idx = r.get("id", j) if isinstance(r, dict) else j
                if isinstance(r, dict) and isinstance(idx, int) and 0 <= idx < len(chunk):
                    results[start + idx] = r
            print(f"  KI: {min(start + self.batch, len(items))}/{len(items)} geprüft")
        return results


def apply(info: dict, r: dict, cfg: dict, this_year: int):
    """KI-Ergebnis in den Eintrag übernehmen und Bereich (focus/other/review/None) anpassen."""
    if not r:
        return
    a = cfg.get("ai", {}) or {}
    sure = str(r.get("sicherheit", "")).lower()
    grund = str(r.get("grund") or "").strip()
    is_startup = r.get("ist_startup")
    info["ai_note"] = f'{"Startup" if is_startup else "kein Startup"} ({sure or "?"}): {grund}'.strip()

    name = str(r.get("name") or "").strip()
    if 1 < len(name) <= 60:
        info["name"] = name
    desc = str(r.get("beschreibung") or "").strip()
    if len(desc) >= 20:
        info["description"] = desc[:400]
    land, stadt = str(r.get("land") or "").strip(), str(r.get("stadt") or "").strip()
    if land:
        info["country"] = land
        if land != "Deutschland":
            info["plz"] = ""
    if stadt and (not info.get("city") or land and land != "Deutschland"):
        info["city"] = stadt
    yr = r.get("gruendungsjahr")
    if isinstance(yr, int) and 1900 <= yr <= this_year and not info.get("founded"):
        info["founded"] = yr
    kat = str(r.get("kategorie") or "").strip().lower()
    if kat in cfg["focus_themes"]:
        info["ai_category"] = kat
        if kat not in info["themes"]:
            info["themes"] = [kat] + info["themes"]
    elif kat == "weitere":
        info["ai_category"] = "weitere"

    if is_startup is False and sure in ("hoch", "mittel", ""):
        info["reject_reason"] = f"KI: kein Startup – {grund}"
        info["bucket"] = None
        return
    if is_startup is False:  # unsicher -> zum Prüfen
        info["review_notes"] = "; ".join(x for x in [info.get("review_notes"), f"KI unsicher: {grund}"] if x)
        if info["bucket"] in ("focus", "other"):
            info["review_of"], info["bucket"] = info["bucket"], "review"
        return
    if is_startup and sure in ("hoch", "mittel") and info["bucket"] == "review" and a.get("confirm_review", True):
        # KI bestätigt einen Grenzfall der Regeln -> doch in die Liste
        info["bucket"] = info.get("review_of") or "other"
        info["review_notes"] = ""
    if is_startup and kat in cfg["focus_themes"] and info["bucket"] == "other":
        info["bucket"] = "focus"
    if is_startup and kat == "weitere" and info["bucket"] == "focus" and a.get("trust_category", True):
        info["bucket"] = "other"
        info["themes"] = []
