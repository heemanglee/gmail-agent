"""애플리케이션 환경 설정.

`.env` 파일에 정의된 값을 런타임 시점에 **1회** 로딩하여 주입한다.
`Settings`의 필드 이름은 환경변수 키와 1:1로 대응하도록 대문자 상수 컨벤션을 따른다.

`settings` 객체는 `get_settings()`(lru_cache) 를 통해 프로세스 내에서 단 한 번만
생성되는 싱글톤이다. 런타임 시점에 주입된 뒤로는 수정되지 않아야 하므로,
모든 모듈은 개별적으로 `Settings()` 를 생성하지 말고 이 `settings` 객체를 공유한다.
"""

from functools import lru_cache

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

    # --- Gmail MCP 서버 (Streamable HTTP) ---
    GMAIL_MCP_SERVER_URL: str

    # --- 상태 지속성 (PostgresSaver, 프로덕션) ---
    # 개발 환경(InMemorySaver)에서는 설정하지 않아도 되므로 선택값으로 둔다.
    DATABASE_URL: str | None = None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """싱글톤 `Settings` 인스턴스를 반환한다.

    `lru_cache(maxsize=1)` 로 최초 호출 시 단 한 번만 `Settings()` 를 생성하고,
    이후 호출은 동일한 인스턴스를 반환한다. 이를 통해 런타임 시점 1회 주입을 보장한다.
    """

    return Settings()


# 런타임 시점 1회 생성되는 싱글톤. 모듈들은 이 객체를 import 하여 공유한다.
settings = get_settings()
