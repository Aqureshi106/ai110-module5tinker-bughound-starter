from reliability.risk_assessor import assess_risk


def test_no_fix_is_high_risk():
    risk = assess_risk(
        original_code="print('hi')\n",
        fixed_code="",
        issues=[{"type": "Code Quality", "severity": "Low", "msg": "print"}],
    )
    assert risk["level"] == "high"
    assert risk["should_autofix"] is False
    assert risk["score"] == 0


def test_low_risk_when_minimal_change_and_low_severity():
    original = "import logging\n\ndef add(a, b):\n    return a + b\n"
    fixed = "import logging\n\ndef add(a, b):\n    return a + b\n"
    risk = assess_risk(
        original_code=original,
        fixed_code=fixed,
        issues=[{"type": "Code Quality", "severity": "Low", "msg": "minor"}],
    )
    assert risk["level"] in ("low", "medium")  # depends on scoring rules
    assert 0 <= risk["score"] <= 100


def test_high_severity_issue_drives_score_down():
    original = "def f():\n    try:\n        return 1\n    except:\n        return 0\n"
    fixed = "def f():\n    try:\n        return 1\n    except Exception as e:\n        return 0\n"
    risk = assess_risk(
        original_code=original,
        fixed_code=fixed,
        issues=[{"type": "Reliability", "severity": "High", "msg": "bare except"}],
    )
    assert risk["score"] <= 60
    assert risk["level"] in ("medium", "high")


def test_missing_return_is_penalized():
    original = "def f(x):\n    return x + 1\n"
    fixed = "def f(x):\n    x + 1\n"
    risk = assess_risk(
        original_code=original,
        fixed_code=fixed,
        issues=[],
    )
    assert risk["score"] < 100
    assert any("Return" in r or "return" in r for r in risk["reasons"])


def test_borderline_low_risk_no_longer_autofixes():
    original = "def f():\n    return True\n"
    fixed = "def f():\n    return True\n"
    issues = [
        {"type": "Code Quality", "severity": "Low", "msg": "a"},
        {"type": "Code Quality", "severity": "Low", "msg": "b"},
        {"type": "Code Quality", "severity": "Low", "msg": "c"},
        {"type": "Code Quality", "severity": "Low", "msg": "d"},
    ]

    risk = assess_risk(original_code=original, fixed_code=fixed, issues=issues)

    assert risk["score"] == 80
    assert risk["level"] == "low"
    assert risk["should_autofix"] is False


def test_function_signature_change_adds_caution():
    original = "def greet(name):\n    print(name)\n"
    fixed = "def greet(name, verbose=False):\n    if verbose:\n        print(name)\n    print(name)\n"

    risk = assess_risk(
        original_code=original,
        fixed_code=fixed,
        issues=[{"type": "Code Quality", "severity": "Low", "msg": "print"}],
    )

    assert any("signature" in reason.lower() for reason in risk["reasons"])
    assert risk["score"] <= 80


def test_syntax_error_in_fixed_code_blocks_autofix():
    from bughound_agent import BugHoundAgent
    from llm_client import MockClient

    class MalformedFixClient(MockClient):
        def complete(self, system_prompt: str, user_prompt: str) -> str:
            if "Return ONLY valid JSON" in system_prompt:
                return '[{"type":"Code Quality","severity":"Low","msg":"print statements"}]'
            return "def f():\n    if True\n        return 1\n"

    result = BugHoundAgent(client=MalformedFixClient()).run("def f():\n    print('hi')\n    return 1\n")

    assert result["risk"]["level"] in ("medium", "high")
    assert result["risk"]["should_autofix"] is False
    assert any("syntax" in reason.lower() for reason in result["risk"]["reasons"])
