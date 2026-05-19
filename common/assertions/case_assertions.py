from __future__ import annotations

from typing import Any

import pytest


def _norm_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text in ("无", "None", "null"):
        return ""
    return text.replace("&#10;", "\n")


def assert_by_case_rule(response, case: dict) -> None:
    check = _norm_text(case.get("check"))
    expected = _norm_text(case.get("expected"))

    if not check:
        return

    if check == "res.json.code":
        options = [x.strip() for x in expected.split("|") if x.strip()]
        if not options:
            raise AssertionError(f"Invalid expected for {check}: {expected!r}")
        actual = None
        try:
            body = response.json()
            if isinstance(body, dict) and "code" in body:
                actual = str(body.get("code"))
        except Exception:
            actual = None
        if actual is None:
            actual = str(response.status_code)
        assert actual in options, f"Expected one of {options}, got {actual}, body={response.text}"
        return

    if check == "res.status_code":
        assert str(response.status_code) == expected, (
            f"Unexpected status code: {response.status_code}, expected={expected}, body={response.text}"
        )
        return

    if check == "res.text":
        assert expected in response.text, f"Expected {expected!r} in response text: {response.text}"
        return

    pytest.fail(f"Unsupported check rule in Excel: {check}")
