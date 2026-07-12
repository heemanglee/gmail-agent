"""LangGraph 에이전트 계층.

`create_agent` 로 ChatOpenAI 기반 에이전트를 구성하고, trash 도구에 대해서만
`HumanInTheLoopMiddleware` 로 승인 게이팅을 적용한다. (PRD §4, FR-3)
"""
