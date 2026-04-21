from __future__ import annotations

import re
from typing import Any


def assert_sql_result(actual: Any, expected: str) -> None:
    exp = (expected or "").strip()
    if not exp or exp.upper() == "N/A":
        return

    if exp.lower() == "not null":
        assert actual is not None, f"Expected not null, got {actual!r}"
        return

    m = re.match(r"^\s*(>=|<=|>|<)\s*(-?\d+)\s*$", exp)
    if m:
        op, num = m.group(1), int(m.group(2))
        assert actual is not None, f"Expected numeric compare {exp}, got None"
        actual_num = int(actual)
        if op == ">=":
            assert actual_num >= num, f"Expected {actual_num} >= {num}"
        elif op == "<=":
            assert actual_num <= num, f"Expected {actual_num} <= {num}"
        elif op == ">":
            assert actual_num > num, f"Expected {actual_num} > {num}"
        else:
            assert actual_num < num, f"Expected {actual_num} < {num}"
        return

    assert str(actual) == exp, f"Expected SQL result {exp!r}, got {actual!r}"
