# Step 4 MCP 도구 바인딩 구현 계획

> **에이전트 작업자용:** 이 계획을 작업 단위로 실행할 때 `superpowers:subagent-driven-development`(권장) 또는 `superpowers:executing-plans` 하위 스킬을 사용해야 한다. 진행 상태는 체크박스로 기록한다.

**목표:** Issue #4를 완료하기 위해 allowlist 처리된 Gmail MCP 도구를 LangGraph 에이전트에 로드하여, 자연어 요청이 도구 호출과 최종 응답 생성까지 이어지게 한다.

**아키텍처:** `build_agent()`는 `ChatOpenAI` 생성, 기존 시스템 프롬프트 적용, `InMemorySaver` 구성만 담당하는 동기식·의존성 주입 가능 조립 함수로 유지한다. 새 비동기 조립 함수가 `load_gmail_tools()`에서 이미 필터링된 도구를 받아 `build_agent()`로 전달하고, CLI는 REPL 시작 전에 이 함수를 호출한다. 따라서 기존 순수 LLM·thread 상태 테스트는 보존하면서 정상 실행 경로에만 MCP 도구를 연결한다.

**기술 스택:** Python 3.12, LangChain v1 `create_agent`, LangGraph v1 `InMemorySaver`, `langchain-mcp-adapters`, pytest, uv.

## 전역 제약

- `app/agent/builder.py`에 구현된 `ChatOpenAI` 생성, `create_agent(...)`, `SYSTEM_PROMPT`, `InMemorySaver`, `thread_id` 구성은 보존한다.
- 도구는 반드시 `app.mcp.client.load_gmail_tools()`로만 가져온다. 이 함수는 Issue #3에서 영구 삭제 도구를 제외하는 allowlist를 적용한다.
- Step 4의 `build_gmail_agent()`와 CLI에는 `list_messages`·`get_message` 읽기 도구만 전달한다. `trash_message`·`untrash_message` 연결은 Human-in-the-Loop 승인이 적용되는 Issue #6 이후에 추가한다.
- `HumanInTheLoopMiddleware`, 승인·거부·재개 처리, 실제 trash 실행, SSE, `PostgresSaver`는 추가하지 않는다. 각각 #6, #7, #8, #10의 범위다.
- 테스트는 OpenAI, Gmail, MCP 서버, OAuth 자격증명에 접속하거나 의존해서는 안 된다.
- 기존 `uv run pytest` 전체 테스트를 계속 통과시킨다.

---

## 확인된 범위 차이

| Issue #4 요구사항 | 현재 상태 | 이 계획의 조치 |
|---|---|---|
| `create_agent` + `ChatOpenAI` | `build_agent()`에 구현됨 | 보존; 중복 구현하지 않음 |
| 프롬프트 인젝션 방어 시스템 프롬프트 | 구현 및 단위 테스트 완료 | 보존; 추가 작업 없음 |
| `InMemorySaver` 체크포인터 | 구현 및 단위 테스트 완료 | 보존; 추가 작업 없음 |
| `thread_id` 상태 관리 | CLI와 단위 테스트에 구현됨 | 보존; REPL당 하나의 ID를 계속 사용 |
| Step 3 MCP 도구 바인딩 | `build_agent(tools=...)`는 받지만, 실행 경로에서 `load_gmail_tools()`를 호출하지 않음 | 비동기 Gmail 에이전트 조립 함수가 도구를 로드한 뒤 읽기 도구만 CLI에 연결 |
| 도구 호출 완료 기준 | 도구를 바인딩한 에이전트 테스트 없음 | 스크립트형 도구 호출 테스트 추가 |

### 작업 1: 비동기 Gmail 에이전트 조립 경계 추가

**파일:**

- 수정: `app/agent/builder.py:29-69`
- 테스트: `tests/test_agent_builder.py`

**인터페이스:**

- 입력: Issue #3의 allowlist 도구를 반환하는 `app.mcp.client.load_gmail_tools() -> Awaitable[list]`
- 출력: `async def build_gmail_agent(*, model: BaseChatModel | None = None, checkpointer: BaseCheckpointSaver | None = None, tool_loader: Callable[[], Awaitable[list]] | None = None) -> CompiledStateGraph`
- 보존: 기존 단위 테스트와 자체 도구 주입 호출자가 쓰는 `build_agent(model=None, checkpointer=None, tools=None) -> CompiledStateGraph`

- [x] **1단계: 실패하는 비동기 조립·도구 호출 테스트 작성**

`tests/test_agent_builder.py`에 다음 import와 도구 호출 가능한 fake 모델을 추가한다.

