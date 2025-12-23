#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "watchdog>=4.0.0",
# ]
# ///

"""
File Watcher für Claude-Automatisierung.

Überwacht einen Ordner und alle Unterordner auf Dateiänderungen.
Wenn eine Datei den Marker 'claude!' enthält, wird asynchron ein
Claude-Befehl ausgeführt.

Anforderungen: siehe ../Anforderungen/file-watcher.md
"""

import argparse
import logging
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

# Logging-Konfiguration
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    stream=sys.stdout,
)
logger = logging.getLogger('file-watcher')


class ClaudeMarkerHandler(FileSystemEventHandler):
    """Handler für Dateiänderungen, der nach claude! Markern sucht."""

    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.processing: set[str] = set()  # Verhindert doppelte Verarbeitung
        self.process_count = 0
        logger.info(f"ClaudeMarkerHandler initialisiert für: {base_path}")

    def on_modified(self, event):
        logger.debug(f"Event: MODIFIED | Verzeichnis: {event.is_directory} | Pfad: {event.src_path}")
        if not event.is_directory:
            self._handle_file_change(event.src_path, event_type="MODIFIED")

    def on_created(self, event):
        logger.debug(f"Event: CREATED | Verzeichnis: {event.is_directory} | Pfad: {event.src_path}")
        if not event.is_directory:
            self._handle_file_change(event.src_path, event_type="CREATED")

    def on_deleted(self, event):
        logger.debug(f"Event: DELETED | Verzeichnis: {event.is_directory} | Pfad: {event.src_path}")

    def on_moved(self, event):
        logger.debug(f"Event: MOVED | Von: {event.src_path} | Nach: {event.dest_path}")

    def _handle_file_change(self, file_path: str, event_type: str):
        """Verarbeitet eine Dateiänderung."""
        path = Path(file_path)

        # Verhindere doppelte Verarbeitung
        if file_path in self.processing:
            logger.debug(f"ÜBERSPRUNGEN: Datei wird bereits verarbeitet: {path.name}")
            return

        # Ignoriere versteckte Dateien und Ordner
        if any(part.startswith('.') for part in path.parts):
            logger.debug(f"ÜBERSPRUNGEN: Versteckte Datei/Ordner: {path.name}")
            return

        # Prüfe Dateigröße
        try:
            file_size = path.stat().st_size
            logger.debug(f"Dateigröße: {file_size} Bytes | Datei: {path.name}")
        except (OSError, FileNotFoundError) as e:
            logger.warning(f"Kann Dateigröße nicht lesen: {path.name} | Fehler: {e}")
            return

        # Ignoriere sehr große Dateien (> 10 MB)
        if file_size > 10 * 1024 * 1024:
            logger.debug(f"ÜBERSPRUNGEN: Datei zu groß ({file_size} Bytes): {path.name}")
            return

        # Versuche Dateiinhalt zu lesen
        logger.debug(f"Lese Dateiinhalt: {path.name}")
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            logger.debug(f"Datei erfolgreich gelesen: {len(content)} Zeichen | Datei: {path.name}")
        except UnicodeDecodeError:
            logger.debug(f"ÜBERSPRUNGEN: Keine Textdatei (UnicodeDecodeError): {path.name}")
            return
        except PermissionError:
            logger.warning(f"ÜBERSPRUNGEN: Keine Leseberechtigung: {path.name}")
            return
        except FileNotFoundError:
            logger.debug(f"ÜBERSPRUNGEN: Datei nicht mehr vorhanden: {path.name}")
            return
        except Exception as e:
            logger.error(f"Unerwarteter Fehler beim Lesen: {path.name} | Fehler: {e}")
            return

        # Prüfe auf claude! Marker
        if 'claude!' not in content:
            logger.debug(f"Kein 'claude!' Marker gefunden in: {path.name}")
            return

        # Marker gefunden!
        logger.info(f"{'='*60}")
        logger.info(f"MARKER GEFUNDEN: 'claude!' in Datei: {file_path}")
        logger.info(f"Event-Typ: {event_type}")

        # Zeige Kontext um den Marker
        marker_pos = content.find('claude!')
        context_start = max(0, marker_pos - 50)
        context_end = min(len(content), marker_pos + 150)
        context = content[context_start:context_end].replace('\n', '\\n')
        logger.info(f"Kontext: ...{context}...")

        # Berechne relativen Pfad
        try:
            rel_path = path.relative_to(self.base_path)
            logger.debug(f"Relativer Pfad: {rel_path}")
        except ValueError:
            rel_path = path
            logger.warning(f"Konnte keinen relativen Pfad berechnen, verwende absoluten Pfad: {path}")

        # Markiere als in Bearbeitung
        self.processing.add(file_path)
        self.process_count += 1
        process_id = self.process_count
        logger.info(f"Prozess #{process_id} gestartet | Aktive Prozesse: {len(self.processing)}")

        # Starte Claude asynchron
        self._run_claude_async(str(rel_path), file_path, process_id)

    def _run_claude_async(self, rel_path: str, abs_path: str, process_id: int):
        """Führt Claude asynchron aus."""
        command = (
            f"Lies die Datei '{rel_path}' und suche nach dem Marker 'claude!'. "
            f"Führe den Befehl aus, der direkt nach 'claude!' steht. "
            f"Nach erfolgreicher Ausführung, entferne den 'claude!' Marker und den zugehörigen Befehl aus der Datei."
        )

        logger.info(f"[Prozess #{process_id}] Starte Claude CLI...")
        logger.debug(f"[Prozess #{process_id}] Arbeitsverzeichnis: {self.base_path}")
        logger.debug(f"[Prozess #{process_id}] Zieldatei: {rel_path}")
        logger.debug(f"[Prozess #{process_id}] Befehl an Claude: {command[:100]}...")

        start_time = datetime.now()

        try:
            # Starte Claude als asynchronen Prozess
            logger.debug(f"[Prozess #{process_id}] Führe subprocess.Popen aus...")
            process = subprocess.Popen(
                [
                    "claude",
                    "--dangerously-skip-permissions",
                    "-p",
                    command,
                ],
                cwd=str(self.base_path),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            logger.info(f"[Prozess #{process_id}] Claude gestartet mit PID: {process.pid}")

            # Starte einen Thread, um auf das Ende zu warten und aufzuräumen
            def cleanup():
                logger.debug(f"[Prozess #{process_id}] Warte auf Beendigung von Claude (PID: {process.pid})...")
                stdout, stderr = process.communicate()
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()

                self.processing.discard(abs_path)

                logger.info(f"[Prozess #{process_id}] {'='*40}")
                logger.info(f"[Prozess #{process_id}] Claude beendet")
                logger.info(f"[Prozess #{process_id}] PID: {process.pid}")
                logger.info(f"[Prozess #{process_id}] Exit-Code: {process.returncode}")
                logger.info(f"[Prozess #{process_id}] Dauer: {duration:.2f} Sekunden")
                logger.info(f"[Prozess #{process_id}] Datei: {rel_path}")

                if stdout:
                    logger.info(f"[Prozess #{process_id}] STDOUT ({len(stdout)} Zeichen):")
                    for line in stdout.strip().split('\n')[:20]:  # Max 20 Zeilen
                        logger.info(f"[Prozess #{process_id}]   > {line}")
                    if stdout.count('\n') > 20:
                        logger.info(f"[Prozess #{process_id}]   ... ({stdout.count(chr(10)) - 20} weitere Zeilen)")

                if stderr:
                    logger.warning(f"[Prozess #{process_id}] STDERR ({len(stderr)} Zeichen):")
                    for line in stderr.strip().split('\n')[:10]:  # Max 10 Zeilen
                        logger.warning(f"[Prozess #{process_id}]   ! {line}")

                if process.returncode != 0:
                    logger.error(f"[Prozess #{process_id}] Claude beendet mit Fehler (Exit-Code: {process.returncode})")
                else:
                    logger.info(f"[Prozess #{process_id}] Claude erfolgreich abgeschlossen")

                logger.info(f"[Prozess #{process_id}] Aktive Prozesse: {len(self.processing)}")
                logger.info(f"[Prozess #{process_id}] {'='*40}")

            thread = threading.Thread(target=cleanup, daemon=True, name=f"claude-cleanup-{process_id}")
            thread.start()
            logger.debug(f"[Prozess #{process_id}] Cleanup-Thread gestartet: {thread.name}")

        except FileNotFoundError:
            logger.error(f"[Prozess #{process_id}] FEHLER: 'claude' Befehl nicht gefunden!")
            logger.error(f"[Prozess #{process_id}] Ist Claude CLI installiert? (npm install -g @anthropic-ai/claude-code)")
            self.processing.discard(abs_path)
        except Exception as e:
            logger.error(f"[Prozess #{process_id}] Unerwarteter Fehler beim Starten von Claude: {e}")
            logger.exception(f"[Prozess #{process_id}] Stack-Trace:")
            self.processing.discard(abs_path)


def main():
    parser = argparse.ArgumentParser(
        description="Überwacht einen Ordner auf Dateiänderungen und führt Claude-Befehle aus."
    )
    parser.add_argument(
        "path",
        type=str,
        help="Der zu überwachende Ordner",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Aktiviert DEBUG-Level Logging",
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Nur Warnungen und Fehler anzeigen",
    )

    args = parser.parse_args()

    # Log-Level anpassen
    if args.verbose:
        logger.setLevel(logging.DEBUG)
        logger.debug("Verbose-Modus aktiviert (DEBUG)")
    elif args.quiet:
        logger.setLevel(logging.WARNING)
    else:
        logger.setLevel(logging.INFO)

    watch_path = Path(args.path).resolve()

    logger.info("="*60)
    logger.info("FILE-WATCHER für Claude-Automatisierung")
    logger.info("="*60)
    logger.info(f"Startzeit: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Python-Version: {sys.version}")
    logger.info(f"Überwachter Pfad: {watch_path}")

    if not watch_path.exists():
        logger.error(f"Pfad existiert nicht: {watch_path}")
        sys.exit(1)

    if not watch_path.is_dir():
        logger.error(f"Pfad ist kein Ordner: {watch_path}")
        sys.exit(1)

    # Zeige Ordnerstatistik
    try:
        file_count = sum(1 for _ in watch_path.rglob('*') if _.is_file())
        dir_count = sum(1 for _ in watch_path.rglob('*') if _.is_dir())
        logger.info(f"Ordnerinhalt: {file_count} Dateien, {dir_count} Unterordner")
    except Exception as e:
        logger.warning(f"Konnte Ordnerstatistik nicht ermitteln: {e}")

    logger.info("-"*60)
    logger.info("Warte auf Dateiänderungen...")
    logger.info("Drücke Ctrl+C zum Beenden")
    logger.info("-"*60)

    event_handler = ClaudeMarkerHandler(watch_path)
    observer = Observer()
    observer.schedule(event_handler, str(watch_path), recursive=True)

    logger.debug(f"Observer erstellt: {observer}")
    logger.debug(f"Rekursive Überwachung: Ja")

    observer.start()
    logger.info("Observer gestartet - Überwachung aktiv")

    try:
        while True:
            observer.join(timeout=1)
    except KeyboardInterrupt:
        logger.info("")
        logger.info("="*60)
        logger.info("BEENDEN angefordert (Ctrl+C)")
        logger.info(f"Beendigungszeit: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Verarbeitete Prozesse: {event_handler.process_count}")
        logger.info(f"Noch aktive Prozesse: {len(event_handler.processing)}")

        if event_handler.processing:
            logger.warning("Warte auf Beendigung aktiver Claude-Prozesse...")
            for path in event_handler.processing:
                logger.warning(f"  - {path}")

        observer.stop()
        logger.info("Observer gestoppt")

    observer.join()
    logger.info("File-Watcher beendet")
    logger.info("="*60)


if __name__ == "__main__":
    main()
