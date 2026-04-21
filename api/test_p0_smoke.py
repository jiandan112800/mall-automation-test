import os
from typing import Any, Optional

import pytest
import allure

from common.assertions.api_assertions import (
    assert_status_code,
    assert_auth_failure,
)
from common.utils.excel_case_loader import assert_by_case_rule, build_request, get_case
from common.utils.excel_case_loader import extract_vars_from_response
from common.utils.excel_case_loader import run_sql_check


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
    with allure.step("Call userid without token"):
        case = get_case("P0-AUTH-002")
        api_client.clear_token()
        resp = api_client.get(api_paths["userid_path"])
        allure.attach(str(resp.status_code), "status-code", allure.attachment_type.TEXT)
        allure.attach(resp.text, "response-body", allure.attachment_type.TEXT)
    with allure.step("Assert auth failed as expected"):
        assert_by_case_rule(resp, case)
        assert_auth_failure(resp)


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


@pytest.mark.labels("smoke", "order")
def test_api_order_list(api_client, case_context, db_client, db_tx):
    case = get_case("P0-ORDER-001")
    path, params, data, json_body = build_request(case, case_context)
    resp_all = api_client.get(path, params=params, data=data, json=json_body)
    assert_by_case_rule(resp_all, case)
    run_sql_check(case, case_context, db_client=db_client, db_tx=db_tx)
    assert_status_code(resp_all, 200)
    data_all = _get_result_data(resp_all)
    assert data_all is not None


@pytest.mark.labels("smoke", "order")
def test_api_order_my(api_client, case_context, db_client, db_tx):
    case = get_case("P0-ORDER-002")
    path, params, data, json_body = build_request(case, case_context)
    resp_my = api_client.get(path, params=params, data=data, json=json_body)
    assert_by_case_rule(resp_my, case)
    assert_status_code(resp_my, 200)
    case_context.update(extract_vars_from_response(case, resp_my.json()))
    run_sql_check(case, case_context, db_client=db_client, db_tx=db_tx)
    my_orders = _get_result_data(resp_my)
    assert my_orders is not None


@pytest.mark.labels("smoke", "order", "payment")
def test_api_order_paid(api_client, env_config, case_context, db_client, db_tx):
    case_my = get_case("P0-ORDER-002")
    # 先从 /my 获取订单号
    path_my, params_my, data_my, json_my = build_request(case_my, case_context)
    resp_my = api_client.get(path_my, params=params_my, data=data_my, json=json_my)
    assert_by_case_rule(resp_my, case_my)
    assert_status_code(resp_my, 200)
    my_orders = _get_result_data(resp_my)
    if isinstance(my_orders, list) and not my_orders:
        pytest.skip("No orders in /api/order/my for current user.")

    order_item = _pick_order_item(my_orders)

    # 允许通过配置指定一个“可用于 paid 的订单号”，提高稳定性
    order_no = (
        env_config.get("orderNoPaid")
        or os.getenv("ORDER_NO_PAID")
        or case_context.get("orderNo")
    )
    if not order_no:
        order_no = _extract_order_no(order_item)

    if not order_no:
        pytest.skip("Cannot determine orderNo for /api/order/paid; set config.orderNoPaid to proceed.")

    # 支付订单（paid）
    case_paid = get_case("P0-ORDER-003")
    context = {"orderNo": order_no, **case_context}
    path_paid, params_paid, data_paid, json_paid = build_request(case_paid, context)
    resp_paid = api_client.get(path_paid, params=params_paid, data=data_paid, json=json_paid)
    assert_by_case_rule(resp_paid, case_paid)
    run_sql_check(case_paid, context, db_client=db_client, db_tx=db_tx)
    # 接口可能返回 Result 错误码但 HTTP 仍是 200；因此优先走 body 断言
    assert_status_code(resp_paid, 200)

