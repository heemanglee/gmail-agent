"""읽기 전용 Gmail MCP 도구를 연결한 에이전트 CLI (Issue #4).

프로세스 실행 동안 하나의 `thread_id` 를 유지하는 간단한 REPL이다. 실제
`ChatOpenAI` 호출과 Gmail MCP 연결을 수행하므로 `.env`의 OpenAI·Gmail OAuth·MCP
설정이 필요하다. 이 단계에서 에이전트에는 읽기 도구만 바인딩된다.

실행:
    uv run python -m app.agent.cli
"""

import asyncio
import uuid

from app.agent.builder import build_gmail_agent


async def run_repl(thread_id: str | None = None) -> None:
    """표준 입력으로 질문을 받아 에이전트 응답을 출력하는 REPL 을 실행한다.

    빈 줄 또는 `exit`/`quit` 입력, EOF(Ctrl-D) 시 종료한다. 하나의
    `thread_id` 를 유지하므로 이어지는 질문은 이전 맥락을 참조한다.
    """

    agent = await build_gmail_agent()
    thread_id = thread_id or f"cli-{uuid.uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": thread_id}}

    print(f"gmail-agent (thread={thread_id}) — 질문을 입력하세요. 종료: 빈 줄 또는 exit")
    while True:
        try:
            question = input("\n> ").strip()
        except EOFError:
            print()
            break
        if question in ("", "exit", "quit"):
            break

        result = await agent.ainvoke({"messages": [("user", question)]}, config)
        print(result["messages"][-1].content)


if __name__ == "__main__":
    asyncio.run(run_repl())
