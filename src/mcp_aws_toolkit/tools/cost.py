import json
from datetime import date, timedelta
import boto3
from mcp.server.fastmcp import FastMCP

# Cost Explorer is a global service; its API endpoint is always us-east-1.
_CE_REGION = "us-east-1"


def _client():
    return boto3.client("ce", region_name=_CE_REGION)


def _parse_groups(groups: list[dict], metric: str = "UnblendedCost") -> list[dict]:
    items = [
        {
            "service": g["Keys"][0],
            "cost": round(float(g["Metrics"][metric]["Amount"]), 4),
            "unit": g["Metrics"][metric]["Unit"],
        }
        for g in groups
    ]
    return sorted(items, key=lambda x: x["cost"], reverse=True)


def cost_current_month() -> str:
    """
    Get AWS costs for the current calendar month broken down by service.

    Returns services sorted by cost descending, plus a month-to-date total.
    Note: Cost Explorer charges $0.01 per API request after the first 10,000/month.
    """
    client = _client()
    today = date.today()
    start = today.replace(day=1).isoformat()
    # CE end date is exclusive; advance by 1 day so today's data is included
    end = (today + timedelta(days=1)).isoformat()

    resp = client.get_cost_and_usage(
        TimePeriod={"Start": start, "End": end},
        Granularity="MONTHLY",
        Metrics=["UnblendedCost"],
        GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
    )
    groups = resp["ResultsByTime"][0]["Groups"] if resp["ResultsByTime"] else []
    items = [i for i in _parse_groups(groups) if i["cost"] > 0]
    total = round(sum(i["cost"] for i in items), 4)
    unit = items[0]["unit"] if items else "USD"
    return json.dumps(
        {
            "period": f"{start} → today ({today.isoformat()})",
            "total_cost": total,
            "unit": unit,
            "services": items,
        },
        indent=2,
    )


def cost_last_month() -> str:
    """
    Get AWS costs for the previous calendar month broken down by service.

    Note: Cost Explorer charges $0.01 per API request after the first 10,000/month.
    """
    client = _client()
    today = date.today()
    first_of_this_month = today.replace(day=1)
    last_month_end = first_of_this_month  # exclusive end = first of this month
    last_month_start = (first_of_this_month - timedelta(days=1)).replace(day=1)

    resp = client.get_cost_and_usage(
        TimePeriod={
            "Start": last_month_start.isoformat(),
            "End": last_month_end.isoformat(),
        },
        Granularity="MONTHLY",
        Metrics=["UnblendedCost"],
        GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
    )
    groups = resp["ResultsByTime"][0]["Groups"] if resp["ResultsByTime"] else []
    items = [i for i in _parse_groups(groups) if i["cost"] > 0]
    total = round(sum(i["cost"] for i in items), 4)
    unit = items[0]["unit"] if items else "USD"
    return json.dumps(
        {
            "period": f"{last_month_start.isoformat()} → {(last_month_end - timedelta(days=1)).isoformat()}",
            "total_cost": total,
            "unit": unit,
            "services": items,
        },
        indent=2,
    )


def cost_date_range(
    start: str,
    end: str,
    granularity: str = "DAILY",
) -> str:
    """
    Get AWS costs for a custom date range, grouped by service.

    Args:
        start: Start date inclusive, YYYY-MM-DD.
        end: End date exclusive, YYYY-MM-DD (use the day after your desired last day).
        granularity: DAILY, MONTHLY, or HOURLY.

    Note: Cost Explorer charges $0.01 per API request after the first 10,000/month.
    """
    client = _client()
    resp = client.get_cost_and_usage(
        TimePeriod={"Start": start, "End": end},
        Granularity=granularity,
        Metrics=["UnblendedCost"],
        GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
    )
    periods = []
    for result in resp["ResultsByTime"]:
        items = [i for i in _parse_groups(result["Groups"]) if i["cost"] > 0]
        total = round(sum(i["cost"] for i in items), 4)
        unit = items[0]["unit"] if items else "USD"
        periods.append(
            {
                "period_start": result["TimePeriod"]["Start"],
                "period_end": result["TimePeriod"]["End"],
                "total_cost": total,
                "unit": unit,
                "estimated": result.get("Estimated", False),
                "services": items,
            }
        )
    return json.dumps(periods, indent=2)


def cost_forecast(
    days: int = 30,
    granularity: str = "DAILY",
) -> str:
    """
    Get an AWS cost forecast for the next N days.

    Args:
        days: Number of days ahead to forecast (default 30).
        granularity: DAILY or MONTHLY granularity for the forecast.

    Note: Cost Explorer charges $0.01 per API request after the first 10,000/month.
    """
    client = _client()
    today = date.today()
    start = today.isoformat()
    end = (today + timedelta(days=days)).isoformat()

    resp = client.get_cost_forecast(
        TimePeriod={"Start": start, "End": end},
        Metric="UNBLENDED_COST",
        Granularity=granularity,
    )
    total = resp["Total"]
    forecasted_total = round(float(total["Amount"]), 4)
    unit = total["Unit"]

    daily = [
        {
            "date": r["TimePeriod"]["Start"],
            "forecasted_cost": round(float(r["MeanValue"]), 4),
            "unit": unit,
        }
        for r in resp.get("ForecastResultsByTime", [])
    ]
    return json.dumps(
        {
            "forecast_period": f"{start} → {end}",
            "forecasted_total": forecasted_total,
            "unit": unit,
            "daily_forecast": daily,
        },
        indent=2,
    )


