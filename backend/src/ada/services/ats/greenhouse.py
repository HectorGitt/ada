from ada.services.ats import ApplicantAnswers, FormAction, FormPlan

SOURCE = "greenhouse"


def build_form_plan(job_url: str, answers: ApplicantAnswers) -> FormPlan:
    actions = (
        FormAction(
            kind="fill", label="first name", value=answers.first_name,
            selectors=(
                "input#first_name",
                'input[name="first_name"]',
                'input[aria-label*="first name" i]',
            ),
        ),
        FormAction(
            kind="fill", label="last name", value=answers.last_name,
            selectors=(
                "input#last_name",
                'input[name="last_name"]',
                'input[aria-label*="last name" i]',
            ),
        ),
        FormAction(
            kind="fill", label="email", value=answers.email,
            selectors=(
                "input#email",
                'input[name="email"]',
                'input[type="email"]',
            ),
        ),
        FormAction(
            kind="fill", label="phone", value=answers.phone, required=False,
            selectors=(
                "input#phone",
                'input[name="phone"]',
                'input[aria-label*="phone" i]',
            ),
        ),
        FormAction(
            kind="upload", label="resume", value=None,
            selectors=(
                "input#resume",
                'input[name="resume"]',
                '#resume_fieldset input[type="file"]',
                'input[type="file"][name*="resume" i]',
                'input[type="file"]',
            ),
        ),
    )
    return FormPlan(
        apply_url=job_url,
        actions=actions,
        submit_selectors=(
            "input#submit_app",
            'button[type="submit"]',
            'input[type="submit"]',
        ),
        confirmation_markers=(
            "#application_confirmation",
            "text=Thank you for applying",
            "text=Your application has been submitted",
        ),
    )
