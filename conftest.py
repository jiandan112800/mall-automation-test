import pytest
import allure
import requests
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from common.client.http_client import HttpClient
from common.db.mysql_client import DBClient
from common.utils.config_loader import load_env_config
from common.assertions.api_assertions import assert_status_code, assert_result_success
from common.utils.auth_helpers import build_login_payload

logger = logging.getLogger(__name__)

@pytest.fixture(scope="session")
def env_config() -> dict:
    return load_env_config()


@pytest.fixture(scope="session")
def case_context(env_config: dict) -> dict:
    """
    全局变量池（仿 data-driven 框架 all={}）：
    用例执行中提取出的 token/orderNo/userId 可写回这里，供后续 case 渲染。
    """
    return dict(env_config)


def _is_prod_like_host(host: str) -> bool:
    h = (host or "").lower()
    keywords = ("prod", "production", "online")
    return any(k in h for k in keywords)


def _resolve_ui_base_url(env_config: dict) -> str:
    """
    Vite (3000) often does not expose /api/* — UI XHR then 404 and search stays 共0条.
    If configured ui_base_url cannot serve /api/good, fall back to base_url (backend host).
    """
    explicit = str(env_config.get("ui_effective_base_url") or env_config.get("ui_spa_base_url") or "").strip()
    if explicit:
        return explicit.rstrip("/")

    configured = str(env_config.get("ui_base_url", "http://localhost:3000")).rstrip("/")
    api_base = str(env_config.get("base_url", "")).rstrip("/")
    timeout = int(env_config.get("timeout", 15))
    verify = bool(env_config.get("verify_ssl", True))
    home_path = str(env_config.get("ui_home_path", "/topview")).strip()
    if not home_path.startswith("/"):
        home_path = f"/{home_path}"

    def _looks_like_spa_shell(html: str) -> bool:
        h = (html or "").lower()
        return "id=\"app\"" in h or "id='app'" in h

    try:
        r = requests.get(f"{configured}/api/good", timeout=timeout, verify=verify)
        if r.status_code == 404 and api_base:
            r2 = requests.get(f"{api_base}/api/good", timeout=timeout, verify=verify)
            if r2.status_code == 200:
                # 仅当后端根路径也托管同一套前端壳时，才回退到 base_url（避免 API 在 8080、SPA 只在 3000 时误用 8080 打开 /login）
                try:
                    spa = requests.get(f"{api_base}{home_path}", timeout=timeout, verify=verify)
                    if spa.status_code == 200 and _looks_like_spa_shell(spa.text):
                        return api_base
                except Exception:
                    return configured
    except Exception:
        pass

    return configured


def _maybe_rewrite_shop_api_origin(driver, env_config: dict) -> None:
    """
    当 Vite 开发服 (ui_base_url) 未代理 /api/*，但后端 (base_url) 提供 /api/good 时，
    在浏览器里把以 /api 开头的 XHR/fetch 重写到后端 origin，避免搜索永远 共0条。
    """
    configured_ui = str(env_config.get("ui_base_url", "http://localhost:3000")).rstrip("/")
    api_base = str(env_config.get("base_url", "")).rstrip("/")
    if not api_base or configured_ui == api_base:
        return
    timeout = int(env_config.get("timeout", 15))
    verify = bool(env_config.get("verify_ssl", True))
    try:
        r_ui = requests.get(f"{configured_ui}/api/good", timeout=timeout, verify=verify)
        r_api = requests.get(f"{api_base}/api/good", timeout=timeout, verify=verify)
    except Exception:
        return
    if r_ui.status_code != 404 or r_api.status_code != 200:
        return

    api_origin = api_base

    # Chrome only (当前 UI 套件使用 Chrome)
    try:
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {
                "source": f"""
(() => {{
  const API_ORIGIN = {api_origin!r};

  const toBackend = (url) => {{
    if (typeof url !== 'string') return url;
    if (url.startsWith('/api')) return API_ORIGIN + url;
    return url;
  }};

  const origOpen = XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open = function(method, url, async, user, password) {{
    return origOpen.call(this, method, toBackend(url), async, user, password);
  }};

  const origFetch = window.fetch;
  window.fetch = function(input, init) {{
    if (typeof input === 'string') return origFetch.call(this, toBackend(input), init);
    if (input && typeof Request !== 'undefined' && input instanceof Request) {{
      const u = toBackend(input.url);
      if (u !== input.url) return origFetch.call(this, new Request(u, input), init);
    }}
    return origFetch.call(this, input, init);
  }};
}})();
"""
            },
        )
    except Exception:
        return


