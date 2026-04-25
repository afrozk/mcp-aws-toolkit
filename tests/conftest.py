import io
import json
import zipfile
import boto3
import pytest
from moto import mock_aws


REGION = "us-east-1"
TRUST_POLICY = json.dumps(
    {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "lambda.amazonaws.com"},
                "Action": "sts:AssumeRole",
            }
        ],
    }
)


@pytest.fixture(autouse=True)
def aws_credentials(monkeypatch):
    """Prevent any real AWS calls from leaving the test process."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", REGION)


@pytest.fixture()
def moto_aws(aws_credentials):
    """Activate moto mock for all AWS services. All fixtures that touch boto3 must depend on this."""
    with mock_aws():
        yield


def make_lambda_zip(handler_code: str = "def handler(e, c): return {'ok': True}") -> bytes:
    """Return a minimal ZIP file containing handler.py for Lambda test fixtures."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("handler.py", handler_code)
    return buf.getvalue()
