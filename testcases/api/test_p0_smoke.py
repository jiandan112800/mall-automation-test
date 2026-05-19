import os
import re
from typing import Any, Optional

import pytest
import allure

from common.assertions.api_assertions import (
    assert_status_code,
    assert_auth_failure,
)
from common.assertions.case_assertions import assert_by_case_rule
from common.utils.excel_case_loader import build_request, get_case
from common.utils.excel_case_loader import extract_vars_from_response
from common.utils.excel_case_loader import run_sql_check
from common.logger import get_logger

logger = get_logger(__name__)


def _extract_order_no(order_item: Any) -> Optional[str]:
    """
    后端 Order 对象的字段名可能在 JSON 里是 orderNo 或 order_no。
    做一个兼容提取，避免字段命名差异导致测试全部失败。
    """
    if isinstance(order_item, dict):
        for key in ("orderNo", "order_no", "orderNO"):
            val = order_item.get(key)
            if val is not None:
                return str(val)
    return None


def _get_result_data(resp) -> Any:
    case = {"check": "res.json.code", "expected": "200"}
    assert_by_case_rule(resp, case)
    body = resp.json()
    return body.get("data")


@pytest.mark.labels("smoke", "security")
@allure.epic("API Automation")
@allure.feature("Auth")
@allure.story("Userid auth guard")
@allure.title("API: userid endpoint requires login")
def test_userid_requires_login(api_client, api_paths):
    # api_client 为 session 级共享，测完必须恢复 token，避免污染后续用例
    prev = api_client.session.headers.get("token")
    with allure.step("Call userid without token"):
        case = get_case("P0-AUTH-002")
        api_client.clear_token()
        resp = api_client.get(api_paths["userid_path"])
        allure.attach(str(resp.status_code), "status-code", allure.attachment_type.TEXT)
        allure.attach(resp.text, "response-body", allure.attachment_type.TEXT)
    with allure.step("Assert auth failed as expected"):
        assert_by_case_rule(resp, case)
        assert_auth_failure(resp)
    if prev:
        api_client.set_token(str(prev))


@pytest.mark.labels("smoke", "user")
@allure.epic("API Automation")
@allure.feature("User")
@allure.story("Get current userid")
@allure.title("API: userid endpoint works after login")
def test_userid_with_login(api_client, current_user_id, api_paths, case_context, db_client, db_tx):
    with allure.step("Call userid with authorized session"):
        case = get_case("P0-USER-001")
        resp = api_client.get(api_paths["userid_path"])
        allure.attach(str(resp.status_code), "status-code", allure.attachment_type.TEXT)
        allure.attach(resp.text, "response-body", allure.attachment_type.TEXT)
    with allure.step("Assert userid and optional SQL check"):
        assert_by_case_rule(resp, case)
        assert_status_code(resp, 200)
        try:
            assert int(resp.json()) == int(current_user_id)
            case_context["current_user_id"] = int(current_user_id)
            run_sql_check(case, {**case_context, "current_user_id": int(current_user_id)}, db_client=db_client, db_tx=db_tx)
        except Exception:
            pytest.fail(f"Unexpected /userid response: {resp.text}")


@pytest.mark.labels("smoke", "address")
def test_api_address_by_userid(api_client, current_user_id, case_context, db_client, db_tx):
    case = get_case("P0-ADDR-001")
    context = {"current_user_id": current_user_id, **case_context}
    path, params, data, json_body = build_request(case, context)
    resp = api_client.get(path, params=params, data=data, json=json_body)
    assert_by_case_rule(resp, case)
    run_sql_check(case, context, db_client=db_client, db_tx=db_tx)
    assert_status_code(resp, 200)
    data = _get_result_data(resp)
    # address list 或单条地址都允许，这里只做“非空”约束
    assert data is not None

def _pick_order_item(my_orders: Any) -> Any:
    order_item = None
    if isinstance(my_orders, list):
        order_item = my_orders[0]
    elif isinstance(my_orders, dict):
        # 若返回不是 list（例如带分页），可以尝试 records
        for key in ("records", "list", "items"):
            if key in my_orders and isinstance(my_orders[key], list) and my_orders[key]:
                order_item = my_orders[key][0]
                break
    return order_item


def _extract_order_state(order_item: Any) -> str:
    if not isinstance(order_item, dict):
        return ""
    for key in ("state", "status", "orderState"):
        val = order_item.get(key)
        if val is not None:
            return str(val)
    return ""


def _find_order_by_state(order_items: Any, include_keywords: tuple[str, ...], exclude_keywords: tuple[str, ...] = ()) -> str | None:
    if not isinstance(order_items, list):
        return None
    for item in order_items:
        order_no = _extract_order_no(item)
        if not order_no:
            continue
        state = _extract_order_state(item)
        if include_keywords and not any(k in state for k in include_keywords):
            continue
        if exclude_keywords and any(k in state for k in exclude_keywords):
            continue
        return order_no
    return None