@pytest.fixture(scope="session")
def db_client(env_config: dict):
    """
    session 级数据库客户端（连接参数复用）。
    """
    db_conf = env_config.get("db") or {}
    required = ("host", "port", "user", "password", "database")
    if not all(str(db_conf.get(k, "")).strip() for k in required):
        yield None
        return

    host = str(db_conf["host"]).strip()
    if _is_prod_like_host(host):
        pytest.skip(f"Refuse to connect production-like DB host: {host}")

    client = DBClient(
        host=host,
        port=int(db_conf["port"]),
        user=str(db_conf["user"]),
        password=str(db_conf["password"]),
        database=str(db_conf["database"]),
        charset=str(db_conf.get("charset", "utf8mb4")),
    )
    try:
        yield client
    finally:
        client.close()


@pytest.fixture(scope="function")
def db_tx(db_client):
    """
    function 级事务连接：
    - 用例内可执行 SQL
    - 用例结束自动回滚，避免数据污染，支持并行
    """
    if db_client is None:
        yield None
        return
    with db_client.transaction() as conn:
        yield conn

@pytest.fixture(scope="session")
def api_client(env_config: dict) -> HttpClient:
    return HttpClient(
        base_url=env_config.get("base_url", "http://localhost:3000"),
        timeout=env_config.get("timeout", 15),
        verify_ssl=env_config.get("verify_ssl", True),
    )


@pytest.fixture(scope="session")
def ui_base_url(env_config: dict) -> str:
    return _resolve_ui_base_url(env_config)


def _apply_ui_driver_timeouts(driver, env_config: dict) -> None:
    load_s = int(env_config.get("ui_page_load_timeout", 45))
    script_s = int(env_config.get("ui_script_timeout", 45))
    driver.set_page_load_timeout(max(load_s, 1))
    driver.set_script_timeout(max(script_s, 1))


@pytest.fixture(scope="function")
def driver(env_config: dict):
    options = Options()
    if env_config.get("headless", True):
        options.add_argument("--headless=new")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    browser_binary = str(env_config.get("chrome_binary", "")).strip()
    if browser_binary:
        options.binary_location = browser_binary

    # 1) 优先使用显式配置的本地 chromedriver 路径（离线环境最稳定）
    local_driver = str(env_config.get("chrome_driver_path", "")).strip()
    if local_driver:
        try:
            service = Service(local_driver)
            web_driver = webdriver.Chrome(service=service, options=options)
            web_driver.implicitly_wait(int(env_config.get("ui_implicit_wait", 5)))
            _apply_ui_driver_timeouts(web_driver, env_config)
            yield web_driver
            web_driver.quit()
            return
        except Exception as exc:
            pytest.skip(f"Configured chrome_driver_path is invalid: {local_driver}. error={exc}")

    # 2) 尝试 Selenium Manager（本机自动探测）
    try:
        web_driver = webdriver.Chrome(options=options)
    except Exception as first_exc:
        pytest.skip(
            "Cannot initialize Chrome WebDriver in current environment. "
            "Set config.dev.yaml 'chrome_driver_path' to a local chromedriver executable. "
            f"selenium-manager error={first_exc}"
        )
    web_driver.implicitly_wait(int(env_config.get("ui_implicit_wait", 5)))
    _apply_ui_driver_timeouts(web_driver, env_config)
    yield web_driver
    web_driver.quit()


