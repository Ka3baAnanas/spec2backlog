"""Shared Gemini HTTP throttle + retry helper.

Free-tier keys are rate limited (RPM/TPM/RPD). We reserve a slot before each
request and retry 429/5xx responses with exponential backoff, honouring Google's
RetryInfo/Retry-After when present. Every wait is reported to an optional event
hook so the pipeline journal can surface it.
"""

import logging
import random
import re
import threading
import time
from collections.abc import Callable

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

EventHook = Callable[[str, str, dict], None] | None
RETRYABLE_STATUS = {429, 500, 502, 503, 504}
RETRY_DELAY_RE = re.compile(r"retry in ([\d.]+)s", re.IGNORECASE)

_lock = threading.Lock()
_next_allowed: dict[str, float] = {}


def _report(hook: EventHook, kind: str, message: str, data: dict) -> None:
    logger.warning(message)
    if hook is None:
        return
    try:
        hook(kind, message, data)
    except Exception:
        logger.exception("could not report Gemini retry event")


def _throttle(scope: str, min_interval: float, hook: EventHook) -> None:
    if min_interval <= 0:
        return
    with _lock:
        now = time.monotonic()
        next_at = _next_allowed.get(scope, 0.0)
        wait = max(0.0, next_at - now)
        _next_allowed[scope] = max(now, next_at) + min_interval
    if wait > 0.05:
        _report(
            hook,
            "info",
            f"Throttling {scope}: waiting {wait:.1f}s before the next request",
            {"scope": scope, "reason": "throttle", "wait_seconds": round(wait, 2)},
        )
        time.sleep(wait)


def _seconds(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    match = re.fullmatch(r"([\d.]+)(ms|s)?", text, re.IGNORECASE)
    if not match:
        return None
    amount = float(match.group(1))
    return amount / 1000 if (match.group(2) or "").lower() == "ms" else amount


def _retry_delay(response: httpx.Response) -> float | None:
    header = response.headers.get("retry-after")
    seconds = _seconds(header)
    if seconds is not None:
        return seconds
    try:
        payload = response.json()
    except ValueError:
        payload = None
    if isinstance(payload, dict):
        error = payload.get("error") or {}
        for detail in error.get("details") or []:
            if isinstance(detail, dict) and str(detail.get("@type", "")).endswith("RetryInfo"):
                seconds = _seconds(detail.get("retryDelay"))
                if seconds is not None:
                    return seconds
        match = RETRY_DELAY_RE.search(str(error.get("message") or ""))
        if match:
            return float(match.group(1))
    return None


def post_with_retry(
    scope: str,
    url: str,
    *,
    params: dict,
    json: dict,
    timeout: float,
    on_event: EventHook = None,
) -> httpx.Response:
    """POST with request throttling and retry/backoff for rate limits and 5xx."""
    max_retries = max(1, settings.gemini_max_retries)
    base = max(0.1, settings.gemini_retry_base_seconds)
    max_wait = max(1.0, settings.gemini_retry_max_seconds)
    attempt = 0

    while True:
        attempt += 1
        _throttle(scope, settings.gemini_min_interval_seconds, on_event)
        try:
            response = httpx.post(url, params=params, json=json, timeout=timeout)
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            if attempt > max_retries:
                raise
            delay = min(max_wait, base * 2 ** (attempt - 1)) + random.uniform(0, 0.5)
            _report(
                on_event,
                "warning",
                f"{scope} network error; retrying in {delay:.1f}s "
                f"(attempt {attempt}/{max_retries})",
                {
                    "scope": scope,
                    "reason": "network",
                    "error": f"{type(exc).__name__}: {exc}",
                    "attempt": attempt,
                    "max_retries": max_retries,
                    "wait_seconds": round(delay, 2),
                },
            )
            time.sleep(delay)
            continue

        if response.status_code in RETRYABLE_STATUS:
            delay = _retry_delay(response)
            if delay is None:
                delay = base * 2 ** (attempt - 1)
            delay = min(max_wait, max(0.5, delay)) + random.uniform(0, 0.75)
            if attempt > max_retries:
                _report(
                    on_event,
                    "warning",
                    f"{scope} still rate limited after {max_retries} retries",
                    {
                        "scope": scope,
                        "reason": "rate_limit_exhausted",
                        "status_code": response.status_code,
                        "attempt": attempt,
                    },
                )
                response.raise_for_status()
            _report(
                on_event,
                "warning",
                f"{scope} returned {response.status_code}; retrying in {delay:.1f}s "
                f"(attempt {attempt}/{max_retries})",
                {
                    "scope": scope,
                    "reason": "rate_limit" if response.status_code == 429 else "server_error",
                    "status_code": response.status_code,
                    "attempt": attempt,
                    "max_retries": max_retries,
                    "wait_seconds": round(delay, 2),
                },
            )
            time.sleep(delay)
            continue

        response.raise_for_status()
        return response
