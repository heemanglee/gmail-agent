"""애플리케이션 환경 설정.

`.env` 파일에 정의된 값을 런타임 시점에 **1회** 로딩하여 주입한다.
`Settings`의 필드 이름은 환경변수 키와 1:1로 대응하도록 대문자 상수 컨벤션을 따른다.

`settings` 객체는 `get_settings()`(lru_cache) 를 통해 프로세스 내에서 단 한 번만
생성되는 싱글톤이다. 런타임 시점에 주입된 뒤로는 수정되지 않아야 하므로,
모든 모듈은 개별적으로 `Settings()` 를 생성하지 말고 이 `settings` 객체를 공유한다.
"""

from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """`.env` 로부터 로딩되는 환경 설정 값.

    필드는 환경변수 키와 동일한 대문자 상수 이름을 사용한다.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # --- LLM (ChatOpenAI) ---
    OPENAI_API_KEY: str
    OPENAI_MODEL: str = "gpt-5-nano"

    # --- Gmail MCP 서버 ---
    # 로컬 개발은 stdio(우리 앱이 npx 로 서버를 자식 프로세스로 실행),
    # 원격/프로덕션은 streamable_http(사이드카/별도 서비스에 HTTP 연결). (PRD §7.3)
    GMAIL_MCP_TRANSPORT: Literal["stdio", "streamable_http"] = "stdio"
    # streamable_http 일 때만 사용. stdio 에서는 불필요하므로 optional.
    GMAIL_MCP_SERVER_URL: str | None = None
    # 버전 고정: 서드파티 서버 스키마 변경 리스크 대응 (Issue #3). stdio 실행 대상.
    GMAIL_MCP_PACKAGE: str = "@shinzolabs/gmail-mcp@1.7.4"

    # --- Gmail OAuth 자격증명 (shinzo-labs 서버에 env 로 주입) ---
    # 명시 주입(프로덕션/ECS Secrets 권장). 셋 다 비어 있으면 client 계층이
    # GMAIL_TOKEN_PATH(로컬 token.json)에서 추출해 보완한다.
    GMAIL_CLIENT_ID: str | None = None
    GMAIL_CLIENT_SECRET: str | None = None
    GMAIL_REFRESH_TOKEN: str | None = None
    # 로컬 개발용 자격증명 fallback 소스 (Step 2 산출물, gmail.modify 토큰).
    GMAIL_TOKEN_PATH: str = "token.json"

    # --- 상태 지속성 (PostgresSaver) ---
    DATABASE_URL: str

    @model_validator(mode="after")
    def _require_url_for_http(self) -> "Settings":
        """streamable_http transport 는 서버 URL 이 반드시 있어야 한다."""

        if self.GMAIL_MCP_TRANSPORT == "streamable_http" and not self.GMAIL_MCP_SERVER_URL:
            raise ValueError(
                "GMAIL_MCP_TRANSPORT=streamable_http 이면 GMAIL_MCP_SERVER_URL 이 필요합니다."
            )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """싱글톤 `Settings` 인스턴스를 반환한다.

    `lru_cache(maxsize=1)` 로 최초 호출 시 단 한 번만 `Settings()` 를 생성하고,
    이후 호출은 동일한 인스턴스를 반환한다. 이를 통해 런타임 시점 1회 주입을 보장한다.
    """

    return Settings()


# 런타임 시점 1회 생성되는 싱글톤. 모듈들은 이 객체를 import 하여 공유한다.
settings = get_settings()
