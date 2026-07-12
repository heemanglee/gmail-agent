"""Gmail 도구 연결 CLI의 에이전트 준비 경로 검증."""

import asyncio

from langchain_core.messages import AIMessage

from app.agent import cli


def test_run_repl_awaits_gmail_agent_builder(monkeypatch, capsys):
    """CLI는 비동기 MCP 도구를 위해 agent.ainvoke()를 사용한다."""

    built = False
    calls = []

    class AsyncOnlyAgent:
        async def ainvoke(self, input, config):
            calls.append((input, config))
            return {"messages": [AIMessage(content="비동기 응답")]}

    async def build_gmail_agent():
        nonlocal built
        built = True
        return AsyncOnlyAgent()

    monkeypatch.setattr(cli, "build_gmail_agent", build_gmail_agent, raising=False)
    monkeypatch.setattr(cli, "build_agent", lambda: object(), raising=False)
    answers = iter(["안녕", "exit"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    asyncio.run(cli.run_repl(thread_id="t-cli"))

    assert built is True
    assert calls == [
        (
            {"messages": [("user", "안녕")]},
            {"configurable": {"thread_id": "t-cli"}},
        )
    ]
    output = capsys.readouterr().out
    assert "thread=t-cli" in output
    assert "비동기 응답" in output
