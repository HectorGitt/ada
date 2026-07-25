from ada.services.ats import ApplicantAnswers, FormAction, FormPlan

SOURCE = "ashby"


def apply_url(job_url: str) -> str:
    base = job_url.rstrip("/")
    return base if base.endswith("/application") else f"{base}/application"


def build_form_plan(job_url: str, answers: ApplicantAnswers) -> FormPlan:
    actions = (
        FormAction(
            kind="fill", label="full name", value=answers.full_name,
            selectors=(
                'input[name="_systemfield_name"]',
                'input[aria-label*="name" i]',
            ),
        ),
        FormAction(
            kind="fill", label="email", value=answers.email,
            selectors=(
                'input[name="_systemfield_email"]',
                'input[type="email"]',
            ),
        ),
        FormAction(
            kind="fill", label="phone", value=answers.phone, required=False,
            selectors=(
                'input[name="_systemfield_phone"]',
                'input[aria-label*="phone" i]',
            ),
        ),
        FormAction(
            kind="upload", label="resume", value=None,
            selectors=(
                'input[name="_systemfield_resume"]',
                'input[type="file"]',
            ),
        ),
    )
    return FormPlan(
        apply_url=apply_url(job_url),
        actions=actions,
        submit_selectors=(
            'button[type="submit"]',
            'button:has-text("Submit application")',
        ),
        confirmation_markers=(
            "text=Application submitted",
            "text=Thank you for applying",
            "text=successfully submitted",
        ),
    )
