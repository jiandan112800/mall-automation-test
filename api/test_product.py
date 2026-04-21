import pytest

from common.assertions.api_assertions import assert_status_code
from common.utils.excel_case_loader import assert_by_case_rule, build_request, get_case, run_sql_check


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
