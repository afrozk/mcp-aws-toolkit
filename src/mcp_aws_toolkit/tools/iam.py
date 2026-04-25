import json
import boto3
from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def iam_list_users(max_items: int = 50) -> str:
        """List IAM users in the account."""
        client = boto3.client("iam")
        users: list[dict] = []
        paginator = client.get_paginator("list_users")
        for page in paginator.paginate(PaginationConfig={"MaxItems": max_items}):
            users.extend(page["Users"])
            if len(users) >= max_items:
                break
        return json.dumps(
            [
                {
                    "username": u["UserName"],
                    "user_id": u["UserId"],
                    "arn": u["Arn"],
                    "created": str(u["CreateDate"]),
                    "password_last_used": str(u.get("PasswordLastUsed", "never")),
                }
                for u in users[:max_items]
            ],
            indent=2,
        )

    @mcp.tool()
    def iam_list_roles(prefix: str | None = None, max_items: int = 50) -> str:
        """
        List IAM roles, optionally filtered by path prefix.

        Args:
            prefix: Role path prefix e.g. '/service-role/'.
            max_items: Maximum roles to return (default 50).
        """
        client = boto3.client("iam")
        kwargs: dict = {}
        if prefix:
            kwargs["PathPrefix"] = prefix
        roles: list[dict] = []
        paginator = client.get_paginator("list_roles")
        for page in paginator.paginate(**kwargs, PaginationConfig={"MaxItems": max_items}):
            roles.extend(page["Roles"])
            if len(roles) >= max_items:
                break
        return json.dumps(
            [
                {
                    "name": r["RoleName"],
                    "role_id": r["RoleId"],
                    "arn": r["Arn"],
                    "path": r["Path"],
                    "created": str(r["CreateDate"]),
                    "description": r.get("Description", ""),
                }
                for r in roles[:max_items]
            ],
            indent=2,
        )

    @mcp.tool()
    def iam_get_role(role_name: str) -> str:
        """Get details for a specific IAM role including its trust policy."""
        client = boto3.client("iam")
        resp = client.get_role(RoleName=role_name)
        role = resp["Role"]
        return json.dumps(
            {
                "name": role["RoleName"],
                "arn": role["Arn"],
                "path": role["Path"],
                "description": role.get("Description", ""),
                "max_session_duration": role.get("MaxSessionDuration"),
                "trust_policy": role["AssumeRolePolicyDocument"],
                "created": str(role["CreateDate"]),
                "tags": {t["Key"]: t["Value"] for t in role.get("Tags", [])},
            },
            indent=2,
        )

    @mcp.tool()
    def iam_list_attached_role_policies(role_name: str) -> str:
        """List all managed policies attached to an IAM role."""
        client = boto3.client("iam")
        policies: list[dict] = []
        paginator = client.get_paginator("list_attached_role_policies")
        for page in paginator.paginate(RoleName=role_name):
            policies.extend(page["AttachedPolicies"])
        return json.dumps(
            [{"name": p["PolicyName"], "arn": p["PolicyArn"]} for p in policies],
            indent=2,
        )

    @mcp.tool()
    def iam_list_policies(
        scope: str = "Local",
        max_items: int = 50,
    ) -> str:
        """
        List IAM managed policies.

        Args:
            scope: 'Local' for customer-managed, 'AWS' for AWS-managed, 'All' for both.
            max_items: Maximum policies to return (default 50).
        """
        client = boto3.client("iam")
        policies: list[dict] = []
        paginator = client.get_paginator("list_policies")
        for page in paginator.paginate(Scope=scope, PaginationConfig={"MaxItems": max_items}):
            policies.extend(page["Policies"])
            if len(policies) >= max_items:
                break
        return json.dumps(
            [
                {
                    "name": p["PolicyName"],
                    "arn": p["PolicyArn"],
                    "description": p.get("Description", ""),
                    "attachment_count": p["AttachmentCount"],
                    "created": str(p["CreateDate"]),
                    "updated": str(p["UpdatedDate"]),
                }
                for p in policies[:max_items]
            ],
            indent=2,
        )

    @mcp.tool()
    def iam_get_policy_document(policy_arn: str) -> str:
        """
        Get the current policy document for an IAM managed policy.

        Args:
            policy_arn: Full ARN of the policy.
        """
        client = boto3.client("iam")
        policy = client.get_policy(PolicyArn=policy_arn)["Policy"]
        version_id = policy["DefaultVersionId"]
        version = client.get_policy_version(PolicyArn=policy_arn, VersionId=version_id)
        return json.dumps(version["PolicyVersion"]["Document"], indent=2)

    @mcp.tool()
    def iam_simulate_principal_policy(
        principal_arn: str,
        action_names: str,
        resource_arns: str = '["*"]',
    ) -> str:
        """
        Simulate IAM policy evaluation for a principal against specified actions/resources.

        Args:
            principal_arn: ARN of the IAM user, role, or group.
            action_names: JSON list of actions e.g. '["s3:GetObject","ec2:DescribeInstances"]'.
            resource_arns: JSON list of resource ARNs (default '[\"*\"]').
        """
        client = boto3.client("iam")
        actions = json.loads(action_names)
        resources = json.loads(resource_arns)
        resp = client.simulate_principal_policy(
            PolicySourceArn=principal_arn,
            ActionNames=actions,
            ResourceArns=resources,
        )
        return json.dumps(
            [
                {
                    "action": r["EvalActionName"],
                    "resource": r["EvalResourceName"],
                    "decision": r["EvalDecision"],
                    "matched_statements": [
                        s["SourcePolicyId"] for s in r.get("MatchedStatements", [])
                    ],
                }
                for r in resp["EvaluationResults"]
            ],
            indent=2,
        )
