# Gmail OAuth 자격증명 구성 가이드

Gmail MCP 서버가 Gmail API에 접근하기 위한 OAuth 자격증명을 발급·구성하는 절차. 스코프는 `gmail.modify` **하나만** 발급한다. (PRD NFR-1.1, §7.2)

## 자격증명이 흐르는 구조

이 프로젝트의 앱은 Gmail API를 **직접 호출하지 않는다.** Gmail 접근은 서드파티 Gmail MCP 서버가 담당하며, OAuth 자격증명(`credentials.json` / `token.json`)은 **MCP 서버가 소비한다.**

```
LangGraph Agent
   │  Streamable HTTP  (GMAIL_MCP_SERVER_URL)
   ▼
[Gmail MCP 서버]
   │  OAuth (scope: gmail.modify)   ← credentials.json / token.json 소비
   ▼
[Gmail API]
```

따라서 앱 `.env` 의 `GMAIL_MCP_SERVER_URL` 은 MCP 서버 **주소**일 뿐이고, 아래에서 발급하는 자격증명 파일은 MCP 서버가 실행되는 위치에 둔다.

---

## 1단계 — Google Cloud 프로젝트 & Gmail API 활성화

1. [Google Cloud Console](https://console.cloud.google.com/) 에서 프로젝트 생성 (예: `gmail-agent`)
2. **API 및 서비스 → 라이브러리** → **Gmail API** 검색 후 **사용 설정(Enable)**

## 2단계 — OAuth 동의 화면 (스코프 최소화가 핵심)

**API 및 서비스 → OAuth 동의 화면**

- User Type: 개인 Gmail 계정이면 **External**, Google Workspace면 Internal
- 게시 상태는 **테스트(Testing)** 로 두고, **테스트 사용자**에 본인 Gmail 계정을 추가한다. (심사 없이 즉시 사용 가능)
- 스코프는 **반드시 아래 하나만** 추가한다 (NFR-1.1):

  ```
  https://www.googleapis.com/auth/gmail.modify
  ```

> ⚠️ `https://mail.google.com/` (전체 접근)는 **절대 추가하지 않는다.** 이 스코프가 포함되면 영구 삭제가 가능해지고 Google restricted-scope 심사 대상이 된다. `gmail.modify` 는 읽기 + 휴지통 이동까지만 허용한다. (PRD §7.2)

## 3단계 — OAuth 클라이언트 ID 발급

**API 및 서비스 → 사용자 인증 정보 → 사용자 인증 정보 만들기 → OAuth 클라이언트 ID**

- 애플리케이션 유형: **데스크톱 앱(Desktop app)** 을 권장한다. (MCP 서버가 로컬 콜백으로 토큰을 받는 방식과 호환)
- 생성 후 **JSON 다운로드** → 파일명을 `credentials.json` (또는 `client_secret*.json`)으로 저장한다.

## 4단계 — 토큰 발급 (최초 1회 인증 → refresh token 획득)

`credentials.json` 으로 OAuth 동의 플로우를 1회 실행하면 access token + refresh token 이 담긴 `token.json` 이 생성된다. **구체적 실행 방법은 채택하는 Gmail MCP 서버가 요구하는 방식을 따른다** — 대부분의 서드파티 Gmail MCP 서버는 자체 인증 커맨드(예: `auth` 서브커맨드)를 제공하며, 실행 시 브라우저가 열려 계정 선택 → 동의 → 로컬 콜백으로 토큰이 저장된다.

동의 화면에 표시되는 권한이 **"Gmail 메시지 읽기·작성·전송 및 (영구 삭제를 제외한) 설정 변경"** 수준(= gmail.modify)인지 확인한다. "모든 Gmail 데이터 관리/삭제" 문구가 뜨면 스코프가 잘못 들어간 것이다.

## 5단계 — 자격증명 파일 보호 (NFR-1.5)

`.gitignore` 에 이미 다음이 등록되어 있어 커밋되지 않는다:

```
credentials.json
client_secret*.json
token.json
token.pickle
*.token
```

추가 주의사항:

- iCloud / Dropbox 등 **동기화 폴더 안에 두지 않는다.** (NFR-1.5: "저장소·동기화 폴더 커밋 금지")
- 파일 권한을 좁힌다: `chmod 600 token.json credentials.json`

---

## 검증 방법

발급한 자격증명이 요구사항을 만족하는지 확인하는 일회성 스크립트를 제공한다: [`scripts/verify_gmail_oauth.py`](../../scripts/verify_gmail_oauth.py)

이 스크립트는 특정 MCP 서버에 종속되지 않는 **순수 표준 OAuth 검증용**이다. `credentials.json` 으로 `gmail.modify` 단일 스코프 동의 플로우를 실행해 `token.json` 을 만들고, 스코프·refresh token·실제 API 호출을 자동 점검한다.

### 실행

1. Google Cloud 에서 받은 OAuth 클라이언트 JSON 을 프로젝트 루트에 `credentials.json` 으로 저장한다.
2. 프로젝트 루트에서 실행한다. (프로젝트 의존성을 오염시키지 않도록 uv `--with` 로 일회성 실행)

   ```bash
   uv run --with google-auth-oauthlib --with google-api-python-client \
       python scripts/verify_gmail_oauth.py
   ```

3. 브라우저가 열리면 **테스트 사용자로 등록한 계정**으로 로그인 → 동의한다.

### 성공 예시

```
토큰을 'token.json' 에 저장했습니다 (권한 600).
발급된 스코프: ['https://www.googleapis.com/auth/gmail.modify']
[성공] 인증 계정: you@gmail.com (총 메시지 N개)

✅ 검증 완료 — gmail.modify 스코프로 정상 인증되며 전체 접근 스코프는 포함되지 않았습니다.
```

스크립트가 자동으로 점검하는 항목:

| 점검 항목 | 근거 |
|-----------|------|
| `gmail.modify` 스코프가 발급되었는가 | NFR-1.1 |
| 전체 접근(`https://mail.google.com/`) 스코프가 **없는가** | §7.2 |
| `refresh_token` 이 발급되었는가 (토큰 갱신 가능) | 이슈 #2 완료 기준 |
| 실제 Gmail API 호출이 되는가 (프로필 조회) | 인증 정상 동작 |

> ⚠️ 이 스크립트가 만든 `token.json` 은 **검증용**이다. 실제 Gmail MCP 서버를 채택하면, 서버가 요구하는 토큰 형식·저장 위치가 다를 수 있어 서버의 auth 커맨드로 다시 발급하게 될 수 있다. 이 단계의 목적은 "Google Cloud OAuth 설정이 올바른가"를 서버와 무관하게 확인하는 것이다.

---

## 트러블슈팅

### `403: access_denied` — "앱이 인증 절차를 완료하지 않았습니다"

로그인 계정이 **테스트 사용자로 등록되지 않았을 때** 발생한다. OAuth 앱이 테스트(Testing) 게시 상태면 등록된 테스터만 접근할 수 있다.

- **해결**: Cloud Console → **OAuth 동의 화면 → 대상(Audience) → 테스트 사용자**에 로그인할 Gmail 계정을 추가한다. 등록 후 반영까지 즉시~수 분 걸릴 수 있다.
- 브라우저에서 **테스트 사용자로 등록한 바로 그 계정**으로 로그인하는지 확인한다.
- 앱을 "프로덕션(게시)"으로 바꿀 필요는 없다. 본인 계정만 테스터로 등록해 쓰는 것이 의도된 방식이다.

### `refresh_token` 이 없다는 경고

이미 한 번 동의한 계정은 재인증 시 refresh token 을 다시 주지 않는다.

- **해결**: [Google 계정 → 보안 → 서드파티 액세스](https://myaccount.google.com/connections)에서 해당 앱 권한을 제거한 뒤 스크립트를 재실행한다.

### 동의 화면에 "모든 Gmail 데이터 관리/삭제" 권한이 표시됨

OAuth 동의 화면에 전체 접근 스코프(`https://mail.google.com/`)가 들어간 것이다.

- **해결**: OAuth 동의 화면 스코프 설정에서 해당 스코프를 제거하고 `gmail.modify` 만 남긴다. (§7.2)

### `[에러] 'credentials.json' 를 현재 디렉터리에서 찾을 수 없습니다`

스크립트를 `credentials.json` 이 없는 디렉터리에서 실행했다.

- **해결**: 다운로드한 OAuth 클라이언트 JSON 을 프로젝트 루트에 `credentials.json` 으로 저장한 뒤, 프로젝트 루트에서 실행한다.

---

## 완료 기준 검증 (이슈 #2)

- [ ] `gmail.modify` 스코프로 인증이 완료되고 토큰이 갱신된다 → 동의 화면 권한 문구로 확인
- [ ] 발급 스코프에 `https://mail.google.com/` (전체 접근)가 **포함되지 않음**을 확인한다 → [Google 계정 → 보안 → 서드파티 액세스](https://myaccount.google.com/connections)에서 앱 권한을 직접 점검 (여기에 "삭제" 권한이 없어야 함)

## 참조

- PRD: [NFR-1.1](../PRD.md), NFR-1.5, §7.2
- 관련 이슈: [#2](https://github.com/heemanglee/gmail-agent/issues/2)
