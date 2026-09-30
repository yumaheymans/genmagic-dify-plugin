"""The one HTTP client every GenMagic tool uses.

It speaks GenMagic's public REST API (https://genmagic.co/openapi.json): bearer
authentication with the user's GenMagic API key, the credit metering headers every
generation returns (X-Cost-Cents, X-Credits-Remaining, X-Media-Url), and the
OpenAI-style error body ({"error": {"message", "code", ...}}). Each request names this
integration in the X-GenMagic-Client header, so the key owner's usage through Dify can
be told apart from their other API use. Nothing is cached except the public model list.
"""

from __future__ import annotations

import base64
import binascii
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import requests

PLUGIN_VERSION = "0.0.1"
BASE_URL = "https://genmagic.co"
CLIENT_HEADER = f"dify-plugin/{PLUGIN_VERSION}"
USER_AGENT = f"genmagic-dify-plugin/{PLUGIN_VERSION}"

UTM = "utm_source=dify-marketplace&utm_medium=integration&utm_campaign=agent-platforms"
KEY_HINT = f"Create a free GenMagic account and an API key at {BASE_URL}/developers?{UTM}"

# Hosts GenMagic serves generated media from (declared in manifest.yaml network.domains).
MEDIA_HOSTS = ("genmagic.co", "tlwdqzfibvgektzgdfqa.supabase.co")
MAX_MEDIA_BYTES = 60 * 1024 * 1024

# The model list is public catalog data (no credits spent), cached briefly so opening a
# tool's settings does not refetch it for every dropdown.
_MODELS_TTL_S = 300
_models_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}


class GenMagicError(Exception):
    """A GenMagic API error, with the HTTP status and the API's own error code."""

    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message

    def user_message(self) -> str:
        if self.status == 401:
            return f"GenMagic rejected the API key ({self.message}). {KEY_HINT}."
        if self.code == "email_verification_required":
            return "Verify the email address of your GenMagic account first, then try again: https://genmagic.co/verify-email"
        if self.status == 402:
            return f"Your GenMagic balance is too low for this generation ({self.message}). Add credits at {BASE_URL}/pricing?{UTM}."
        if self.status == 429:
            return f"GenMagic rate limit reached ({self.message}). Wait a moment and try again."
        return f"GenMagic error {self.status} ({self.code}): {self.message}"


@dataclass
class Metering:
    """What a call cost and what is left, from GenMagic's response headers (cents)."""

    cost_cents: float | None = None
    balance_cents: float | None = None
    media_url: str | None = None

    @classmethod
    def from_headers(cls, headers: Any) -> Metering:
        def number(name: str) -> float | None:
            raw = headers.get(name)
            try:
                return float(raw) if raw is not None else None
            except ValueError:
                return None

        return cls(
            cost_cents=number("X-Cost-Cents"),
            balance_cents=number("X-Credits-Remaining"),
            media_url=headers.get("X-Media-Url") or None,
        )

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        if self.cost_cents is not None:
            out["cost_usd"] = round(self.cost_cents / 100, 6)
        if self.balance_cents is not None:
            out["balance_usd"] = round(self.balance_cents / 100, 6)
        return out


