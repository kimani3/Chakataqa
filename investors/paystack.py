"""Minimal Paystack client: https://paystack.com/docs/api/transaction/"""

import hashlib
import hmac

import requests
from django.conf import settings

TIMEOUT = 15


class PaystackError(Exception):
    pass


def _headers():
    if not settings.PAYSTACK_SECRET_KEY:
        raise PaystackError("PAYSTACK_SECRET_KEY is not configured.")
    return {"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"}


def _request(method, path, **kwargs):
    try:
        response = requests.request(
            method,
            f"{settings.PAYSTACK_BASE_URL}{path}",
            headers=_headers(),
            timeout=TIMEOUT,
            **kwargs,
        )
        body = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise PaystackError(f"Could not reach Paystack: {exc}") from exc
    if not response.ok or not body.get("status"):
        raise PaystackError(body.get("message", "Paystack rejected the request."))
    return body["data"]


def initialize(*, email, amount_subunit, currency, reference, callback_url):
    """Start a payment and return the URL to send the investor to."""
    data = _request(
        "POST",
        "/transaction/initialize",
        json={
            "email": email,
            "amount": amount_subunit,
            "currency": currency,
            "reference": reference,
            "callback_url": callback_url,
        },
    )
    return data["authorization_url"]


def verify(reference):
    return _request("GET", f"/transaction/verify/{reference}")


def valid_signature(body: bytes, signature: str) -> bool:
    if not settings.PAYSTACK_SECRET_KEY or not signature:
        return False
    expected = hmac.new(
        settings.PAYSTACK_SECRET_KEY.encode(), body, hashlib.sha512
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
