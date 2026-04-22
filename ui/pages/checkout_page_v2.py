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

from ui.pages.base_page import BasePage


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
        print(f"搜索输入框当前值{context}: {typed_value}")
        assert keyword in typed_value, f"Search input value mismatch, expected={keyword}, actual={typed_value}"

        try:
            local_btn = input_el.find_element(By.XPATH, "./following-sibling::button[1]")
            try:
                local_btn.click()
            except Exception:
                self.driver.execute_script("arguments[0].click();", local_btn)
            print(f"搜索按钮点击成功{context}")
        except Exception:
            if self.click_first(self.SEARCH_BUTTONS):
                print(f"搜索按钮点击成功{context}")
            else:
                input_el.send_keys(Keys.ENTER)
                print(f"已使用回车触发搜索{context}")
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
        retry_search_screenshot = f"screenshot_after_search_retry_{int(time.time())}.png"
        self.driver.save_screenshot(retry_search_screenshot)
        print(f"重试加购-搜索后截图: {retry_search_screenshot}")
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
        search_screenshot = f"screenshot_after_search_{int(time.time())}.png"
        self.driver.save_screenshot(search_screenshot)
        print(f"主流程-搜索后截图: {search_screenshot}")

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

from ui.pages.base_page import BasePage


class CheckoutPage(BasePage):
    """精简版结算页：与前端 data-testid / ElementUI 结构对齐，行为与 checkout_page 首段实现一致。"""

    logger = logging.getLogger(__name__)

    # 顺序很重要：避免匹配到页面上其它隐藏的 input[type=text]（会导致 v-model 不同步、搜索共0条）
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
        (By.XPATH, "//input[contains(@placeholder,'请输入商品')]/following-sibling::button[1]"),
        (By.XPATH, "//button[contains(., '搜索')]"),
    ]
    FIRST_PRODUCTS = [
        (By.CSS_SELECTOR, "[data-testid='product-card']"),
        (By.CSS_SELECTOR, ".recommend .el-card:first-child"),
        (By.CSS_SELECTOR, ".el-card:first-child"),
        (By.XPATH, "(//*[contains(@class,'el-card') or contains(@class,'good') or contains(@class,'product')])[1]"),
    ]
    ADD_TO_CART_BTNS = [
        (By.XPATH, "//button[contains(@class,'cart-button') and .//span[normalize-space()='加入购物车']]"),
        (By.CSS_SELECTOR, "button.cart-button"),
        (By.CSS_SELECTOR, "[data-testid='add-to-cart']"),
        (By.CSS_SELECTOR, "button.el-button--warning"),
        (By.XPATH, "//button[contains(normalize-space(.), '加入购物车')]"),
        (By.XPATH, "//*[self::button or self::a][contains(normalize-space(.), '加入购物车')]"),
        (By.XPATH, "//*[contains(@class,'button') and contains(normalize-space(.), '加入购物车')]"),
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
        (By.CSS_SELECTOR, ".spec-item .el-tag"),
        (By.CSS_SELECTOR, ".sku .el-tag"),
        (By.CSS_SELECTOR, ".sku-item"),
        (By.CSS_SELECTOR, ".el-dialog .el-tag"),
        (By.XPATH, "//*[contains(@class,'spec') or contains(@class,'sku')]//*[self::span or self::div or self::button][contains(@class,'tag') or contains(@class,'item')]"),
    ]
    SPEC_CONFIRM_BTNS = [
        (By.XPATH, "//button[contains(normalize-space(.), '确定')]"),
        (By.XPATH, "//button[contains(normalize-space(.), '确认')]"),
        (By.XPATH, "//button[contains(normalize-space(.), '完成')]"),
    ]
    GO_CART_BTNS = [
        (By.XPATH, "//a[contains(normalize-space(.), '我的购物车')]"),
        (By.XPATH, "//a[contains(normalize-space(.), '购物车')]"),
    ]
    CART_PAY_NOW_BTNS = [
        (By.CSS_SELECTOR, "[data-testid='pay-now']"),
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
            cards = driver.find_elements(By.CSS_SELECTOR, "[data-testid='product-card']")
            if len(cards) >= 1:
                return True
            for css in (
                ".recommend .el-card",
                ".el-card",
                ".el-table__body-wrapper tbody .el-table__row",
                ".el-table__body-wrapper tbody tr",
                ".el-table__body .el-table__row",
                ".goods-list .el-card",
                ".product-list .el-card",
            ):
                els = driver.find_elements(By.CSS_SELECTOR, css)
                if any(e.is_displayed() for e in els):
                    return True
            compact = body.replace(" ", "")
            if "共0条" in compact:
                return False
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
        self.logger.info(f"搜索输入框当前值{context}: {typed_value}")
        print(f"搜索输入框当前值{context}: {typed_value}")
        assert keyword in typed_value, f"Search input value mismatch, expected={keyword}, actual={typed_value}"

        local_clicked = False
        try:
            local_btn = input_el.find_element(By.XPATH, "./following-sibling::button[1]")
            self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", local_btn)
            try:
                local_btn.click()
            except Exception:
                self.driver.execute_script("arguments[0].click();", local_btn)
            local_clicked = True
        except Exception:
            local_clicked = False

        if local_clicked or self.click_first(self.SEARCH_BUTTONS):
            self.logger.info(f"搜索按钮点击成功{context}")
            print(f"搜索按钮点击成功{context}")
        else:
            self.logger.warning(f"未点击到搜索按钮，尝试回车触发搜索{context}")
            print(f"未点击到搜索按钮，尝试回车触发搜索{context}")
            input_el.send_keys(Keys.ENTER)
            self.logger.info(f"已使用回车触发搜索{context}")
            print(f"已使用回车触发搜索{context}")
        ok = self._wait_listing_ready(timeout=18)
        if not ok:
            self.logger.error("搜索后列表仍为空")
        return ok

    def _wait_add_to_cart_success(self, timeout: int = 2) -> bool:
        return any(self.is_visible(locator, timeout=timeout) for locator in self.ADD_TO_CART_SUCCESS_MARKERS)

    def _click_add_to_cart_robust(self, retries: int = 2) -> bool:
        for _ in range(retries + 1):
            for locator in self.ADD_TO_CART_BTNS:
                try:
                    # 某些商品必须先选规格，点击前先尝试一次规格选择
                    self._select_spec_if_needed()
                    btn = WebDriverWait(self.driver, 4).until(EC.presence_of_element_located(locator))
                    self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
                    try:
                        btn.click()
                    except Exception:
                        self.driver.execute_script("arguments[0].click();", btn)
                    # 针对已知 HTML（button.cart-button + span加入购物车），允许无 toast 也视为成功点击
                    classes = (btn.get_attribute("class") or "").strip()
                    if "cart-button" in classes:
                        return True
                    if self._wait_add_to_cart_success(timeout=2):
                        return True
                    time.sleep(0.6)
                    # 未看到成功提示，继续尝试其它定位器，不提前判定成功
                    continue
                except Exception:
                    continue
            try:
                # 文案兜底：有些前端不是标准 button/a，而是可点击 div/span
                clicked = self.driver.execute_script(
                    """
                    const nodes = Array.from(
                      document.querySelectorAll("button,a,div,span,[role='button']")
                    );
                    const target = nodes.find(n => {
                      const txt = (n.innerText || n.textContent || "").replace(/\\s+/g, "");
                      if (!txt.includes("加入购物车")) return false;
                      const style = window.getComputedStyle(n);
                      return style && style.display !== "none" && style.visibility !== "hidden";
                    });
                    if (!target) return false;
                    target.scrollIntoView({ block: "center" });
                    target.click();
                    return true;
                    """
                )
                if clicked and self._wait_add_to_cart_success(timeout=2):
                    return True
            except Exception:
                pass
            time.sleep(0.6)
        return False

    def _select_spec_if_needed(self) -> None:
        # 等详情内容稳定，避免规格节点尚未渲染
        time.sleep(0.8)

        # 针对你提供的 HTML：el-radio-group + label[role=radio]
        try:
            radios = self.driver.find_elements(By.CSS_SELECTOR, ".el-radio-group label[role='radio']")
            if radios:
                # 优先点击未选中的规格，触发一次明确选择动作
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
                    time.sleep(0.2)
                    self.click_first(self.SPEC_CONFIRM_BTNS, per_locator_timeout=0.8)
                    return
                # 全部都已选中/不可选时，至少保证有已选规格
                if any((r.get_attribute("aria-checked") or "").lower() == "true" for r in radios):
                    return
                first = radios[0]
                self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", first)
                try:
                    first.click()
                except Exception:
                    self.driver.execute_script("arguments[0].click();", first)
                time.sleep(0.2)
                self.click_first(self.SPEC_CONFIRM_BTNS, per_locator_timeout=0.8)
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

        picked = False
        for by, sel in self.SPEC_OPTION_LOCATORS:
            try:
                opts = self.driver.find_elements(by, sel)
                if opts and _click_first_enabled(opts):
                    picked = True
                    break
            except Exception:
                continue

        # 有些页面点规格后需要点“确定/确认”
        if picked:
            self.click_first(self.SPEC_CONFIRM_BTNS, per_locator_timeout=0.8)

    def _is_add_to_cart_ready(self) -> bool:
        return any(self.is_visible(locator, timeout=1) for locator in self.ADD_TO_CART_BTNS)

    def _open_first_product_detail(self) -> bool:
        image_locators = [
            (By.CSS_SELECTOR, ".goods-list img"),
            (By.CSS_SELECTOR, ".product-list img"),
            (By.CSS_SELECTOR, ".recommend img"),
            (By.CSS_SELECTOR, ".el-col img"),
            (By.CSS_SELECTOR, ".el-image img"),
            (By.XPATH, "(//img[contains(@src,'/file/')])[1]"),
        ]
        for locator in image_locators:
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

        row_locators = [
            (By.CSS_SELECTOR, ".el-table__body-wrapper tbody tr:first-child"),
            (By.CSS_SELECTOR, ".el-table tbody tr:first-child"),
        ]
        for locator in row_locators:
            try:
                row = WebDriverWait(self.driver, 4).until(EC.presence_of_element_located(locator))
                self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", row)
                try:
                    row.click()
                except Exception:
                    self.driver.execute_script("arguments[0].click();", row)
                time.sleep(0.4)
                if self._is_add_to_cart_ready():
                    return True
            except Exception:
                continue

        for locator in self.FIRST_PRODUCTS:
            try:
                card = WebDriverWait(self.driver, 4).until(EC.presence_of_element_located(locator))
                self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", card)
                try:
                    card.click()
                except Exception:
                    self.driver.execute_script("arguments[0].click();", card)
                if self._is_add_to_cart_ready():
                    return True
                for css in ("a", "img", ".el-card__body", ".name", ".title"):
                    try:
                        child = card.find_element(By.CSS_SELECTOR, css)
                        try:
                            child.click()
                        except Exception:
                            self.driver.execute_script("arguments[0].click();", child)
                        if self._is_add_to_cart_ready():
                            return True
                    except Exception:
                        continue
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
        # 结算按钮存在时，优先视为非空，避免被页面其它“去购物”等文案误判
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
            assert self._wait_listing_ready(timeout=18), (
                "Strict search failed on retry add: no rows after clicking search and opening goodList?searchText"
            )
        retry_search_screenshot = f"screenshot_after_search_retry_{int(time.time())}.png"
        self.driver.save_screenshot(retry_search_screenshot)
        self.logger.info(f"重试加购-搜索后截图: {retry_search_screenshot}")
        print(f"重试加购-搜索后截图: {retry_search_screenshot}")
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

    def complete_checkout(
        self,
        base_url: str,
        keyword: str = "手机",
        home_path: str = "/topview",
        cart_path: str = "/cart",
    ) -> str:
        self.open(f"{base_url}{home_path}")
        try:
            self.wait_for_vue_app_mounted(timeout=25)
        except Exception:
            pass

        searched = self._search_with_fallback(keyword)
        if not searched:
            encoded = quote(keyword, safe="")
            self.open(f"{base_url}/goodList?searchText={encoded}")
            assert self._wait_listing_ready(timeout=18), (
                "Strict search failed: no rows after clicking search and opening goodList?searchText"
            )
        search_screenshot = f"screenshot_after_search_{int(time.time())}.png"
        self.driver.save_screenshot(search_screenshot)
        self.logger.info(f"主流程-搜索后截图: {search_screenshot}")
        print(f"主流程-搜索后截图: {search_screenshot}")

        assert self._open_first_product_detail(), "No product detail opened (check product card selectors)"
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

        assert self.click_first(self.CART_PAY_NOW_BTNS, per_locator_timeout=4), "Pay-now button not found after navigating to cart"
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
