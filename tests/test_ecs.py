import json
import boto3
import pytest

from mcp_aws_toolkit.tools.ecs import (
    ecs_describe_cluster,
    ecs_describe_service,
    ecs_list_clusters,
    ecs_list_services,
    ecs_list_tasks,
    ecs_update_service,
)

REGION = "us-east-1"


@pytest.fixture()
def ecs_cluster(moto_aws):
    ecs = boto3.client("ecs", region_name=REGION)
    ecs.create_cluster(clusterName="test-cluster")
    return "test-cluster"


@pytest.fixture()
def ecs_service(ecs_cluster):
    ecs = boto3.client("ecs", region_name=REGION)
    ecs.register_task_definition(
        family="test-task",
        containerDefinitions=[
            {
                "name": "app",
                "image": "nginx:latest",
                "memory": 128,
                "cpu": 256,
            }
        ],
    )
    ecs.create_service(
        cluster=ecs_cluster,
        serviceName="test-service",
        taskDefinition="test-task",
        desiredCount=2,
    )
    return "test-service"


def test_list_clusters_no_clusters_message(moto_aws):
    raw = ecs_list_clusters(region=REGION)
    assert raw == "No clusters found."


def test_list_clusters_returns_created(ecs_cluster):
    result = json.loads(ecs_list_clusters(region=REGION))
    names = [c["name"] for c in result]
    assert "test-cluster" in names


def test_list_clusters_has_required_fields(ecs_cluster):
    result = json.loads(ecs_list_clusters(region=REGION))
    cluster = result[0]
    for field in ["name", "arn", "status", "active_services", "running_tasks"]:
        assert field in cluster


def test_describe_cluster(ecs_cluster):
    result = json.loads(ecs_describe_cluster(cluster="test-cluster", region=REGION))
    assert result["clusterName"] == "test-cluster"
    assert result["status"] == "ACTIVE"


def test_describe_cluster_not_found(moto_aws):
    result = ecs_describe_cluster(cluster="nonexistent", region=REGION)
    assert "not found" in result


def test_list_services_empty(ecs_cluster):
    result = ecs_list_services(cluster="test-cluster", region=REGION)
    assert "No services found" in result


def test_list_services_returns_created(ecs_service):
    result = json.loads(ecs_list_services(cluster="test-cluster", region=REGION))
    names = [s["name"] for s in result]
    assert "test-service" in names


def test_list_services_desired_count(ecs_service):
    result = json.loads(ecs_list_services(cluster="test-cluster", region=REGION))
    svc = next(s for s in result if s["name"] == "test-service")
    assert svc["desired"] == 2


def test_describe_service(ecs_service):
    result = json.loads(
        ecs_describe_service(cluster="test-cluster", service="test-service", region=REGION)
    )
    assert result["serviceName"] == "test-service"


def test_describe_service_not_found(ecs_cluster):
    result = ecs_describe_service(cluster="test-cluster", service="ghost", region=REGION)
    assert "not found" in result


def test_list_tasks_empty(ecs_cluster):
    result = ecs_list_tasks(cluster="test-cluster", region=REGION)
    assert result == "No tasks found."


def test_update_service_desired_count(ecs_service):
    result = json.loads(
        ecs_update_service(
            cluster="test-cluster",
            service="test-service",
            desired_count=5,
            region=REGION,
        )
    )
    assert result["desired"] == 5
    assert result["service"] == "test-service"
