from __future__ import annotations

import re
from typing import Any

from common.assertions.api_assertions import (
    assert_auth_failure,
    assert_result_code,
    assert_result_success,
    assert_status_code,
)
from common.assertions.case_assertions import assert_by_case_rule


def assert_regex(text: str, pattern: str) -> None:
    assert re.search(pattern, text), f"Pattern not matched: pattern={pattern}, text={text}"


def assert_jsonpath_value(body: Any, path: str, expected: Any) -> None:
    if path == "$":
        actual = body
    else:
        if not path.startswith("$."):
            raise AssertionError(f"Unsupported path: {path}")
        actual = body
        for token in path[2:].split("."):
            match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)(\[(\d+)\])?$", token)
            if not match:
                raise AssertionError(f"Unsupported token: {token}")
            key = match.group(1)
            idx = match.group(3)
            if not isinstance(actual, dict) or key not in actual:
                raise AssertionError(f"Missing key: {key} in {actual}")
            actual = actual[key]
            if idx is not None:
                i = int(idx)
                if not isinstance(actual, list) or i >= len(actual):
                    raise AssertionError(f"Invalid index: {idx} in {actual}")
                actual = actual[i]
    assert actual == expected, f"Json path assertion failed: actual={actual}, expected={expected}"


__all__ = [
    "assert_by_case_rule",
    "assert_auth_failure",
    "assert_result_code",
    "assert_result_success",
    "assert_status_code",
    "assert_regex",
    "assert_jsonpath_value",
]
