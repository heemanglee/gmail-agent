"""`app.agent.builder.build_agent` 의 뼈대 동작 검증 (Issue #16).

이 단계의 에이전트는 **도구를 바인딩하지 않고** 순수 LLM 응답만 생성한다.
실제 OpenAI 호출은 하지 않는다 — LLM 은 외부 의존성이므로 fake chat model 로
대체하고, 검증 대상은 어디까지나 **에이전트 배선**(create_agent · checkpointer ·
thread 상태 유지)이다. fake model 은 프레임워크가 무엇을 모델에 넘겼는지
관찰하기 위한 프로브로만 쓴다.
"""

import asyncio
from itertools import cycle

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import tool
from pydantic import PrivateAttr

from app.agent.builder import SYSTEM_PROMPT, build_agent, build_gmail_agent


class RecordingFakeModel(GenericFakeChatModel):
    """호출 시 모델에 넘어온 메시지 배치를 기록하는 fake chat model.

    `received[-1]` 은 가장 최근 호출에서 프레임워크가 모델에 전달한 메시지
    목록이다. 이를 통해 checkpointer 가 이전 턴 상태를 복원해 넘겨주는지를
    관찰한다.
    """

    _received: list = PrivateAttr(default_factory=list)

    @property
    def received(self) -> list:
        return self._received

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self._received.append(list(messages))
        return super()._generate(
            messages, stop=stop, run_manager=run_manager, **kwargs
        )


class ToolCallingFakeModel(RecordingFakeModel):
    """도구 바인딩과 호출 흐름을 검증할 수 있는 fake chat model."""

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
    """Move a Gmail message to trash."""

    return f"휴지통 이동: {message_id}"


def _fake(answer: str = "고정 응답") -> RecordingFakeModel:
    """항상 동일한 텍스트를 반환하는 기록형 fake model 을 만든다."""

    return RecordingFakeModel(messages=cycle([AIMessage(content=answer)]))


def _contents(messages: list) -> list[str]:
    return [getattr(m, "content", "") for m in messages]


def _human_contents(messages: list) -> list[str]:
    return [m.content for m in messages if isinstance(m, HumanMessage)]


def test_responds_to_natural_language_question():
    """자연어 질문을 입력하면 응답 텍스트를 생성한다."""

    agent = build_agent(model=_fake("안녕하세요, 무엇을 도와드릴까요?"))

    result = agent.invoke(
        {"messages": [("user", "안녕")]},
        {"configurable": {"thread_id": "t-basic"}},
    )

    assert result["messages"][-1].content == "안녕하세요, 무엇을 도와드릴까요?"


def test_no_tools_node_in_graph():
    """도구를 바인딩하지 않으므로 그래프에 tools 노드가 없다 (순수 LLM 응답)."""

    agent = build_agent(model=_fake())

    assert "tools" not in agent.nodes


def test_build_gmail_agent_binds_read_tools_and_completes_a_tool_call():
    """Gmail 도구 중 읽기 도구만 바인딩하고 호출 결과로 답변한다."""

    model = ToolCallingFakeModel(
        messages=cycle(
            [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "list_messages",
                            "args": {"query": "from:alice"},
                            "id": "call-1",
                        }
                    ],
                ),
                AIMessage(content="Alice에게서 온 메일을 찾았습니다."),
            ]
        )
    )
    loaded = False

    async def load_tools():
        nonlocal loaded
        loaded = True
        return [list_messages, trash_message]

    agent = asyncio.run(build_gmail_agent(model=model, tool_loader=load_tools))
    result = agent.invoke(
        {"messages": [("user", "Alice 메일을 찾아줘")]},
        {"configurable": {"thread_id": "t-tools"}},
    )

    assert loaded is True
    assert "tools" in agent.nodes
    assert [tool.name for tool in model.bound_tools] == ["list_messages"]
    assert "trash_message" not in [tool.name for tool in model.bound_tools]
    assert [message.type for message in result["messages"]] == [
        "human",
        "ai",
        "tool",
        "ai",
    ]
    assert result["messages"][-1].content == "Alice에게서 온 메일을 찾았습니다."


def test_same_thread_id_preserves_context():
    """동일 thread_id 로 이어 질문하면 이전 턴 발화가 모델 입력에 포함된다."""

    model = _fake()
    agent = build_agent(model=model)
    cfg = {"configurable": {"thread_id": "t-ctx"}}

    agent.invoke({"messages": [("user", "내 이름은 철수야")]}, cfg)
    agent.invoke({"messages": [("user", "내 이름이 뭐야?")]}, cfg)

    # 두 번째 호출 시 모델이 받은 메시지에 첫 턴 발화가 남아 있어야 한다.
    second_turn_inputs = _contents(model.received[-1])
    assert "내 이름은 철수야" in second_turn_inputs
    assert "내 이름이 뭐야?" in second_turn_inputs


def test_different_thread_id_isolates_context():
    """다른 thread_id 는 독립된 상태를 가진다 — 이전 thread 발화가 새지 않는다."""

    model = _fake()
    agent = build_agent(model=model)

    agent.invoke(
        {"messages": [("user", "비밀 메모입니다")]},
        {"configurable": {"thread_id": "t-a"}},
    )
    agent.invoke(
        {"messages": [("user", "안녕")]},
        {"configurable": {"thread_id": "t-b"}},
    )

    # 새 thread(t-b) 의 모델 입력에는 t-a 의 발화가 포함되면 안 된다.
    assert "비밀 메모입니다" not in _human_contents(model.received[-1])


def test_system_prompt_is_wired():
    """시스템 프롬프트가 모델 입력의 SystemMessage 로 주입된다."""

    model = _fake()
    agent = build_agent(model=model)

    agent.invoke(
        {"messages": [("user", "안녕")]},
        {"configurable": {"thread_id": "t-sys"}},
    )

    system_messages = [
        m for m in model.received[-1] if isinstance(m, SystemMessage)
    ]
    assert len(system_messages) == 1
    assert system_messages[0].content == SYSTEM_PROMPT


def test_system_prompt_treats_input_as_untrusted():
    """시스템 프롬프트는 외부 입력을 신뢰하지 않도록 명시한다 (NFR-1.4)."""

    # 프롬프트 인젝션 대비 골격: '신뢰할 수 없는 입력' 취급과
    # 숨은 지시 불이행 방침이 프롬프트에 담겨 있어야 한다.
    assert "신뢰" in SYSTEM_PROMPT
    assert "지시" in SYSTEM_PROMPT
