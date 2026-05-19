from __future__ import annotations

import sys

import pytest


def main() -> int:
    args = [
        "testcases",
        "-q",
        "--alluredir=reports/allure-results",
    ]
    return pytest.main(args)


if __name__ == "__main__":
    sys.exit(main())