def _uniq_paths(*paths: str) -> list[str]:
    result: list[str] = []
    seen = set()
    for p in paths:
        if not p:
            continue
        path = p.strip()
        if not path:
            continue
        if not path.startswith("/"):
            path = f"/{path}"
        if path not in seen:
            seen.add(path)
            result.append(path)
    return result


def _first_non_404_post(api_client: HttpClient, paths: list[str], json_body: dict) -> str | None:
    for path in paths:
        try:
            resp = api_client.post(path, json=json_body)
            if resp.status_code != 404:
                return path
        except Exception:
            continue
    return None


def _first_non_404_get(api_client: HttpClient, paths: list[str]) -> str | None:
    for path in paths:
        try:
            resp = api_client.get(path)
            if resp.status_code != 404:
                return path
        except Exception:
            continue
    return None


@pytest.fixture(scope="session")
def api_paths(api_client: HttpClient, env_config: dict) -> dict:
    """
    自动探测接口路径，避免不同后端路由导致固定路径 404。
    可通过 config/dev.yaml 覆盖：
      - login_path
      - userid_path
    """
    login_candidates = _uniq_paths(
        env_config.get("login_path", ""),
        "/login",
        "/api/login",
        "/api/user/login",
        "/user/login",
        "/auth/login",
    )
    userid_candidates = _uniq_paths(
        env_config.get("userid_path", ""),
        "/userid",
        "/api/userid",
        "/api/user/id",
        "/api/user/info",
        "/user/id",
    )

    # 与 auth_token / test_auth 一致，避免已配置 md5 时这里仍发明文导致探测与登录不一致
    payload = build_login_payload(env_config)
    login_path = _first_non_404_post(api_client, login_candidates, payload)
    userid_path = _first_non_404_get(api_client, userid_candidates)

    if not login_path:
        pytest.skip(
            "API route not found for login. "
            f"Tried: {login_candidates}. "
            "Please set 'login_path' in config/dev.yaml to your real backend route."
        )
    if not userid_path:
        pytest.skip(
            "API route not found for userid. "
            f"Tried: {userid_candidates}. "
            "Please set 'userid_path' in config/dev.yaml to your real backend route."
        )

    return {"login_path": login_path, "userid_path": userid_path}

@pytest.fixture(scope="session")
def auth_token(api_client: HttpClient, env_config: dict, api_paths: dict) -> str:
    payload = build_login_payload(env_config)
    logger.info(
        "auth_token login start: path=%s user=%s encoding=%s",
        api_paths["login_path"],
        env_config.get("username", ""),
        env_config.get("login_password_encoding", "plain"),
    )
    resp = api_client.post(api_paths["login_path"], json=payload)
    logger.info(
        "auth_token login response: status=%s body_preview=%s",
        resp.status_code,
        (resp.text or "")[:400],
    )
    assert_status_code(resp, 200)
    body = resp.json()
    assert_result_success(body)
    token = body.get("data", {}).get("token")
    assert token, "Missing token in login response"
    api_client.set_token(token)
    return token

@pytest.fixture(scope="session")
def current_user_id(api_client: HttpClient, auth_token: str, api_paths: dict) -> int:
    resp = api_client.get(api_paths["userid_path"])
    assert_status_code(resp, 200)
    return int(resp.json())


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    setattr(item, f"rep_{rep.when}", rep)
    if rep.when != "call" or rep.passed:
        return
    driver = item.funcargs.get("driver")
    if not driver:
        return
    try:
        allure.attach(
            driver.get_screenshot_as_png(),
            name="failure-screenshot",
            attachment_type=allure.attachment_type.PNG,
        )
    except Exception:
        pass
    try:
        allure.attach(
            driver.page_source,
            name="failure-page-source",
            attachment_type=allure.attachment_type.HTML,
        )
    except Exception:
        pass