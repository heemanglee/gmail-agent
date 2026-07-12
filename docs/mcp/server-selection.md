# Gmail MCP 서버 선정 근거

> 관련: Issue #3, PRD §3·§7.1, NFR-1.1~1.3, FR-2.4
> 채택: **`@shinzolabs/gmail-mcp@1.7.4`**

## 선별 기준

1. **전용 `trash` 도구 노출** — 영구 삭제가 아닌 휴지통 이동(FR-2.1)
2. **Streamable HTTP 전송 지원**(원격) + stdio(로컬 개발) — §7.3
3. **`gmail.modify` 스코프 호환** — NFR-1.1
4. **버전 고정 가능** + 유지보수/라이선스 건전성

## 후보 비교 (소스 코드 직접 검증)

| 항목 | **shinzo-labs/gmail-mcp** ✅ | GongRzhe/Gmail-MCP-Server ❌ | taylorwilsdon/google_workspace_mcp ❌ |
|---|---|---|---|
| Stars / 언어 / 라이선스 | 56 / JS(Node) / MIT | 1,157 / JS / MIT | 2,835 / Python / MIT |
| 최근 갱신 | 2025-11 | 2025-08 (정체) | 2026-07 (활발) |
| **전용 trash 도구** | `trash_message`(→`users.messages.trash`) **+ `untrash_message`** | **없음** — `delete_email`/`batch_delete_emails`가 `users.messages.delete`(영구삭제) | 없음(`modify_..._labels`로 TRASH 우회만) |
| 읽기 도구 | `list_messages`(Gmail `q` 문법), `get_message` | search/read 있음 | search/get 있음 |
| Streamable HTTP | ✅ `PORT`(기본 3000) + stdio | 불명확(stdio 중심) | ✅ (권장 모드) |
| 스코프 | `gmail.modify` 포함 | `gmail.modify`+settings | 누적 레벨제 — `gmail.modify` 단일 매핑 불가 |
| 배포 아티팩트 | `@shinzolabs/gmail-mcp@1.7.4` | `@gongrzhe/...@1.1.11` | `workspace-mcp` |

### 탈락 사유

- **GongRzhe**(최다 인기): `delete_email`이 `gmail.users.messages.delete`(**영구삭제**)이고 전용 trash 도구가 **없음**. PRD가 금지한 영구삭제 계열만 노출 → 부적합.
- **google_workspace_mcp**(최다 활성): 전용 trash 도구 없이 라벨 조작으로 우회하며, 스코프가 `readonly/organize/.../full` 누적 레벨제라 NFR-1.1의 `gmail.modify` 단일 스코프에 깔끔히 매핑되지 않음. 워크스페이스 전체 오버스펙 → 부적합.

## 채택 서버 상세 (소스 검증 결과)

`src/index.ts` 에서 확인한 실제 도구 등록명 기준:

- **에이전트에 노출(allowlist)**: `list_messages`, `get_message`, `trash_message`, `untrash_message`
- **차단(영구삭제 벡터)**: `delete_message`, `batch_delete_messages`, `delete_thread`
- 그 외 `send_message`, 라벨/필터/설정/위임 등 다수 도구는 범위 밖으로 미노출

`list_messages` 는 `q` 파라미터로 Gmail 검색창 문법(from:, subject:, after: 등)을 지원하여 FR-1.1/1.2 를 충족한다.

## 통합 방식

### 자격증명

shinzo-labs 서버는 `CLIENT_ID`/`CLIENT_SECRET`/`REFRESH_TOKEN` env 를 읽는다.
Step 2에서 발급한 `token.json`(gmail.modify)에 세 값이 모두 들어 있으므로, 대화형
`npx @shinzolabs/gmail-mcp auth` 재실행 없이 그대로 매핑해 주입한다.

- **로컬 개발**: `token.json` 에서 자동 추출 (`app/mcp/client.py::_resolve_credentials`)
- **프로덕션/ECS**: `GMAIL_CLIENT_ID/SECRET/REFRESH_TOKEN` 을 Secrets Manager/SSM 으로 명시 주입(토큰 파일 미배포)

### 스코프 이중 방어 (NFR-1.3)

서버 기본 요청 스코프(`src/oauth2.ts`)는 넓지만(`gmail.modify`/`compose`/`send`/`settings.*`),
우리가 주입하는 refresh_token 은 **gmail.modify 단일 스코프**로 발급된 것이라, send/settings
계열 호출은 Gmail API 가 403 을 반환한다. 즉 (a) 도구 필터링으로 호출 자체를 배제하고,
(b) 스코프 부족으로 API 가 거부하는 이중 방어가 성립한다.

필요 시 서버의 `src/oauth2.ts` SCOPES 를 `gmail.modify` 만으로 좁혀 재빌드하면 동의 화면까지
최소화할 수 있으나, 현재는 gmail.modify 토큰 주입만으로 충분하다.

## 버전 고정 근거

서드파티 서버의 스키마 변경은 도구 연동 중단으로 이어질 수 있다(PRD 리스크 표). 따라서
`GMAIL_MCP_PACKAGE=@shinzolabs/gmail-mcp@1.7.4` 로 버전을 고정하고, `filter_gmail_tools`
가 필수 도구 누락 시 fail-fast 하도록 하여 스키마 변경을 조기에 감지한다.

## 프로덕션 배포 토폴로지 (참고)

ECS Fargate 기준 권장안:

- **옵션 A(사이드카, 권장)**: FastAPI 컨테이너와 Gmail MCP 컨테이너를 같은 Task 에 두고
  `localhost` 로 통신. 서비스 디스커버리 불필요, 지연·비용 최소. 단일 계정 전제와 부합.
- **옵션 B(별도 서비스)**: MCP 를 자체 ECS Service 로 분리하고 Service Connect/Cloud Map 으로
  연결. 독립 스케일·공유가 필요해질 때 전환.

## 참고

- shinzo-labs/gmail-mcp (`src/index.ts`, `src/oauth2.ts`) — 도구명·스코프 검증
- GongRzhe/Gmail-MCP-Server (`src/index.ts`) — delete_email 영구삭제 확인
- taylorwilsdon/google_workspace_mcp (README) — 스코프 레벨제·trash 부재 확인
