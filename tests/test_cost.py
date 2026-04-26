"""
Cost Explorer tests use unittest.mock rather than moto because moto does not
implement get_cost_and_usage or get_cost_forecast.  We patch boto3.client in
the cost module so the tools' parsing and formatting logic is fully exercised.
"""
import json
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest

from mcp_aws_toolkit.tools.cost import (
    cost_by_tag,
    cost_current_month,
    cost_daily_trend,
    cost_date_range,
    cost_forecast,
    cost_last_month,
    cost_top_services,
)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_USD = "USD"


def _group(service: str, amount: str) -> dict:
    return {
        "Keys": [service],
        "Metrics": {"UnblendedCost": {"Amount": amount, "Unit": _USD}},
    }


def _time_period(start: str, end: str) -> dict:
    return {"Start": start, "End": end}


def _usage_result(start: str, end: str, groups: list[dict], estimated: bool = False) -> dict:
    return {
        "TimePeriod": _time_period(start, end),
        "Groups": groups,
        "Total": {},
        "Estimated": estimated,
    }


def _mock_ce(response: dict) -> MagicMock:
    """Return a mock boto3 CE client pre-loaded with a get_cost_and_usage response."""
    mock = MagicMock()
    mock.get_cost_and_usage.return_value = response
    return mock


# ---------------------------------------------------------------------------
# cost_current_month
# ---------------------------------------------------------------------------

@patch("mcp_aws_toolkit.tools.cost.boto3")
def test_current_month_total(mock_boto3):
    today = date.today()
    start = today.replace(day=1).isoformat()
    end = today.isoformat()
    mock_boto3.client.return_value = _mock_ce(
        {
            "ResultsByTime": [
                _usage_result(
                    start,
                    end,
                    [_group("Amazon ECS", "45.20"), _group("AWS Lambda", "5.00")],
                )
            ]
        }
    )
    result = json.loads(cost_current_month())
    assert result["total_cost"] == pytest.approx(50.20, abs=0.01)
    assert result["unit"] == _USD


@patch("mcp_aws_toolkit.tools.cost.boto3")
def test_current_month_services_sorted_desc(mock_boto3):
    today = date.today()
    start = today.replace(day=1).isoformat()
    mock_boto3.client.return_value = _mock_ce(
        {
            "ResultsByTime": [
                _usage_result(
                    start,
                    today.isoformat(),
                    [
                        _group("Amazon S3", "10.00"),
                        _group("Amazon ECS", "80.00"),
                        _group("AWS Lambda", "3.00"),
                    ],
                )
            ]
        }
    )
    result = json.loads(cost_current_month())
    costs = [s["cost"] for s in result["services"]]
    assert costs == sorted(costs, reverse=True)
    assert result["services"][0]["service"] == "Amazon ECS"


@patch("mcp_aws_toolkit.tools.cost.boto3")
def test_current_month_excludes_zero_cost_services(mock_boto3):
    today = date.today()
    start = today.replace(day=1).isoformat()
    mock_boto3.client.return_value = _mock_ce(
        {
            "ResultsByTime": [
                _usage_result(
                    start,
                    today.isoformat(),
                    [_group("Amazon EC2", "20.00"), _group("AWS IAM", "0.00")],
                )
            ]
        }
    )
    result = json.loads(cost_current_month())
    service_names = [s["service"] for s in result["services"]]
    assert "AWS IAM" not in service_names


@patch("mcp_aws_toolkit.tools.cost.boto3")
def test_current_month_empty(mock_boto3):
    today = date.today()
    mock_boto3.client.return_value = _mock_ce(
        {"ResultsByTime": [_usage_result(today.isoformat(), today.isoformat(), [])]}
    )
    result = json.loads(cost_current_month())
    assert result["total_cost"] == 0
    assert result["services"] == []


# ---------------------------------------------------------------------------
# cost_last_month
# ---------------------------------------------------------------------------

@patch("mcp_aws_toolkit.tools.cost.boto3")
def test_last_month_total(mock_boto3):
    today = date.today()
    first = today.replace(day=1)
    lm_start = (first - timedelta(days=1)).replace(day=1)
    mock_boto3.client.return_value = _mock_ce(
        {
            "ResultsByTime": [
                _usage_result(
                    lm_start.isoformat(),
                    first.isoformat(),
                    [_group("Amazon RDS", "120.50"), _group("Amazon S3", "8.75")],
                )
            ]
        }
    )
    result = json.loads(cost_last_month())
    assert result["total_cost"] == pytest.approx(129.25, abs=0.01)
    assert "period" in result


@patch("mcp_aws_toolkit.tools.cost.boto3")
def test_last_month_has_services(mock_boto3):
    today = date.today()
    first = today.replace(day=1)
    lm_start = (first - timedelta(days=1)).replace(day=1)
    mock_boto3.client.return_value = _mock_ce(
        {
            "ResultsByTime": [
                _usage_result(
                    lm_start.isoformat(),
                    first.isoformat(),
                    [_group("Amazon RDS", "120.50")],
                )
            ]
        }
    )
    result = json.loads(cost_last_month())
    assert result["services"][0]["service"] == "Amazon RDS"


