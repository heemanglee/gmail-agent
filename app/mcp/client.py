"""Gmail MCP 서버 연결 및 도구 로딩 (Issue #3).

`MultiServerMCPClient` 로 shinzo-labs/gmail-mcp 서버에 연결하고, 로드한 도구를
`filter_gmail_tools` 로 좁혀 에이전트에 넘긴다.

transport 두 가지를 지원한다 (PRD §7.3):
- **stdio**(로컬 개발): 우리 앱이 `npx <패키지>` 를 자식 프로세스로 실행하고 표준입출력으로 통신.
- **streamable_http**(원격/프로덕션): 별도로 기동된 MCP 서버에 HTTP 로 연결(사이드카 등).

자격증명은 shinzo-labs 규격의 env(`CLIENT_ID`/`CLIENT_SECRET`/`REFRESH_TOKEN`)로 주입한다.
값은 설정에 명시된 것을 우선 사용하고, 없으면 Step 2 산출물인 로컬 `token.json`
(gmail.modify 토큰)에서 추출한다.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.config import Settings, settings
from app.mcp.filter import filter_gmail_tools


class CredentialError(RuntimeError):
    """Gmail OAuth 자격증명을 구성하지 못했을 때 발생."""


def _resolve_credentials(cfg: Settings) -> dict[str, str]:
    """shinzo-labs 서버에 주입할 OAuth env 값을 해석한다.

    우선순위: 설정에 명시된 값 → 로컬 `token.json`. 셋 모두 확보하지 못하면
    `CredentialError` 를 던진다.

    Returns:
        `{"CLIENT_ID": ..., "CLIENT_SECRET": ..., "REFRESH_TOKEN": ...}`
    """

    client_id = cfg.GMAIL_CLIENT_ID
    client_secret = cfg.GMAIL_CLIENT_SECRET
    refresh_token = cfg.GMAIL_REFRESH_TOKEN

    if not (client_id and client_secret and refresh_token):
        token_path = Path(cfg.GMAIL_TOKEN_PATH)
        if not token_path.exists():
            raise CredentialError(
                "Gmail 자격증명이 없습니다. GMAIL_CLIENT_ID/SECRET/REFRESH_TOKEN 을 "
                f"설정하거나 '{token_path}' (Step 2 산출물)를 준비하세요."
            )
        data = json.loads(token_path.read_text(encoding="utf-8"))
        client_id = client_id or data.get("client_id")
        client_secret = client_secret or data.get("client_secret")
        refresh_token = refresh_token or data.get("refresh_token")

    missing = [
        key
        for key, value in (
            ("CLIENT_ID", client_id),
            ("CLIENT_SECRET", client_secret),
            ("REFRESH_TOKEN", refresh_token),
        )
        if not value
    ]
    if missing:
        raise CredentialError(
            f"Gmail 자격증명 항목이 비어 있습니다: {missing}. "
            "token.json 또는 GMAIL_* 설정을 확인하세요."
        )

    return {
        "CLIENT_ID": client_id,
        "CLIENT_SECRET": client_secret,
        "REFRESH_TOKEN": refresh_token,
    }


def build_connections(cfg: Settings = settings) -> dict[str, dict[str, Any]]:
    """`MultiServerMCPClient` 에 넘길 서버 연결 설정을 구성한다.

    transport 에 따라 stdio(npx 자식 프로세스) 또는 streamable_http(HTTP URL) 형태로
    "gmail" 서버 하나를 정의한다. 향후 Slack 등 다른 MCP 는 이 dict 에 키를 추가하면 된다.
    """

    if cfg.GMAIL_MCP_TRANSPORT == "stdio":
        creds = _resolve_credentials(cfg)
        return {
            "gmail": {
                "command": "npx",
                "args": ["-y", cfg.GMAIL_MCP_PACKAGE],
                # 이 서버는 stdio와 함께 HTTP 보조 서버도 기동한다. MCP 어댑터가 도구
                # 호출마다 새 stdio 세션을 만들므로, OS가 매번 충돌 없는 임시 포트를
                # 배정하도록 한다.
                # 자격증명 + 분석수집 비활성화(프라이버시 기본값).
                "env": {**creds, "PORT": "0", "TELEMETRY_ENABLED": "false"},
                "transport": "stdio",
            }
        }

    # streamable_http: 별도 기동된 서버에 URL 로 연결. 자격증명은 그 서버가 보유한다.
    return {
        "gmail": {
            "url": cfg.GMAIL_MCP_SERVER_URL,
            "transport": "streamable_http",
        }
    }


async def load_gmail_tools(cfg: Settings = settings) -> list:
    """Gmail MCP 서버에서 도구를 로드하고 읽기 + trash 도구만 반환한다.

    영구 삭제 도구는 `filter_gmail_tools` 에서 배제된다 (NFR-1.2/1.3).
    """

    # 지연 임포트: MCP 어댑터 의존성은 실제 로딩 경로에서만 필요하다
    # (설정·필터 단위 테스트는 이 의존성 없이 동작).
    from langchain_mcp_adapters.client import MultiServerMCPClient

    client = MultiServerMCPClient(build_connections(cfg))
    tools = await client.get_tools()
    return filter_gmail_tools(tools)
