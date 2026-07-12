"""MCP 도구 필터링 검증 (Issue #3, NFR-1.2 / NFR-1.3 / FR-2.4).

allowlist 방식으로 읽기 + trash 도구만 통과시키고, 영구 삭제 도구가
에이전트 도구 목록에서 배제됨을 검증한다. 네트워크·실서버 없이 순수 단위 테스트로
`filter_gmail_tools` 의 계약만 확인한다 (기존 test_config·test_agent_builder 패턴 준수).
"""

from dataclasses import dataclass

import pytest

from app.mcp.filter import (
    ALLOWED_TOOLS,
    PERMANENT_DELETE_TOOLS,
    REQUIRED_TOOLS,
    ToolFilterError,
    filter_gmail_tools,
)


@dataclass
class _FakeTool:
    """`.name` 만 갖는 LangChain 도구 대역.

    `filter_gmail_tools` 는 도구 객체의 `name` 속성만 사용하므로,
    실제 `BaseTool` 없이도 필터 계약을 검증할 수 있다.
    """

    name: str


def _tool_names(tools):
    return {t.name for t in tools}


# shinzo-labs/gmail-mcp 가 실제로 노출하는 도구명 일부 (소스 검증 기준).
# 읽기·trash·영구삭제·무관한 라벨 도구를 섞어 현실적인 서버 응답을 흉내낸다.
def _server_tools():
    names = [
        # 읽기
        "list_messages",
        "get_message",
        # trash (휴지통 이동 — 노출 허용)
        "trash_message",
        "untrash_message",
        # 영구 삭제 (반드시 배제)
        "delete_message",
        "batch_delete_messages",
        "delete_thread",
        # 이번 범위 밖 (노출 안 함)
        "send_message",
        "create_label",
        "modify_message",
    ]
    return [_FakeTool(n) for n in names]


def test_only_allowlist_tools_pass():
    """읽기 + trash/untrash 도구만 통과하고 나머지는 모두 제외된다."""

    filtered = filter_gmail_tools(_server_tools())

    assert _tool_names(filtered) == ALLOWED_TOOLS


def test_permanent_delete_tools_are_excluded():
    """영구 삭제 도구가 결과 목록에 존재하지 않는다. (FR-2.4, NFR-1.2)"""

    filtered = filter_gmail_tools(_server_tools())
    names = _tool_names(filtered)

    for dangerous in PERMANENT_DELETE_TOOLS:
        assert dangerous not in names


def test_out_of_scope_tools_are_excluded():
    """send/label/modify 등 범위 밖 도구도 노출되지 않는다."""

    filtered = filter_gmail_tools(_server_tools())
    names = _tool_names(filtered)

    for out in ("send_message", "create_label", "modify_message"):
        assert out not in names


def test_missing_required_tool_fails_fast():
    """필수 도구가 서버 응답에서 빠지면 즉시 예외를 던진다. (스키마 변경 조기 감지)"""

    # trash_message 누락 → 삭제 기능 자체가 불가능하므로 fail-fast.
    tools = [t for t in _server_tools() if t.name != "trash_message"]

    with pytest.raises(ToolFilterError) as exc:
        filter_gmail_tools(tools)

    assert "trash_message" in str(exc.value)


def test_optional_tool_absence_is_tolerated():
    """선택 도구(untrash_message)가 없어도 필터는 정상 동작한다."""

    tools = [t for t in _server_tools() if t.name != "untrash_message"]

    filtered = filter_gmail_tools(tools)
    names = _tool_names(filtered)

    assert "untrash_message" not in names
    assert REQUIRED_TOOLS <= names


def test_required_is_subset_of_allowed():
    """필수 도구 집합은 허용 집합의 부분집합이어야 한다 (구성 정합성)."""

    assert REQUIRED_TOOLS <= ALLOWED_TOOLS
    # 허용 집합과 영구삭제 집합은 절대 겹치지 않는다.
    assert ALLOWED_TOOLS.isdisjoint(PERMANENT_DELETE_TOOLS)
