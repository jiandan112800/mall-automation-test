from typing import Any


def assert_status_code(response, expected: int = 200) -> None:
    assert response.status_code == expected, (
        f"Unexpected status code: {response.status_code}, body: {response.text}"
    )


def assert_result_code(body: Any, expected: str) -> None:
    """
    后端统一 Result：{"code":"200","msg":null,"data":...}
    这里用 code 字符串断言，兼容后端把 code 输出成数字的情况。
    """
    if isinstance(body, dict) and "code" in body:
        actual = body.get("code")
        actual_str = str(actual) if actual is not None else actual
        assert actual_str == str(expected), f"Unexpected result code: {body}"
    else:
        raise AssertionError(f"Response body is not a Result object: {body}")


def assert_result_success(body: Any, code_ok: str = "200") -> None:
    assert_result_code(body, expected=code_ok)


def assert_auth_failure(response) -> None:
    """
    鉴权失败的表现不一定完全一致：可能是 401/403，也可能是 HTTP 200 + Result.code=401。
    """
    ct = response.headers.get("Content-Type", "")
    if "application/json" in ct:
        try:
            body = response.json()
            if isinstance(body, dict) and "code" in body:
                assert str(body.get("code")) in ("401", "403"), f"Unexpected body: {body}"
                return
        except Exception:
            pass
    assert response.status_code in (401, 403), f"Unexpected status code: {response.status_code}, body: {response.text}"
