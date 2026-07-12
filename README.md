# gmail-agent

LangGraph 기반 Gmail 읽기·휴지통 이동 챗봇. 삭제는 자동으로 수행하지 않고, 대상 메일을 먼저 제시한 뒤 사용자 승인(Human-in-the-Loop)을 받아 **휴지통 이동으로만** 처리한다.

## 요구사항

- **Python 3.12+** (`langchain-mcp-adapters` 가 3.11+ 요구)
- **[uv](https://docs.astral.sh/uv/)** — 패키지·가상환경 관리

uv 가 없다면 먼저 설치한다.

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
# 또는 Homebrew
brew install uv
```

## 프로젝트 셋업

### 1. 저장소 클론

```bash
git clone https://github.com/heemanglee/gmail-agent.git
cd gmail-agent
```

### 2. 의존성 설치

`uv sync` 는 `.python-version`(3.12)에 맞는 인터프리터를 자동으로 확보하고, `uv.lock` 에 고정된 버전으로 `.venv/` 가상환경을 구성한다.

```bash
uv sync
```

> `.venv/` 는 자동 생성되며 git 에 커밋되지 않는다. 별도로 `activate` 하지 않아도 `uv run` 으로 실행하면 가상환경이 적용된다.

### 3. 환경변수 설정

환경변수는 `.env` 파일에서 **런타임 시점에 1회** 로딩된다 ([app/core/config.py](app/core/config.py)). 템플릿을 복사한 뒤 실제 값을 채운다.

```bash
cp .env.example .env
```

| 환경변수 | 필수 | 설명 |
|----------|------|------|
| `OPENAI_API_KEY` | ✅ | ChatOpenAI API 키 |
| `OPENAI_MODEL` | | LLM 모델명 (기본: `gpt-5-nano`) |
| `GMAIL_MCP_SERVER_URL` | ✅ | Gmail MCP 서버 주소 (Streamable HTTP) |
| `DATABASE_URL` | ✅ | Postgres 체크포인터 접속 URL (`.env` 에서 주입, 소스에 기본값 없음) |

필수 값이 누락되면 앱 시작 시 pydantic 이 어떤 값이 빠졌는지 즉시 알려준다(fail-fast).

> `.env` 및 OAuth credential/token 파일은 git 에 커밋되지 않는다 (NFR-1.5, [.gitignore](.gitignore) 참고).

### 4. Gmail OAuth 자격증명 구성

Gmail 접근은 서드파티 Gmail MCP 서버가 `gmail.modify` **단일 스코프**로 담당한다. Google Cloud OAuth 클라이언트 발급부터 토큰 획득·파일 보호까지의 절차는 별도 가이드를 참고한다.

📄 [docs/mcp/gmail-oauth-setup.md](docs/mcp/gmail-oauth-setup.md)

## 실행 / 테스트

```bash
uv run python main.py   # 진입점 — 설정 로딩 확인
uv run pytest           # 테스트
```

## 프로젝트 구조

```
gmail-agent/
├─ app/
│  ├─ __init__.py
│  ├─ core/              # 공통 인프라 (설정·로깅 등)
│  │  └─ config.py       #   pydantic-settings 기반 설정 (싱글톤)
│  ├─ agent/             # LangGraph 에이전트 (create_agent, HITL 미들웨어)
│  ├─ mcp/               # Gmail MCP 연동 (MultiServerMCPClient, 도구 필터링)
│  └─ server/            # FastAPI 서버 (SSE 스트리밍, thread/resume 관리)
├─ tests/
│  └─ test_config.py     # 설정 로딩·싱글톤 검증
├─ docs/
│  ├─ PRD.md             # 요구사항 문서
│  └─ mcp/
│     └─ gmail-oauth-setup.md  # Gmail OAuth 자격증명 구성 가이드
├─ main.py               # 앱 진입점
├─ .env.example          # 환경변수 템플릿
├─ pyproject.toml        # 프로젝트 메타·의존성
└─ uv.lock               # 의존성 잠금 파일
```
