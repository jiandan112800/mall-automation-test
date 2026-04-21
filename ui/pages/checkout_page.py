import logging
import time

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from ui.pages.base_page import BasePage


class CheckoutPage(BasePage):
    logger = logging.getLogger(__name__)
    SEARCH_INPUTS = [
        (By.CSS_SELECTOR, "[data-testid='search-input']"),
        (By.CSS_SELECTOR, "input.el-input__inner[placeholder*='搜索']"),
        (By.CSS_SELECTOR, "input.el-input__inner[placeholder*='关键词']"),
        (By.CSS_SELECTOR, ".el-header input.el-input__inner"),
        (By.CSS_SELECTOR, "input[placeholder*='搜索']"),
        (By.CSS_SELECTOR, "input[type='text']"),
    ]
    SEARCH_BUTTONS = [
        (By.CSS_SELECTOR, "[data-testid='search-btn']"),
        (By.XPATH, "//i[contains(@class,'el-icon-search')]/ancestor::button[1]"),
        (By.XPATH, "//button[contains(@class,'el-button') and .//span[contains(.,'搜索')]]"),
        (By.XPATH, "//button[contains(., '搜索')]"),
        (By.XPATH, "//button[contains(., '查询')]"),
        (By.CSS_SELECTOR, ".el-input-group__append button"),
        (By.CSS_SELECTOR, ".el-icon-search"),
    ]
    FIRST_PRODUCTS = [
        (By.CSS_SELECTOR, "[data-testid='product-card']:first-child"),
        (By.CSS_SELECTOR, "#app .el-row .el-col:first-child .el-card"),
        (By.CSS_SELECTOR, "#app .el-card"),
        (By.CSS_SELECTOR, ".good-card:first-child"),
        (By.CSS_SELECTOR, ".goods-item:first-child"),
        (By.CSS_SELECTOR, ".product-item:first-child"),
        (By.XPATH, "(//*[contains(@class,'good') or contains(@class,'product')])[1]"),
    ]
    ADD_TO_CART_BTNS = [
        (By.CSS_SELECTOR, "[data-testid='add-to-cart']"),
        (By.XPATH, "//button[contains(@class,'el-button') and .//span[contains(.,'加入购物车')]]"),
        (By.XPATH, "//button[contains(., '加入购物车')]"),
    ]
    GO_CART_BTNS = [
        (By.XPATH, "//a[contains(normalize-space(.), '我的购物车')]"),
        (By.XPATH, "//*[self::a or self::span or self::div][contains(normalize-space(.), '我的购物车')]"),
        (By.CSS_SELECTOR, "[data-testid='go-cart']"),
        (By.XPATH, "//a[contains(@class,'el-menu-item') and contains(., '购物车')]"),
        (By.XPATH, "//*[contains(@class,'el-menu-item') and .//span[contains(.,'购物车')]]"),
        (By.XPATH, "//a[contains(., '购物车')]"),
        (By.XPATH, "//button[contains(., '购物车')]"),
        (By.XPATH, "//*[contains(@class,'cart') and (self::a or self::button)]"),
    ]
    # 购物车页按钮：点击后跳转到「提交订单」页面
    CART_PAY_NOW_BTNS = [
        (By.CSS_SELECTOR, "[data-testid='pay-now']"),
        (By.CSS_SELECTOR, "button.pay-btn.el-button--success"),
        (By.CSS_SELECTOR, ".action-section button.el-button--success"),
        (By.XPATH, "//button[contains(@class,'el-button') and .//span[contains(.,'立即支付')]]"),
        (By.XPATH, "//button[contains(normalize-space(.), '立即支付')]"),
    ]
    # 提交订单页按钮：点击后进入结算页（图二）
    SUBMIT_ORDER_BTNS = [
        (By.CSS_SELECTOR, "[data-testid='submit-order']"),
        (By.XPATH, "//button[contains(@class,'el-button') and .//span[contains(.,'提交订单')]]"),
        (By.XPATH, "//button[contains(normalize-space(.), '提交订单')]"),
    ]
    ORDER_PAGE_MARKERS = [
        (By.XPATH, "//*[contains(normalize-space(.), '收货地址')]"),
        (By.XPATH, "//*[contains(normalize-space(.), '提交订单')]"),
        (By.XPATH, "//*[contains(normalize-space(.), '总价')]"),
    ]
    PAY_PAGE_MARKERS = [
        (By.XPATH, "//*[contains(normalize-space(.), '订单号')]"),
        (By.XPATH, "//*[contains(normalize-space(.), '支付方式')]"),
        (By.XPATH, "//*[contains(normalize-space(.), '金额')]"),
    ]
    # 结算页：支付方式图标（通常是微信/支付宝图标）
    PAY_METHOD_BTNS = [
        (By.CSS_SELECTOR, "[data-testid='pay-wechat']"),
        (By.CSS_SELECTOR, "[data-testid='pay-alipay']"),
        (
            By.XPATH,
            "//*[contains(@class,'wechat') or contains(@class,'Wechat')]"
            "[self::div or self::span or self::button or self::img]",
        ),
        (
            By.XPATH,
            "//*[contains(@class,'alipay') or contains(@class,'Alipay')]"
            "[self::div or self::span or self::button or self::img]",
        ),
        (
            By.XPATH,
            "//*[contains(., '微信支付') or contains(., '微信')]"
            "[self::div or self::span or self::button or self::a or self::img]",
        ),
        (By.XPATH, "//*[contains(., '支付宝')][self::div or self::span or self::button or self::a or self::img]"),
        # 根据你提供的HTML截图：支付方式是两个 img 标签，带有 cursor: pointer 样式
        (By.XPATH, "//img[contains(@style,'cursor: pointer') and @src]"),
        (By.CSS_SELECTOR, "img[style*='cursor: pointer']"),
    ]
    ORDER_STATUS_FLAGS = [
        (By.CSS_SELECTOR, "[data-testid='order-status']"),
        (By.XPATH, "//*[contains(text(), '已支付')]"),
        (By.XPATH, "//*[contains(text(), '支付成功')]"),
    ]

    CART_URLS = ["/cart", "/#/cart", "/front/cart", "/index/cart"]

    def _wait_add_to_cart_toast_dismissed(self, max_wait: float = 6.0) -> None:
        """加购后顶部 Toast 可能遮挡导航/购物车，等待其消失再后续操作。"""
        try:
            # 同时兼容 Element UI 常见消息容器
            toast_locator = (
                By.CSS_SELECTOR,
                ".el-message, .el-message-box__wrapper, [role='alert']",
            )
            WebDriverWait(self.driver, 2).until(
                EC.presence_of_element_located(toast_locator)
            )
            WebDriverWait(self.driver, max_wait).until(
                EC.invisibility_of_element_located(toast_locator)
            )
            self.logger.info("Toast 提示已消失")
        except Exception:
            # 如果没找到 Toast，短暂等待让页面稳定
            self.logger.warning("未检测到 Toast，使用默认等待时间")
            time.sleep(1.5)

    def _click_my_cart_nav(self) -> bool:
        """优先点击导航栏「我的购物车」，失败再交给通用入口逻辑。"""
        my_cart_locators = [
            (By.XPATH, "//a[contains(normalize-space(.), '我的购物车')]"),
            (
                By.XPATH,
                "//*[contains(@class,'el-menu-item') and contains(normalize-space(.), '我的购物车')]",
            ),
            (
                By.XPATH,
                "//*[self::a or self::span or self::div][contains(normalize-space(.), '我的购物车')]",
            ),
        ]
        if self.click_first(my_cart_locators, per_locator_timeout=2):
            self.logger.info("已点击导航栏“我的购物车”")
            return True
        return False

    def _is_cart_page(self) -> bool:
        current_url = (self.driver.current_url or "").lower()
        if "cart" in current_url:
            return True
        cart_page_markers = [
            (By.XPATH, "//*[contains(normalize-space(.), '我的购物车')]"),
            (By.XPATH, "//*[contains(normalize-space(.), '购物车')]"),
            (By.XPATH, "//button[contains(normalize-space(.), '立即支付')]"),
            (By.XPATH, "//button[contains(normalize-space(.), '结算')]"),
        ]
        return any(self.is_visible(locator, timeout=1) for locator in cart_page_markers)

    def _wait_after_cart_checkout_click(self) -> None:
        """点击「立即支付」等进入提交订单页后，等待 SPA 渲染稳定。"""
        try:
            self.wait_for_vue_app_mounted(timeout=15)
        except Exception:
            pass
        time.sleep(0.8)

    def _is_order_page(self) -> bool:
        current_url = (self.driver.current_url or "").lower()
        if "preorder" in current_url:
            return True
        return any(self.is_visible(locator, timeout=1) for locator in self.ORDER_PAGE_MARKERS)

    def _is_pay_page(self) -> bool:
        current_url = (self.driver.current_url or "").lower()
        if "/pay" in current_url:
            return True
        return any(self.is_visible(locator, timeout=1) for locator in self.PAY_PAGE_MARKERS)

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

        # 搜索与加购步骤允许跳过，避免首页结构差异导致主链路中断
        if self.type_first(self.SEARCH_INPUTS, keyword):
            self.click_first(self.SEARCH_BUTTONS)
        
        assert self.click_first(self.FIRST_PRODUCTS), (
            "No product entry found (check home_path / page structure or data-testid)"
        )
        
        assert self.click_first(self.ADD_TO_CART_BTNS), "Add-to-cart control not found"
        
        # 等待 Toast 消失，避免遮挡购物车按钮
        self._wait_add_to_cart_toast_dismissed()

        # 进入购物车
        if not self._click_my_cart_nav() and not self.click_first(self.GO_CART_BTNS):
            # 路径 B：直接通过 URL 访问购物车
            self.logger.info("未找到购物车导航按钮，尝试直接访问购物车页面")
            self.open(f"{base_url}{cart_path}")
            
            if not self.click_first(self.CART_PAY_NOW_BTNS):
                # 兼容其他购物车路由
                entered = False
                for route in self.CART_URLS:
                    self.logger.info(f"尝试备用购物车路由: {route}")
                    self.open(f"{base_url}{route}")
                    if self.click_first(self.CART_PAY_NOW_BTNS):
                        self.logger.info(f"成功通过路由 {route} 点击立即支付")
                        entered = True
                        break
                
                assert entered, "Pay-now button not found in any cart routes"
            else:
                self.logger.info("成功在指定购物车路径点击立即支付")
        else:
            self.logger.info("成功点击购物车导航按钮")
            # 等待购物车页面加载完成
            time.sleep(2)
            try:
                self.wait_for_vue_app_mounted(timeout=10)
            except Exception:
                pass
            assert self._is_cart_page(), "点击导航栏后仍未进入购物车页面"
            
            # 调试：截图并打印页面信息
            screenshot_path = f"screenshot_cart_{int(time.time())}.png"
            self.driver.save_screenshot(screenshot_path)
            self.logger.info(f"已保存购物车页面截图: {screenshot_path}")
            
            # 打印页面上所有按钮的文本
            try:
                all_buttons = self.driver.find_elements(By.TAG_NAME, "button")
                button_texts = [btn.text.strip() for btn in all_buttons if btn.text.strip()]
                self.logger.info(f"页面上的按钮文本: {button_texts}")
            except Exception as e:
                self.logger.warning(f"无法获取按钮列表: {e}")
            
            if self.click_first(self.CART_PAY_NOW_BTNS):
                self.logger.info("成功在购物车页面点击立即支付")
            else:
                self.logger.error("在购物车页面未找到立即支付按钮")
                self.logger.error(f"请检查截图: {screenshot_path}")
                assert False, "Pay-now button not found after navigating to cart"

        # 第一步完成：已从购物车点击立即支付，进入提交订单页面（图一）
        self._wait_after_cart_checkout_click()
        assert self._is_order_page(), "点击立即支付后未进入提交订单页面"
        self.logger.info("已进入提交订单页面")

        # 第二步：提交订单，进入结算页（图二）
        assert self.click_first(self.SUBMIT_ORDER_BTNS), "Submit-order button not found"
        self._wait_after_cart_checkout_click()
        assert self._is_pay_page(), "点击提交订单后未进入结算页面"
        self.logger.info("已进入结算页面")
        
        # 第三步：结算页选择支付方式（可选）
        pay_method_clicked = self.click_first(self.PAY_METHOD_BTNS)
        if pay_method_clicked:
            self.logger.info("已选择支付方式")
        else:
            self.logger.warning("未找到支付方式图标")

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
