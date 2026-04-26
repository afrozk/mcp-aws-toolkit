from mcp.server.fastmcp import FastMCP

from mcp_aws_toolkit.tools import cloudwatch, cost, ecs, iam, lambda_tools, s3

mcp = FastMCP(
    name="mcp-aws-toolkit",
    instructions=(
        "AWS operations toolkit. "
        "Provides tools for ECS, CloudWatch, S3, IAM, Lambda, and Cost Explorer. "
        "All tools accept a 'region' parameter (default: us-east-1). "
        "Cost tools use the Cost Explorer API (global service, always us-east-1). "
        "AWS credentials are resolved via the standard boto3 chain: "
        "env vars, ~/.aws/credentials, or instance/task roles."
    ),
)

ecs.register(mcp)
cloudwatch.register(mcp)
s3.register(mcp)
iam.register(mcp)
lambda_tools.register(mcp)
cost.register(mcp)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
