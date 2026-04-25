import json
import boto3
from mcp.server.fastmcp import FastMCP


def ecs_list_clusters(region: str = "us-east-1") -> str:
    """List all ECS clusters in a region."""
    client = boto3.client("ecs", region_name=region)
    arns = client.list_clusters()["clusterArns"]
    if not arns:
        return "No clusters found."
    details = client.describe_clusters(clusters=arns)["clusters"]
    return json.dumps(
        [
            {
                "name": c["clusterName"],
                "arn": c["clusterArn"],
                "status": c["status"],
                "active_services": c["activeServicesCount"],
                "running_tasks": c["runningTasksCount"],
                "pending_tasks": c["pendingTasksCount"],
            }
            for c in details
        ],
        indent=2,
    )


def ecs_describe_cluster(cluster: str, region: str = "us-east-1") -> str:
    """Get details for a specific ECS cluster (name or ARN)."""
    client = boto3.client("ecs", region_name=region)
    resp = client.describe_clusters(clusters=[cluster], include=["STATISTICS", "TAGS"])
    clusters = resp.get("clusters", [])
    if not clusters:
        return f"Cluster '{cluster}' not found."
    return json.dumps(clusters[0], indent=2, default=str)


def ecs_list_services(cluster: str, region: str = "us-east-1") -> str:
    """List all services in an ECS cluster."""
    client = boto3.client("ecs", region_name=region)
    arns: list[str] = []
    paginator = client.get_paginator("list_services")
    for page in paginator.paginate(cluster=cluster):
        arns.extend(page["serviceArns"])
    if not arns:
        return f"No services found in cluster '{cluster}'."
    details = client.describe_services(cluster=cluster, services=arns)["services"]
    return json.dumps(
        [
            {
                "name": s["serviceName"],
                "status": s["status"],
                "desired": s["desiredCount"],
                "running": s["runningCount"],
                "pending": s["pendingCount"],
                "task_definition": s["taskDefinition"].split("/")[-1],
                "launch_type": s.get("launchType", "UNKNOWN"),
            }
            for s in details
        ],
        indent=2,
    )


def ecs_describe_service(cluster: str, service: str, region: str = "us-east-1") -> str:
    """Get full details for an ECS service."""
    client = boto3.client("ecs", region_name=region)
    resp = client.describe_services(cluster=cluster, services=[service])
    services = resp.get("services", [])
    if not services:
        return f"Service '{service}' not found in cluster '{cluster}'."
    return json.dumps(services[0], indent=2, default=str)


def ecs_list_tasks(
    cluster: str,
    service: str | None = None,
    status: str = "RUNNING",
    region: str = "us-east-1",
) -> str:
    """
    List tasks in an ECS cluster.

    Args:
        cluster: Cluster name or ARN.
        service: Optional service name to filter by.
        status: Task status filter — RUNNING, PENDING, or STOPPED.
        region: AWS region.
    """
    client = boto3.client("ecs", region_name=region)
    kwargs: dict = {"cluster": cluster, "desiredStatus": status}
    if service:
        kwargs["serviceName"] = service
    arns: list[str] = []
    paginator = client.get_paginator("list_tasks")
    for page in paginator.paginate(**kwargs):
        arns.extend(page["taskArns"])
    if not arns:
        return "No tasks found."
    details = client.describe_tasks(cluster=cluster, tasks=arns)["tasks"]
    return json.dumps(
        [
            {
                "task_id": t["taskArn"].split("/")[-1],
                "status": t["lastStatus"],
                "desired_status": t["desiredStatus"],
                "task_definition": t["taskDefinitionArn"].split("/")[-1],
                "started_at": str(t.get("startedAt", "")),
                "group": t.get("group", ""),
            }
            for t in details
        ],
        indent=2,
    )


def ecs_update_service(
    cluster: str,
    service: str,
    desired_count: int | None = None,
    force_new_deployment: bool = False,
    region: str = "us-east-1",
) -> str:
    """
    Update an ECS service.

    Args:
        cluster: Cluster name or ARN.
        service: Service name or ARN.
        desired_count: New desired task count (omit to leave unchanged).
        force_new_deployment: Force a new deployment without other changes.
        region: AWS region.
    """
    client = boto3.client("ecs", region_name=region)
    kwargs: dict = {
        "cluster": cluster,
        "service": service,
        "forceNewDeployment": force_new_deployment,
    }
    if desired_count is not None:
        kwargs["desiredCount"] = desired_count
    resp = client.update_service(**kwargs)
    s = resp["service"]
    return json.dumps(
        {
            "service": s["serviceName"],
            "status": s["status"],
            "desired": s["desiredCount"],
            "running": s["runningCount"],
            "pending": s["pendingCount"],
        },
        indent=2,
    )


def register(mcp: FastMCP) -> None:
    for fn in [
        ecs_list_clusters,
        ecs_describe_cluster,
        ecs_list_services,
        ecs_describe_service,
        ecs_list_tasks,
        ecs_update_service,
    ]:
        mcp.tool()(fn)