def _call_pay(api_client, order_no: str):
    return api_client.get(f"/api/order/paid/{order_no}")


def _assert_result_code_and_msg(resp, code_candidates: tuple[str, ...], msg_keywords: tuple[str, ...] = ()) -> None:
    assert_status_code(resp, 200)
    try:
        body = resp.json()
    except Exception:
        pytest.fail(f"Response is not JSON: status={resp.status_code}, body={resp.text}")
    actual_code = str(body.get("code")) if isinstance(body, dict) and "code" in body else ""
    assert actual_code in code_candidates, f"Unexpected code={actual_code}, expected={code_candidates}, body={body}"
    if msg_keywords:
        msg = str(body.get("msg", "")) if isinstance(body, dict) else ""
        assert any(k in msg for k in msg_keywords), f"Unexpected msg={msg!r}, expected keywords={msg_keywords}, body={body}"


def _query_order_state_from_db(db_client, order_no: str) -> str | None:
    if db_client is None:
        return None
    sql = f"SELECT state FROM t_order WHERE order_no='{order_no}' LIMIT 1;"
    val = db_client.query_first(sql)
    if val is None:
        return None
    return str(val)


@pytest.mark.labels("smoke", "order")
def test_api_order_list(api_client, auth_token, case_context, db_client, db_tx):
    case = get_case("P0-ORDER-001")
    path, params, data, json_body = build_request(case, case_context)
    resp_all = api_client.get(path, params=params, data=data, json=json_body)
    assert_by_case_rule(resp_all, case)
    run_sql_check(case, case_context, db_client=db_client, db_tx=db_tx)
    assert_status_code(resp_all, 200)
    data_all = _get_result_data(resp_all)
    assert data_all is not None


@pytest.mark.labels("smoke", "order")
def test_api_order_my(api_client, auth_token, case_context, db_client, db_tx):
    case = get_case("P0-ORDER-002")
    path, params, data, json_body = build_request(case, case_context)
    resp_my = api_client.get(path, params=params, data=data, json=json_body)
    assert_by_case_rule(resp_my, case)
    assert_status_code(resp_my, 200)
    case_context.update(extract_vars_from_response(case, resp_my.json()))
    run_sql_check(case, case_context, db_client=db_client, db_tx=db_tx)
    my_orders = _get_result_data(resp_my)
    assert my_orders is not None


