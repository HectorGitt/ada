"""ATS application submission: pure per-source form plans + one browser executor."""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ApplicantAnswers:
    full_name: str
    first_name: str
    last_name: str
    email: str
    phone: str | None
    linkedin_url: str | None
    cv_filename: str
    cv_bytes: bytes


@dataclass(frozen=True)
class FormAction:
    kind: str
    selectors: tuple[str, ...]
    value: str | None = None
    required: bool = True
    label: str = ""


@dataclass(frozen=True)
class FormPlan:
    apply_url: str
    actions: tuple[FormAction, ...]
    submit_selectors: tuple[str, ...]
    confirmation_markers: tuple[str, ...]


@dataclass
class SubmitOutcome:
    status: str
    detail: str | None = None
    missing: list[str] = field(default_factory=list)


def split_name(full_name: str) -> tuple[str, str]:
    parts = full_name.strip().split()
    if len(parts) == 1:
        return parts[0], parts[0]
    return parts[0], " ".join(parts[1:])
