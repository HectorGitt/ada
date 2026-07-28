#!/usr/bin/env python3
"""Generate Uche's voice intro with Gemini TTS (Google AI Studio).

Uche is the employer's agent. Produces frontend/public/uche-intro.mp3 in a warm,
confident male Nigerian English voice (mirror of generate-ada-voice.py).

Needs a free AI Studio API key (https://aistudio.google.com/apikey):
    GEMINI_API_KEY=... python scripts/generate-ada-voice.py

Overrides:  ADA_VOICE=Aoede  GEMINI_TTS_MODEL=gemini-2.5-flash-preview-tts
Requires ffmpeg on PATH (or set FFMPEG=/path/to/ffmpeg) to encode PCM -> MP3.
"""
from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

STYLE = "Say warmly and confidently, in a friendly Nigerian English accent, like a seasoned recruiter speaking to a hiring manager"
SCRIPT = (
    "Hello — I'm Uche, your hiring partner. Tell me the role you're filling, and I'll "
    "bring you a shortlist of vetted candidates who actually fit — each one already "
    "assessed, with a clear reason they belong on your desk. No job boards, no noise. "
    "When you're ready to hire, I've already done the searching. Let's find the one."
)

OUT = Path(__file__).resolve().parents[1] / "public" / "uche-intro.mp3"
VOICE = os.environ.get("UCHE_VOICE", "Charon")
MODEL = os.environ.get("GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts")
PCM_RATE = 24000


def main() -> int:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        print("Set GEMINI_API_KEY (https://aistudio.google.com/apikey).", file=sys.stderr)
        return 1
    ffmpeg = os.environ.get("FFMPEG") or shutil.which("ffmpeg")
    if not ffmpeg:
        print("ffmpeg not found. Install it or set FFMPEG=/path/to/ffmpeg.", file=sys.stderr)
        return 1

    payload = json.dumps({
        "contents": [{"parts": [{"text": f"{STYLE}: {SCRIPT}"}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": VOICE}}},
        },
    }).encode()
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}"
        f":generateContent?key={key}"
    )
    try:
        with urllib.request.urlopen(
            urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        ) as resp:
            body = json.load(resp)
    except urllib.error.HTTPError as exc:
        print(f"TTS request failed ({exc.code}): {exc.read().decode()[:500]}", file=sys.stderr)
        return 1

    try:
        pcm = base64.b64decode(body["candidates"][0]["content"]["parts"][0]["inlineData"]["data"])
    except (KeyError, IndexError):
        print(f"Unexpected response: {json.dumps(body)[:500]}", file=sys.stderr)
        return 1

    with tempfile.NamedTemporaryFile(suffix=".pcm", delete=False) as tmp:
        tmp.write(pcm)
        raw = tmp.name
    try:
        subprocess.run(
            [ffmpeg, "-y", "-f", "s16le", "-ar", str(PCM_RATE), "-ac", "1",
             "-i", raw, "-codec:a", "libmp3lame", "-qscale:a", "4", str(OUT)],
            check=True, capture_output=True,
        )
    finally:
        os.unlink(raw)
    print(f"Wrote {OUT} ({OUT.stat().st_size // 1024} KB) in voice {VOICE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
