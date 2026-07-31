from ada.services.insights import CandidateInsight, _experience_facts


def _insight(**over: object) -> CandidateInsight:
    base = dict(
        headline="Product Manager, Fintech", seniority="senior", years_experience=6,
        experience=["PM — Paystack (2021–2024)", "APM — Flutterwave (2019–2021)"],
        top_skills=["roadmapping", "SQL", "user research", "A/B testing"],
        market_fit="Fits senior PM roles in African fintech.", readiness_score=80,
        summary="You've got a strong fintech PM track record — let's aim high.",
    )
    base.update(over)
    return CandidateInsight(**base)  # type: ignore[arg-type]


def test_experience_facts_are_specific_and_bounded():
    facts = _experience_facts(_insight())
    assert facts[0] == "6 years' experience as Product Manager, Fintech."
    # Recent roles carried through (capped at two) and skills summarised.
    assert any("Paystack" in f for f in facts)
    assert sum(f.startswith("Experience:") for f in facts) == 2
    assert any(f.startswith("Key skills:") for f in facts)


def test_experience_facts_empty_when_nothing_to_say():
    thin = _insight(years_experience=0, experience=[], top_skills=[])
    assert _experience_facts(thin) == []
