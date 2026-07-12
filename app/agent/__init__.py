"""LangGraph 에이전트 계층.

`create_agent`로 ChatOpenAI 기반 에이전트를 구성한다. Step 4에서는 읽기 도구만
연결하며, trash 도구의 `HumanInTheLoopMiddleware` 승인 게이팅은 Issue #6에서 적용한다.
"""