def cost_top_services(
    top_n: int = 10,
    days: int = 30,
) -> str:
    """
    Get the top N most expensive AWS services over the last N days.

    Args:
        top_n: Number of top services to return (default 10).
        days: How many days of history to look back (default 30).

    Note: Cost Explorer charges $0.01 per API request after the first 10,000/month.
    """
    client = _client()
    today = date.today()
    start = (today - timedelta(days=days)).isoformat()
    end = (today + timedelta(days=1)).isoformat()

    resp = client.get_cost_and_usage(
        TimePeriod={"Start": start, "End": end},
        Granularity="MONTHLY",
        Metrics=["UnblendedCost"],
        GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
    )
    # Aggregate across all returned time periods
    aggregated: dict[str, float] = {}
    unit = "USD"
    for result in resp["ResultsByTime"]:
        for g in result["Groups"]:
            svc = g["Keys"][0]
            amt = float(g["Metrics"]["UnblendedCost"]["Amount"])
            unit = g["Metrics"]["UnblendedCost"]["Unit"]
            aggregated[svc] = aggregated.get(svc, 0.0) + amt

    ranked = sorted(aggregated.items(), key=lambda x: x[1], reverse=True)
    top = [
        {"rank": i + 1, "service": svc, "cost": round(cost, 4), "unit": unit}
        for i, (svc, cost) in enumerate(ranked[:top_n])
        if cost > 0
    ]
    total = round(sum(c for _, c in ranked), 4)
    return json.dumps(
        {
            "period": f"last {days} days ({start} → today)",
            "total_cost": total,
            "unit": unit,
            "top_services": top,
        },
        indent=2,
    )


def cost_daily_trend(days: int = 14) -> str:
    """
    Get daily AWS spending for the last N days with a per-service breakdown.

    Args:
        days: Number of days of history (default 14).

    Note: Cost Explorer charges $0.01 per API request after the first 10,000/month.
    """
    client = _client()
    today = date.today()
    start = (today - timedelta(days=days)).isoformat()
    end = (today + timedelta(days=1)).isoformat()

    resp = client.get_cost_and_usage(
        TimePeriod={"Start": start, "End": end},
        Granularity="DAILY",
        Metrics=["UnblendedCost"],
        GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
    )
    trend = []
    for result in resp["ResultsByTime"]:
        items = [i for i in _parse_groups(result["Groups"]) if i["cost"] > 0]
        total = round(sum(i["cost"] for i in items), 4)
        unit = items[0]["unit"] if items else "USD"
        trend.append(
            {
                "date": result["TimePeriod"]["Start"],
                "total_cost": total,
                "unit": unit,
                "estimated": result.get("Estimated", False),
                "top_services": items[:5],
            }
        )
    return json.dumps(trend, indent=2)


def cost_by_tag(
    tag_key: str,
    days: int = 30,
) -> str:
    """
    Get AWS costs grouped by a cost allocation tag for the last N days.

    Requires cost allocation tags to be activated in your AWS Billing console.

    Args:
        tag_key: The tag key to group by (e.g. 'Environment', 'Team', 'Project').
        days: Number of days of history (default 30).

    Note: Cost Explorer charges $0.01 per API request after the first 10,000/month.
    """
    client = _client()
    today = date.today()
    start = (today - timedelta(days=days)).isoformat()
    end = (today + timedelta(days=1)).isoformat()

    resp = client.get_cost_and_usage(
        TimePeriod={"Start": start, "End": end},
        Granularity="MONTHLY",
        Metrics=["UnblendedCost"],
        GroupBy=[{"Type": "TAG", "Key": tag_key}],
    )
    aggregated: dict[str, float] = {}
    unit = "USD"
    for result in resp["ResultsByTime"]:
        for g in result["Groups"]:
            tag_value = g["Keys"][0].replace(f"{tag_key}$", "") or "(untagged)"
            amt = float(g["Metrics"]["UnblendedCost"]["Amount"])
            unit = g["Metrics"]["UnblendedCost"]["Unit"]
            aggregated[tag_value] = aggregated.get(tag_value, 0.0) + amt

    ranked = sorted(aggregated.items(), key=lambda x: x[1], reverse=True)
    items = [
        {"tag_value": v, "cost": round(c, 4), "unit": unit}
        for v, c in ranked
        if c > 0
    ]
    total = round(sum(c for _, c in ranked), 4)
    return json.dumps(
        {
            "tag_key": tag_key,
            "period": f"last {days} days ({start} → today)",
            "total_cost": total,
            "unit": unit,
            "breakdown": items,
        },
        indent=2,
    )


def register(mcp: FastMCP) -> None:
    for fn in [
        cost_current_month,
        cost_last_month,
        cost_date_range,
        cost_forecast,
        cost_top_services,
        cost_daily_trend,
        cost_by_tag,
    ]:
        mcp.tool()(fn)
