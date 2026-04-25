# 🛠️ MCP AWS Toolkit

> **Control your AWS infrastructure with natural language** — An MCP (Model Context Protocol) server that exposes AWS operations as AI-callable tools, compatible with Claude Desktop, Claude Code, and any MCP-compatible client.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-1.0-green.svg)](https://modelcontextprotocol.io)
[![AWS](https://img.shields.io/badge/AWS-boto3-orange.svg)](https://boto3.amazonaws.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 💬 What You Can Do

Once connected, ask Claude things like:

```
"List all my ECS clusters and show services in production-cluster"
"Tail the last 50 error logs from /ecs/my-api"
"Show me all ALARM state CloudWatch alarms"
"Force deploy the payments-service in my prod ECS cluster"
"Browse objects in my-data-bucket under the /exports prefix"
"Describe the TaskExecutionRole and show its attached policies"
"Generate a presigned download URL for s3://reports/2025-q4.pdf"
```

---

## 🧰 Tools Included

### 🟦 ECS
| Tool | Description |
|------|-------------|
| `ecs_list_clusters` | List all ECS clusters |
| `ecs_list_services` | List services in a cluster |
| `ecs_list_tasks` | List running tasks with status |
| `ecs_describe_service` | Full service detail — counts, events, task def |
| `ecs_force_deploy` | Trigger a rolling restart / force new deployment |

### 📊 CloudWatch
| Tool | Description |
|------|-------------|
| `cw_list_log_groups` | List log groups with optional prefix filter |
| `cw_tail_logs` | Fetch recent log events, with filter pattern support |
| `cw_list_alarms` | List alarms filtered by state (OK/ALARM/INSUFFICIENT_DATA) |
| `cw_get_alarm_history` | Get state change history for an alarm |

### 🪣 S3
| Tool | Description |
|------|-------------|
| `s3_list_buckets` | List all buckets with creation dates |
| `s3_browse` | Browse objects in a bucket by prefix |
| `s3_get_object_info` | Object metadata, size, tags, storage class |
| `s3_presign_url` | Generate presigned GET or PUT URLs |
| `s3_bucket_stats` | Total object count and size for a bucket/prefix |

### 🔐 IAM
| Tool | Description |
|------|-------------|
| `iam_list_roles` | List roles with optional prefix filter |
| `iam_describe_role` | Role ARN, trust policy, managed + inline policies |
| `iam_list_policies` | List customer-managed or AWS-managed policies |
| `iam_list_users` | List users with last login date |
| `iam_get_policy_document` | Get the full JSON policy document |

---

## 🚀 Quick Start

### 1. Clone and install

```bash
git clone https://github.com/yourusername/mcp-aws-toolkit.git
cd mcp-aws-toolkit
pip install -e .
```

### 2. Configure AWS credentials

The server uses your existing AWS credentials. Any of these work:

```bash
# Option A — named profile
export AWS_PROFILE=my-profile

# Option B — environment variables
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export AWS_DEFAULT_REGION=ap-southeast-2

# Option C — IAM role (EC2/ECS instance profile, no config needed)
```

### 3. Connect to Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "aws-toolkit": {
      "command": "python",
      "args": ["/path/to/mcp-aws-toolkit/src/server.py"],
      "env": {
        "AWS_PROFILE": "default",
        "AWS_DEFAULT_REGION": "ap-southeast-2"
      }
    }
  }
}
```

macOS config path: `~/Library/Application Support/Claude/claude_desktop_config.json`

### 4. Connect to Claude Code

```bash
claude mcp add aws-toolkit python /path/to/mcp-aws-toolkit/src/server.py
```

---

## 🏗️ Architecture

```
Claude Desktop / Claude Code
         │
         │  MCP (stdio transport)
         ▼
┌─────────────────────────────┐
│      MCP AWS Toolkit        │
│  ┌──────┐ ┌──┐ ┌──┐ ┌───┐  │
│  │ ECS  │ │CW│ │S3│ │IAM│  │
│  └──────┘ └──┘ └──┘ └───┘  │
│         boto3 SDK           │
└─────────────────────────────┘
         │
         │  AWS API calls
         ▼
    AWS Services
```

Each service module is independently testable and new services can be added without touching the server core.

---

## 🧪 Running Tests

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

Tests use [moto](https://github.com/getmoto/moto) to mock AWS services — no real AWS account needed for testing.

---

## ➕ Adding New AWS Services

1. Create `src/tools/newservice.py` implementing a class with `get_tools() -> dict`
2. Import and register in `src/server.py`
3. That's it — tools are auto-registered

```python
class NewServiceTools:
    def get_tools(self) -> dict:
        return {
            "tool_name": {
                "description": "What this tool does",
                "inputSchema": { "type": "object", "properties": { ... } },
                "handler": self.my_handler,
            }
        }

    async def my_handler(self, args: dict) -> str:
        client = get_client("newservice", args.get("profile"), args.get("region"))
        # ... boto3 calls
        return "formatted string result"
```

**Planned v2 tools:** Lambda invoke/list, EC2 start/stop, RDS instance management, Cost Explorer, SSM Parameter Store, Secrets Manager.

---

## 🔐 Required IAM Permissions

Minimum permissions for read-only usage:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ecs:List*", "ecs:Describe*",
        "logs:DescribeLogGroups", "logs:FilterLogEvents",
        "cloudwatch:DescribeAlarms", "cloudwatch:DescribeAlarmHistory",
        "s3:ListAllMyBuckets", "s3:ListBucket", "s3:GetObject", "s3:GetObjectTagging",
        "iam:ListRoles", "iam:GetRole", "iam:ListAttachedRolePolicies",
        "iam:ListRolePolicies", "iam:ListPolicies", "iam:GetPolicy",
        "iam:GetPolicyVersion", "iam:ListUsers"
      ],
      "Resource": "*"
    }
  ]
}
```

For write actions (force deploy, presigned PUT), additionally add:
`ecs:UpdateService`, `s3:PutObject`

---

## 🤝 Contributing

PRs welcome! Please open an issue first for new service additions.

---

## 📄 License

MIT — see [LICENSE](LICENSE)
