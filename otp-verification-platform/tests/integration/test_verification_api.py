"""Integration tests for the verification API and browser app."""

from typing import Optional

from fastapi.testclient import TestClient
from otp_api.email import EmailDeliveryError
from otp_api.main import create_app
from otp_api.settings import Settings
from otp_core.models import ChallengeStatus
from otp_core.service import OTPService


class RecordingEmailSender:
    def __init__(self, fail: bool = False) -> None:
        self.recipient: Optional[str] = None
        self.otp: Optional[str] = None
        self.ttl_seconds: Optional[int] = None
        self.fail = fail

    def send_otp(self, recipient: str, otp: str, ttl_seconds: int) -> None:
        if self.fail:
            raise EmailDeliveryError("SMTP delivery failed")
        self.recipient = recipient
        self.otp = otp
        self.ttl_seconds = ttl_seconds


def make_client(
    sender: RecordingEmailSender,
    otp_length: int = 6,
) -> tuple[TestClient, OTPService]:
    config = Settings(
        app_env="test",
        otp_hmac_secret="integration-test-secret-with-32-bytes-minimum",
        otp_length=otp_length,
        otp_resend_cooldown_seconds=60,
    )
    service = OTPService(
        secret=config.otp_hmac_secret.get_secret_value().encode("utf-8"),
        ttl_seconds=config.otp_ttl_seconds,
        max_attempts=config.otp_max_attempts,
        otp_length=config.otp_length,
        resend_cooldown_seconds=config.otp_resend_cooldown_seconds,
    )
    return TestClient(create_app(config, sender, service)), service


def test_issue_and_verify_code_without_returning_the_code() -> None:
    sender = RecordingEmailSender()
    client, _ = make_client(sender)

    issue = client.post(
        "/api/v1/challenges",
        json={"email": "person@example.com"},
    )

    assert issue.status_code == 202
    assert sender.recipient == "person@example.com"
    assert sender.otp is not None
    assert sender.ttl_seconds == 300
    assert sender.otp not in issue.text
    assert issue.headers["cache-control"] == "no-store"

    verify = client.post(
        f"/api/v1/challenges/{issue.json()['challenge_id']}/verify",
        json={"email": "person@example.com", "code": sender.otp},
    )

    assert verify.status_code == 200
    assert verify.json() == {"verified": True}
    assert verify.headers["cache-control"] == "no-store"


def test_delivery_failure_cancels_code_and_allows_retry() -> None:
    client, service = make_client(RecordingEmailSender(fail=True))

    first_response = client.post(
        "/api/v1/challenges",
        json={"email": "person@example.com"},
    )

    assert first_response.status_code == 503
    assert "challenge_id" not in first_response.text
    challenge_id = next(iter(service._challenges))
    challenge = service.get_challenge(challenge_id)
    assert challenge is not None
    assert challenge.status == ChallengeStatus.EXPIRED

    retry_response = client.post(
        "/api/v1/challenges",
        json={"email": "person@example.com"},
    )
    assert retry_response.status_code == 503


def test_resend_cooldown_returns_retry_after() -> None:
    sender = RecordingEmailSender()
    client, _ = make_client(sender)
    first = client.post(
        "/api/v1/challenges",
        json={"email": "person@example.com"},
    )
    second = client.post(
        "/api/v1/challenges",
        json={"email": "person@example.com"},
    )

    assert first.status_code == 202
    assert second.status_code == 429
    assert second.headers["retry-after"] == "60"


def test_static_web_gui_is_served() -> None:
    client, _ = make_client(RecordingEmailSender())

    response = client.get("/")

    assert response.status_code == 200
    assert "Verify your email" in response.text
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/api/v1/config").json() == {
        "otp_length": 6,
        "ttl_seconds": 300,
    }
    assert response.headers["content-security-policy"].startswith("default-src 'self'")


def test_client_address_rate_limit_is_enforced() -> None:
    client, _ = make_client(RecordingEmailSender())
    responses = [
        client.post(
            "/api/v1/challenges",
            json={"email": f"person{index}@example.com"},
        )
        for index in range(6)
    ]

    assert [response.status_code for response in responses] == [
        202,
        202,
        202,
        202,
        202,
        429,
    ]
    assert responses[-1].headers["retry-after"]


def test_configured_code_length_is_used_by_the_service_and_api() -> None:
    sender = RecordingEmailSender()
    client, _ = make_client(sender, otp_length=8)
    issue = client.post(
        "/api/v1/challenges",
        json={"email": "person@example.com"},
    )

    assert issue.status_code == 202
    assert sender.otp is not None and len(sender.otp) == 8
    assert client.get("/api/v1/config").json()["otp_length"] == 8

    invalid_length = client.post(
        f"/api/v1/challenges/{issue.json()['challenge_id']}/verify",
        json={"email": "person@example.com", "code": "123456"},
    )
    valid_length = client.post(
        f"/api/v1/challenges/{issue.json()['challenge_id']}/verify",
        json={"email": "person@example.com", "code": sender.otp},
    )

    assert invalid_length.status_code == 422
    assert invalid_length.headers["cache-control"] == "no-store"
    assert valid_length.status_code == 200


def test_invalid_email_and_code_are_rejected() -> None:
    client, _ = make_client(RecordingEmailSender())

    invalid_email = client.post(
        "/api/v1/challenges",
        json={"email": "not-an-email"},
    )
    invalid_code = client.post(
        "/api/v1/challenges/example/verify",
        json={"email": "person@example.com", "code": "letters"},
    )

    assert invalid_email.status_code == 422
    assert invalid_code.status_code == 422
    assert invalid_code.headers["cache-control"] == "no-store"