class GenMagicClient:
    def __init__(self, api_key: str, base_url: str = BASE_URL):
        self.api_key = (api_key or "").strip()
        self.base_url = base_url.rstrip("/")

    # ------------------------------------------------------------------ transport
    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        accept: str = "application/json",
        timeout: float = 120,
    ) -> requests.Response:
        if not self.api_key:
            raise GenMagicError(401, "missing_api_key", "No API key is configured")
        try:
            res = requests.request(
                method,
                f"{self.base_url}{path}",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Accept": accept,
                    "X-GenMagic-Client": CLIENT_HEADER,
                    "User-Agent": USER_AGENT,
                },
                json=json,
                params=params,
                timeout=(10, timeout),
            )
        except requests.Timeout as e:
            raise GenMagicError(504, "timeout", "GenMagic did not answer in time") from e
        except requests.RequestException as e:
            raise GenMagicError(503, "network_error", f"Could not reach GenMagic: {e.__class__.__name__}") from e
        if res.status_code >= 400:
            raise _error_from(res)
        return res

    # ------------------------------------------------------------------ account
    def usage(self) -> dict[str, Any]:
        return self._request("GET", "/api/v1/usage", timeout=20).json()

    # ------------------------------------------------------------------ catalog
    def models(self, category: str) -> list[dict[str, Any]]:
        cached = _models_cache.get(category)
        if cached and time.monotonic() - cached[0] < _MODELS_TTL_S:
            return cached[1]
        data = self._request("GET", "/api/v1/models", params={"category": category}, timeout=30).json().get("data", [])
        models = [m for m in data if isinstance(m, dict) and m.get("id")]
        # Newest first, the order GenMagic's own model library uses.
        models.sort(key=lambda m: (-(m.get("created") or 0), str(m.get("name") or m["id"])))
        _models_cache[category] = (time.monotonic(), models)
        return models

    # ------------------------------------------------------------------ generation
    def text(self, body: dict[str, Any]) -> tuple[dict[str, Any], Metering]:
        res = self._request("POST", "/api/v1/text", json=body, timeout=180)
        return res.json(), Metering.from_headers(res.headers)

    def image(self, body: dict[str, Any]) -> tuple[dict[str, Any], Metering]:
        res = self._request("POST", "/api/v1/images/generations", json=body, timeout=180)
        return res.json(), Metering.from_headers(res.headers)

    def speech(self, body: dict[str, Any]) -> tuple[bytes, str, Metering]:
        res = self._request("POST", "/api/v1/audio/speech", json=body, accept="audio/*", timeout=180)
        return res.content, _mime(res.headers.get("Content-Type"), "audio/mpeg"), Metering.from_headers(res.headers)

    def music(self, body: dict[str, Any]) -> tuple[bytes, str, Metering]:
        res = self._request("POST", "/api/v1/audio/music", json=body, accept="audio/*", timeout=200)
        return res.content, _mime(res.headers.get("Content-Type"), "audio/mpeg"), Metering.from_headers(res.headers)

    def create_video(self, body: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/api/v1/videos", json=body, timeout=60).json()

    def get_video(self, job_id: str) -> tuple[dict[str, Any], Metering]:
        safe_id = requests.utils.quote(job_id, safe="")
        res = self._request("GET", f"/api/v1/videos/{safe_id}", timeout=60)
        return res.json(), Metering.from_headers(res.headers)

    # ------------------------------------------------------------------ media
    def fetch_media(self, url: str) -> tuple[bytes, str] | None:
        """The bytes and MIME type of a generated file, or None when it cannot be fetched.

        A data URL is decoded in place. An https URL is downloaded only from GenMagic's
        own media hosts, never from an arbitrary address.
        """
        if url.startswith("data:"):
            header, _, payload = url.partition(",")
            if ";base64" not in header:
                return None
            try:
                return base64.b64decode(payload, validate=True), header[5:].split(";")[0] or "application/octet-stream"
            except (binascii.Error, ValueError):
                return None
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname not in MEDIA_HOSTS:
            return None
        try:
            with requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=(10, 120), stream=True) as res:
                if res.status_code != 200:
                    return None
                chunks: list[bytes] = []
                size = 0
                for chunk in res.iter_content(chunk_size=256 * 1024):
                    size += len(chunk)
                    if size > MAX_MEDIA_BYTES:
                        return None
                    chunks.append(chunk)
                return b"".join(chunks), _mime(res.headers.get("Content-Type"), "application/octet-stream")
        except requests.RequestException:
            return None


def _mime(content_type: str | None, fallback: str) -> str:
    return (content_type or fallback).split(";")[0].strip() or fallback


def _error_from(res: requests.Response) -> GenMagicError:
    code, message = "http_error", f"HTTP {res.status_code}"
    try:
        err = res.json().get("error")
        if isinstance(err, dict):
            code = str(err.get("code") or code)
            message = str(err.get("message") or message)
    except ValueError:
        pass
    return GenMagicError(res.status_code, code, message)


EXTENSIONS = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
    "image/gif": "gif",
    "image/svg+xml": "svg",
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/ogg": "ogg",
    "audio/aac": "aac",
    "audio/flac": "flac",
    "video/mp4": "mp4",
    "video/webm": "webm",
    "video/quicktime": "mov",
}


def filename_for(stem: str, mime: str) -> str:
    return f"{stem}.{EXTENSIONS.get(mime, 'bin')}"
