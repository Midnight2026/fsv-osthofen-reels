#!/usr/bin/env python3
"""Baut aus einer geparsten Aufstellung (JSON von parse_spielbericht.py) das
Aufstellungs-Reel (1080x1920) im FSV-Design:

  * <name>.dc.html  – Artboard für den Design-Canvas (Vorlage tools/templates/Aufstellung.dc.html)
  * <name>.png      – fertig gerendertes Bild (Playwright/Chromium)

Aufruf (alle Pfade relativ zum Repo-Root möglich):
  python3 -I tools/build_aufstellung.py \
      --lineup lineup.json \
      --crest tools/crests/tus-offstein.png \
      --crest-blob /_blob/b612ace5a01ea5bd593e3f32cef4db78 \
      --out-dc out/Aufstellung-2-2026-10-11.dc.html \
      --out-png out/FSV03_Aufstellung_11-10-2026_2-Mannschaft.png

--crest-blob ist optional: wenn das Gegnerwappen noch nicht im Canvas hochgeladen
ist, bleibt im .dc.html der Platzhalter /_blob/GEGNER stehen (nach dem Upload ersetzen).
"""
import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, "templates", "Aufstellung.dc.html")
ASSETS = os.path.join(HERE, "assets")

FSV_LOGO_BLOB = "/_blob/67e41d99804ea8781c08ab74a7d6b71f"
TEMPLATE_OPP_BLOB = "/_blob/c6b7ec256780292d023f239a31bb6516"  # TuS Wörrstadt in der Vorlage
SPONSOR_BLOBS = {
    "/_blob/9c4793158db0f868ad78f2183aae0cd9": "sponsor-mbl.png",
    "/_blob/9284c71dcef85035b2a56c43a5031d03": "sponsor-rheinhessen-bau.png",
    "/_blob/74f586ada2ca2cb8d6f365df03a0aa6d": "sponsor-dogan.png",
}
WEEKDAYS = ["Mo.", "Di.", "Mi.", "Do.", "Fr.", "Sa.", "So."]


def league_label(comp: str) -> str:
    c = (comp or "").lower()
    if "pokal" in c:
        return "Kreispokal Alzey-Worms"
    for k in ("A-Klasse", "B-Klasse", "C-Klasse", "Kreisliga", "Bezirksliga"):
        if k.lower() in c:
            return f"{k} Alzey-Worms"
    return comp or ""


def fsv_display(team: str) -> str:
    return "FSV 03 Osthofen II" if team == "2" else "FSV 03 Osthofen"


def player_label(p: dict) -> str:
    return f"{p['name']} ({p['hint']})" if p.get("hint") else p["name"]


def build(lineup: dict, crest_png: str, crest_blob: str | None, out_dc: str, out_png: str | None, kickoff: str | None):
    tpl = open(TEMPLATE, encoding="utf-8").read()
    team = lineup["team"]
    is_home = lineup["fsv_side"] == "home"
    opp = lineup["away"] if is_home else lineup["home"]

    if not kickoff:
        d = dt.datetime.strptime(lineup["date"], "%d.%m.%Y").date()
        kickoff = f"{WEEKDAYS[d.weekday()]} {lineup['time']}"

    props = {
        "league": league_label(lineup.get("competition")),
        "team": "2. Mannschaft" if team == "2" else "1. Mannschaft",
        "numeral": "II" if team == "2" else "I",
        "subline": "Heimspiel" if is_home else "Auswärtsspiel",
        "kickoff": kickoff,
        "home": fsv_display(team) if is_home else opp,
        "away": opp if is_home else fsv_display(team),
        "title1": "Startelf",
        "title2": "Ersatzbank",
    }
    start = lineup["startelf"][:11]
    for i in range(11):
        p = start[i] if i < len(start) else None
        props[f"s{i+1}n"] = str(p["nr"]) if p else ""
        props[f"s{i+1}"] = player_label(p) if p else ""
    bank = lineup["bank"][:7]
    for i, p in enumerate(bank):
        props[f"b{i+1}n"] = str(p["nr"])
        props[f"b{i+1}"] = player_label(p)

    # --- Ersatzbank-Zeilen dynamisch (Anzahl = Bankspieler) ---
    a = tpl.index("<!-- BANK-START -->") + len("<!-- BANK-START -->")
    b = tpl.index("<!-- BANK-END -->")
    block = tpl[a:b]
    rows = re.findall(r"\s*<div style=\"display: flex; align-items: center; gap: 12px; height: 32px\">.*?</div>\s*</div>", block, flags=re.S)
    assert rows, "Bank-Zeilen in Vorlage nicht gefunden"
    row_tpl = rows[0]
    head = block[: block.index(rows[0])]
    new_rows = "".join(row_tpl.replace("{{b1n}}", f"{{{{b{i+1}n}}}}").replace("{{b1}}", f"{{{{b{i+1}}}}}") for i in range(len(bank)))
    tpl = tpl[:a] + head + new_rows + "\n      " + tpl[b:]

    # --- Paarung: bei Auswärtsspiel Gegner links, FSV rechts (wie Spieltag-Reels) ---
    if not is_home:
        pa = tpl.index("<!-- Paarung -->")
        pb = tpl.index("<!-- Aufstellung -->")
        pair = tpl[pa:pb]
        cols = re.findall(r"    <div style=\"display: flex; flex-direction: column; align-items: center; gap: 16px\">.*?\n    </div>\n", pair, flags=re.S)
        assert len(cols) == 2, "Paarungsspalten nicht gefunden"
        left, right = cols
        # Spalte 1 enthält {{home}}, Spalte 2 {{away}} – Inhalte tauschen, Platzhalter behalten
        new_left = right.replace("{{away}}", "{{home}}")
        new_right = left.replace("{{home}}", "{{away}}")
        pair = pair.replace(left, "\x00L\x00").replace(right, "\x00R\x00").replace("\x00L\x00", new_left).replace("\x00R\x00", new_right)
        tpl = tpl[:pa] + pair + tpl[pb:]

    # --- Gegnerwappen-Blob + alt-Text ---
    tpl = tpl.replace(TEMPLATE_OPP_BLOB, crest_blob or "/_blob/GEGNER")
    tpl = tpl.replace('alt="TuS Wörrstadt"', f'alt="{opp}"')

    # --- Defaults in data-props und renderVals setzen ---
    m = re.search(r"data-props='([^']*)'", tpl)
    dp = json.loads(m.group(1))
    for k, v in props.items():
        if k in dp:
            dp[k]["default"] = v
        else:
            dp[k] = {"editor": "text", "default": v}
    for k in list(dp):
        if re.match(r"^b\d+n?$", k) and k not in props:
            del dp[k]
    tpl = tpl[: m.start(1)] + json.dumps(dp, ensure_ascii=False).replace("'", "&#39;") + tpl[m.end(1):]

    def rv(mm):
        body = "\n".join(f"{k}: p.{k} ?? {json.dumps(v, ensure_ascii=False)}," for k, v in {"accent": "#F0141E", **props, "sponsorlabel": "Unsere Hauptsponsoren"}.items())
        return "renderVals() {\nconst p = this.props;\nreturn {\n" + body.rstrip(",") + "\n};\n}"
    tpl = re.sub(r"renderVals\(\) \{.*?\n\};\n\}", rv, tpl, flags=re.S)

    d = dt.datetime.strptime(lineup["date"], "%d.%m.%Y").date()
    tpl = re.sub(r"<title>.*?</title>", f"<title>Aufstellung {d.day}.{d.month}. – {props['team']}</title>", tpl)

    os.makedirs(os.path.dirname(os.path.abspath(out_dc)), exist_ok=True)
    open(out_dc, "w", encoding="utf-8").write(tpl)
    print("DC geschrieben:", out_dc)

    if out_png:
        render(tpl, props, crest_png, crest_blob or "/_blob/GEGNER", out_png)


