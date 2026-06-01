from public_warning import PUBLIC_WARNING_TEXT


def test_public_warning_makes_financial_advice_boundary_clear():
    normalized = PUBLIC_WARNING_TEXT.lower()

    assert "coding exercise" in normalized
    assert "not financial advice" in normalized
    assert "planner" in normalized
    assert "sandbox" in normalized
    assert "vibe coding" in normalized
