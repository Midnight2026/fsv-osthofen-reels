#!/usr/bin/env python3
"""Parst einen DFBnet-Spielbericht und gibt die FSV-Aufstellung als JSON aus.

Eingabe: PDF (pdftotext -layout wird aufgerufen) ODER eine Textdatei mit dem
Text des Spielberichts (z. B. aus Google Drive `read_file_content`, dort sind
die Spalten nur durch einfache Leerzeichen getrennt – beides wird unterstützt).

Aufruf:
    python3 -I parse_spielbericht.py Spielbericht.pdf
    python3 -I parse_spielbericht.py spielbericht.txt

Ausgabe (JSON):
{
  "team": "1"|"2",                 # FSV Osthofen = 1. Mannschaft, FSV Osthofen II = 2. Mannschaft
  "fsv_side": "home"|"away",
  "home": "TuS Offstein", "away": "FSV Osthofen II",
  "date": "11.10.2026", "time": "13:05", "venue": "Offstein Rasenplatz",
  "competition": "C-Klasse Alzey-Worms Süd",
  "startelf": [{"nr": 1, "name": "Pavlak, Denis", "hint": "TW"}, ...],   # 11 Spieler
  "bank":     [{"nr": 5, "name": "Kocak, Bilal", "hint": ""}, ...],
  "warnings": []                   # z. B. unsichere Zuordnung einzelner Bankspieler
}
"""
import json
import re
import subprocess
import sys

# Ein Spieler-Eintrag: Nr  Name (Nachname, Vorname[n])  [TW|C]  Geb-Datum  Passnummer
PLAYER = re.compile(
    r"(?<![\d\-])(\d{1,2})\s+([^\d]+?)\s+(?:(TW|C)\s+)?(\d\d\.\d\d\.\d{4})\s+([\d\-]{6,})"
)


def load_text(path: str) -> str:
    if path.lower().endswith(".pdf"):
        return subprocess.run(["pdftotext", "-layout", path, "-"], capture_output=True, text=True, check=True).stdout
    return open(path, encoding="utf-8", errors="replace").read()


def mk(m):
    name = re.sub(r"\s+", " ", m.group(2)).strip()
    hint = m.group(3) or ""
    mh = re.match(r"^(.*?)\s+(ETW|TW|C)$", name)
    if mh:
        name, hint = mh.group(1), mh.group(2)
    return {"nr": int(m.group(1)), "name": name, "hint": hint}


def parse(text: str) -> dict:
    lines = text.splitlines()
    layout = any("   " in ln for ln in lines)  # pdftotext -layout: Spalten durch viele Leerzeichen
    out = {"team": None, "fsv_side": None, "home": None, "away": None, "date": None, "time": None,
           "venue": None, "competition": None, "startelf": [], "bank": [], "warnings": []}

    head = "\n".join(lines[:14])
    m = re.search(r"Spielbericht\s+(.+?)\s+Nr\.", head)
    if m:
        comp = re.sub(r"\s+", " ", m.group(1)).strip()
        comp = re.sub(r"^(?:[A-C]-Klasse|Kreisliga|Bezirksliga|Kreispokal)\s+Herren\s+", "", comp)
        out["competition"] = comp
    m = re.search(r"am:\s*(\d\d\.\d\d\.\d{4})", head)
    if m:
        out["date"] = m.group(1)
    m = re.search(r"um:\s*(\d\d:\d\d)", head)
    if m:
        out["time"] = m.group(1)
    for ln in lines[:10]:
        mm = re.match(r"^(\S.*?)\s+um:", ln)
        if mm:
            out["venue"] = mm.group(1).strip()
            break

    for ln in lines:
        m = re.search(r"Heim:\s*(.+?)\s+Gast:\s*(.+?)\s*$", ln)
        if m:
            out["home"], out["away"] = m.group(1).strip(), m.group(2).strip()
            break
    if not out["home"]:
        raise SystemExit("Heim/Gast-Zeile nicht gefunden")

    def is_fsv(name):
        return "osthofen" in name.lower()

    if is_fsv(out["home"]):
        out["fsv_side"], fsv_name = "home", out["home"]
    elif is_fsv(out["away"]):
        out["fsv_side"], fsv_name = "away", out["away"]
    else:
        raise SystemExit("FSV Osthofen kommt im Spielbericht nicht vor")
    out["team"] = "2" if re.search(r"\bII\b|\b2\b", fsv_name) else "1"
    want = 0 if out["fsv_side"] == "home" else 1

    section = None
    last_nr = {"start": [0, 0], "bank": [0, 0]}
    count = {"start": [0, 0], "bank": [0, 0]}
    for ln in lines:
        s = ln.strip()
        if re.match(r"^Nr\.\s+Name", s):
            section = "start"
            continue
        if s.startswith("Auswechselspieler"):
            section = "bank"
            continue
        if section and (s.startswith("Bestätigt") or s.startswith("Trainer")):
            break
        if not section or not s:
            continue
        ms = list(PLAYER.finditer(ln))
        if not ms:
            continue
        if len(ms) >= 2:
            sides = [(0, ms[0]), (1, ms[1])]
        else:
            m0 = ms[0]
            if layout:
                side = 1 if m0.start() > len(ln) * 0.45 else 0
            else:
                nr = int(m0.group(1))
                # Listen sind je Seite aufsteigend nummeriert: Seite, auf der nr noch passt
                ok = [i for i in (0, 1) if nr > last_nr[section][i]]
                if len(ok) == 1:
                    side = ok[0]
                else:
                    # beide möglich -> die Seite mit weniger Einträgen ist wahrscheinlicher
                    side = 0 if count[section][0] <= count[section][1] else 1
                    out["warnings"].append(f"Zuordnung unsicher: {mk(m0)['name']} (Nr. {nr}) -> {'Heim' if side == 0 else 'Gast'}")
            sides = [(side, m0)]
        for side, mm in sides:
            p = mk(mm)
            last_nr[section][side] = p["nr"]
            count[section][side] += 1
            if side == want:
                out["startelf" if section == "start" else "bank"].append(p)

    if len(out["startelf"]) != 11:
        out["warnings"].append(f"{len(out['startelf'])} Startelf-Spieler erkannt (erwartet 11)")
    return out


if __name__ == "__main__":
    print(json.dumps(parse(load_text(sys.argv[1])), ensure_ascii=False, indent=1))
