import json
import boto3
from botocore.exceptions import ClientError
from mcp.server.fastmcp import FastMCP


def s3_list_buckets(region: str = "us-east-1") -> str:
    """List all S3 buckets in the account."""
    client = boto3.client("s3", region_name=region)
    resp = client.list_buckets()
    buckets = resp.get("Buckets", [])
    return json.dumps(
        [{"name": b["Name"], "created": str(b["CreationDate"])} for b in buckets],
        indent=2,
    )


def s3_list_objects(
    bucket: str,
    prefix: str = "",
    max_keys: int = 50,
    region: str = "us-east-1",
) -> str:
    """
    List objects in an S3 bucket.

    Args:
        bucket: Bucket name.
        prefix: Key prefix to filter by (e.g. 'logs/2024/').
        max_keys: Maximum number of objects to return (default 50).
        region: AWS region.
    """
    client = boto3.client("s3", region_name=region)
    resp = client.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=max_keys)
    objects = resp.get("Contents", [])
    return json.dumps(
        [
            {
                "key": o["Key"],
                "size_bytes": o["Size"],
                "last_modified": str(o["LastModified"]),
                "storage_class": o.get("StorageClass", "STANDARD"),
            }
            for o in objects
        ],
        indent=2,
    )


def s3_get_object(bucket: str, key: str, region: str = "us-east-1") -> str:
    """
    Read the content of an S3 object (text/UTF-8).

    Args:
        bucket: Bucket name.
        key: Object key.
        region: AWS region.
    """
    client = boto3.client("s3", region_name=region)
    resp = client.get_object(Bucket=bucket, Key=key)
    content = resp["Body"].read()
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        return f"[binary content, {len(content)} bytes — not displayable as text]"


def s3_put_object(
    bucket: str,
    key: str,
    body: str,
    content_type: str = "text/plain",
    region: str = "us-east-1",
) -> str:
    """
    Upload text content to an S3 object.

    Args:
        bucket: Bucket name.
        key: Destination key.
        body: Text content to upload.
        content_type: MIME type (default 'text/plain').
        region: AWS region.
    """
    client = boto3.client("s3", region_name=region)
    client.put_object(
        Bucket=bucket,
        Key=key,
        Body=body.encode("utf-8"),
        ContentType=content_type,
    )
    return f"Uploaded s3://{bucket}/{key} ({len(body)} chars)."


def s3_delete_object(bucket: str, key: str, region: str = "us-east-1") -> str:
    """
    Delete an S3 object.

    Args:
        bucket: Bucket name.
        key: Object key.
        region: AWS region.
    """
    client = boto3.client("s3", region_name=region)
    client.delete_object(Bucket=bucket, Key=key)
    return f"Deleted s3://{bucket}/{key}."


def s3_get_bucket_policy(bucket: str, region: str = "us-east-1") -> str:
    """
    Get the bucket policy for an S3 bucket.

    Args:
        bucket: Bucket name.
        region: AWS region.
    """
    client = boto3.client("s3", region_name=region)
    try:
        resp = client.get_bucket_policy(Bucket=bucket)
        policy = json.loads(resp["Policy"])
        return json.dumps(policy, indent=2)
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchBucketPolicy":
            return f"Bucket '{bucket}' has no bucket policy."
        raise


def s3_get_bucket_versioning(bucket: str, region: str = "us-east-1") -> str:
    """
    Get the versioning configuration for an S3 bucket.

    Args:
        bucket: Bucket name.
        region: AWS region.
    """
    client = boto3.client("s3", region_name=region)
    resp = client.get_bucket_versioning(Bucket=bucket)
    return json.dumps(
        {
            "status": resp.get("Status", "Disabled"),
            "mfa_delete": resp.get("MFADelete", "Disabled"),
        },
        indent=2,
    )


def register(mcp: FastMCP) -> None:
    for fn in [
        s3_list_buckets,
        s3_list_objects,
        s3_get_object,
        s3_put_object,
        s3_delete_object,
        s3_get_bucket_policy,
        s3_get_bucket_versioning,
    ]:
        mcp.tool()(fn)
