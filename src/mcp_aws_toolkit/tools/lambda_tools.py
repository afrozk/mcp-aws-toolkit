import base64
import json
import boto3
from mcp.server.fastmcp import FastMCP


def lambda_list_functions(max_items: int = 50, region: str = "us-east-1") -> str:
    """List Lambda functions in a region."""
    client = boto3.client("lambda", region_name=region)
    functions: list[dict] = []
    paginator = client.get_paginator("list_functions")
    for page in paginator.paginate(PaginationConfig={"MaxItems": max_items}):
        functions.extend(page["Functions"])
        if len(functions) >= max_items:
            break
    return json.dumps(
        [
            {
                "name": f["FunctionName"],
                "arn": f["FunctionArn"],
                "runtime": f.get("Runtime", ""),
                "handler": f.get("Handler", ""),
                "role": f["Role"],
                "memory_mb": f["MemorySize"],
                "timeout_s": f["Timeout"],
                "last_modified": f["LastModified"],
                "state": f.get("State", "Active"),
                "description": f.get("Description", ""),
            }
            for f in functions[:max_items]
        ],
        indent=2,
    )


def lambda_get_function(function_name: str, region: str = "us-east-1") -> str:
    """
    Get full details for a Lambda function including configuration and code location.

    Args:
        function_name: Function name or ARN.
        region: AWS region.
    """
    client = boto3.client("lambda", region_name=region)
    resp = client.get_function(FunctionName=function_name)
    conf = resp["Configuration"]
    code = resp.get("Code", {})
    concurrency = resp.get("Concurrency", {})
    return json.dumps(
        {
            "name": conf["FunctionName"],
            "arn": conf["FunctionArn"],
            "description": conf.get("Description", ""),
            "runtime": conf.get("Runtime", ""),
            "handler": conf.get("Handler", ""),
            "role": conf["Role"],
            "memory_mb": conf["MemorySize"],
            "timeout_s": conf["Timeout"],
            "last_modified": conf["LastModified"],
            "code_size_bytes": conf["CodeSize"],
            "state": conf.get("State", "Active"),
            "state_reason": conf.get("StateReason", ""),
            "package_type": conf.get("PackageType", "Zip"),
            "architectures": conf.get("Architectures", ["x86_64"]),
            "layers": [layer["Arn"] for layer in conf.get("Layers", [])],
            "environment": conf.get("Environment", {}).get("Variables", {}),
            "reserved_concurrency": concurrency.get("ReservedConcurrentExecutions"),
            "code_location": code.get("Location", ""),
            "tags": resp.get("Tags", {}),
        },
        indent=2,
    )


def lambda_invoke(
    function_name: str,
    payload: str = "{}",
    invocation_type: str = "RequestResponse",
    region: str = "us-east-1",
) -> str:
    """
    Invoke a Lambda function and return the response.

    Args:
        function_name: Function name or ARN.
        payload: JSON string to send as the event payload (default '{}').
        invocation_type: 'RequestResponse' (sync), 'Event' (async), or 'DryRun'.
        region: AWS region.
    """
    client = boto3.client("lambda", region_name=region)
    resp = client.invoke(
        FunctionName=function_name,
        InvocationType=invocation_type,
        LogType="Tail" if invocation_type == "RequestResponse" else "None",
        Payload=payload.encode("utf-8"),
    )
    status_code = resp["StatusCode"]
    function_error = resp.get("FunctionError", "")

    result: dict = {
        "status_code": status_code,
        "function_error": function_error,
        "executed_version": resp.get("ExecutedVersion", "$LATEST"),
    }

    if invocation_type == "RequestResponse":
        raw_payload = resp["Payload"].read()
        try:
            result["response"] = json.loads(raw_payload)
        except json.JSONDecodeError:
            result["response"] = raw_payload.decode("utf-8")

        log_result = resp.get("LogResult", "")
        if log_result:
            result["tail_logs"] = base64.b64decode(log_result).decode("utf-8")

    return json.dumps(result, indent=2)


def lambda_list_versions(function_name: str, region: str = "us-east-1") -> str:
    """
    List all published versions of a Lambda function.

    Args:
        function_name: Function name or ARN.
        region: AWS region.
    """
    client = boto3.client("lambda", region_name=region)
    versions: list[dict] = []
    paginator = client.get_paginator("list_versions_by_function")
    for page in paginator.paginate(FunctionName=function_name):
        versions.extend(page["Versions"])
    return json.dumps(
        [
            {
                "version": v["Version"],
                "arn": v["FunctionArn"],
                "description": v.get("Description", ""),
                "runtime": v.get("Runtime", ""),
                "last_modified": v["LastModified"],
                "code_size_bytes": v["CodeSize"],
                "state": v.get("State", "Active"),
            }
            for v in versions
        ],
        indent=2,
    )


