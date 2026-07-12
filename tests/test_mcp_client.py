"""Gmail MCP 연결 구성·자격증명 해석 검증 (Issue #3).

`build_connections` / `_resolve_credentials` 는 순수 로직이므로 네트워크·실서버 없이
검증한다. 실제 도구 로딩(`load_gmail_tools`)은 MCP 어댑터·서버가 필요하므로
여기서 다루지 않는다 (Phase 7 스모크로 확인).
"""

import json

import pytest

from app.core.config import Settings
from app.mcp.client import CredentialError, _resolve_credentials, build_connections


def _settings(**overrides) -> Settings:
    """`.env` 영향을 배제하고 필수값을 채운 Settings 를 만든다."""

    base = {
        "OPENAI_API_KEY": "test-key",
        "DATABASE_URL": "postgresql://t:t@localhost:5432/t",
    }
    base.update(overrides)
    return Settings(_env_file=None, **base)


def _write_token(tmp_path, **fields):
    token = {
        "client_id": "tok-id",
        "client_secret": "tok-secret",
        "refresh_token": "tok-refresh",
        "scopes": ["https://www.googleapis.com/auth/gmail.modify"],
    }
    token.update(fields)
    path = tmp_path / "token.json"
    path.write_text(json.dumps(token), encoding="utf-8")
    return path


def test_stdio_connection_uses_pinned_package_and_token_credentials(tmp_path):
    token = _write_token(tmp_path)
    cfg = _settings(GMAIL_MCP_TRANSPORT="stdio", GMAIL_TOKEN_PATH=str(token))

    conns = build_connections(cfg)
    gmail = conns["gmail"]

    assert gmail["transport"] == "stdio"
    assert gmail["command"] == "npx"
    # 버전 고정된 패키지가 실행 대상이어야 한다 (스키마 변경 리스크 대응).
    assert cfg.GMAIL_MCP_PACKAGE in gmail["args"]
    assert "@shinzolabs/gmail-mcp@" in cfg.GMAIL_MCP_PACKAGE
    # token.json 에서 추출한 자격증명이 shinzo-labs env 규격으로 주입된다.
    assert gmail["env"]["CLIENT_ID"] == "tok-id"
    assert gmail["env"]["CLIENT_SECRET"] == "tok-secret"
    assert gmail["env"]["REFRESH_TOKEN"] == "tok-refresh"
    # 프라이버시 기본값: 분석 수집 비활성화.
    assert gmail["env"]["TELEMETRY_ENABLED"] == "false"


def test_explicit_credentials_take_precedence_over_token_file(tmp_path):
    token = _write_token(tmp_path)
    cfg = _settings(
        GMAIL_MCP_TRANSPORT="stdio",
        GMAIL_TOKEN_PATH=str(token),
        GMAIL_CLIENT_ID="env-id",
        GMAIL_CLIENT_SECRET="env-secret",
        GMAIL_REFRESH_TOKEN="env-refresh",
    )

    env = build_connections(cfg)["gmail"]["env"]

    assert env["CLIENT_ID"] == "env-id"
    assert env["CLIENT_SECRET"] == "env-secret"
    assert env["REFRESH_TOKEN"] == "env-refresh"


def test_streamable_http_connection_shape():
    cfg = _settings(
        GMAIL_MCP_TRANSPORT="streamable_http",
        GMAIL_MCP_SERVER_URL="http://gmail-mcp.internal:3000/mcp",
    )

    gmail = build_connections(cfg)["gmail"]

    assert gmail["transport"] == "streamable_http"
    assert gmail["url"] == "http://gmail-mcp.internal:3000/mcp"
    # HTTP 모드에선 자격증명을 우리 앱이 주입하지 않는다(서버가 보유).
    assert "env" not in gmail


def test_missing_credentials_raises(tmp_path):
    # token.json 도 없고 명시 자격증명도 없으면 명확히 실패해야 한다.
    cfg = _settings(
        GMAIL_MCP_TRANSPORT="stdio",
        GMAIL_TOKEN_PATH=str(tmp_path / "nonexistent.json"),
    )

    with pytest.raises(CredentialError):
        _resolve_credentials(cfg)


def test_streamable_http_requires_url():
    # transport 검증: URL 없이 streamable_http 는 설정 단계에서 막힌다.
    with pytest.raises(Exception) as exc:
        _settings(GMAIL_MCP_TRANSPORT="streamable_http")

    assert "GMAIL_MCP_SERVER_URL" in str(exc.value)
