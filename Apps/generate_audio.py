#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "openai>=1.0.0",
# ]
# ///

"""
Generiert Audio-Dateien für den File-Watcher mit OpenAI TTS API.

Erstellt zwei MP3-Dateien:
- process_started.mp3: "Prozess gestartet"
- process_completed.mp3: "Prozess abgeschlossen"

Benötigt: OPENAI_API_KEY Umgebungsvariable
"""

import os
import sys
from pathlib import Path

from openai import OpenAI


def generate_audio(text: str, output_path: Path, voice: str = "onyx") -> None:
    """Generiert eine Audio-Datei mit OpenAI TTS."""
    client = OpenAI()

    response = client.audio.speech.create(
        model="tts-1",
        voice=voice,
        input=text,
    )

    response.stream_to_file(str(output_path))
    print(f"Audio generiert: {output_path}")


def main():
    # Prüfe API-Key
    if not os.getenv("OPENAI_API_KEY"):
        print("Fehler: OPENAI_API_KEY Umgebungsvariable nicht gesetzt!")
        sys.exit(1)

    # Audio-Verzeichnis
    audio_dir = Path(__file__).parent / "audio"
    audio_dir.mkdir(exist_ok=True)

    # Generiere Audio-Dateien
    audio_files = [
        ("Prozess gestartet", "process_started.mp3"),
        ("Prozess abgeschlossen", "process_completed.mp3"),
    ]

    for text, filename in audio_files:
        output_path = audio_dir / filename
        print(f"Generiere: '{text}' -> {filename}")
        generate_audio(text, output_path)

    print("\nAlle Audio-Dateien wurden erfolgreich generiert!")
    print(f"Speicherort: {audio_dir}")


if __name__ == "__main__":
    main()
