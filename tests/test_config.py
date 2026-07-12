"""`app.core.config` 의 로딩·싱글톤 동작 검증."""

import importlib

import pytest


@pytest.fixture
def config_module(monkeypatch):
    """환경변수를 주입한 상태로 `app.core.config` 를 새로 로딩한다.

    `settings` / `get_settings` 는 프로세스 전역 싱글톤이므로, 각 테스트가
    독립적으로 초기 상태에서 시작하도록 모듈을 reload 하고 캐시를 비운다.
    """

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("GMAIL_MCP_SERVER_URL", "http://localhost:8000/mcp")
    # `.env` 파일이 존재하더라도 테스트가 그 값에 의존하지 않도록 무시시킨다.
    monkeypatch.setenv("OPENAI_MODEL", "test-model")

    import app.core.config as config

    # reload 시 lru_cache 가 새로 만들어지고 모듈 레벨 `settings` 가 재생성되어
    # 캐시와 `settings` 가 동일 인스턴스로 동기화된 상태에서 시작한다.
    config = importlib.reload(config)
    yield config
    config.get_settings.cache_clear()


def test_loads_values_from_environment(config_module):
    settings = config_module.get_settings()

    assert settings.OPENAI_API_KEY == "test-key"
    assert settings.OPENAI_MODEL == "test-model"
    assert settings.GMAIL_MCP_SERVER_URL == "http://localhost:8000/mcp"


def test_database_url_defaults_to_none(config_module, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    config_module.get_settings.cache_clear()

    assert config_module.get_settings().DATABASE_URL is None


def test_get_settings_returns_singleton(config_module):
    first = config_module.get_settings()
    second = config_module.get_settings()

    # 런타임 1회 생성 보장: 두 참조는 동일한 인스턴스여야 한다.
    assert first is second


def test_module_level_settings_is_same_singleton(config_module):
    assert config_module.settings is config_module.get_settings()
