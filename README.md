# FSV 03 Osthofen – Reels

Wöchentliche Instagram-Grafiken (1080 × 1920) für die 1. und 2. Mannschaft.
Übersicht: https://midnight2026.github.io/fsv-osthofen-reels/

## Automatisierungen

| Was | Wann | Quelle |
|---|---|---|
| Wochenübersicht + Spieltag-Reels | montags 07:52 | fussball.de, fsv-osthofen.de/trainingszeiten |
| Aufstellung (Startelf + Ersatzbank) | sonntags alle 30 Min. (10:35–16:05) | DFBnet-Spielbericht-PDF aus der E-Mail „Aufstellung …“ |

## Aufstellung – so läuft es

1. Die E-Mail mit dem Spielbericht-PDF (Betreff „Aufstellung 1. Mannschaft und 2. Mannschaft für Sonntag“,
   ggf. zwei einzelne Mails) kommt im Postfach an.
2. Das Google-Apps-Script `tools/gmail_to_drive.gs` (läuft alle 5 Min. im Postfach) legt jede PDF im
   Drive-Ordner **FSV Aufstellung** ab.
3. Der Sonntags-Task liest neue PDFs aus dem Ordner, parst sie mit `tools/parse_spielbericht.py`,
   baut die Grafik mit `tools/build_aufstellung.py` (Vorlage `tools/templates/Aufstellung.dc.html`),
   legt das PNG unter `img/` ab, trägt es in `index.html` ein und schickt die Links per Mail.
   Verarbeitete Drive-Dateien stehen in `aufstellung/processed.json`.

## Werkzeuge (`tools/`)

```bash
# Spielbericht (PDF oder Text aus Google Drive) → JSON
python3 -I tools/parse_spielbericht.py Spielbericht.pdf > lineup.json

# JSON → Artboard (.dc.html) + fertiges PNG
NODE_PATH=$(npm root -g) python3 -I tools/build_aufstellung.py \
  --lineup lineup.json \
  --crest tools/crests/tus-offstein.png \
  --crest-blob /_blob/b612ace5a01ea5bd593e3f32cef4db78 \
  --out-dc out/Aufstellung-2-2026-10-11.dc.html \
  --out-png out/FSV03_Aufstellung_11-10-2026_2-Mannschaft.png
```

- `tools/assets/` – FSV-Logo und die drei Hauptsponsoren (fest, keine Rotation)
- `tools/crests/` – bereits sauber geladene Gegnerwappen (Dateiname = FuPa-Slug); neue Wappen hier ergänzen
- Bekannte Canvas-Blobs: FSV `/_blob/67e41d99804ea8781c08ab74a7d6b71f`, TuS Wörrstadt `/_blob/c6b7ec256780292d023f239a31bb6516`,
  SV Leiselheim `/_blob/56b4ee75a8525d9e21c59a1f753c012f`, TuS Offstein `/_blob/b612ace5a01ea5bd593e3f32cef4db78`,
  SG Weinheim/Heimersheim `/_blob/64c32a261efd3ebbb2c38617d2d68da8`,
  SG Spiesheim/Albig `/_blob/7d8bc2470853a82e13e6f3bce5b8315c`, SV Normannia Pfiffligheim `/_blob/beb93ca79d427f931efda7790552b87d`
