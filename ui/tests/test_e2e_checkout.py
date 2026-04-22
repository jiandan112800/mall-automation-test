import pytest
import allure

from common.assertions.api_assertions import assert_result_success, assert_status_code
from common.utils.auth_helpers import build_login_payload
from ui.pages.checkout_page_v2 import CheckoutPage
from ui.pages.login_page import LoginPage


def _checkout_search_keyword(env_config: dict) -> str:
    """Prefer config; otherwise default to 手机 (validated manually)."""
    configured = (env_config.get("ui_checkout_keyword") or env_config.get("ui_checkout_search_keyword") or "").strip()
    if configured:
        return configured
    return "手机"


def _inject_ui_token(driver, ui_base_url: str, env_config: dict, token: str) -> None:
    key = str(env_config.get("ui_token_storage_key", "token")).strip() or "token"
    home = str(env_config.get("ui_home_path", "/topview")).strip()
    if not home.startswith("/"):
        home = f"/{home}"
    driver.get(f"{ui_base_url.rstrip('/')}{home}")
    driver.execute_script(
        "window.localStorage.setItem(arguments[0], arguments[1]);",
        key,
        token,
    )
    driver.execute_script(
        "window.sessionStorage.setItem(arguments[0], arguments[1]);",
        key,
        token,
    )
    # 很多 Vue 项目只在初始化阶段读取 token，注入后需刷新一次让鉴权状态生效
    driver.refresh()


@pytest.mark.smoke
@pytest.mark.ui
@allure.epic("UI Automation")
@allure.feature("Checkout")
@allure.story("E2E checkout flow")
@allure.title("UI: login then complete checkout flow")
def test_ui_e2e_checkout(driver, ui_base_url, env_config, request):
    login_ok = False
    login_page = LoginPage(driver)

    with allure.step("Login to UI"):
        # 优先真实表单登录，确保与手工路径一致；API token 仅作兜底
        candidates = [
            (env_config.get("username"), env_config.get("password")),
            (env_config.get("admin_username"), env_config.get("admin_password")),
        ]
        for username, password in candidates:
            if not username or not password:
                continue
            login_page.login(ui_base_url, username, password)
            if login_page.is_login_success():
                login_ok = True
                break

        if not login_ok and env_config.get("ui_use_api_token"):
            api_client = request.getfixturevalue("api_client")
            api_paths = request.getfixturevalue("api_paths")
            payload = build_login_payload(env_config)
            resp = api_client.post(api_paths["login_path"], json=payload)
            assert_status_code(resp, 200)
            body = resp.json()
            assert_result_success(body)
            token = body.get("data", {}).get("token")
            assert token, "API login ok but token missing"
            _inject_ui_token(driver, ui_base_url, env_config, token)
            login_ok = login_page.is_login_success(timeout=8)

    assert login_ok, (
        "Login failed: enable ui_use_api_token in config if form login does not match "
        "your front-end, or fix credentials/selectors."
    )

    with allure.step("Complete checkout flow"):
        checkout_page = CheckoutPage(driver)
        keyword = _checkout_search_keyword(env_config)
        allure.attach(keyword, name="checkout-search-keyword", attachment_type=allure.attachment_type.TEXT)
        pay_alert_text = checkout_page.complete_checkout(
            ui_base_url,
            keyword=keyword,
            home_path=env_config.get("ui_home_path", "/topview"),
            cart_path=env_config.get("ui_cart_path", "/cart"),
        )

    with allure.step("Verify payment result"):
        if pay_alert_text:
            allure.attach(
                pay_alert_text,
                name="pay-alert-text",
                attachment_type=allure.attachment_type.TEXT,
            )
            assert "成功支付" in pay_alert_text or "支付成功" in pay_alert_text, (
                f"Unexpected pay alert text: {pay_alert_text}"
            )
            return

        status_text = checkout_page.get_order_status()
        allure.attach(
            status_text or "<empty>",
            name="order-status-text",
            attachment_type=allure.attachment_type.TEXT,
        )
        if "已支付" in status_text or "支付成功" in status_text:
            return
        assert checkout_page.is_pay_page_ready(), (
            f"No pay success text yet, and not on pay-method page. status={status_text}"
        )