# ---------------------------------------------------------------------------
# cost_date_range
# ---------------------------------------------------------------------------

@patch("mcp_aws_toolkit.tools.cost.boto3")
def test_date_range_single_period(mock_boto3):
    mock_boto3.client.return_value = _mock_ce(
        {
            "ResultsByTime": [
                _usage_result(
                    "2024-01-01",
                    "2024-02-01",
                    [_group("Amazon EC2", "200.00"), _group("Amazon S3", "15.00")],
                )
            ]
        }
    )
    result = json.loads(cost_date_range(start="2024-01-01", end="2024-02-01"))
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["total_cost"] == pytest.approx(215.00, abs=0.01)


@patch("mcp_aws_toolkit.tools.cost.boto3")
def test_date_range_multiple_periods(mock_boto3):
    mock_boto3.client.return_value = _mock_ce(
        {
            "ResultsByTime": [
                _usage_result("2024-01-01", "2024-01-02", [_group("Amazon EC2", "5.00")]),
                _usage_result("2024-01-02", "2024-01-03", [_group("Amazon EC2", "7.00")]),
                _usage_result("2024-01-03", "2024-01-04", [_group("Amazon EC2", "6.00")]),
            ]
        }
    )
    result = json.loads(cost_date_range(start="2024-01-01", end="2024-01-04", granularity="DAILY"))
    assert len(result) == 3
    assert result[0]["period_start"] == "2024-01-01"
    assert result[2]["period_start"] == "2024-01-03"


@patch("mcp_aws_toolkit.tools.cost.boto3")
def test_date_range_passes_correct_params(mock_boto3):
    mock_ce = _mock_ce({"ResultsByTime": []})
    mock_boto3.client.return_value = mock_ce
    cost_date_range(start="2024-03-01", end="2024-04-01", granularity="MONTHLY")
    call_kwargs = mock_ce.get_cost_and_usage.call_args.kwargs
    assert call_kwargs["TimePeriod"]["Start"] == "2024-03-01"
    assert call_kwargs["TimePeriod"]["End"] == "2024-04-01"
    assert call_kwargs["Granularity"] == "MONTHLY"


# ---------------------------------------------------------------------------
# cost_forecast
# ---------------------------------------------------------------------------

@patch("mcp_aws_toolkit.tools.cost.boto3")
def test_forecast_total_and_daily(mock_boto3):
    today = date.today()
    mock_ce = MagicMock()
    mock_boto3.client.return_value = mock_ce
    mock_ce.get_cost_forecast.return_value = {
        "Total": {"Amount": "300.00", "Unit": _USD},
        "ForecastResultsByTime": [
            {
                "TimePeriod": _time_period(today.isoformat(), (today + timedelta(days=1)).isoformat()),
                "MeanValue": "10.00",
            },
            {
                "TimePeriod": _time_period(
                    (today + timedelta(days=1)).isoformat(),
                    (today + timedelta(days=2)).isoformat(),
                ),
                "MeanValue": "10.50",
            },
        ],
    }
    result = json.loads(cost_forecast(days=30))
    assert result["forecasted_total"] == pytest.approx(300.00, abs=0.01)
    assert result["unit"] == _USD
    assert len(result["daily_forecast"]) == 2
    assert result["daily_forecast"][0]["forecasted_cost"] == pytest.approx(10.00, abs=0.01)


@patch("mcp_aws_toolkit.tools.cost.boto3")
def test_forecast_passes_correct_params(mock_boto3):
    today = date.today()
    mock_ce = MagicMock()
    mock_boto3.client.return_value = mock_ce
    mock_ce.get_cost_forecast.return_value = {
        "Total": {"Amount": "0", "Unit": _USD},
        "ForecastResultsByTime": [],
    }
    cost_forecast(days=14, granularity="MONTHLY")
    call_kwargs = mock_ce.get_cost_forecast.call_args.kwargs
    assert call_kwargs["TimePeriod"]["Start"] == today.isoformat()
    assert call_kwargs["Granularity"] == "MONTHLY"
    assert call_kwargs["Metric"] == "UNBLENDED_COST"


# ---------------------------------------------------------------------------
# cost_top_services
# ---------------------------------------------------------------------------

@patch("mcp_aws_toolkit.tools.cost.boto3")
def test_top_services_ranking(mock_boto3):
    today = date.today()
    start = (today - timedelta(days=30)).isoformat()
    mock_boto3.client.return_value = _mock_ce(
        {
            "ResultsByTime": [
                _usage_result(
                    start,
                    today.isoformat(),
                    [
                        _group("Amazon EC2", "500.00"),
                        _group("Amazon S3", "50.00"),
                        _group("AWS Lambda", "10.00"),
                        _group("Amazon RDS", "200.00"),
                    ],
                )
            ]
        }
    )
    result = json.loads(cost_top_services(top_n=3))
    assert result["top_services"][0]["service"] == "Amazon EC2"
    assert result["top_services"][0]["rank"] == 1
    assert len(result["top_services"]) == 3


