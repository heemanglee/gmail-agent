"""Gmail MCP 연동 계층.

`MultiServerMCPClient`(Streamable HTTP)로 Gmail MCP 서버에 연결하고, MCP 도구를
LangChain 도구로 변환한다. 읽기 + trash 도구만 로드하고 영구 삭제 도구는
제외한다. (PRD §3, NFR-1.2)
"""
