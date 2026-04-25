# MCP AWS Toolkit

MCP server that exposes AWS operations as AI-callable tools, compatible with Claude Desktop, Claude Code, and any MCP-compatible client.

```
"List all my ECS clusters and show services in production-cluster"
"Tail the last 50 error logs from /ecs/my-api"
"Show me all ALARM state CloudWatch alarms"
"Force deploy the payments-service in my prod ECS cluster"
"Invoke the data-processor Lambda with this payload and show me the response"
"Show who can invoke the payments Lambda function"
```

---

## Tools (36 total)

### ECS

| Tool | Description |
|------|-------------|
| `ecs_list_clusters` | List all ECS clusters with status and task counts |
| `ecs_describe_cluster` | Full cluster detail including statistics and tags |
| `ecs_list_services` | List services in a cluster with desired/running counts |
| `ecs_describe_service` | Full service detail — deployments, events, task definition |
| `ecs_list_tasks` | List tasks filtered by status (RUNNING/PENDING/STOPPED) |
| `ecs_update_service` | Change desired count or force a new deployment |

### CloudWatch

| Tool | Description |
|------|-------------|
| `cloudwatch_list_metrics` | List metrics filtered by namespace and/or metric name |
| `cloudwatch_get_metric_statistics` | Get datapoints for a metric over a time window |
| `cloudwatch_describe_alarms` | List alarms filtered by state or name prefix |
| `cloudwatch_list_log_groups` | List log groups with optional prefix filter |
| `cloudwatch_list_log_streams` | List streams in a log group, newest first |
| `cloudwatch_get_log_events` | Fetch recent log events from a stream |

### S3

| Tool | Description |
|------|-------------|
| `s3_list_buckets` | List all buckets with creation dates |
| `s3_list_objects` | Browse objects by prefix with size and storage class |
| `s3_get_object` | Read text content of an object |
| `s3_put_object` | Upload text content to a key |
| `s3_delete_object` | Delete an object |
| `s3_get_bucket_policy` | Get the bucket resource policy |
| `s3_get_bucket_versioning` | Get versioning configuration |

### IAM

| Tool | Description |
|------|-------------|
| `iam_list_users` | List users with last login date |
| `iam_list_roles` | List roles with optional path prefix filter |
| `iam_get_role` | Role ARN, trust policy, description, tags |
| `iam_list_attached_role_policies` | Managed policies attached to a role |
| `iam_list_policies` | List customer-managed or AWS-managed policies |
| `iam_get_policy_document` | Get the full JSON policy document |
| `iam_simulate_principal_policy` | Simulate policy evaluation for a principal |

### Lambda

| Tool | Description |
|------|-------------|
| `lambda_list_functions` | List functions with runtime, memory, timeout |
| `lambda_get_function` | Full function detail — env vars, layers, concurrency |
| `lambda_invoke` | Invoke synchronously/asynchronously, returns response + tail logs |
| `lambda_list_versions` | List all published versions |
| `lambda_list_aliases` | List aliases and their version routing config |
| `lambda_list_event_source_mappings` | List triggers (SQS, Kinesis, DynamoDB, etc.) |
| `lambda_get_function_url_config` | Get function URL and auth type |
| `lambda_put_function_concurrency` | Set reserved concurrency (set to 0 to throttle) |
| `lambda_delete_function_concurrency` | Remove reserved concurrency limit |
| `lambda_get_policy` | Get resource-based policy (who can invoke) |

---

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Running

**Development — browser inspector UI:**

```bash
mcp dev src/mcp_aws_toolkit/server.py
```

**Claude Desktop** — add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "aws-toolkit": {
      "command": "/path/to/.venv/bin/mcp-aws-toolkit",
      "env": {
        "AWS_PROFILE": "your-profile",
        "AWS_DEFAULT_REGION": "us-east-1"
      }
    }
  }
}
```

**Claude Code:**

```bash
claude mcp add aws-toolkit /path/to/.venv/bin/mcp-aws-toolkit
```

## Testing

```bash
pip install -e ".[dev]"
pytest
```

All tests use [moto](https://github.com/getmoto/moto) to mock AWS — no real credentials needed.

## Project structure

```
src/mcp_aws_toolkit/
├── server.py              # FastMCP app — imports and registers all tool modules
└── tools/
    ├── ecs.py
    ├── cloudwatch.py
    ├── s3.py
    ├── iam.py
    └── lambda_tools.py
tests/
├── conftest.py            # Shared fixtures: aws_credentials, make_lambda_zip, iam_role_arn
├── test_ecs.py
├── test_cloudwatch.py
├── test_s3.py
├── test_iam.py
└── test_lambda.py
```

## Adding a new service

1. Create `src/mcp_aws_toolkit/tools/myservice.py` — define functions at module level, add a `register(mcp)` that calls `mcp.tool()(fn)` for each
2. Import and call `myservice.register(mcp)` in `server.py`
3. Add `tests/test_myservice.py` using `@mock_aws`

## Required IAM permissions

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": [
      "ecs:List*", "ecs:Describe*", "ecs:UpdateService",
      "logs:DescribeLogGroups", "logs:DescribeLogStreams", "logs:GetLogEvents",
      "cloudwatch:ListMetrics", "cloudwatch:GetMetricStatistics", "cloudwatch:DescribeAlarms",
      "s3:ListAllMyBuckets", "s3:ListBucket", "s3:GetObject", "s3:PutObject",
      "s3:DeleteObject", "s3:GetBucketPolicy", "s3:GetBucketVersioning",
      "iam:ListUsers", "iam:ListRoles", "iam:GetRole",
      "iam:ListAttachedRolePolicies", "iam:ListPolicies",
      "iam:GetPolicy", "iam:GetPolicyVersion", "iam:SimulatePrincipalPolicy",
      "lambda:ListFunctions", "lambda:GetFunction", "lambda:InvokeFunction",
      "lambda:ListVersionsByFunction", "lambda:ListAliases",
      "lambda:ListEventSourceMappings", "lambda:GetFunctionUrlConfig",
      "lambda:PutFunctionConcurrency", "lambda:DeleteFunctionConcurrency",
      "lambda:GetPolicy"
    ],
    "Resource": "*"
  }]
}
```
