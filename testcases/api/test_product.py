from typing import Any

import pytest

from common.assertions.api_assertions import assert_status_code
from common.assertions.case_assertions import assert_by_case_rule
from common.utils.excel_case_loader import build_request, get_case, run_sql_check


@pytest.mark.labels("smoke", "good")
def test_product_list(api_client, case_context, db_client, db_tx):
    # GoodController: GET /api/good 返回推荐/前台商品列表
    case = get_case("P0-GOOD-001")
    path, params, data, json_body = build_request(case, {})
    resp = api_client.get(path, params=params, data=data, json=json_body)
    assert_by_case_rule(resp, case)
    run_sql_check(case, case_context, db_client=db_client, db_tx=db_tx)
    assert_status_code(resp, 200)
    body = resp.json()
    assert "data" in body, f"Missing data in response: {body}"


def _extract_first_good_id(goods_data: Any) -> int | None:
    records = goods_data
    if isinstance(goods_data, dict):
        for key in ("records", "list", "items", "rows", "data"):
            v = goods_data.get(key)
            if isinstance(v, list) and v:
                records = v
                break
    if not isinstance(records, list) or not records:
        return None
    first = records[0]
    if not isinstance(first, dict):
        return None
    for key in ("id", "goodId", "goodsId"):
        value = first.get(key)
        if value is not None:
            try:
                return int(value)
            except Exception:
                return None
    return None


def _is_result_success(resp) -> bool:
    try:
        body = resp.json()
    except Exception:
        return False
    if isinstance(body, dict) and "code" in body:
        return str(body.get("code")) == "200"
    return resp.status_code == 200


@pytest.mark.labels("smoke", "cart", "add")
def test_api_cart_add_success(api_client, auth_token, case_context):
    # 1) 先从商品列表获取一个可用 good_id（避免写死测试数据）
    case_goods = get_case("P0-GOOD-001")
    path, params, data, json_body = build_request(case_goods, case_context)
    resp_goods = api_client.get(path, params=params, data=data, json=json_body)
    assert_status_code(resp_goods, 200)
    goods_body = resp_goods.json()
    goods_data = goods_body.get("data") if isinstance(goods_body, dict) else None
    good_id = _extract_first_good_id(goods_data)
    assert good_id is not None, f"Cannot extract good id from /api/good response: {goods_body}"

    # 2) 探测常见加购接口与参数风格（兼容不同后端实现）
    endpoints = [
        "/api/cart",
        "/cart",
        "/api/cart/add",
        "/cart/add",
        "/api/shoppingCart/add",
        "/api/shoppingcart/add",
        "/api/shoppingCart",
        "/api/shoppingcart",
        f"/api/cart/{good_id}",
        f"/cart/{good_id}",
    ]
    payloads = [
        {"goodId": good_id, "count": 1},
        {"goodId": good_id, "num": 1},
        {"goodsId": good_id, "count": 1},
        {"goodsId": good_id, "num": 1},
        {"id": good_id, "count": 1},
    ]

    tried: list[str] = []
    for ep in endpoints:
        for payload in payloads:
            # 某些后端把加购做成 GET（参数在 query），这里同时兼容 GET/POST。
            candidates = [
                ("POST", {"json": payload}),
                ("POST", {"data": payload}),
                ("GET", {"params": payload}),
            ]
            for method, kwargs in candidates:
                resp = api_client.request(method, ep, **kwargs)
                tried.append(f"{method} {ep} <- {payload}")
                # 接口/方法不匹配：继续探测其它组合
                if resp.status_code == 404:
                    continue
                mismatch_signatures = (
                    "not supported",
                    "failed to convert value",
                    "numberformatexception",
                    "required type",
                )
                resp_text = (resp.text or "").lower()
                if resp.status_code >= 500 and any(s in resp_text for s in mismatch_signatures):
                    continue
                assert_status_code(resp, 200)
                assert _is_result_success(resp), (
                    f"Cart add business failed: method={method}, ep={ep}, payload={payload}, body={resp.text}"
                )
                return

    pytest.fail("Cart add API not found or all payload styles failed. tried=" + " | ".join(tried))