def lambda_list_aliases(function_name: str, region: str = "us-east-1") -> str:
    """
    List aliases for a Lambda function.

    Args:
        function_name: Function name or ARN.
        region: AWS region.
    """
    client = boto3.client("lambda", region_name=region)
    aliases: list[dict] = []
    paginator = client.get_paginator("list_aliases")
    for page in paginator.paginate(FunctionName=function_name):
        aliases.extend(page["Aliases"])
    return json.dumps(
        [
            {
                "name": a["Name"],
                "arn": a["AliasArn"],
                "function_version": a["FunctionVersion"],
                "description": a.get("Description", ""),
                "routing_config": a.get("RoutingConfig", {}),
            }
            for a in aliases
        ],
        indent=2,
    )


def lambda_list_event_source_mappings(
    function_name: str | None = None,
    region: str = "us-east-1",
) -> str:
    """
    List event source mappings (triggers) for a Lambda function or all functions.

    Args:
        function_name: Function name to filter by (omit for all mappings).
        region: AWS region.
    """
    client = boto3.client("lambda", region_name=region)
    kwargs: dict = {}
    if function_name:
        kwargs["FunctionName"] = function_name
    mappings: list[dict] = []
    paginator = client.get_paginator("list_event_source_mappings")
    for page in paginator.paginate(**kwargs):
        mappings.extend(page["EventSourceMappings"])
    return json.dumps(
        [
            {
                "uuid": m["UUID"],
                "event_source_arn": m.get("EventSourceArn", ""),
                "function_arn": m["FunctionArn"],
                "state": m["State"],
                "batch_size": m.get("BatchSize"),
                "bisect_on_error": m.get("BisectBatchOnFunctionError", False),
                "last_modified": str(m.get("LastModified", "")),
                "last_processing_result": m.get("LastProcessingResult", ""),
            }
            for m in mappings
        ],
        indent=2,
    )


def lambda_get_function_url_config(
    function_name: str,
    qualifier: str | None = None,
    region: str = "us-east-1",
) -> str:
    """
    Get the function URL configuration for a Lambda function.

    Args:
        function_name: Function name or ARN.
        qualifier: Alias or version qualifier.
        region: AWS region.
    """
    client = boto3.client("lambda", region_name=region)
    kwargs: dict = {"FunctionName": function_name}
    if qualifier:
        kwargs["Qualifier"] = qualifier
    try:
        resp = client.get_function_url_config(**kwargs)
        return json.dumps(
            {
                "function_url": resp["FunctionUrl"],
                "function_arn": resp["FunctionArn"],
                "auth_type": resp["AuthType"],
                "cors": resp.get("Cors", {}),
                "creation_time": resp["CreationTime"],
                "last_modified": resp["LastModifiedTime"],
                "invoke_mode": resp.get("InvokeMode", "BUFFERED"),
            },
            indent=2,
        )
    except client.exceptions.ResourceNotFoundException:
        return f"No function URL configured for '{function_name}'."


def lambda_put_function_concurrency(
    function_name: str,
    reserved_concurrent_executions: int,
    region: str = "us-east-1",
) -> str:
    """
    Set reserved concurrency for a Lambda function. Set to 0 to throttle it completely.

    Args:
        function_name: Function name or ARN.
        reserved_concurrent_executions: Number of reserved concurrent executions.
        region: AWS region.
    """
    client = boto3.client("lambda", region_name=region)
    resp = client.put_function_concurrency(
        FunctionName=function_name,
        ReservedConcurrentExecutions=reserved_concurrent_executions,
    )
    return json.dumps(
        {
            "function_name": function_name,
            "reserved_concurrent_executions": resp["ReservedConcurrentExecutions"],
        },
        indent=2,
    )


def lambda_delete_function_concurrency(
    function_name: str,
    region: str = "us-east-1",
) -> str:
    """
    Remove reserved concurrency from a Lambda function (revert to account-level pool).

    Args:
        function_name: Function name or ARN.
        region: AWS region.
    """
    client = boto3.client("lambda", region_name=region)
    client.delete_function_concurrency(FunctionName=function_name)
    return f"Removed reserved concurrency from '{function_name}'."


def lambda_get_policy(
    function_name: str,
    qualifier: str | None = None,
    region: str = "us-east-1",
) -> str:
    """
    Get the resource-based policy for a Lambda function (who can invoke it).

    Args:
        function_name: Function name or ARN.
        qualifier: Alias or version qualifier.
        region: AWS region.
    """
    client = boto3.client("lambda", region_name=region)
    kwargs: dict = {"FunctionName": function_name}
    if qualifier:
        kwargs["Qualifier"] = qualifier
    try:
        resp = client.get_policy(**kwargs)
        return json.dumps(json.loads(resp["Policy"]), indent=2)
    except client.exceptions.ResourceNotFoundException:
        return f"No resource-based policy on '{function_name}'."


def register(mcp: FastMCP) -> None:
    for fn in [
        lambda_list_functions,
        lambda_get_function,
        lambda_invoke,
        lambda_list_versions,
        lambda_list_aliases,
        lambda_list_event_source_mappings,
        lambda_get_function_url_config,
        lambda_put_function_concurrency,
        lambda_delete_function_concurrency,
        lambda_get_policy,
    ]:
        mcp.tool()(fn)
