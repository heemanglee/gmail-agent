"""Gmail 도구 연결 CLI의 에이전트 준비 경로 검증."""

import asyncio

from app.agent import cli


def test_run_repl_awaits_gmail_agent_builder(monkeypatch, capsys):
    """CLI는 thread ID를 유지한 채 비동기 Gmail 에이전트를 준비한다."""

    built = False

    async def build_gmail_agent():
        nonlocal built
        built = True
        return object()

    monkeypatch.setattr(cli, "build_gmail_agent", build_gmail_agent, raising=False)
    monkeypatch.setattr(cli, "build_agent", lambda: object(), raising=False)
    monkeypatch.setattr("builtins.input", lambda _: "exit")

    asyncio.run(cli.run_repl(thread_id="t-cli"))

    assert built is True
    assert "thread=t-cli" in capsys.readouterr().out
