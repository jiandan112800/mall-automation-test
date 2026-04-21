from __future__ import annotations

import hashlib

from common.assertions.api_assertions import assert_result_success, assert_status_code
from common.client.http_client import HttpClient


def encode_login_password(password: str, encoding: str) -> str:
    """
    与前端提交方式对齐。常见：明文 plain；与抓包一致时对密码做 MD5 小写十六进制。
    """
    enc = (encoding or "plain").strip().lower()
    if enc in ("plain", "", "none"):
        return password
    if enc == "md5":
        return hashlib.md5(password.encode("utf-8")).hexdigest()
    raise ValueError(f"Unsupported login_password_encoding: {encoding!r}")


def build_login_payload(env_config: dict) -> dict:
    """构造登录 JSON：username + password（可按配置对密码做 MD5 等）。"""
    enc = str(env_config.get("login_password_encoding", "plain")).strip()
    pw = encode_login_password(str(env_config.get("password", "")), enc)
    return {
        "username": env_config["username"],
        "password": pw,
    }


def normalize_api_path(p: str) -> str:
    p = (p or "").strip()
    if not p:
        return ""
    return p if p.startswith("/") else f"/{p}"


def post_role_after_login(api_client: HttpClient, env_config: dict) -> None:
    """
    与浏览器一致：登录成功并带上 token 后，部分后端会再请求 POST /role。
    在 dev.yaml 中配置 role_path；留空则跳过。
    """
    role_path = normalize_api_path(str(env_config.get("role_path", "") or ""))
    if not role_path:
        return
    body = env_config.get("role_body")
    if body is None:
        body = {}
    resp = api_client.post(role_path, json=body)
    assert_status_code(resp, 200)
    ct = resp.headers.get("Content-Type", "")
    if "application/json" in ct and resp.text.strip():
        try:
            data = resp.json()
            if isinstance(data, dict) and "code" in data:
                assert_result_success(data)
        except Exception:
            pass
