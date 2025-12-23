# Create Python UV App

Erstelle eine neue UV-basierte Python-Anwendung in diesem Repository.

## Aufgaben

1. **Verzeichnisstruktur anlegen** (falls nicht vorhanden):
   - `Anforderungen/` - Hier werden Anforderungsdokumente für neue Apps abgelegt
   - `Apps/` - Hier liegen die fertigen UV-Single-File-Scripts

2. **README.md aktualisieren** mit folgender Struktur:
   ```markdown
   # [Repository Name]

   Dieses Repository enthält UV-basierte Python-Anwendungen als Single-File-Scripts.

   ## Struktur

   - **Anforderungen/** - Anforderungsdokumente für neue Apps (Markdown-Dateien)
   - **Apps/** - Fertige UV-Single-File-Scripts

   ## Verwendung

   ### App ausführen

   ```bash
   uv run Apps/<app-name>.py
   ```

   ### Neue App erstellen

   1. Anforderungsdokument in `Anforderungen/` anlegen
   2. App in `Apps/` implementieren

   ## Apps

   | App | Beschreibung |
   |-----|--------------|
   | *noch keine Apps* | |

   ## UV Single-File Script Format

   Jede App ist ein einzelnes Python-Script mit eingebetteten Abhängigkeiten:

   ```python
   #!/usr/bin/env python3
   # /// script
   # requires-python = ">=3.11"
   # dependencies = [
   #     "package1",
   #     "package2>=1.0",
   # ]
   # ///

   """
   App-Beschreibung hier.
   """

   # Code hier...
   ```
   ```

3. **Frage den Benutzer** nach dem Namen und Zweck der ersten App (optional)

4. **Wenn eine App erstellt werden soll**, lege folgende Dateien an:
   - `Anforderungen/<app-name>.md` - Anforderungsdokument
   - `Apps/<app-name>.py` - Das UV-Single-File-Script mit dem Standard-Header

## UV Single-File Script Template

```python
#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
# ]
# ///

"""
[App-Beschreibung]

Anforderungen: siehe ../Anforderungen/[app-name].md
"""

def main():
    pass

if __name__ == "__main__":
    main()
```

## Anforderungsdokument Template

```markdown
# [App-Name]

## Zweck

[Was soll die App tun?]

## Funktionale Anforderungen

- [ ] Anforderung 1
- [ ] Anforderung 2

## Technische Anforderungen

- Python >= 3.11
- Abhängigkeiten: [Liste]

## Verwendung

```bash
uv run Apps/[app-name].py [argumente]
```

## Beispiele

[Beispielaufrufe und erwartete Ausgaben]
```
