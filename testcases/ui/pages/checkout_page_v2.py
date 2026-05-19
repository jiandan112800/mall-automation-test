import logging
import re
import time
from typing import Any, Optional, Sequence
from urllib.parse import quote

from selenium.webdriver import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from testcases.ui.pages.base_page import BasePage


class CheckoutPage(BasePage):
    logger = logging.getLogger(__name__)

    SEARCH_INPUTS = [
        (By.CSS_SELECTOR, "[data-testid='search-input']"),
        (By.CSS_SELECTOR, "div.search input.el-input__inner"),
        (By.CSS_SELECTOR, "div.search input[type='text']"),
        (By.CSS_SELECTOR, "input[placeholder*='请输入商品']"),
    ]
    SEARCH_BUTTONS = [
        (By.CSS_SELECTOR, "[data-testid='search-btn']"),
        (By.CSS_SELECTOR, "div.search button"),
        (By.XPATH, "//div[contains(@class,'search')]//input/following-sibling::button[1]"),
        (By.XPATH, "//button[contains(., '搜索')]"),
    ]
    FIRST_PRODUCTS = [
        (By.CSS_SELECTOR, "[data-testid='product-card']"),
        (By.CSS_SELECTOR, ".recommend .el-card:first-child"),
        (By.CSS_SELECTOR, ".el-card:first-child"),
    ]
    ADD_TO_CART_BTNS = [
        (By.XPATH, "//button[contains(@class,'cart-button') and .//span[normalize-space()='加入购物车']]"),
        (By.CSS_SELECTOR, "button.cart-button"),
        (By.CSS_SELECTOR, "button.el-button--warning"),
        (By.XPATH, "//button[contains(normalize-space(.), '加入购物车')]"),
        (By.XPATH, "//span[contains(normalize-space(.), '加入购物车')]/ancestor::*[self::button or self::a][1]"),
    ]
    ADD_TO_CART_SUCCESS_MARKERS = [
        (By.XPATH, "//*[contains(normalize-space(.), '成功添加购物车')]"),
        (By.XPATH, "//*[contains(normalize-space(.), '加入购物车成功')]"),
        (By.XPATH, "//*[contains(normalize-space(.), '添加成功')]"),
    ]
    SPEC_OPTION_LOCATORS = [
        (By.CSS_SELECTOR, ".el-radio-group label[role='radio']"),
        (By.CSS_SELECTOR, ".el-radio-group .el-radio-button"),
        (By.CSS_SELECTOR, ".el-radio-group .el-radio-button__inner"),
        (By.CSS_SELECTOR, ".spec .el-tag"),
        (By.CSS_SELECTOR, ".sku .el-tag"),
        (By.CSS_SELECTOR, ".sku-item"),
    ]
    SPEC_CONFIRM_BTNS = [
        (By.XPATH, "//button[contains(normalize-space(.), '确定')]"),
        (By.XPATH, "//button[contains(normalize-space(.), '确认')]"),
    ]
    GO_CART_BTNS = [
        (By.XPATH, "//a[contains(normalize-space(.), '我的购物车')]"),
        (By.XPATH, "//a[contains(normalize-space(.), '购物车')]"),
    ]
    CART_PAY_NOW_BTNS = [
        (By.CSS_SELECTOR, "button.pay-btn.el-button--success"),
        (By.XPATH, "//button[contains(normalize-space(.), '立即支付')]"),
    ]
    SUBMIT_ORDER_BTNS = [
        (By.CSS_SELECTOR, "[data-testid='submit-order']"),
        (By.XPATH, "//button[contains(normalize-space(.), '提交订单')]"),
    ]
    PAY_METHOD_BTNS = [
        (By.CSS_SELECTOR, "[data-testid='pay-wechat']"),
        (By.CSS_SELECTOR, "[data-testid='pay-alipay']"),
        (By.XPATH, "//*[contains(., '微信支付') or contains(., '微信')][self::div or self::span or self::img or self::button]"),
        (By.XPATH, "//*[contains(., '支付宝')][self::div or self::span or self::img or self::button]"),
    ]
    ORDER_STATUS_FLAGS = [
        (By.CSS_SELECTOR, "[data-testid='order-status']"),
        (By.XPATH, "//*[contains(text(), '已支付')]"),
        (By.XPATH, "//*[contains(text(), '支付成功')]"),
    ]
    CART_EMPTY_MARKERS = [
        (By.XPATH, "//*[contains(normalize-space(.), '购物车是空的')]"),
        (By.XPATH, "//*[contains(normalize-space(.), '购物车为空')]"),
    ]

    def _wait_listing_ready(self, timeout: int = 18) -> bool:
        def _listing_ready(driver: Any) -> bool:
            body = driver.find_element(By.TAG_NAME, "body").text or ""
            count_match = re.search(r"共\s*(\d+)\s*条", body)
            if count_match:
                try:
                    if int(count_match.group(1)) > 0:
                        return True
                except Exception:
                    pass
            for css in (".recommend .el-card", ".el-card", ".goods-list .el-card", ".product-list .el-card"):
                els = driver.find_elements(By.CSS_SELECTOR, css)
                if any(e.is_displayed() for e in els):
                    return True
            return False

        try:
            WebDriverWait(self.driver, timeout).until(_listing_ready)
            return True
        except Exception:
            return False

    def _type_search_keyword_robust(self, keyword: str) -> Optional[WebElement]:
        for locator in self.SEARCH_INPUTS:
            try:
                element = WebDriverWait(self.driver, 4).until(EC.visibility_of_element_located(locator))
                self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", element)
                try:
                    element.clear()
                except Exception:
                    pass
                element.send_keys(keyword)
                value = (element.get_attribute("value") or "").strip()
                if keyword in value:
                    return element
                self.driver.execute_script(
                    """
                    const el = arguments[0];
                    const v = arguments[1];
                    el.value = v;
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                    """,
                    element,
                    keyword,
                )
                value = (element.get_attribute("value") or "").strip()
                if keyword in value:
                    return element
            except Exception:
                continue
        return None

    def _search_with_fallback(self, keyword: str, context: str = "") -> bool:
        input_el = self._type_search_keyword_robust(keyword)
        assert input_el is not None, f"Search input not found{context}"
        typed_value = (input_el.get_attribute("value") or "").strip()
        assert keyword in typed_value, f"Search input value mismatch, expected={keyword}, actual={typed_value}"

        try:
            local_btn = input_el.find_element(By.XPATH, "./following-sibling::button[1]")
            try:
                local_btn.click()
            except Exception:
                self.driver.execute_script("arguments[0].click();", local_btn)
        except Exception:
            if not self.click_first(self.SEARCH_BUTTONS):
                input_el.send_keys(Keys.ENTER)
        ok = self._wait_listing_ready(timeout=18)
        if not ok:
            self.logger.error("搜索后列表仍为空")
        return ok

    def _wait_add_to_cart_success(self, timeout: int = 2) -> bool:
        return any(self.is_visible(locator, timeout=timeout) for locator in self.ADD_TO_CART_SUCCESS_MARKERS)

    def _select_spec_if_needed(self) -> None:
        time.sleep(0.8)
        try:
            radios = self.driver.find_elements(By.CSS_SELECTOR, ".el-radio-group label[role='radio']")
            if radios:
                for r in radios:
                    checked = (r.get_attribute("aria-checked") or "").lower() == "true"
                    cls = (r.get_attribute("class") or "").lower()
                    if checked or "disabled" in cls:
                        continue
                    self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", r)
                    try:
                        r.click()
                    except Exception:
                        self.driver.execute_script("arguments[0].click();", r)
                    self.click_first(self.SPEC_CONFIRM_BTNS, per_locator_timeout=0.8)
                    return
                return
        except Exception:
            pass

        def _click_first_enabled(elements: Sequence[WebElement]) -> bool:
            for el in elements:
                try:
                    if not el.is_displayed():
                        continue
                    cls = (el.get_attribute("class") or "").lower()
                    if "disabled" in cls:
                        continue
                    self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                    try:
                        el.click()
                    except Exception:
                        self.driver.execute_script("arguments[0].click();", el)
                    return True
                except Exception:
                    continue
            return False

        for by, sel in self.SPEC_OPTION_LOCATORS:
            try:
                opts = self.driver.find_elements(by, sel)
                if opts and _click_first_enabled(opts):
                    self.click_first(self.SPEC_CONFIRM_BTNS, per_locator_timeout=0.8)
                    return
            except Exception:
                continue

    def _click_add_to_cart_robust(self, retries: int = 2) -> bool:
        for _ in range(retries + 1):
            for locator in self.ADD_TO_CART_BTNS:
                try:
                    self._select_spec_if_needed()
                    btn = WebDriverWait(self.driver, 4).until(EC.presence_of_element_located(locator))
                    self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
                    try:
                        btn.click()
                    except Exception:
                        self.driver.execute_script("arguments[0].click();", btn)
                    classes = (btn.get_attribute("class") or "").strip()
                    if "cart-button" in classes or self._wait_add_to_cart_success(timeout=2):
                        return True
                except Exception:
                    continue
            time.sleep(0.6)
        return False

    def _is_add_to_cart_ready(self) -> bool:
        return any(self.is_visible(locator, timeout=1) for locator in self.ADD_TO_CART_BTNS)

    def _open_first_product_detail(self) -> bool:
        image_locators = [
            (By.CSS_SELECTOR, ".goods-list img"),
            (By.CSS_SELECTOR, ".product-list img"),
            (By.CSS_SELECTOR, ".recommend img"),
            (By.CSS_SELECTOR, ".el-col img"),
            (By.XPATH, "(//img[contains(@src,'/file/')])[1]"),
        ]
        for locator in image_locators + self.FIRST_PRODUCTS:
            try:
                target = WebDriverWait(self.driver, 4).until(EC.presence_of_element_located(locator))
                self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", target)
                try:
                    target.click()
                except Exception:
                    self.driver.execute_script("arguments[0].click();", target)
                time.sleep(0.5)
                if self._is_add_to_cart_ready():
                    return True
            except Exception:
                continue
        return False

    def _wait_add_to_cart_toast_dismissed(self) -> None:
        try:
            toast_locator = (By.CSS_SELECTOR, ".el-message, [role='alert']")
            WebDriverWait(self.driver, 2).until(EC.presence_of_element_located(toast_locator))
            WebDriverWait(self.driver, 6).until(EC.invisibility_of_element_located(toast_locator))
        except Exception:
            time.sleep(1.2)

    def _is_cart_empty(self) -> bool:
        if any(self.is_visible(locator, timeout=1) for locator in self.CART_PAY_NOW_BTNS):
            return False
        return any(self.is_visible(locator, timeout=1) for locator in self.CART_EMPTY_MARKERS)

    def _add_one_item_from_home(self, base_url: str, home_path: str, keyword: str) -> None:
        self.open(f"{base_url}{home_path}")
        try:
            self.wait_for_vue_app_mounted(timeout=20)
        except Exception:
            pass
        searched = self._search_with_fallback(keyword, context=" on retry add")
        if not searched:
            encoded = quote(keyword, safe="")
            self.open(f"{base_url}/goodList?searchText={encoded}")
            assert self._wait_listing_ready(timeout=18), "Retry add search has no product rows"
        assert self._open_first_product_detail(), "No product detail opened on retry add"
        assert self._click_add_to_cart_robust(), "Retry add-to-cart failed"
        self._wait_add_to_cart_toast_dismissed()

    def _is_order_page(self) -> bool:
        current_url = (self.driver.current_url or "").lower()
        if "preorder" in current_url:
            return True
        return self.is_visible((By.XPATH, "//*[contains(normalize-space(.), '提交订单')]"), timeout=2)

    def _is_pay_page(self) -> bool:
        current_url = (self.driver.current_url or "").lower()
        if "/pay" in current_url:
            return True
        return self.is_visible((By.XPATH, "//*[contains(normalize-space(.), '支付方式')]"), timeout=2)

    def complete_checkout(self, base_url: str, keyword: str = "手机", home_path: str = "/topview", cart_path: str = "/cart") -> str:
        self.open(f"{base_url}{home_path}")
        try:
            self.wait_for_vue_app_mounted(timeout=25)
        except Exception:
            pass
        searched = self._search_with_fallback(keyword)
        if not searched:
            encoded = quote(keyword, safe="")
            self.open(f"{base_url}/goodList?searchText={encoded}")
            assert self._wait_listing_ready(timeout=18), "Strict search failed: no rows after searching"
        assert self._open_first_product_detail(), "No product detail opened (check selectors)"
        assert self._click_add_to_cart_robust(), "Add-to-cart control not found"
        self._wait_add_to_cart_toast_dismissed()
        if not self.click_first(self.GO_CART_BTNS):
            self.open(f"{base_url}{cart_path}")
        assert self.is_visible((By.XPATH, "//*[contains(normalize-space(.), '购物车')]"), timeout=6), "Still not in cart page"
        if self._is_cart_empty():
            self.logger.warning("购物车为空，自动重试一次加购")
            self._add_one_item_from_home(base_url, home_path, keyword)
            if not self.click_first(self.GO_CART_BTNS):
                self.open(f"{base_url}{cart_path}")
            assert not self._is_cart_empty(), "Cart is still empty after retry add"
        assert self.click_first(self.CART_PAY_NOW_BTNS, per_locator_timeout=4), "Pay-now button not found"
        time.sleep(0.8)
        assert self._is_order_page(), "点击立即支付后未进入提交订单页面"
        assert self.click_first(self.SUBMIT_ORDER_BTNS, per_locator_timeout=4), "Submit-order button not found"
        time.sleep(0.8)
        assert self._is_pay_page(), "点击提交订单后未进入结算页面"
        self.click_first(self.PAY_METHOD_BTNS, per_locator_timeout=2)
        return self.handle_pay_alert()

    def handle_pay_alert(self, timeout: int = 8) -> str:
        try:
            alert = WebDriverWait(self.driver, timeout).until(EC.alert_is_present())
            text = alert.text or ""
            alert.accept()
            self.logger.info(f"捕获到支付弹窗: {text}")
            return text
        except Exception:
            self.logger.warning("未检测到支付弹窗")
            return ""

    def get_order_status(self) -> str:
        for locator in self.ORDER_STATUS_FLAGS:
            if self.is_visible(locator, timeout=8):
                return self.get_text(locator)
        return ""

    def is_pay_page_ready(self) -> bool:
        return self._is_pay_page()
