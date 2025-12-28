#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "watchdog>=4.0.0",
#     "openai>=1.0.0",
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
import os
import shutil
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

# Globale Konfiguration für TTS
READ_OUTPUT_ENABLED = False

# Logging-Konfiguration
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    stream=sys.stdout,
)
logger = logging.getLogger('file-watcher')

# Audio-Dateien Pfade
AUDIO_DIR = Path(__file__).parent / "audio"
AUDIO_STARTED = AUDIO_DIR / "process_started.mp3"
AUDIO_COMPLETED = AUDIO_DIR / "process_completed.mp3"


def play_audio(audio_file: Path, blocking: bool = False) -> None:
    """Spielt eine Audio-Datei ab.

    Args:
        audio_file: Pfad zur Audio-Datei
        blocking: Wenn True, wartet bis Audio fertig abgespielt ist
    """
    if not audio_file.exists():
        logger.warning(f"Audio-Datei nicht gefunden: {audio_file}")
        return

    def _play():
        try:
            # Versuche verschiedene Audio-Player (Linux)
            players = [
                ["mpv", "--no-video", "--really-quiet", str(audio_file)],
                ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", str(audio_file)],
                ["paplay", str(audio_file)],
                ["aplay", str(audio_file)],
            ]

            for player_cmd in players:
                player = shutil.which(player_cmd[0])
                if player:
                    subprocess.run(
                        player_cmd,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    return

            logger.warning("Kein Audio-Player gefunden (mpv, ffplay, paplay, aplay)")
        except Exception as e:
            logger.debug(f"Fehler beim Abspielen von Audio: {e}")

    if blocking:
        _play()
    else:
        # Starte in separatem Thread um nicht zu blockieren
        threading.Thread(target=_play, daemon=True).start()


def read_text_aloud(text: str) -> None:
    """Liest Text vor mittels OpenAI TTS und löscht die temporäre Audio-Datei danach.

    Args:
        text: Der vorzulesende Text
    """
    if not text or not text.strip():
        logger.debug("Kein Text zum Vorlesen vorhanden")
        return

    # Prüfe ob OPENAI_API_KEY gesetzt ist
    if not os.getenv("OPENAI_API_KEY"):
        logger.warning("OPENAI_API_KEY nicht gesetzt - kann Output nicht vorlesen")
        return

    try:
        from openai import OpenAI
    except ImportError:
        logger.warning("openai-Paket nicht installiert - kann Output nicht vorlesen")
        return

    # Kürze Text wenn nötig (TTS hat Limits)
    max_chars = 4000
    if len(text) > max_chars:
        text = text[:max_chars] + "... (Text gekürzt)"
        logger.info(f"Text für TTS auf {max_chars} Zeichen gekürzt")

    try:
        logger.info("Generiere Audio für Output...")
        client = OpenAI()

        # Erstelle temporäre Datei im tmp-Verzeichnis neben diesem Script
        tmp_dir = Path(__file__).parent / "tmp"
        tmp_dir.mkdir(exist_ok=True)
        tmp_path = tmp_dir / f"tts_output_{os.getpid()}.mp3"

        response = client.audio.speech.create(
            model="tts-1",
            voice="onyx",
            input=text,
        )
        response.stream_to_file(str(tmp_path))

        logger.info("Spiele Output-Audio ab...")
        play_audio(tmp_path, blocking=True)

        # Lösche temporäre Datei
        try:
            tmp_path.unlink()
            logger.debug(f"Temporäre Audio-Datei gelöscht: {tmp_path}")
        except OSError as e:
            logger.warning(f"Konnte temporäre Audio-Datei nicht löschen: {e}")

    except Exception as e:
        logger.error(f"Fehler beim Vorlesen des Outputs: {e}")


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

        # Verhindere doppelte Verarbeitung - keine neuen Prozesse für Dateien mit aktivem Claude-Prozess
        if file_path in self.processing:
            logger.info(f"ÜBERSPRUNGEN: Datei hat bereits einen laufenden Claude-Prozess: {path.name}")
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
            f"Führe den Befehl aus, der direkt nach 'claude!' steht (bis zum Zeilenende oder nächsten Absatz). "
            f"WICHTIG: Nach Ausführung des Befehls MUSST du die gesamte Zeile bzw. den Block mit 'claude!' "
            f"und dem Befehl aus der Datei entfernen, um Endlosschleifen zu verhindern. "
            f"Entferne dabei den kompletten 'claude! <befehl>'-Text, sodass kein 'claude!' mehr in der Datei steht."
        )

        logger.info(f"[Prozess #{process_id}] Starte Claude CLI...")
        logger.debug(f"[Prozess #{process_id}] Arbeitsverzeichnis: {self.base_path}")
        logger.debug(f"[Prozess #{process_id}] Zieldatei: {rel_path}")
        logger.debug(f"[Prozess #{process_id}] Befehl an Claude: {command[:100]}...")

        start_time = datetime.now()

        try:
            # Starte Claude als asynchronen Prozess
            # Finde claude-Executable (kann in verschiedenen Pfaden sein)
            claude_path = shutil.which("claude")
            if not claude_path:
                # Versuche gängige Installationspfade
                home = Path.home()
                possible_paths = [
                    home / ".claude" / "local" / "claude",
                    home / ".local" / "bin" / "claude",
                    home / ".npm-global" / "bin" / "claude",
                    Path("/usr/local/bin/claude"),
                    Path("/usr/bin/claude"),
                ]
                for p in possible_paths:
                    if p.exists():
                        claude_path = str(p)
                        break

            if not claude_path:
                raise FileNotFoundError("claude command not found in PATH or common locations")

            logger.debug(f"[Prozess #{process_id}] Claude gefunden: {claude_path}")
            logger.debug(f"[Prozess #{process_id}] Führe subprocess.Popen aus...")

            # Erweitere PATH um gängige Benutzer-Verzeichnisse
            env = os.environ.copy()
            home = Path.home()
            extra_paths = [
                str(home / ".claude" / "local"),
                str(home / ".local" / "bin"),
                str(home / ".npm-global" / "bin"),
                "/usr/local/bin",
            ]
            env["PATH"] = ":".join(extra_paths) + ":" + env.get("PATH", "")

            process = subprocess.Popen(
                [
                    claude_path,
                    "--dangerously-skip-permissions",
                    "-p",
                    command,
                ],
                cwd=str(self.base_path),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
            )
            logger.info(f"[Prozess #{process_id}] Claude gestartet mit PID: {process.pid}")
            play_audio(AUDIO_STARTED)

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

                play_audio(AUDIO_COMPLETED)

                # Lese Output vor, wenn aktiviert
                if READ_OUTPUT_ENABLED and stdout:
                    read_text_aloud(stdout)

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
    parser.add_argument(
        "--read-output",
        action="store_true",
        help="Liest den Claude-Output nach Prozessende vor (benötigt OPENAI_API_KEY)",
    )

    args = parser.parse_args()

    # Setze globale TTS-Konfiguration
    global READ_OUTPUT_ENABLED
    READ_OUTPUT_ENABLED = args.read_output

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