class TestPaymentP0:
    @pytest.mark.labels("smoke", "order", "payment")
    def test_payment_create_success_flow(self, api_client, auth_token, case_context, db_client):
        """
        1) 正向流程：支付创建成功
        - 从订单列表挑一笔非“已支付”的订单
        - 调用支付接口
        - 断言 code=200；若有 DB 配置则校验状态变更为待支付/支付中/已支付之一
        """
        resp_my = api_client.get("/api/order/my")
        assert_status_code(resp_my, 200)
        my_orders = _get_result_data(resp_my)
        order_no = _find_order_by_state(my_orders, include_keywords=("待付款", "待支付", "支付中"), exclude_keywords=("已支付",))
        if not order_no:
            # 若列表里无待支付，也允许拿第一笔订单验证接口可用性（兼容测试环境脏数据）
            order_no = _extract_order_no(_pick_order_item(my_orders))
        if not order_no:
            pytest.skip("No available orderNo found in /api/order/my for payment success flow.")

        resp = _call_pay(api_client, order_no)
        _assert_result_code_and_msg(resp, ("200",))

        state = _query_order_state_from_db(db_client, order_no)
        if state is not None:
            assert any(k in state for k in ("待付款", "待支付", "支付中", "已支付")), f"Unexpected DB state after pay: {state}"

    @pytest.mark.labels("smoke", "order", "payment", "negative")
    def test_payment_missing_required_param(self, api_client, auth_token):
        """
        2) 路径中缺少 {orderNo}（本次请求未指明要支付哪一笔订单）：
        预期为客户端/路由可见的错误（常见 404、405，或进入业务后的 4xx），不应作为未捕获异常返回 500。
        """
        candidates = ["/api/order/paid", "/api/order/paid/"]
        matched = False
        for path in candidates:
            resp = api_client.get(path)
            logger.info(
                "payment missing param probe: path=%s status=%s request_headers=%s response_body=%s",
                path,
                resp.status_code,
                dict(resp.request.headers),
                resp.text,
            )
            if resp.status_code in (404, 405):
                # 路由层拒绝，继续探测另一路径
                continue
            matched = True
            assert resp.status_code < 500, (
                "missing path orderNo should not yield 5xx; "
                f"got status={resp.status_code}, body={resp.text}"
            )
            break
        if not matched:
            pytest.skip("Router rejects missing path-param directly (404/405), business-layer assertion skipped.")

    @pytest.mark.labels("smoke", "order", "payment", "negative")
    @pytest.mark.parametrize("bad_amount", [0, -0.01, -100])
    def test_payment_invalid_amount_not_supported_by_current_api(self, api_client, auth_token, bad_amount):
        """
        3) 金额零或负数：
        当前支付接口仅接受 path-orderNo，不接受 amount 参数，无法在该接口层面直接验证。
        """
        pytest.skip(
            f"Current API '/api/order/paid/{{orderNo}}' has no amount field; cannot validate bad amount={bad_amount}. "
            "Need payment-create API with explicit amount."
        )

    @pytest.mark.labels("smoke", "order", "payment", "negative")
    def test_payment_nonexistent_order(self, api_client, auth_token):
        """
        4) 路径上带了 orderNo，但库中不存在该单（与「路径里完全缺 orderNo」不同）：
        预期业务明确失败（如 code≠200、msg 提示无效/不存在），HTTP 层不应 5xx。
        """
        fake_order_no = f"NOT_EXIST_{os.getpid()}_{os.getpid() % 1000}"
        path = f"/api/order/paid/{fake_order_no}"
        resp = _call_pay(api_client, fake_order_no)
        logger.info(
            "payment nonexistent order: path=%s status=%s request_headers=%s response_body=%s",
            path,
            resp.status_code,
            dict(resp.request.headers),
            resp.text,
        )
        assert resp.status_code < 500, f"Non-existent order should not crash: {resp.status_code}, body={resp.text}"
        try:
            body = resp.json()
        except Exception:
            pytest.fail(f"Expected JSON for nonexistent order, got: {resp.text}")
        code = str(body.get("code")) if isinstance(body, dict) else ""
        assert code != "200", f"Non-existent order should not succeed, body={body}"
        msg = str(body.get("msg", "")) if isinstance(body, dict) else ""
        if msg:
            assert any(k in msg for k in ("不存在", "无效", "not", "fail", "失败")), f"Unexpected msg for nonexistent order: {msg}"

    @pytest.mark.labels("smoke", "order", "payment", "idempotency")
    def test_payment_repeat_paid_order_idempotent(self, api_client, auth_token):
        """
        5) 重复支付幂等：
        对已支付订单重复调用，不能再次扣款；应返回“已支付/重复”类结果或幂等成功。
        """
        resp_my = api_client.get("/api/order/my")
        assert_status_code(resp_my, 200)
        my_orders = _get_result_data(resp_my)
        paid_order_no = _find_order_by_state(my_orders, include_keywords=("已支付",))
        if not paid_order_no:
            pytest.skip("No paid order found in /api/order/my to validate idempotency.")
        resp = _call_pay(api_client, paid_order_no)
        assert_status_code(resp, 200)
        body = resp.json()
        code = str(body.get("code")) if isinstance(body, dict) else ""
        msg = str(body.get("msg", "")) if isinstance(body, dict) else ""
        # 允许两种：幂等成功(200) 或 业务拒绝(非200 + 已支付/重复提示)
        if code == "200":
            return
        assert any(k in msg for k in ("已支付", "重复", "勿重复", "already")), f"Unexpected idempotency message: code={code}, msg={msg}, body={body}"

    @pytest.mark.labels("smoke", "order", "payment", "callback")
    def test_payment_callback_success_processing_not_available(self):
        """
        6) 支付回调成功处理：
        目前未提供可用回调接口契约（URL/签名/字段），先显式跳过，避免假断言。
        """
        pytest.skip("Payment callback contract is missing. Need callback URL/method/body/signature spec.")

    @pytest.mark.labels("smoke", "order", "payment", "resilience")
    def test_payment_downstream_timeout_not_available(self):
        """
        7) 下游超时：
        说明：Mock 是“用替身模拟下游行为”的测试技术，例如把下游支付接口模拟成超时返回。
        当前项目未接入下游 mock 框架与可注入点，先显式跳过。
        """
        pytest.skip("No downstream mock hook configured yet. Need mock framework (responses/pytest-mock) and injection point.")

    @pytest.mark.labels("smoke", "order", "payment", "security")
    def test_payment_requires_auth(self, api_client):
        """
        8) 未授权访问
        """
        prev = api_client.session.headers.get("token")
        try:
            api_client.clear_token()
            resp = _call_pay(api_client, "20260424113602748407")
            # 与你要求一致：按 code401 校验（兼容 HTTP 401/403）
            assert_auth_failure(resp)
        finally:
            if prev:
                api_client.set_token(str(prev))