```python
import asyncio
from langchain_core.tools import tool

from app.agent.builder import build_agent, build_gmail_agent


class ToolCallingFakeModel(RecordingFakeModel):
    _bound_tools: list = PrivateAttr(default_factory=list)

    @property
    def bound_tools(self) -> list:
        return self._bound_tools

    def bind_tools(self, tools, **kwargs):
        self._bound_tools = list(tools)
        return self


@tool
def list_messages(query: str) -> str:
    """Search Gmail messages by query."""
    return f"검색 결과: {query}"


@tool
def trash_message(message_id: str) -> str:
    """Move one message to Gmail trash."""
    return f"휴지통 이동: {message_id}"
```

기존 no-tools 테스트 다음에 아래 테스트를 추가한다.

```python
def test_build_gmail_agent_loads_tools_and_completes_a_tool_call():
    model = ToolCallingFakeModel(
        messages=cycle([
            AIMessage(
                content="",
                tool_calls=[{
                    "name": "list_messages",
                    "args": {"query": "from:alice"},
                    "id": "call-1",
                }],
            ),
            AIMessage(content="Alice에게서 온 메일을 찾았습니다."),
        ])
    )
    loaded = False

    async def load_tools():
        nonlocal loaded
        loaded = True
        return [list_messages, trash_message]

    agent = asyncio.run(
        build_gmail_agent(model=model, tool_loader=load_tools)
    )
    result = agent.invoke(
        {"messages": [("user", "Alice 메일을 찾아줘")]},
        {"configurable": {"thread_id": "t-tools"}},
    )

    assert loaded is True
    assert "tools" in agent.nodes
    assert [tool.name for tool in model.bound_tools] == ["list_messages"]
    assert "trash_message" not in [tool.name for tool in model.bound_tools]
    assert [message.type for message in result["messages"]] == [
        "human", "ai", "tool", "ai"
    ]
    assert result["messages"][-1].content == "Alice에게서 온 메일을 찾았습니다."
```

- [x] **2단계: 새 테스트가 실패하는지 확인**

실행: `uv run pytest tests/test_agent_builder.py::test_build_gmail_agent_loads_tools_and_completes_a_tool_call -q`

기대 결과: `ImportError: cannot import name 'build_gmail_agent' from 'app.agent.builder'`로 테스트 수집 단계에서 실패한다.

- [x] **3단계: 비동기 조립 함수 구현**

`app/agent/builder.py`의 다른 import 근처에 추가한다.

```python
from collections.abc import Awaitable, Callable
```

`build_agent()` 아래에 다음 함수를 추가한다.

```python
async def build_gmail_agent(
    *,
    model: BaseChatModel | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
    tool_loader: Callable[[], Awaitable[list]] | None = None,
) -> CompiledStateGraph:
    """Issue #3의 allowlisted Gmail MCP 도구를 연결한 에이전트를 만든다."""

    if tool_loader is None:
        # 테스트/도구 미사용 경로에서 OAuth 설정을 읽지 않도록 실제 실행 때만 import한다.
        from app.mcp.client import load_gmail_tools

        tool_loader = load_gmail_tools

    tools = await tool_loader()
    read_tools = [
        tool for tool in tools if tool.name in {"list_messages", "get_message"}
    ]

    return build_agent(
        model=model,
        checkpointer=checkpointer,
        tools=read_tools,
    )
```

`build_agent()`의 기본값은 바꾸지 않는다. 기존 no-tools 테스트를 유지하기 위해 `tools or []`도 그대로 둔다.

- [x] **4단계: 에이전트 테스트 통과 확인**

실행: `uv run pytest tests/test_agent_builder.py -q`

기대 결과: 새 `human → ai(tool call) → tool → ai` 실행 흐름을 포함한 모든 agent-builder 테스트가 통과한다.

- [x] **5단계: 조립 경계와 테스트 커밋**

```bash
git add app/agent/builder.py tests/test_agent_builder.py
git commit -m "feat: bind filtered Gmail tools to agent runtime"
```

### 작업 2: 도구 연결 에이전트로 CLI 시작

**파일:**

- 수정: `app/agent/cli.py:1-44`

**인터페이스:**

- 입력: 작업 1의 `await build_gmail_agent()`
- 출력: `async def run_repl(thread_id: str | None = None) -> None`; 모듈 진입점에서 `asyncio.run(run_repl())` 호출
- 보존: REPL 전체에서 `cli-<8 hex chars>` 하나를 생성하고 하나의 `config = {"configurable": {"thread_id": thread_id}}`를 사용

- [x] **1단계: CLI 준비 코드를 도구 연결 빌더 대기로 전환**

`app/agent/cli.py`의 import와 준비 코드를 다음으로 교체한다.

```python
import asyncio
import uuid

from app.agent.builder import build_gmail_agent


async def run_repl(thread_id: str | None = None) -> None:
    """Gmail 도구를 연결한 REPL을 실행한다."""

    agent = await build_gmail_agent()
    thread_id = thread_id or f"cli-{uuid.uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": thread_id}}

    print(f"gmail-agent (thread={thread_id}) — 질문을 입력하세요. 종료: 빈 줄 또는 exit")
```

