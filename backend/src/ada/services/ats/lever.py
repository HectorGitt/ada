from ada.services.ats import ApplicantAnswers, FormAction, FormPlan

SOURCE = "lever"


def apply_url(job_url: str) -> str:
    base = job_url.rstrip("/")
    return base if base.endswith("/apply") else f"{base}/apply"


def build_form_plan(job_url: str, answers: ApplicantAnswers) -> FormPlan:
    actions = (
        FormAction(
            kind="fill", label="full name", value=answers.full_name,
            selectors=('input[name="name"]', 'input[aria-label*="full name" i]'),
        ),
        FormAction(
            kind="fill", label="email", value=answers.email,
            selectors=('input[name="email"]', 'input[type="email"]'),
        ),
        FormAction(
            kind="fill", label="phone", value=answers.phone, required=False,
            selectors=('input[name="phone"]',),
        ),
        FormAction(
            kind="fill", label="linkedin", value=answers.linkedin_url, required=False,
            selectors=('input[name="urls[LinkedIn]"]',),
        ),
        FormAction(
            kind="upload", label="resume", value=None,
            selectors=(
                'input[name="resume"]',
                'input[type="file"][name*="resume" i]',
                'input[type="file"]',
            ),
        ),
    )
    return FormPlan(
        apply_url=apply_url(job_url),
        actions=actions,
        submit_selectors=('button[type="submit"]', "#btn-submit"),
        confirmation_markers=(
            "text=Application submitted",
            "text=Thank you",
            'css=[data-qa="msg-submit-success"]',
        ),
    )
