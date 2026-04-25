import json
import time
import boto3
import pytest

from mcp_aws_toolkit.tools.cloudwatch import (
    cloudwatch_describe_alarms,
    cloudwatch_get_log_events,
    cloudwatch_get_metric_statistics,
    cloudwatch_list_log_groups,
    cloudwatch_list_log_streams,
    cloudwatch_list_metrics,
)

REGION = "us-east-1"
LOG_GROUP = "/aws/test/app"
LOG_STREAM = "stream-001"


@pytest.fixture()
def cw_alarm(moto_aws):
    cw = boto3.client("cloudwatch", region_name=REGION)
    # put_metric_data registers the metric so list_metrics can find it
    cw.put_metric_data(
        Namespace="AWS/EC2",
        MetricData=[{"MetricName": "CPUUtilization", "Value": 50.0, "Unit": "Percent"}],
    )
    cw.put_metric_alarm(
        AlarmName="high-cpu",
        MetricName="CPUUtilization",
        Namespace="AWS/EC2",
        Period=300,
        EvaluationPeriods=1,
        Threshold=80.0,
        ComparisonOperator="GreaterThanThreshold",
        Statistic="Average",
    )


@pytest.fixture()
def log_group_with_stream(moto_aws):
    logs = boto3.client("logs", region_name=REGION)
    logs.create_log_group(logGroupName=LOG_GROUP)
    logs.create_log_stream(logGroupName=LOG_GROUP, logStreamName=LOG_STREAM)
    return logs


def test_list_metrics_empty(moto_aws):
    result = json.loads(cloudwatch_list_metrics(region=REGION))
    assert result == []


def test_list_metrics_with_namespace_filter(cw_alarm):
    result = json.loads(
        cloudwatch_list_metrics(namespace="AWS/EC2", metric_name="CPUUtilization", region=REGION)
    )
    assert any(m["MetricName"] == "CPUUtilization" for m in result)


def test_get_metric_statistics_returns_list(cw_alarm):
    dims = json.dumps([{"Name": "InstanceId", "Value": "i-1234"}])
    result = json.loads(
        cloudwatch_get_metric_statistics(
            namespace="AWS/EC2",
            metric_name="CPUUtilization",
            dimensions=dims,
            hours=1,
            region=REGION,
        )
    )
    assert isinstance(result, list)


def test_describe_alarms_empty(moto_aws):
    result = json.loads(cloudwatch_describe_alarms(region=REGION))
    assert result == []


def test_describe_alarms_returns_created(cw_alarm):
    result = json.loads(cloudwatch_describe_alarms(region=REGION))
    names = [a["name"] for a in result]
    assert "high-cpu" in names


def test_describe_alarms_state_filter(cw_alarm):
    result = json.loads(cloudwatch_describe_alarms(state="OK", region=REGION))
    assert all(a["state"] == "OK" for a in result)


def test_describe_alarms_prefix_filter(cw_alarm):
    result = json.loads(cloudwatch_describe_alarms(prefix="high", region=REGION))
    assert all(a["name"].startswith("high") for a in result)


def test_list_log_groups_empty(moto_aws):
    result = json.loads(cloudwatch_list_log_groups(region=REGION))
    assert result == []


def test_list_log_groups_returns_created(log_group_with_stream):
    result = json.loads(cloudwatch_list_log_groups(region=REGION))
    names = [g["name"] for g in result]
    assert LOG_GROUP in names


def test_list_log_groups_prefix_filter(log_group_with_stream):
    result = json.loads(cloudwatch_list_log_groups(prefix="/aws/test", region=REGION))
    assert all(g["name"].startswith("/aws/test") for g in result)


def test_list_log_streams(log_group_with_stream):
    result = json.loads(cloudwatch_list_log_streams(log_group=LOG_GROUP, region=REGION))
    names = [s["name"] for s in result]
    assert LOG_STREAM in names


def test_get_log_events_empty_stream(log_group_with_stream):
    result = json.loads(
        cloudwatch_get_log_events(log_group=LOG_GROUP, log_stream=LOG_STREAM, region=REGION)
    )
    assert result == []


def test_get_log_events_returns_messages(log_group_with_stream):
    logs = log_group_with_stream
    logs.put_log_events(
        logGroupName=LOG_GROUP,
        logStreamName=LOG_STREAM,
        logEvents=[{"timestamp": int(time.time() * 1000), "message": "hello from test"}],
    )
    result = json.loads(
        cloudwatch_get_log_events(
            log_group=LOG_GROUP, log_stream=LOG_STREAM, minutes=60, region=REGION
        )
    )
    messages = [e["message"] for e in result]
    assert any("hello from test" in m for m in messages)
