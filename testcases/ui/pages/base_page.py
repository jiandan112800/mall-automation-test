import time

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class BasePage:
    def __init__(self, driver, timeout: int = 10):
        self.driver = driver
        self.timeout = timeout

    def open(self, url: str) -> None:
        try:
            self.driver.get(url)
        except TimeoutException:
            try:
                self.driver.execute_script("window.stop();")
            except Exception:
                pass

    def wait_for_vue_app_mounted(self, timeout: int | None = None) -> None:
        t = self.timeout if timeout is None else timeout

        def _shell_ready(driver):
            try:
                return bool(
                    driver.execute_script(
                        """
                        var app = document.getElementById('app');
                        if (!app || app.children.length === 0) return false;
                        return !!app.querySelector(
                          'input.el-input__inner, button, .el-button, .el-card, '
                          + '.el-menu, .el-row, [class*="good"], [class*="product"], '
                          + '.el-form'
                        );
                        """
                    )
                )
            except Exception:
                return False

        WebDriverWait(self.driver, t).until(_shell_ready)

    def wait_until_any_visible(self, locators: list[tuple[str, str]], total_timeout: int | None = None, poll: float = 0.35) -> bool:
        deadline = time.time() + float(self.timeout if total_timeout is None else total_timeout)
        while time.time() < deadline:
            for loc in locators:
                if self.is_visible(loc, timeout=1):
                    return True
            time.sleep(poll)
        return False

    def click(self, locator) -> None:
        WebDriverWait(self.driver, self.timeout).until(EC.element_to_be_clickable(locator)).click()

    def type_text(self, locator, value: str) -> None:
        element = WebDriverWait(self.driver, self.timeout).until(EC.visibility_of_element_located(locator))
        element.clear()
        element.send_keys(value)

    def get_text(self, locator) -> str:
        element = WebDriverWait(self.driver, self.timeout).until(EC.visibility_of_element_located(locator))
        return element.text

    def is_visible(self, locator, timeout: int | None = None) -> bool:
        t = self.timeout if timeout is None else timeout
        try:
            WebDriverWait(self.driver, t).until(EC.visibility_of_element_located(locator))
            return True
        except TimeoutException:
            return False

    def click_first(self, locators: list[tuple[str, str]], per_locator_timeout: float = 3) -> bool:
        for locator in locators:
            try:
                WebDriverWait(self.driver, per_locator_timeout).until(EC.element_to_be_clickable(locator)).click()
                return True
            except Exception:
                continue
        return False

    def type_first(self, locators: list[tuple[str, str]], value: str, per_locator_timeout: float = 3) -> bool:
        for locator in locators:
            try:
                element = WebDriverWait(self.driver, per_locator_timeout).until(EC.visibility_of_element_located(locator))
                element.clear()
                element.send_keys(value)
                return True
            except Exception:
                continue
        return False

    @staticmethod
    def css(selector: str) -> tuple[str, str]:
        return (By.CSS_SELECTOR, selector)
