"""앱 진입점.

`app.config.settings` 를 import 하는 순간 `.env` 값이 런타임 1회 로딩된다.
필수 환경변수가 없으면 pydantic 이 fail-fast 로 어떤 값이 누락됐는지 알려준다.
"""

from app.core.config import settings


def main() -> None:
    print(f"gmail-agent 시작 · model={settings.OPENAI_MODEL}")


if __name__ == "__main__":
    main()
