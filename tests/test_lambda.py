import json
import boto3
import pytest

from mcp_aws_toolkit.tools.lambda_tools import (
    lambda_delete_function_concurrency,
    lambda_get_function,
    lambda_get_function_url_config,
    lambda_get_policy,
    lambda_invoke,
    lambda_list_aliases,
    lambda_list_event_source_mappings,
    lambda_list_functions,
    lambda_list_versions,
    lambda_put_function_concurrency,
)
from tests.conftest import TRUST_POLICY, make_lambda_zip

REGION = "us-east-1"
FN_NAME = "test-function"


@pytest.fixture()
def lambda_role_arn(moto_aws):
    iam = boto3.client("iam", region_name=REGION)
    resp = iam.create_role(
        RoleName="lambda-role",
        AssumeRolePolicyDocument=TRUST_POLICY,
    )
    return resp["Role"]["Arn"]


@pytest.fixture()
def fn(lambda_role_arn):
    client = boto3.client("lambda", region_name=REGION)
    client.create_function(
        FunctionName=FN_NAME,
        Runtime="python3.12",
        Role=lambda_role_arn,
        Handler="handler.handler",
        Code={"ZipFile": make_lambda_zip()},
        Description="Test function",
        Timeout=30,
        MemorySize=128,
    )
    return FN_NAME


def test_list_functions_empty(moto_aws):
    result = json.loads(lambda_list_functions(region=REGION))
    assert result == []


def test_list_functions_returns_created(fn):
    result = json.loads(lambda_list_functions(region=REGION))
    names = [f["name"] for f in result]
    assert FN_NAME in names


def test_list_functions_has_required_fields(fn):
    result = json.loads(lambda_list_functions(region=REGION))
    func = next(f for f in result if f["name"] == FN_NAME)
    for field in ["arn", "runtime", "handler", "memory_mb", "timeout_s"]:
        assert field in func


def test_get_function(fn):
    result = json.loads(lambda_get_function(function_name=FN_NAME, region=REGION))
    assert result["name"] == FN_NAME
    assert result["runtime"] == "python3.12"
    assert result["handler"] == "handler.handler"
    assert result["memory_mb"] == 128
    assert result["timeout_s"] == 30
    assert result["description"] == "Test function"


def test_invoke_sync(fn):
    result = json.loads(
        lambda_invoke(
            function_name=FN_NAME,
            payload='{"key": "value"}',
            region=REGION,
        )
    )
    # moto returns 200 even when Docker-based execution fails; just verify structure
    assert result["status_code"] == 200
    assert "response" in result
    assert "executed_version" in result


def test_invoke_default_payload(fn):
    result = json.loads(lambda_invoke(function_name=FN_NAME, region=REGION))
    assert result["status_code"] == 200


def test_list_versions_includes_latest(fn):
    result = json.loads(lambda_list_versions(function_name=FN_NAME, region=REGION))
    versions = [v["version"] for v in result]
    assert "$LATEST" in versions


def test_list_versions_published(fn):
    boto3.client("lambda", region_name=REGION).publish_version(FunctionName=FN_NAME)
    result = json.loads(lambda_list_versions(function_name=FN_NAME, region=REGION))
    versions = [v["version"] for v in result]
    assert "1" in versions


def test_list_aliases_empty(fn):
    result = json.loads(lambda_list_aliases(function_name=FN_NAME, region=REGION))
    assert result == []


def test_list_aliases_returns_created(fn):
    boto3.client("lambda", region_name=REGION).create_alias(
        FunctionName=FN_NAME,
        Name="live",
        FunctionVersion="$LATEST",
    )
    result = json.loads(lambda_list_aliases(function_name=FN_NAME, region=REGION))
    names = [a["name"] for a in result]
    assert "live" in names


def test_list_event_source_mappings_empty(fn):
    result = json.loads(
        lambda_list_event_source_mappings(function_name=FN_NAME, region=REGION)
    )
    assert result == []


def test_get_function_url_config_not_configured(fn):
    result = lambda_get_function_url_config(function_name=FN_NAME, region=REGION)
    assert "No function URL" in result


def test_get_function_url_config_when_set(fn):
    boto3.client("lambda", region_name=REGION).create_function_url_config(
        FunctionName=FN_NAME,
        AuthType="NONE",
    )
    result = json.loads(lambda_get_function_url_config(function_name=FN_NAME, region=REGION))
    assert "function_url" in result
    assert result["auth_type"] == "NONE"


def test_put_function_concurrency(fn):
    result = json.loads(
        lambda_put_function_concurrency(
            function_name=FN_NAME,
            reserved_concurrent_executions=10,
            region=REGION,
        )
    )
    assert result["reserved_concurrent_executions"] == 10


def test_delete_function_concurrency(fn):
    lambda_put_function_concurrency(
        function_name=FN_NAME, reserved_concurrent_executions=5, region=REGION
    )
    msg = lambda_delete_function_concurrency(function_name=FN_NAME, region=REGION)
    assert FN_NAME in msg


def test_get_policy_no_policy(fn):
    result = lambda_get_policy(function_name=FN_NAME, region=REGION)
    assert "No resource-based policy" in result


def test_get_policy_after_add_permission(fn):
    boto3.client("lambda", region_name=REGION).add_permission(
        FunctionName=FN_NAME,
        StatementId="allow-apigateway",
        Action="lambda:InvokeFunction",
        Principal="apigateway.amazonaws.com",
    )
    result = json.loads(lambda_get_policy(function_name=FN_NAME, region=REGION))
    assert "Statement" in result
