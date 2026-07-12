"""MCP 도구 필터링 — 읽기 + trash 도구만 노출 (Issue #3).

에이전트에 로드할 Gmail 도구를 **allowlist** 방식으로 좁힌다. 서드파티 MCP 서버가
영구 삭제 도구를 함께 노출하더라도, 여기서 걸러 에이전트 도구 목록에 등록하지 않는다.
이는 NFR-1.2(도구 필터링)이자 NFR-1.3(스코프 제한과 함께 작동하는 이중 방어)의 한 축이다.

도구명은 shinzo-labs/gmail-mcp 소스에서 확인한 실제 등록명을 따른다.
- 검색: `list_messages` (Gmail 검색 문법 `q` 파라미터 지원 — FR-1.1/1.2)
- 조회: `get_message` (개별 메일 상세 — FR-1.3)
- 휴지통: `trash_message` (FR-2), 복원: `untrash_message` (백로그 untrash)
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol


class _Named(Protocol):
    """`filter_gmail_tools` 가 요구하는 최소 계약 — 이름을 가진 도구."""

    name: str


# 에이전트에 노출을 허용하는 도구 (읽기 + 휴지통 이동/복원).
ALLOWED_TOOLS: frozenset[str] = frozenset(
    {
        "list_messages",
        "get_message",
        "trash_message",
        "untrash_message",
    }
)

# 이 중 하나라도 서버 응답에 없으면 삭제·조회 기본 기능이 성립하지 않으므로 fail-fast.
# (untrash_message 는 복원용 선택 도구라 필수에서 제외한다.)
REQUIRED_TOOLS: frozenset[str] = frozenset(
    {
        "list_messages",
        "get_message",
        "trash_message",
    }
)

# 절대 에이전트에 로드되어서는 안 되는 영구 삭제 계열 (방어적 재확인용).
# allowlist 로 이미 배제되지만, 서버가 새 삭제 도구를 추가하거나 allowlist 를
# 잘못 수정한 경우를 대비해 결과에 이들이 없음을 이중으로 assert 한다. (NFR-1.2/1.3, FR-2.4)
PERMANENT_DELETE_TOOLS: frozenset[str] = frozenset(
    {
        "delete_message",
        "batch_delete_messages",
        "delete_thread",
    }
)


class ToolFilterError(RuntimeError):
    """MCP 서버의 도구 목록이 기대와 다를 때 발생 (스키마 변경 등)."""


def filter_gmail_tools(tools: Iterable[_Named]) -> list[_Named]:
    """MCP 서버 도구 목록을 읽기 + trash 도구만 남기도록 필터링한다.

    Args:
        tools: MCP 서버에서 로드한 도구들 (`name` 속성을 가진 객체).

    Returns:
        `ALLOWED_TOOLS` 에 속한 도구만 담은 새 리스트.

    Raises:
        ToolFilterError: 필수 도구(`REQUIRED_TOOLS`)가 서버 응답에 없을 때.
            서드파티 서버의 스키마 변경을 조기에 감지하기 위한 fail-fast 다.
    """

    by_name = {tool.name: tool for tool in tools}

    missing_required = REQUIRED_TOOLS - by_name.keys()
    if missing_required:
        raise ToolFilterError(
            "MCP 서버에서 기대한 필수 도구를 찾지 못했습니다: "
            f"{sorted(missing_required)}. 서버 버전/스키마를 확인하세요."
        )

    filtered = [tool for name, tool in by_name.items() if name in ALLOWED_TOOLS]

    # 이중 방어: 필터 결과에 영구 삭제 도구가 절대 남지 않았음을 재확인한다.
    leaked = PERMANENT_DELETE_TOOLS & {tool.name for tool in filtered}
    if leaked:  # pragma: no cover - allowlist 상 도달 불가, 회귀 방지용 안전망
        raise ToolFilterError(
            f"영구 삭제 도구가 필터를 통과했습니다: {sorted(leaked)}. "
            "ALLOWED_TOOLS/PERMANENT_DELETE_TOOLS 구성을 점검하세요."
        )

    return filtered