def render(tpl: str, props: dict, crest_png: str, crest_blob: str, out_png: str):
    body = tpl[tpl.index("<helmet>") + 8: tpl.index("</helmet>")] + tpl[tpl.index("</helmet>") + 9: tpl.index("</x-dc>")]
    vals = {"accent": "#F0141E", "sponsorlabel": "Unsere Hauptsponsoren", **props}
    body = re.sub(r"\{\{(\w+)\}\}", lambda m: str(vals.get(m.group(1), "")), body)
    body = body.replace(FSV_LOGO_BLOB, "file://" + os.path.join(ASSETS, "fsv-osthofen-logo.png"))
    for blob, fn in SPONSOR_BLOBS.items():
        body = body.replace(blob, "file://" + os.path.join(ASSETS, fn))
    body = body.replace(crest_blob, "file://" + os.path.abspath(crest_png))
    tmp = tempfile.mkdtemp()
    html = os.path.join(tmp, "render.html")
    open(html, "w", encoding="utf-8").write('<!doctype html><html><head><meta charset="utf-8"></head><body>' + body + "</body></html>")
    shot = os.path.join(tmp, "shot.png")
    js = os.path.join(tmp, "shot.js")
    open(js, "w").write(
        "const {chromium}=require('playwright');(async()=>{const b=await chromium.launch({executablePath:'/opt/pw-browsers/chromium'});"
        "const p=await b.newPage({viewport:{width:1080,height:1920}});await p.goto('file://" + html + "');"
        "await p.waitForTimeout(3000);await p.screenshot({path:'" + shot + "'});await b.close();})();"
    )
    node_path = os.environ.get("NODE_PATH", "")
    subprocess.run(["node", js], check=True, env={**os.environ, "NODE_PATH": node_path})
    from PIL import Image
    im = Image.open(shot).convert("RGB")
    os.makedirs(os.path.dirname(os.path.abspath(out_png)), exist_ok=True)
    im.save(out_png, optimize=True)
    print("PNG geschrieben:", out_png, im.size)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--lineup", required=True)
    ap.add_argument("--crest", required=True, help="PNG des Gegnerwappens (lokal)")
    ap.add_argument("--crest-blob", default=None, help="/_blob/<id> des Gegnerwappens im Canvas")
    ap.add_argument("--out-dc", required=True)
    ap.add_argument("--out-png", default=None)
    ap.add_argument("--kickoff", default=None, help='z. B. "So. 15:30" (Standard: aus Datum/Uhrzeit des Spielberichts)')
    a = ap.parse_args()
    build(json.load(open(a.lineup, encoding="utf-8")), a.crest, a.crest_blob, a.out_dc, a.out_png, a.kickoff)
