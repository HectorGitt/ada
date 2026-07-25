"""Voice intake via the Gemini Live API (native audio).

connect opens a Live session for the spoken intake; extract turns the resulting
transcript into the {target_role, cv_text} the typed form also produces. Voice only
populates intake fields and never triggers a run. Requires live Vertex credentials.
"""
import json

from google.genai import types

from ada.config import get_settings
from ada.vertex import vertex_client

_INTAKE_SYSTEM = """You are Ada, a warm, efficient career coach running a short spoken \
intake. Ask about the candidate's target role, recent experience, key skills, and \
education — one question at a time, and keep it under a few minutes. Do not give advice \
yet; just gather what you need for a CV and job match."""

_EXTRACT_SYSTEM = """From this intake transcript between Ada and a candidate, extract the \
candidate's target role and a plain-text CV draft built ONLY from what the candidate \
actually said (experience, skills, education, dates). Never invent facts. Return JSON of \
the exact shape: {"target_role": str, "cv_text": str}."""


class VoiceIntake:
    def __init__(self) -> None:
        s = get_settings()
        self._client = vertex_client()
        self._live_model = s.live_model
        self._model = s.vertex_model

    def connect(self):
        """Async context manager yielding a Live session.

        Native-audio Live models only speak AUDIO; we discard the audio bytes and
        rely on input/output transcription for the text transcript both the client
        UI and extract() consume.
        """
        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            system_instruction=_INTAKE_SYSTEM,
            input_audio_transcription=types.AudioTranscriptionConfig(),
            output_audio_transcription=types.AudioTranscriptionConfig(),
        )
        return self._client.aio.live.connect(model=self._live_model, config=config)

    async def extract(self, transcript: str) -> dict:
        resp = await self._client.aio.models.generate_content(
            model=self._model,
            contents=transcript,
            config=types.GenerateContentConfig(
                system_instruction=_EXTRACT_SYSTEM,
                temperature=0.2,
                response_mime_type="application/json",
            ),
        )
        return json.loads(resp.text or "{}")
