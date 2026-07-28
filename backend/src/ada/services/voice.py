"""Voice conversation via the Gemini Live API (native audio).

connect opens a Live session grounded in what Ada already knows about the caller,
in one of two modes: an open career conversation, or a spoken mock interview.
Requires live Vertex credentials.
"""
from typing import Literal

from google.genai import types

from ada.config import get_settings
from ada.vertex import vertex_client

Mode = Literal["conversation", "interview"]

_CONVERSATION_PERSONA = """You are Ada, a warm and genuinely curious career coach having a \
real spoken phone conversation with someone about their working life. This is a \
conversation, not a form. React like a person — brief acknowledgements, the occasional \
reflection back ("that sounds like…"). Ask ONE question at a time, keep your turns short, \
and let them talk. Don't give long advice; this is about hearing their story. Naturally, \
over the conversation, come to understand their experience, skills, and what they want \
next — but let it surface, never interrogate."""

_INTERVIEW_PERSONA = """You are Ada, running a realistic spoken mock interview to help \
someone practice. Interview them for the kind of role they're targeting, grounded in their \
background. Ask ONE question at a time and WAIT for the full answer — behavioural and \
role-specific questions, following up on what they say the way a sharp interviewer would \
("can you walk me through how you approached that?"). Keep your own turns short. Don't \
coach mid-answer. Near the end, give brief, honest, specific feedback: what landed, and the \
one or two things to tighten. Stay encouraging but real."""

_COLD_OPEN = """Open naturally: greet them and begin."""

_GROUNDED_RULES = """You ALREADY KNOW this person from their profile and CV (below). Use it.

- NEVER ask something the context already answers ("what do you do?", "tell me about your \
experience", "what are your skills?"). You know these.
- OPEN by greeting them by name and naming something specific you see — e.g. "I can see \
you're a {{role}} — {{specific detail}}. …". Make them feel recognised in the first breath.
- Make every question specific to THIS person — reference their actual roles and companies.
- Treat the context as known truth; confirm or go deeper, don't re-collect it.

WHAT YOU KNOW ABOUT THIS PERSON:
{context}"""

_MAX_CONTEXT_CHARS = 6_000


def format_candidate_context(
    *,
    full_name: str | None,
    profile_text: str | None,
    cv_text: str | None,
    memories: list[str] | None,
) -> str | None:
    """A single grounding block from everything Ada knows, or None if nothing is known."""
    parts: list[str] = []
    if full_name and full_name.strip():
        parts.append(f"Name: {full_name.strip()}")
    if profile_text and profile_text.strip():
        parts.append(f"Profile (from LinkedIn / their own words):\n{profile_text.strip()}")
    if cv_text and cv_text.strip():
        parts.append(f"Most recent CV:\n{cv_text.strip()}")
    if memories:
        remembered = "\n".join(f"- {m}" for m in memories)
        parts.append(f"Remembered from past conversations:\n{remembered}")
    if not parts:
        return None
    return "\n\n".join(parts)[:_MAX_CONTEXT_CHARS]


_ACCENT = "Speak in a warm, natural Nigerian English accent throughout."


def _system_instruction(context: str | None, mode: Mode) -> str:
    persona = _INTERVIEW_PERSONA if mode == "interview" else _CONVERSATION_PERSONA
    tail = _GROUNDED_RULES.format(context=context) if context else _COLD_OPEN
    return f"{_ACCENT}\n\n{persona}\n\n{tail}"


class VoiceIntake:
    def __init__(self) -> None:
        s = get_settings()
        self._client = vertex_client()
        self._live_model = s.live_model
        self._voice = s.live_voice

    def connect(self, context: str | None = None, mode: Mode = "conversation"):
        """Async context manager yielding a Live session grounded in `context` when the
        caller is known. Emits native audio plus input/output transcription."""
        config = types.LiveConnectConfig(
            response_modalities=[types.Modality.AUDIO],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=self._voice)
                )
            ),
            system_instruction=_system_instruction(context, mode),
            input_audio_transcription=types.AudioTranscriptionConfig(),
            output_audio_transcription=types.AudioTranscriptionConfig(),
        )
        return self._client.aio.live.connect(model=self._live_model, config=config)
