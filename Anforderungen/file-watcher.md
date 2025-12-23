# file-watcher

## Zweck

Überwacht einen angegebenen Ordner (und alle Unterordner) auf Dateiänderungen. Wenn eine Änderung erkannt wird und die Datei den Marker `claude!` enthält, wird asynchron ein Claude-Befehl ausgeführt.

## Funktionale Anforderungen

- [x] Ordner A wird als Kommandozeilenargument angegeben
- [x] Rekursive Überwachung aller Unterordner von A
- [x] Bei Dateiänderung: Prüfen, ob `claude!` in der Datei vorkommt
- [x] Wenn `claude!` gefunden: Asynchron `claude --dangerously-skip-permissions -p "BEFEHL"` ausführen
- [x] Arbeitsverzeichnis für Claude ist Ordner A
- [x] BEFEHL enthält den relativen Pfad zur geänderten Datei und Anweisung, den `claude!`-Marker zu suchen und auszuführen

## Technische Anforderungen

- Python >= 3.11
- Abhängigkeiten: watchdog (für Dateiüberwachung)

## Marker-Format

Der Marker `claude!` in einer Datei signalisiert, dass Claude einen Befehl ausführen soll. Das erwartete Format:

```
claude! <Befehl hier>
```

## Verwendung

```bash
uv run Apps/file-watcher.py /pfad/zu/ordner/A
```

## Beispiele

### Beispiel-Datei mit Marker

```markdown
# Meine Notiz

claude! Fasse den Inhalt dieser Datei zusammen und speichere die Zusammenfassung in summary.md
```

### Erwartetes Verhalten

1. file-watcher überwacht `/home/user/obsidian-vault`
2. Benutzer ändert `notizen/projekt.md` und fügt `claude!` Marker hinzu
3. file-watcher erkennt die Änderung
4. file-watcher prüft, ob `claude!` in der Datei vorkommt → Ja
5. file-watcher führt asynchron aus:
   ```bash
   claude --dangerously-skip-permissions -p "Suche in der Datei 'notizen/projekt.md' nach 'claude!' und führe den damit verbundenen Befehl aus."
   ```
   mit Arbeitsverzeichnis `/home/user/obsidian-vault`
