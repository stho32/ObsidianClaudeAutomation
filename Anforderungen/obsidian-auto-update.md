# obsidian-auto-update

## Zweck

Automatischer Verbesserungsprozess für Obsidian-Dateien. Die App wählt zufällig eine Markdown-Datei aus einem Obsidian-Vault aus und markiert sie zur Aktualisierung durch Claude, sofern sie nicht bereits markiert ist oder bestimmte Ausschlusskriterien erfüllt.

## Funktionale Anforderungen

- [x] Rekursives Durchsuchen eines Verzeichnisses nach .md-Dateien
- [x] Ignorieren von Verzeichnissen, die mit `.` beginnen (z.B. `.obsidian`, `.git`)
- [x] Ignorieren von Dateien, die mit `.` beginnen
- [x] Zufällige Auswahl einer Markdown-Datei
- [x] Prüfung: Wenn `claude!` in der Datei steht → nichts tun
- [x] Prüfung: Wenn "Leitfragen" als Wort in der Datei steht → nichts tun
- [x] Prüfung: Wenn Dateiname "Prompt" oder "Goal" enthält → nichts tun
- [x] Andernfalls: Text "Bitte aktualisiere diesen Artikel claude!" am Ende der Datei einfügen
- [x] Wiederholung alle 5 Minuten

## Technische Anforderungen

- Python >= 3.11
- Keine externen Abhängigkeiten (nur Standardbibliothek)

## Verwendung

```bash
uv run Apps/obsidian-auto-update.py /pfad/zum/obsidian/vault
```

### Optionale Parameter

- `--interval SEKUNDEN` - Intervall zwischen Durchläufen (Standard: 300 = 5 Minuten)
- `--once` - Nur einmal ausführen, nicht wiederholen

## Beispiele

```bash
# Standard: alle 5 Minuten eine Datei markieren
uv run Apps/obsidian-auto-update.py ~/Documents/MyVault

# Alle 10 Minuten
uv run Apps/obsidian-auto-update.py ~/Documents/MyVault --interval 600

# Nur einmal ausführen (zum Testen)
uv run Apps/obsidian-auto-update.py ~/Documents/MyVault --once
```

## Zusammenspiel mit file-watcher

Diese App arbeitet zusammen mit dem file-watcher:
1. `obsidian-auto-update` fügt "claude!" in zufällige Dateien ein
2. Der `file-watcher` erkennt die Änderung und führt Claude aus
3. Claude aktualisiert/verbessert den Artikel
