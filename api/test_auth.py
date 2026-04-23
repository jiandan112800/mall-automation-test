import logging

import pytest
 
from common.assertions.api_assertions import (
    assert_auth_failure,
)
from common.utils.auth_helpers import encode_login_password
from common.utils.excel_case_loader import (
    assert_by_case_rule,
    build_request,
    extract_vars_from_response,
    get_case,
    run_sql_check,
)

logger = logging.getLogger(__name__)


@pytest.mark.labels("smoke", "auth")
def test_login_success(api_client, env_config, api_paths, case_context, db_client, db_tx):
    case = get_case("P0-AUTH-001")
    context = {**env_config, **case_context}
    context["password_encoded"] = encode_login_password(
        str(env_config.get("password", "")),
        str(env_config.get("login_password_encoding", "plain")),
    )
    logger.info(
        "login request prepared: path=%s, user=%s, encoding=%s",
        api_paths["login_path"],
        env_config.get("username", ""),
        env_config.get("login_password_encoding", "plain"),
    )
    _, params, data, json_body = build_request(case, context)
    resp = api_client.post(api_paths["login_path"], params=params, data=data, json=json_body)
    body_preview = (resp.text or "")[:400]
    logger.info(
        "login response: status=%s body_preview=%s",
        resp.status_code,
        body_preview,
    )
    assert_by_case_rule(resp, case)
    body = resp.json()
    case_context.update(extract_vars_from_response(case, body))
    run_sql_check(case, context, db_client=db_client, db_tx=db_tx)
    assert "token" in body.get("data", {}), f"Missing token in response: {body}"
    

@pytest.mark.labels("security")
def test_token_expired_access_profile(api_client, api_paths):
    case = get_case("P0-AUTH-003")
    api_client.set_token("expired.fake.token")
    # 具体 profile 接口你们项目里未确认；这里用 /userid 作为鉴权探针
    resp = api_client.get(api_paths["userid_path"])
    assert_by_case_rule(resp, case)
    assert_auth_failure(resp)