@patch("mcp_aws_toolkit.tools.cost.boto3")
def test_top_services_total(mock_boto3):
    today = date.today()
    start = (today - timedelta(days=30)).isoformat()
    mock_boto3.client.return_value = _mock_ce(
        {
            "ResultsByTime": [
                _usage_result(
                    start,
                    today.isoformat(),
                    [_group("Amazon EC2", "100.00"), _group("Amazon S3", "50.00")],
                )
            ]
        }
    )
    result = json.loads(cost_top_services())
    assert result["total_cost"] == pytest.approx(150.00, abs=0.01)


# ---------------------------------------------------------------------------
# cost_daily_trend
# ---------------------------------------------------------------------------

@patch("mcp_aws_toolkit.tools.cost.boto3")
def test_daily_trend_structure(mock_boto3):
    today = date.today()
    mock_boto3.client.return_value = _mock_ce(
        {
            "ResultsByTime": [
                _usage_result(
                    (today - timedelta(days=2)).isoformat(),
                    (today - timedelta(days=1)).isoformat(),
                    [_group("Amazon ECS", "12.00")],
                ),
                _usage_result(
                    (today - timedelta(days=1)).isoformat(),
                    today.isoformat(),
                    [_group("Amazon ECS", "14.00"), _group("AWS Lambda", "1.00")],
                ),
            ]
        }
    )
    result = json.loads(cost_daily_trend(days=2))
    assert isinstance(result, list)
    assert len(result) == 2
    assert "date" in result[0]
    assert "total_cost" in result[0]
    assert "top_services" in result[0]


@patch("mcp_aws_toolkit.tools.cost.boto3")
def test_daily_trend_top_services_limited_to_5(mock_boto3):
    today = date.today()
    mock_boto3.client.return_value = _mock_ce(
        {
            "ResultsByTime": [
                _usage_result(
                    (today - timedelta(days=1)).isoformat(),
                    today.isoformat(),
                    [
                        _group("Service A", "10.00"),
                        _group("Service B", "9.00"),
                        _group("Service C", "8.00"),
                        _group("Service D", "7.00"),
                        _group("Service E", "6.00"),
                        _group("Service F", "5.00"),
                        _group("Service G", "4.00"),
                    ],
                )
            ]
        }
    )
    result = json.loads(cost_daily_trend(days=1))
    assert len(result[0]["top_services"]) <= 5


# ---------------------------------------------------------------------------
# cost_by_tag
# ---------------------------------------------------------------------------

@patch("mcp_aws_toolkit.tools.cost.boto3")
def test_by_tag_breakdown(mock_boto3):
    today = date.today()
    start = (today - timedelta(days=30)).isoformat()
    mock_boto3.client.return_value = _mock_ce(
        {
            "ResultsByTime": [
                _usage_result(
                    start,
                    today.isoformat(),
                    [
                        {"Keys": ["Environment$production"], "Metrics": {"UnblendedCost": {"Amount": "400.00", "Unit": _USD}}},
                        {"Keys": ["Environment$staging"], "Metrics": {"UnblendedCost": {"Amount": "60.00", "Unit": _USD}}},
                        {"Keys": ["Environment$"], "Metrics": {"UnblendedCost": {"Amount": "20.00", "Unit": _USD}}},
                    ],
                )
            ]
        }
    )
    result = json.loads(cost_by_tag(tag_key="Environment"))
    assert result["tag_key"] == "Environment"
    tag_values = [b["tag_value"] for b in result["breakdown"]]
    assert "production" in tag_values
    assert "staging" in tag_values
    assert "(untagged)" in tag_values


@patch("mcp_aws_toolkit.tools.cost.boto3")
def test_by_tag_sorted_desc(mock_boto3):
    today = date.today()
    start = (today - timedelta(days=30)).isoformat()
    mock_boto3.client.return_value = _mock_ce(
        {
            "ResultsByTime": [
                _usage_result(
                    start,
                    today.isoformat(),
                    [
                        {"Keys": ["Team$platform"], "Metrics": {"UnblendedCost": {"Amount": "30.00", "Unit": _USD}}},
                        {"Keys": ["Team$data"], "Metrics": {"UnblendedCost": {"Amount": "200.00", "Unit": _USD}}},
                    ],
                )
            ]
        }
    )
    result = json.loads(cost_by_tag(tag_key="Team"))
    costs = [b["cost"] for b in result["breakdown"]]
    assert costs == sorted(costs, reverse=True)


@patch("mcp_aws_toolkit.tools.cost.boto3")
def test_by_tag_total(mock_boto3):
    today = date.today()
    start = (today - timedelta(days=30)).isoformat()
    mock_boto3.client.return_value = _mock_ce(
        {
            "ResultsByTime": [
                _usage_result(
                    start,
                    today.isoformat(),
                    [
                        {"Keys": ["Project$alpha"], "Metrics": {"UnblendedCost": {"Amount": "100.00", "Unit": _USD}}},
                        {"Keys": ["Project$beta"], "Metrics": {"UnblendedCost": {"Amount": "75.00", "Unit": _USD}}},
                    ],
                )
            ]
        }
    )
    result = json.loads(cost_by_tag(tag_key="Project"))
    assert result["total_cost"] == pytest.approx(175.00, abs=0.01)
