"""Dormant MC-010 request/response contract. No credentials or startup hooks.

The production service does not construct this runtime. A future activation
must supply a reviewed model/rate policy and protected credentials. The
transport is injected; offline tests use mocks, never the real HTTP adapter.
"""
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Callable
import http.client
import json
import time

INPUT_LIMIT = 4000
OUTPUT_LIMIT = 750
DAILY_MICRO_USD = 5_000_000
INSTRUCTIONS = (
    "You are the Mission Control Chief of Staff. Provide advisory text only. "
    "You cannot authorize or perform tools, assignments, execution, delegation, "
    "notifications, or external changes. Do not claim to have performed actions."
)


class ProviderFailure(ValueError):
    """Fixed safe error code; never contains provider response content."""


@dataclass(frozen=True)
class ProviderPolicy:
    model: str
    # Integer micro-USD per million tokens; never floating-point money.
    input_rate: int
    output_rate: int
    valid_until: int

    def validate(self, now: int) -> None:
        if (not isinstance(self.model, str) or not self.model or len(self.model) > 100
                or any(type(x) is not int or x <= 0 for x in (self.input_rate, self.output_rate, self.valid_until))
                or now >= self.valid_until):
            raise ProviderFailure("provider_policy_unverified")

    def reservation(self) -> int:
        # Conservatively allow one charged input-count call plus generation.
        # Retain the full reservation after success or an uncertain outcome.
        return (2 * INPUT_LIMIT * self.input_rate + OUTPUT_LIMIT * self.output_rate + 999_999) // 1_000_000


class ProviderRuntime:
    def __init__(self, policy: ProviderPolicy, count_input: Callable, send: Callable):
        self.policy, self.count_input, self.send = policy, count_input, send

    def prepare(self, body: str, now: int) -> dict:
        self.policy.validate(now)
        payload = {"model": self.policy.model, "instructions": INSTRUCTIONS,
                   "input": [{"role": "user", "content": body}],
                   "max_output_tokens": OUTPUT_LIMIT, "store": False,
                   "stream": False, "tools": [], "tool_choice": "none",
                   "reasoning": {"effort": "none"}}
        return payload

    def complete(self, payload: dict) -> str:
        # Called only after the encrypted spend reservation is persisted. The
        # official count endpoint includes instructions and message framing.
        count = self.count_input(payload)
        if type(count) is not int or count < 1 or count > INPUT_LIMIT:
            raise ProviderFailure("provider_input_limit")
        # One inference attempt; no redirects or automatic retries.
        result = self.send(payload, timeout_seconds=30, max_retries=0)
        if not isinstance(result, dict) or result.get("status") != "completed":
            raise ProviderFailure("provider_incomplete")
        if result.get("model") != self.policy.model:
            raise ProviderFailure("provider_response_invalid")
        usage = result.get("usage")
        if not isinstance(usage, dict) or any(type(usage.get(k)) is not int for k in ("input_tokens", "output_tokens")):
            raise ProviderFailure("provider_response_invalid")
        if not 0 <= usage["input_tokens"] <= INPUT_LIMIT or not 0 <= usage["output_tokens"] <= OUTPUT_LIMIT:
            raise ProviderFailure("provider_response_invalid")
        output = result.get("output")
        if not isinstance(output, list) or not output:
            raise ProviderFailure("provider_response_invalid")
        parts = []
        for item in output:
            if not isinstance(item, dict) or item.get("type") != "message" or item.get("role") != "assistant" or item.get("status") != "completed":
                raise ProviderFailure("provider_response_invalid")
            content = item.get("content")
            if not isinstance(content, list) or not content:
                raise ProviderFailure("provider_response_invalid")
            for part in content:
                if not isinstance(part, dict) or part.get("type") != "output_text" or not isinstance(part.get("text"), str):
                    raise ProviderFailure("provider_response_invalid")
                parts.append(part["text"])
        text = "\n".join(parts)
        if not text or len(text) > 20_000:
            raise ProviderFailure("provider_response_invalid")
        return text


def budget_day(now: int) -> str:
    return datetime.fromtimestamp(now, timezone(timedelta(hours=9))).date().isoformat()


class OpenAITransport:
    """Explicitly constructed only; no environment discovery or startup activation.

    Fixed TLS origin, no proxies, redirects, retries, or response-body logging.
    Each socket operation is bounded; the body also has a monotonic deadline.
    DNS resolution remains subject to the host resolver timeout.
    """
    def __init__(self, api_key: str):
        if not isinstance(api_key, str) or not api_key or any(c.isspace() for c in api_key):
            raise ProviderFailure("provider_credentials_invalid")
        self._api_key = api_key

    def _post(self, path: str, payload: dict, timeout_seconds: int = 30) -> dict:
        connection = http.client.HTTPSConnection("api.openai.com", timeout=timeout_seconds)
        deadline = time.monotonic() + timeout_seconds
        try:
            connection.request("POST", path, json.dumps(payload).encode("utf-8"),
                               {"Authorization": "Bearer " + self._api_key,
                                "Content-Type": "application/json"})
            response = connection.getresponse()
            if response.status != 200:
                raise ProviderFailure("provider_transport_failed")
            chunks, size = [], 0
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ProviderFailure("provider_transport_failed")
                if connection.sock is not None:
                    connection.sock.settimeout(remaining)
                chunk = response.read1(min(8192, 262145 - size))
                if not chunk:
                    break
                chunks.append(chunk)
                size += len(chunk)
                if size > 262144:
                    raise ProviderFailure("provider_transport_failed")
            result = json.loads(b"".join(chunks))
            if not isinstance(result, dict):
                raise ProviderFailure("provider_transport_failed")
            return result
        except Exception:
            raise ProviderFailure("provider_transport_failed") from None
        finally:
            connection.close()

    def count_input(self, payload: dict) -> int:
        result = self._post("/v1/responses/input_tokens",
                            {k: payload[k] for k in ("model", "instructions", "input", "tools", "tool_choice", "reasoning")})
        if result.get("object") != "response.input_tokens":
            raise ProviderFailure("provider_input_count_invalid")
        return result.get("input_tokens")

    def send(self, payload: dict, *, timeout_seconds: int, max_retries: int) -> dict:
        if max_retries != 0 or timeout_seconds != 30:
            raise ProviderFailure("provider_transport_policy_invalid")
        return self._post("/v1/responses", payload, timeout_seconds)
