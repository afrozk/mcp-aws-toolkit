import json
from datetime import datetime, timedelta, timezone
import boto3
from mcp.server.fastmcp import FastMCP


def cloudwatch_list_metrics(
    namespace: str | None = None,
    metric_name: str | None = None,
    region: str = "us-east-1",
) -> str:
    """
    List available CloudWatch metrics, optionally filtered by namespace and/or metric name.

    Args:
        namespace: AWS namespace e.g. 'AWS/ECS', 'AWS/Lambda', 'AWS/S3'.
        metric_name: Metric name to filter by e.g. 'CPUUtilization'.
        region: AWS region.
    """
    client = boto3.client("cloudwatch", region_name=region)
    kwargs: dict = {}
    if namespace:
        kwargs["Namespace"] = namespace
    if metric_name:
        kwargs["MetricName"] = metric_name
    metrics: list[dict] = []
    paginator = client.get_paginator("list_metrics")
    for page in paginator.paginate(**kwargs):
        metrics.extend(page["Metrics"])
        if len(metrics) >= 100:
            break
    return json.dumps(metrics[:100], indent=2)


def cloudwatch_get_metric_statistics(
    namespace: str,
    metric_name: str,
    dimensions: str,
    period: int = 300,
    hours: int = 1,
    statistic: str = "Average",
    region: str = "us-east-1",
) -> str:
    """
    Get statistics for a CloudWatch metric.

    Args:
        namespace: Metric namespace e.g. 'AWS/ECS'.
        metric_name: Metric name e.g. 'CPUUtilization'.
        dimensions: JSON list of {Name, Value} dicts e.g. '[{"Name":"ClusterName","Value":"my-cluster"}]'.
        period: Aggregation period in seconds (default 300).
        hours: How many hours of history to retrieve (default 1).
        statistic: One of Average, Sum, Minimum, Maximum, SampleCount.
        region: AWS region.
    """
    client = boto3.client("cloudwatch", region_name=region)
    end = datetime.now(tz=timezone.utc)
    start = end - timedelta(hours=hours)
    dims = json.loads(dimensions)
    resp = client.get_metric_statistics(
        Namespace=namespace,
        MetricName=metric_name,
        Dimensions=dims,
        StartTime=start,
        EndTime=end,
        Period=period,
        Statistics=[statistic],
    )
    datapoints = sorted(resp["Datapoints"], key=lambda d: d["Timestamp"])
    return json.dumps(
        [
            {"timestamp": str(d["Timestamp"]), "value": d[statistic], "unit": d["Unit"]}
            for d in datapoints
        ],
        indent=2,
    )


def cloudwatch_describe_alarms(
    state: str | None = None,
    prefix: str | None = None,
    region: str = "us-east-1",
) -> str:
    """
    List CloudWatch alarms, optionally filtered by state or name prefix.

    Args:
        state: Filter by state — OK, ALARM, or INSUFFICIENT_DATA.
        prefix: Alarm name prefix filter.
        region: AWS region.
    """
    client = boto3.client("cloudwatch", region_name=region)
    kwargs: dict = {}
    if state:
        kwargs["StateValue"] = state
    if prefix:
        kwargs["AlarmNamePrefix"] = prefix
    alarms: list[dict] = []
    paginator = client.get_paginator("describe_alarms")
    for page in paginator.paginate(**kwargs):
        alarms.extend(page["MetricAlarms"])
    return json.dumps(
        [
            {
                "name": a["AlarmName"],
                "state": a["StateValue"],
                "metric": a.get("MetricName", ""),
                "namespace": a.get("Namespace", ""),
                "threshold": a.get("Threshold"),
                "comparison": a.get("ComparisonOperator", ""),
                "updated": str(a.get("StateUpdatedTimestamp", "")),
                "reason": a.get("StateReason", ""),
            }
            for a in alarms
        ],
        indent=2,
    )


def cloudwatch_list_log_groups(
    prefix: str | None = None,
    region: str = "us-east-1",
) -> str:
    """
    List CloudWatch Logs log groups.

    Args:
        prefix: Optional name prefix filter e.g. '/aws/lambda/'.
        region: AWS region.
    """
    client = boto3.client("logs", region_name=region)
    kwargs: dict = {}
    if prefix:
        kwargs["logGroupNamePrefix"] = prefix
    groups: list[dict] = []
    paginator = client.get_paginator("describe_log_groups")
    for page in paginator.paginate(**kwargs):
        groups.extend(page["logGroups"])
        if len(groups) >= 100:
            break
    return json.dumps(
        [
            {
                "name": g["logGroupName"],
                "retention_days": g.get("retentionInDays", "never expires"),
                "stored_bytes": g.get("storedBytes", 0),
            }
            for g in groups[:100]
        ],
        indent=2,
    )


def cloudwatch_list_log_streams(
    log_group: str,
    prefix: str | None = None,
    limit: int = 20,
    region: str = "us-east-1",
) -> str:
    """
    List log streams within a CloudWatch Logs log group, newest first.

    Args:
        log_group: Log group name.
        prefix: Optional stream name prefix.
        limit: Maximum streams to return (default 20).
        region: AWS region.
    """
    client = boto3.client("logs", region_name=region)
    kwargs: dict = {
        "logGroupName": log_group,
        "orderBy": "LastEventTime",
        "descending": True,
        "limit": limit,
    }
    if prefix:
        kwargs["logStreamNamePrefix"] = prefix
    resp = client.describe_log_streams(**kwargs)
    streams = resp.get("logStreams", [])
    return json.dumps(
        [
            {
                "name": s["logStreamName"],
                "last_event": datetime.fromtimestamp(
                    s["lastEventTimestamp"] / 1000, tz=timezone.utc
                ).isoformat()
                if "lastEventTimestamp" in s
                else None,
                "stored_bytes": s.get("storedBytes", 0),
            }
            for s in streams
        ],
        indent=2,
    )


def cloudwatch_get_log_events(
    log_group: str,
    log_stream: str,
    minutes: int = 30,
    limit: int = 100,
    region: str = "us-east-1",
) -> str:
    """
    Retrieve log events from a CloudWatch Logs stream.

    Args:
        log_group: Log group name.
        log_stream: Log stream name.
        minutes: How many minutes of history to retrieve (default 30).
        limit: Maximum number of events to return (default 100).
        region: AWS region.
    """
    client = boto3.client("logs", region_name=region)
    start_ms = int((datetime.now(tz=timezone.utc) - timedelta(minutes=minutes)).timestamp() * 1000)
    resp = client.get_log_events(
        logGroupName=log_group,
        logStreamName=log_stream,
        startTime=start_ms,
        limit=limit,
        startFromHead=True,
    )
    events = resp.get("events", [])
    return json.dumps(
        [
            {
                "timestamp": datetime.fromtimestamp(e["timestamp"] / 1000, tz=timezone.utc).isoformat(),
                "message": e["message"].rstrip(),
            }
            for e in events
        ],
        indent=2,
    )


def register(mcp: FastMCP) -> None:
    for fn in [
        cloudwatch_list_metrics,
        cloudwatch_get_metric_statistics,
        cloudwatch_describe_alarms,
        cloudwatch_list_log_groups,
        cloudwatch_list_log_streams,
        cloudwatch_get_log_events,
    ]:
        mcp.tool()(fn)