기존 입력 루프와 `agent.invoke(..., config)`는 변경하지 않는다. 모듈 가드는 다음으로 교체한다.

```python
if __name__ == "__main__":
    asyncio.run(run_repl())
```

모듈·함수 docstring에서 더 이상 사실이 아닌 “도구 없음” 문구를 제거하고, 시작 시 MCP 연결과 Gmail OAuth 설정이 필요함을 명시한다.

- [x] **2단계: 정적 import와 전체 자동 검증**

실행: `uv run python -m compileall app/agent`

기대 결과: `app/agent`가 오류 없이 컴파일된다.

실행: `uv run pytest -q`

기대 결과: 모든 테스트가 통과하며, 테스트는 OpenAI·Gmail·OAuth·MCP 서버를 요구하지 않는다.

- [ ] **3단계: 설정된 자격증명으로 실제 통합 스모크 테스트**

문서화된 `.env`와 로컬 또는 원격 Gmail MCP 서버를 준비한 뒤 실행한다.

```bash
uv run python -m app.agent.cli
```

프롬프트에서 `최근 메일 3개를 보여줘` 같은 읽기 전용 요청을 입력한다. MCP 서버가 시작·연결되고 에이전트가 최종 자연어 응답을 반환하며, 후속 질문에도 시작 줄의 `thread=` 값 하나가 유지되는지 확인한다. Step 4에서는 trash 요청을 제출하지 않는다. 승인 게이팅은 명시적으로 Issue #6 범위다.

- [x] **4단계: CLI 런타임 통합 커밋**

```bash
git add app/agent/cli.py
git commit -m "feat: run CLI with Gmail MCP tools"
```

### 작업 3: 로컬 에이전트 실행 방법 문서화

**파일:**

- 수정: `README.md:60-66`
- 테스트: Task 2의 모듈 진입점과 README 명령이 일치하는지 확인

**인터페이스:**

- 입력: Task 2에서 만든 `python -m app.agent.cli` 모듈 가드
- 출력: 기존 `.env` Gmail MCP/OAuth 설정이 필요함을 밝히는 로컬 실행 명령

- [x] **1단계: README 실행 섹션에 에이전트 명령 추가**

기존 테스트 명령 바로 아래에 추가한다.

```markdown
# Gmail MCP 도구를 연결한 대화형 에이전트 (OAuth/MCP 설정 필요)
uv run python -m app.agent.cli
```

바로 다음 문장을 추가한다.

```markdown
CLI는 실행 중 하나의 `thread_id`를 유지해 후속 질문의 대화 맥락을 보존하며, 로드 가능한 도구는 `app.mcp.filter`의 읽기·trash allowlist로 제한된다.
```

- [x] **2단계: 문서 일관성 검증**

실행: `rg -n "도구 없음|tools=\[\]|python -m app\.agent\.cli|thread_id" README.md app/agent/cli.py app/agent/builder.py`

기대 결과: 사용자에게 보이는 CLI 문구에 `도구 없음`이 없고, README 명령은 모듈 가드와 정확히 일치한다. `tools=[]`는 보존된 범용 no-tool 빌더 경로를 설명하는 소스 문서·테스트에만 존재한다.

- [x] **3단계: 전체 검증 재실행**

실행: `uv run pytest -q && uv run python -m compileall app/agent`

기대 결과: 전체 테스트가 통과하고 컴파일 명령의 종료 상태가 0이다.

- [x] **4단계: 로컬 실행 문서 커밋**

```bash
git add README.md
git commit -m "docs: document Gmail agent CLI"
```

## 계획 자체 검토

- **요구사항 범위:** 아직 미완료인 Issue #4 항목은 MCP 도구 바인딩뿐이다. 작업 1이 기존 필터 로더를 연결하고 `list_messages`·`get_message`만 골라 실제 LangGraph 도구 호출 주기를 검증하며, 기존 구현은 유지한다. 작업 2는 이를 기본 CLI 실행 경로로 만들고, 작업 3은 개발자가 실행할 수 있게 문서화한다.
- **의도적 제외:** Gmail 읽기 기능의 세부 동작은 Issue #5, trash 승인·재개는 #6, 실제 trash 실행은 #7의 범위다. 따라서 이 계획은 승인되지 않은 삭제 동작을 추가하지 않는다.
- **완결성:** 모든 수정 위치, 테스트 코드, 실행 명령, 기대 결과, 커밋 범위를 구체적으로 기술했다.
- **타입 일관성:** `build_gmail_agent`는 `list`를 반환하는 인자 없는 비동기 `tool_loader`를 받고, `run_repl`은 그래프 호출 전에 해당 함수를 `await`한다.
