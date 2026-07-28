from ada.services.voice import _system_instruction, format_candidate_context


def test_context_is_none_when_nothing_known():
    assert format_candidate_context(
        full_name=None, profile_text=None, cv_text=None, memories=None
    ) is None
    assert format_candidate_context(
        full_name="  ", profile_text="", cv_text="  ", memories=[]
    ) is None


def test_context_assembles_known_fields():
    context = format_candidate_context(
        full_name="Jane Doe",
        profile_text="Senior backend engineer, 8 years, fintech.",
        cv_text="Led the payments platform at Acme.",
        memories=["Wants to move into management", "Prefers remote"],
    )
    assert context is not None
    assert "Jane Doe" in context
    assert "backend engineer" in context
    assert "payments platform" in context
    assert "move into management" in context


def test_context_truncates():
    context = format_candidate_context(
        full_name="Jane", profile_text="x" * 10_000, cv_text=None, memories=None
    )
    assert context is not None
    assert len(context) <= 6_000


def test_grounded_instruction_forbids_generic_questions():
    context = format_candidate_context(
        full_name="Jane Doe", profile_text="Product manager at Acme.",
        cv_text=None, memories=None,
    )
    grounded = _system_instruction(context, "conversation")
    assert "NEVER ask" in grounded
    assert "greeting them by name" in grounded
    assert "Product manager at Acme." in grounded


def test_cold_instruction_when_no_context():
    cold = _system_instruction(None, "conversation")
    assert "Open naturally" in cold
    assert "NEVER ask" not in cold
    assert "WHAT YOU KNOW" not in cold


def test_interview_mode_uses_interview_persona():
    conversation = _system_instruction(None, "conversation")
    interview = _system_instruction(None, "interview")
    assert "mock interview" in interview
    assert "mock interview" not in conversation
    # Interview stays grounded when context exists.
    grounded = _system_instruction(
        format_candidate_context(
            full_name="Sam", profile_text="Data analyst.", cv_text=None, memories=None
        ),
        "interview",
    )
    assert "Data analyst." in grounded and "NEVER ask" in grounded


async def test_resolve_caller_anonymous_without_cookie():
    from ada.api.routes.voice import _resolve_caller

    class _WS:
        cookies: dict[str, str] = {}

    assert await _resolve_caller(_WS()) == (None, None)
