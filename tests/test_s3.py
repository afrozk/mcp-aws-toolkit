import json
import boto3
import pytest

from mcp_aws_toolkit.tools.s3 import (
    s3_delete_object,
    s3_get_bucket_policy,
    s3_get_bucket_versioning,
    s3_get_object,
    s3_list_buckets,
    s3_list_objects,
    s3_put_object,
)

REGION = "us-east-1"
BUCKET = "test-bucket"


@pytest.fixture()
def bucket(moto_aws):
    s3 = boto3.client("s3", region_name=REGION)
    s3.create_bucket(Bucket=BUCKET)
    return BUCKET


def test_list_buckets_empty(moto_aws):
    result = json.loads(s3_list_buckets(region=REGION))
    assert result == []


def test_list_buckets_returns_created(bucket):
    result = json.loads(s3_list_buckets(region=REGION))
    names = [b["name"] for b in result]
    assert BUCKET in names


def test_list_objects_empty(bucket):
    result = json.loads(s3_list_objects(bucket=BUCKET, region=REGION))
    assert result == []


def test_put_and_list_objects(bucket):
    s3_put_object(bucket=BUCKET, key="hello.txt", body="world", region=REGION)
    result = json.loads(s3_list_objects(bucket=BUCKET, region=REGION))
    keys = [o["key"] for o in result]
    assert "hello.txt" in keys


def test_list_objects_prefix_filter(bucket):
    s3_put_object(bucket=BUCKET, key="logs/a.log", body="a", region=REGION)
    s3_put_object(bucket=BUCKET, key="data/b.csv", body="b", region=REGION)
    result = json.loads(s3_list_objects(bucket=BUCKET, prefix="logs/", region=REGION))
    assert all(o["key"].startswith("logs/") for o in result)
    assert len(result) == 1


def test_put_object_returns_confirmation(bucket):
    msg = s3_put_object(bucket=BUCKET, key="note.txt", body="hi", region=REGION)
    assert f"s3://{BUCKET}/note.txt" in msg


def test_get_object_returns_content(bucket):
    s3_put_object(bucket=BUCKET, key="file.txt", body="hello world", region=REGION)
    content = s3_get_object(bucket=BUCKET, key="file.txt", region=REGION)
    assert content == "hello world"


def test_delete_object(bucket):
    s3_put_object(bucket=BUCKET, key="temp.txt", body="bye", region=REGION)
    msg = s3_delete_object(bucket=BUCKET, key="temp.txt", region=REGION)
    assert f"s3://{BUCKET}/temp.txt" in msg
    result = json.loads(s3_list_objects(bucket=BUCKET, region=REGION))
    assert not any(o["key"] == "temp.txt" for o in result)


def test_get_bucket_policy_no_policy(bucket):
    result = s3_get_bucket_policy(bucket=BUCKET, region=REGION)
    assert "no bucket policy" in result


def test_get_bucket_policy_returns_policy(bucket):
    policy = json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": "s3:GetObject",
                    "Resource": f"arn:aws:s3:::{BUCKET}/*",
                }
            ],
        }
    )
    boto3.client("s3", region_name=REGION).put_bucket_policy(Bucket=BUCKET, Policy=policy)
    result = json.loads(s3_get_bucket_policy(bucket=BUCKET, region=REGION))
    assert result["Statement"][0]["Effect"] == "Allow"


def test_get_bucket_versioning_disabled(bucket):
    result = json.loads(s3_get_bucket_versioning(bucket=BUCKET, region=REGION))
    assert result["status"] == "Disabled"


def test_get_bucket_versioning_enabled(bucket):
    boto3.client("s3", region_name=REGION).put_bucket_versioning(
        Bucket=BUCKET,
        VersioningConfiguration={"Status": "Enabled"},
    )
    result = json.loads(s3_get_bucket_versioning(bucket=BUCKET, region=REGION))
    assert result["status"] == "Enabled"
