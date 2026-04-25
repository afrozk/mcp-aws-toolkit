import json
import boto3
import pytest

from mcp_aws_toolkit.tools.iam import (
    iam_get_policy_document,
    iam_get_role,
    iam_list_attached_role_policies,
    iam_list_policies,
    iam_list_roles,
    iam_list_users,
    iam_simulate_principal_policy,
)
from tests.conftest import TRUST_POLICY

REGION = "us-east-1"
POLICY_DOCUMENT = json.dumps(
    {
        "Version": "2012-10-17",
        "Statement": [{"Effect": "Allow", "Action": "s3:GetObject", "Resource": "*"}],
    }
)


@pytest.fixture()
def iam_user(moto_aws):
    iam = boto3.client("iam", region_name=REGION)
    iam.create_user(UserName="alice")
    return "alice"


@pytest.fixture()
def iam_role(moto_aws):
    iam = boto3.client("iam", region_name=REGION)
    resp = iam.create_role(
        RoleName="app-role",
        AssumeRolePolicyDocument=TRUST_POLICY,
        Description="Test role",
    )
    return resp["Role"]


@pytest.fixture()
def iam_policy(moto_aws):
    iam = boto3.client("iam", region_name=REGION)
    resp = iam.create_policy(
        PolicyName="s3-read",
        PolicyDocument=POLICY_DOCUMENT,
    )
    return resp["Policy"]


def test_list_users_empty(moto_aws):
    result = json.loads(iam_list_users())
    assert result == []


def test_list_users_returns_created(iam_user):
    result = json.loads(iam_list_users())
    names = [u["username"] for u in result]
    assert "alice" in names


def test_list_roles_empty(moto_aws):
    result = json.loads(iam_list_roles())
    assert result == []


def test_list_roles_returns_created(iam_role):
    result = json.loads(iam_list_roles())
    names = [r["name"] for r in result]
    assert "app-role" in names


def test_list_roles_has_required_fields(iam_role):
    result = json.loads(iam_list_roles())
    role = next(r for r in result if r["name"] == "app-role")
    assert "arn" in role
    assert "created" in role


def test_get_role(iam_role):
    result = json.loads(iam_get_role(role_name="app-role"))
    assert result["name"] == "app-role"
    assert result["description"] == "Test role"
    assert "trust_policy" in result


def test_list_attached_role_policies_empty(iam_role):
    result = json.loads(iam_list_attached_role_policies(role_name="app-role"))
    assert result == []


def test_list_attached_role_policies_after_attach(iam_role, iam_policy):
    iam = boto3.client("iam", region_name=REGION)
    iam.attach_role_policy(RoleName="app-role", PolicyArn=iam_policy["Arn"])
    result = json.loads(iam_list_attached_role_policies(role_name="app-role"))
    names = [p["name"] for p in result]
    assert "s3-read" in names


def test_list_policies_empty(moto_aws):
    result = json.loads(iam_list_policies(scope="Local"))
    assert result == []


def test_list_policies_returns_created(iam_policy):
    result = json.loads(iam_list_policies(scope="Local"))
    names = [p["name"] for p in result]
    assert "s3-read" in names


def test_get_policy_document(iam_policy):
    result = json.loads(iam_get_policy_document(policy_arn=iam_policy["Arn"]))
    assert result["Version"] == "2012-10-17"
    assert result["Statement"][0]["Action"] == "s3:GetObject"


@pytest.mark.skip(reason="simulate_principal_policy not implemented in moto")
def test_simulate_principal_policy(iam_role, iam_policy):
    iam = boto3.client("iam", region_name=REGION)
    iam.attach_role_policy(RoleName="app-role", PolicyArn=iam_policy["Arn"])
    role = json.loads(iam_get_role(role_name="app-role"))
    result = json.loads(
        iam_simulate_principal_policy(
            principal_arn=role["arn"],
            action_names='["s3:GetObject"]',
            resource_arns='["*"]',
        )
    )
    assert isinstance(result, list)
    assert result[0]["action"] == "s3:GetObject"
    assert "decision" in result[0]
