"""질문 응답 전용 최소 에이전트 CLI (Issue #16).

프로세스 실행 동안 하나의 `thread_id` 를 유지하며 멀티턴 대화를 확인하는
간단한 REPL. 실제 `ChatOpenAI` 를 호출하므로 `.env` 의 `OPENAI_API_KEY` 가
필요하다. 도구는 바인딩되지 않으며 순수 LLM 응답만 반환한다.

실행:
    uv run python -m app.agent.cli
"""

import uuid

from app.agent.builder import build_agent


def run_repl(thread_id: str | None = None) -> None:
    """표준 입력으로 질문을 받아 에이전트 응답을 출력하는 REPL 을 실행한다.

    빈 줄 또는 `exit`/`quit` 입력, EOF(Ctrl-D) 시 종료한다. 하나의
    `thread_id` 를 유지하므로 이어지는 질문은 이전 맥락을 참조한다.
    """

    agent = build_agent()
    thread_id = thread_id or f"cli-{uuid.uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": thread_id}}

    print(f"gmail-agent (도구 없음 · thread={thread_id}) — 질문을 입력하세요. 종료: 빈 줄 또는 exit")
    while True:
        try:
            question = input("\n> ").strip()
        except EOFError:
            print()
            break
        if question in ("", "exit", "quit"):
            break

        result = agent.invoke({"messages": [("user", question)]}, config)
        print(result["messages"][-1].content)


if __name__ == "__main__":
    run_repl()
