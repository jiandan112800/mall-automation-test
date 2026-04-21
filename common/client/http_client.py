from typing import Any

import requests


class HttpClient:
    def __init__(self, base_url: str, timeout: int = 15, verify_ssl: bool = True):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.verify = verify_ssl

    def set_token(self, token: str) -> None:
        # 后端在多个 Controller 中使用 request.getHeader("token") 取鉴权
        self.session.headers.update({"token": token})
        # 兼容可能的 Bearer 约定（不影响 token 读取）
        self.session.headers.update({"Authorization": f"Bearer {token}"})

    def clear_token(self) -> None:
        self.session.headers.pop("token", None)
        self.session.headers.pop("Authorization", None)

    def request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        url = f"{self.base_url}{path}"
        kwargs.setdefault("timeout", self.timeout)
        return self.session.request(method=method, url=url, **kwargs)

    def get(self, path: str, **kwargs: Any) -> requests.Response:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> requests.Response:
        return self.request("POST", path, **kwargs)

    def put(self, path: str, **kwargs: Any) -> requests.Response:
        return self.request("PUT", path, **kwargs)

    def delete(self, path: str, **kwargs: Any) -> requests.Response:
        return self.request("DELETE", path, **kwargs)
