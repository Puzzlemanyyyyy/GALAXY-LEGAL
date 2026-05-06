"""Unit tests for the Drive integration service.

Mocks tokeninfo + Drive API HTTP calls to verify:
  1. validate_access_token: aud mismatch → DriveTokenError(TOKEN_VALIDATION_FAILED)
  2. validate_access_token: scope missing → DriveTokenError(TOKEN_VALIDATION_FAILED)
  3. validate_access_token: missing GOOGLE_CLIENT_ID → DriveTokenError(DRIVE_NOT_CONFIGURED)
  4. download_drive_file: google-native doc uses /export?mimeType=...
  5. download_drive_file: binary uses ?alt=media
  6. download_drive_file: 401 from Drive → DriveTokenError(DRIVE_TOKEN_EXPIRED)
"""
from __future__ import annotations

import json
import pytest
import httpx
from unittest.mock import patch

from services.drive import (
    DriveTokenError,
    download_drive_file,
    validate_access_token,
    GOOGLE_NATIVE_EXPORT,
)
from config import settings


@pytest.fixture
def with_client_id(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "test-client.apps.googleusercontent.com", raising=False)


def _resp(status_code: int, json_data: dict | None = None, content: bytes = b"") -> httpx.Response:
    body = content
    headers = {}
    if json_data is not None:
        body = json.dumps(json_data).encode()
        headers = {"content-type": "application/json"}
    req = httpx.Request("GET", "https://example.com")
    return httpx.Response(status_code, request=req, content=body, headers=headers)


def _make_fake_get(captured: dict, response: httpx.Response):
    """Return a coroutine that mimics AsyncClient.get(self, url, **kw)."""
    async def fake(_self, url, **kwargs):  # noqa: ANN001
        captured["url"] = url
        captured["params"] = kwargs.get("params")
        captured["headers"] = kwargs.get("headers")
        return response
    return fake


@pytest.mark.asyncio
async def test_validate_token_unconfigured_server(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "", raising=False)
    with pytest.raises(DriveTokenError) as exc:
        await validate_access_token("a" * 30)
    assert exc.value.code == "DRIVE_NOT_CONFIGURED"
    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_validate_token_aud_mismatch(with_client_id):
    """Defense vs confused-deputy attack: token from another OAuth client."""
    captured = {}
    response = _resp(200, {
        "aud": "OTHER-client.apps.googleusercontent.com",
        "scope": "https://www.googleapis.com/auth/drive.file",
    })
    with patch("httpx.AsyncClient.get", new=_make_fake_get(captured, response)):
        with pytest.raises(DriveTokenError) as exc:
            await validate_access_token("a" * 30)
    assert exc.value.code == "TOKEN_VALIDATION_FAILED"
    assert "audience" in str(exc.value).lower()


@pytest.mark.asyncio
async def test_validate_token_scope_missing(with_client_id):
    captured = {}
    response = _resp(200, {
        "aud": "test-client.apps.googleusercontent.com",
        "scope": "https://www.googleapis.com/auth/userinfo.email",  # no drive.file
    })
    with patch("httpx.AsyncClient.get", new=_make_fake_get(captured, response)):
        with pytest.raises(DriveTokenError) as exc:
            await validate_access_token("a" * 30)
    assert exc.value.code == "TOKEN_VALIDATION_FAILED"
    assert "scope" in str(exc.value).lower()


@pytest.mark.asyncio
async def test_validate_token_ok(with_client_id):
    captured = {}
    response = _resp(200, {
        "aud": "test-client.apps.googleusercontent.com",
        "scope": "https://www.googleapis.com/auth/drive.file openid",
        "email": "test@example.com",
    })
    with patch("httpx.AsyncClient.get", new=_make_fake_get(captured, response)):
        info = await validate_access_token("a" * 30)
    assert info["email"] == "test@example.com"


@pytest.mark.asyncio
async def test_download_google_native_uses_export():
    """google-apps.document MUST go through /export?mimeType=docx."""
    captured = {}
    response = _resp(200, content=b"PK\x03\x04 fake docx")
    with patch("httpx.AsyncClient.get", new=_make_fake_get(captured, response)):
        raw, mime, ext = await download_drive_file(
            "tok", "doc-id-abc", "application/vnd.google-apps.document"
        )
    assert "export" in captured["url"]
    expected_mime = GOOGLE_NATIVE_EXPORT["application/vnd.google-apps.document"][0]
    assert captured["params"]["mimeType"] == expected_mime
    assert mime == expected_mime
    assert ext == ".docx"
    assert raw.startswith(b"PK")


@pytest.mark.asyncio
async def test_download_binary_uses_alt_media():
    captured = {}
    response = _resp(200, content=b"%PDF-1.4 fake")
    with patch("httpx.AsyncClient.get", new=_make_fake_get(captured, response)):
        raw, mime, ext = await download_drive_file("tok", "pdf-id", "application/pdf")
    assert captured["params"] == {"alt": "media"}
    assert "/export" not in captured["url"]
    assert ext == ".pdf"
    assert raw == b"%PDF-1.4 fake"


@pytest.mark.asyncio
async def test_download_401_maps_to_token_expired():
    captured = {}
    response = _resp(401)
    with patch("httpx.AsyncClient.get", new=_make_fake_get(captured, response)):
        with pytest.raises(DriveTokenError) as exc:
            await download_drive_file("tok", "id", "application/pdf")
    assert exc.value.code == "DRIVE_TOKEN_EXPIRED"
    assert exc.value.status_code == 403  # surfaced to client as 403 with code
