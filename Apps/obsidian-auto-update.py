#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
Automatischer Verbesserungsprozess für Obsidian-Dateien.

Wählt zufällig eine Markdown-Datei aus einem Obsidian-Vault aus und markiert
sie zur Aktualisierung durch Claude, sofern bestimmte Kriterien erfüllt sind.

Anforderungen: siehe ../Anforderungen/obsidian-auto-update.md
"""

import argparse
import os
import random
import re
import time
from datetime import datetime
from pathlib import Path


def timestamp() -> str:
    """Gibt den aktuellen Zeitstempel formatiert zurück."""
    return datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")


def collect_markdown_files(root_path: Path) -> list[Path]:
    """Sammelt alle gültigen Markdown-Dateien rekursiv."""
    md_files = []

    for dirpath, dirnames, filenames in os.walk(root_path):
        # Verzeichnisse, die mit . beginnen, aus der Suche ausschließen
        dirnames[:] = [d for d in dirnames if not d.startswith('.')]

        for filename in filenames:
            # Dateien überspringen, die mit . beginnen
            if filename.startswith('.'):
                continue

            # Nur .md-Dateien
            if not filename.lower().endswith('.md'):
                continue

            # Dateien mit "Prompt" oder "Goal" im Namen überspringen
            if 'Prompt' in filename or 'Goal' in filename:
                continue

            md_files.append(Path(dirpath) / filename)

    return md_files


def check_file(file_path: Path) -> str:
    """
    Prüft eine Datei und gibt den Status zurück.

    Returns:
        'skip' - Datei soll übersprungen werden
        'delete' - Datei ist leer und soll gelöscht werden
        'mark' - Datei soll markiert werden
    """
    try:
        content = file_path.read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError):
        return 'skip'

    # Leere Datei → löschen
    if not content.strip():
        return 'delete'

    # Wenn "claude!" in der Datei steht → überspringen
    if 'claude!' in content:
        return 'skip'

    # Wenn "Leitfragen" als Wort in der Datei steht → überspringen
    if re.search(r'\bLeitfragen\b', content):
        return 'skip'

    return 'mark'


def mark_file_for_update(file_path: Path) -> bool:
    """Fügt den Update-Marker am Ende der Datei ein."""
    try:
        content = file_path.read_text(encoding='utf-8')

        # Marker am Ende einfügen
        marker = "\n\nBitte aktualisiere diesen Artikel claude!"
        new_content = content.rstrip() + marker + "\n"

        file_path.write_text(new_content, encoding='utf-8')
        return True
    except (OSError, UnicodeDecodeError) as e:
        print(f"Fehler beim Schreiben: {e}")
        return False


def delete_file(file_path: Path) -> bool:
    """Löscht eine leere Datei."""
    try:
        file_path.unlink()
        return True
    except OSError as e:
        print(f"{timestamp()} Fehler beim Löschen: {e}")
        return False


def process_once(root_path: Path) -> bool:
    """Führt einen Durchlauf aus. Gibt True zurück, wenn eine Aktion durchgeführt wurde."""
    md_files = collect_markdown_files(root_path)

    if not md_files:
        print(f"{timestamp()} Keine gültigen Markdown-Dateien gefunden.")
        return False

    # Zufällige Reihenfolge für die Suche
    random.shuffle(md_files)

    for file_path in md_files:
        status = check_file(file_path)

        if status == 'skip':
            continue

        if status == 'delete':
            print(f"{timestamp()} Lösche leere Datei: {file_path}")
            if delete_file(file_path):
                return True
            continue

        # status == 'mark'
        print(f"{timestamp()} Markiere: {file_path}")
        if mark_file_for_update(file_path):
            return True

    print(f"{timestamp()} Keine Datei gefunden, die markiert werden muss.")
    return False


def main():
    parser = argparse.ArgumentParser(
        description='Automatischer Verbesserungsprozess für Obsidian-Dateien'
    )
    parser.add_argument(
        'vault_path',
        type=Path,
        help='Pfad zum Obsidian-Vault'
    )
    parser.add_argument(
        '--interval',
        type=int,
        default=300,
        help='Intervall zwischen Durchläufen in Sekunden (Standard: 300 = 5 Minuten)'
    )
    parser.add_argument(
        '--once',
        action='store_true',
        help='Nur einmal ausführen, nicht wiederholen'
    )

    args = parser.parse_args()

    if not args.vault_path.is_dir():
        print(f"{timestamp()} Fehler: {args.vault_path} ist kein gültiges Verzeichnis")
        return 1

    print(f"{timestamp()} Überwache: {args.vault_path}")
    print(f"{timestamp()} Intervall: {args.interval} Sekunden")

    if args.once:
        process_once(args.vault_path)
    else:
        print(f"{timestamp()} Drücke Strg+C zum Beenden")
        try:
            while True:
                process_once(args.vault_path)
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print(f"\n{timestamp()} Beendet.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
