import pytest
import allure
import requests
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from common.client.http_client import HttpClient
from common.db.mysql_client import DBClient
from config.settings import load_settings
from common.assertions.api_assertions import assert_status_code, assert_result_success
from common.utils.auth_helpers import build_login_payload
from common.logger import get_logger

logger = get_logger(__name__)


@pytest.fixture(scope="session")
def env_config() -> dict:
    return load_settings()


@pytest.fixture(scope="session")
def case_context(env_config: dict) -> dict:
    return dict(env_config)


def _is_prod_like_host(host: str) -> bool:
    h = (host or "").lower()
    keywords = ("prod", "production", "online")
    return any(k in h for k in keywords)


def _resolve_ui_base_url(env_config: dict) -> str:
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
                try:
                    spa = requests.get(f"{api_base}{home_path}", timeout=timeout, verify=verify)
                    if spa.status_code == 200 and _looks_like_spa_shell(spa.text):
                        return api_base
                except Exception:
                    return configured
    except Exception:
        pass
    return configured


@pytest.fixture(scope="session")
def db_client(env_config: dict):
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
    if db_client is None:
        yield None
        return
    with db_client.transaction() as conn:
        yield conn


@pytest.fixture(scope="session")
def api_client(env_config: dict) -> HttpClient:
    return HttpClient(
        base_url=env_config.get("base_url", "http://localhost:8080"),
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


def _start_chrome_webdriver(options: Options, env_config: dict) -> webdriver.Chrome:
    """Resolve ChromeDriver: explicit path -> webdriver-manager -> Selenium Manager."""
    local_driver = str(env_config.get("chrome_driver_path", "")).strip()
    use_manager = bool(env_config.get("chrome_use_webdriver_manager", False))
    errors: list[str] = []

    if local_driver and not use_manager:
        try:
            return webdriver.Chrome(service=Service(local_driver), options=options)
        except Exception as exc:
            errors.append(f"chrome_driver_path ({local_driver}): {exc}")

    if use_manager or local_driver:
        try:
            manager_path = ChromeDriverManager().install()
            return webdriver.Chrome(service=Service(manager_path), options=options)
        except Exception as exc:
            errors.append(f"webdriver-manager: {exc}")

    try:
        return webdriver.Chrome(options=options)
    except Exception as exc:
        errors.append(f"selenium-manager: {exc}")

    detail = " | ".join(errors) if errors else "no driver strategy configured"
    pytest.skip(
        "Cannot initialize Chrome WebDriver. "
        "Install Chrome, set chrome_use_webdriver_manager: true in config/config.yaml, "
        "or set chrome_driver_path to a driver matching your Chrome version. "
        f"Details: {detail}"
    )


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

    web_driver = _start_chrome_webdriver(options, env_config)
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
    payload = build_login_payload(env_config)
    login_path = _first_non_404_post(api_client, login_candidates, payload)
    userid_path = _first_non_404_get(api_client, userid_candidates)
    if not login_path:
        pytest.skip(
            "API route not found for login. "
            f"Tried: {login_candidates}. "
            "Please set 'login_path' in config/config.yaml to your real backend route."
        )
    if not userid_path:
        pytest.skip(
            "API route not found for userid. "
            f"Tried: {userid_candidates}. "
            "Please set 'userid_path' in config/config.yaml to your real backend route."
        )
    return {"login_path": login_path, "userid_path": userid_path}


@pytest.fixture(scope="session")
def auth_token(api_client: HttpClient, env_config: dict, api_paths: dict) -> str:
    payload = build_login_payload(env_config)
    payload_preview = {**payload, "password": "***"}
    login_path = api_paths["login_path"]
    encoding = env_config.get("login_password_encoding", "plain")
    user = env_config.get("username", "")
    logger.info(
        "auth_token login start: path=%s user=%s encoding=%s",
        login_path,
        user,
        encoding,
    )
    resp = api_client.post(login_path, json=payload)
    logger.info(
        "auth_token login response: status=%s body_preview=%s",
        resp.status_code,
        (resp.text or "")[:400],
    )
    try:
        assert_status_code(resp, 200)
        body = resp.json()
        assert_result_success(body)
        token = body.get("data", {}).get("token")
        assert token, "Missing token in login response"
    except Exception as exc:
        body_preview = (resp.text or "")[:400]
        raise AssertionError(
            "auth_token login failed. "
            f"path={login_path}, user={user}, encoding={encoding}, "
            f"payload={payload_preview}, status={resp.status_code}, body_preview={body_preview}"
        ) from exc
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
    web_driver = item.funcargs.get("driver")
    if not web_driver:
        return
    try:
        allure.attach(
            web_driver.get_screenshot_as_png(),
            name="failure-screenshot",
            attachment_type=allure.attachment_type.PNG,
        )
    except Exception:
        pass
    try:
        allure.attach(
            web_driver.page_source,
            name="failure-page-source",
            attachment_type=allure.attachment_type.HTML,
        )
    except Exception:
        pass


def pytest_collection_modifyitems(config, items):
    """
    Only unstable tests get reruns.
    Requires pytest-rerunfailures plugin.
    """
    for item in items:
        if item.get_closest_marker("unstable"):
            item.add_marker(pytest.mark.flaky(reruns=2, reruns_delay=5))
