/**
 * FSV 03 Osthofen – Spielbericht-PDFs automatisch aus Gmail in Google Drive ablegen.
 *
 * Einrichtung (einmalig, ca. 5 Minuten) – im Google-Konto, das die Aufstellungs-Mails EMPFÄNGT:
 *   1. https://script.google.com öffnen → „Neues Projekt“.
 *   2. Diesen Code komplett in die Datei Code.gs einfügen, Projekt z. B. „FSV Aufstellung“ nennen, speichern.
 *   3. Oben die Funktion `saveSpielberichte` auswählen → „Ausführen“ → Berechtigungen bestätigen
 *      (Gmail lesen/Labels, Drive schreiben). Beim ersten Lauf wird der Drive-Ordner „FSV Aufstellung“ angelegt.
 *   4. Links „Trigger“ (Wecker-Symbol) → „Trigger hinzufügen“: Funktion saveSpielberichte,
 *      Ereignisquelle „Zeitgesteuert“, „Minuten-Timer“, „Alle 5 Minuten“ → speichern.
 *   5. Falls das Konto NICHT info@fsv-osthofen.de ist: den Ordner „FSV Aufstellung“ in Drive
 *      mit info@fsv-osthofen.de teilen (Rolle „Betrachter“ reicht).
 *
 * Danach landet jede PDF aus Mails mit „Aufstellung“ oder „Spielbericht“ im Betreff innerhalb von
 * 5 Minuten im Ordner – die Mail bekommt das Label „FSV/Aufstellung-gespeichert“.
 */
var FOLDER_NAME = 'FSV Aufstellung';
var DONE_LABEL = 'FSV/Aufstellung-gespeichert';
var QUERY = '(subject:Aufstellung OR subject:Spielbericht OR filename:Spielbericht) has:attachment filename:pdf newer_than:3d -label:' + DONE_LABEL.replace('/', '-');

function saveSpielberichte() {
  var folder = getOrCreateFolder_(FOLDER_NAME);
  var label = GmailApp.getUserLabelByName(DONE_LABEL) || GmailApp.createLabel(DONE_LABEL);
  var threads = GmailApp.search(QUERY, 0, 20);
  threads.forEach(function (thread) {
    thread.getMessages().forEach(function (msg) {
      var saved = 0;
      msg.getAttachments({ includeInlineImages: false, includeAttachments: true }).forEach(function (att) {
        if (att.getContentType() !== 'application/pdf' && !/\.pdf$/i.test(att.getName())) return;
        var stamp = Utilities.formatDate(msg.getDate(), 'Europe/Berlin', 'yyyy-MM-dd_HHmm');
        var name = stamp + '_' + att.getName().replace(/[^\w.\-]+/g, '_');
        if (folder.getFilesByName(name).hasNext()) return; // schon da
        folder.createFile(att.copyBlob().setName(name));
        saved++;
      });
      if (saved > 0) Logger.log('Gespeichert: ' + saved + ' PDF(s) aus „' + msg.getSubject() + '“');
    });
    thread.addLabel(label);
  });
}

function getOrCreateFolder_(name) {
  var it = DriveApp.getFoldersByName(name);
  return it.hasNext() ? it.next() : DriveApp.createFolder(name);
}
