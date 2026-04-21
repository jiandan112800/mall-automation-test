import time

from selenium.webdriver.common.by import By

from ui.pages.base_page import BasePage


class LoginPage(BasePage):
    """
    登录页与首页共用同一套 index.html（Vue SPA）：静态里只有 #app，
    /login 与 /topview 一样由 app.js 挂载；script defer 后才会出现表单 DOM。
    """

    # Element UI：真实输入框多为 input.el-input__inner；文案多在内部 span
    USERNAME_LOCATORS = [
        (By.CSS_SELECTOR, "[data-testid='login-username']"),
        (By.CSS_SELECTOR, ".el-form input.el-input__inner[placeholder*='账号']"),
        (By.CSS_SELECTOR, ".el-form input.el-input__inner[placeholder*='用户名']"),
        (By.CSS_SELECTOR, "input.el-input__inner[placeholder*='账号']"),
        (By.CSS_SELECTOR, "input.el-input__inner[placeholder*='用户名']"),
        (By.CSS_SELECTOR, "input[placeholder*='账号']"),
        (By.CSS_SELECTOR, "input[placeholder*='用户名']"),
        (By.CSS_SELECTOR, "input[name='username']"),
    ]
    PASSWORD_LOCATORS = [
        (By.CSS_SELECTOR, "[data-testid='login-password']"),
        (By.CSS_SELECTOR, ".el-form input.el-input__inner[type='password']"),
        (By.CSS_SELECTOR, "input.el-input__inner[type='password']"),
        (By.CSS_SELECTOR, "input[placeholder*='密码']"),
        (By.CSS_SELECTOR, "input[name='password']"),
        (By.CSS_SELECTOR, "input[type='password']"),
    ]
    SUBMIT_LOCATORS = [
        (By.CSS_SELECTOR, "[data-testid='login-submit']"),
        (By.CSS_SELECTOR, ".el-form button.el-button--primary"),
        (By.XPATH, "//button[contains(@class,'el-button') and .//span[contains(.,'登录')]]"),
        (By.CSS_SELECTOR, "button[type='submit']"),
        (By.XPATH, "//button[contains(., '登录')]"),
    ]
    HOME_FLAGS = [
        (By.CSS_SELECTOR, "[data-testid='home-user-avatar']"),
        (By.CSS_SELECTOR, ".el-avatar"),
        (By.XPATH, "//*[contains(text(), '退出登录')]"),
    ]

    def login(self, base_url: str, username: str, password: str) -> None:
        root = base_url.rstrip("/")
        form_ready = False
        for url in (f"{root}/login", f"{root}/#/login"):
            self.open(url)
            try:
                self.wait_for_vue_app_mounted(timeout=25)
            except Exception:
                pass
            if self.wait_until_any_visible(self.USERNAME_LOCATORS, total_timeout=18):
                form_ready = True
                break
        assert form_ready, (
            "Login SPA: username field not visible after /login and /#/login "
            "(same index.html as home; check router base or placeholders)."
        )
        assert self.type_first(self.USERNAME_LOCATORS, username), "Username input not found"
        assert self.type_first(self.PASSWORD_LOCATORS, password), "Password input not found"
        assert self.click_first(self.SUBMIT_LOCATORS), "Login submit button not found"

    def is_login_success(self, timeout: int = 18) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            for locator in self.HOME_FLAGS:
                if self.is_visible(locator, timeout=1):
                    return True
            try:
                cur = self.driver.current_url or ""
            except Exception:
                cur = ""
            if "/login" not in cur and "#/login" not in cur:
                return True
            try:
                token = self.driver.execute_script(
                    "return window.localStorage.getItem('token') "
                    "|| window.sessionStorage.getItem('token');"
                )
                if token:
                    return True
            except Exception:
                pass
            time.sleep(0.35)
        return False
