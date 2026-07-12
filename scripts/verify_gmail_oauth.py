"""Gmail OAuth 토큰 발급 검증 스크립트 (일회성).

`credentials.json` 으로 `gmail.modify` **단일 스코프** OAuth 동의 플로우를 실행해
`token.json` 을 생성하고, 발급된 스코프가 요구사항(NFR-1.1)을 만족하는지 검증한다.

이 스크립트는 특정 Gmail MCP 서버에 종속되지 않는, 순수 표준 OAuth 검증용이다.
검증이 끝나 MCP 서버를 채택하면, 토큰 발급은 그 서버의 auth 커맨드로 대체한다.

## 실행 방법

프로젝트 의존성을 오염시키지 않도록 uv 의 `--with` 로 일회성 실행한다.
`credentials.json` 이 있는 디렉터리에서 실행해야 한다.

    uv run --with google-auth-oauthlib --with google-api-python-client \
        python scripts/verify_gmail_oauth.py

## 종료 코드

    0  검증 성공 (gmail.modify 발급 + 전체 접근 스코프 없음 + API 호출 성공)
    1  credentials.json 없음
    2  검증 실패 (스코프 불일치 또는 API 호출 실패)
"""

from __future__ import annotations

from pathlib import Path

# gmail.modify 단일 스코프만 요청한다 (NFR-1.1: 읽기 + 휴지통 이동).
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
# 영구 삭제가 가능한 전체 접근 스코프. 발급 결과에 절대 포함되면 안 된다 (§7.2).
FORBIDDEN_SCOPE = "https://mail.google.com/"

CREDENTIALS_FILE = Path("credentials.json")
TOKEN_FILE = Path("token.json")


def main() -> int:
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    if not CREDENTIALS_FILE.exists():
        print(f"[에러] '{CREDENTIALS_FILE}' 를 현재 디렉터리에서 찾을 수 없습니다.")
        print("       Google Cloud 에서 받은 OAuth 클라이언트 JSON 을")
        print(f"       '{CREDENTIALS_FILE.resolve()}' 로 저장한 뒤 다시 실행하세요.")
        return 1

    # 브라우저가 열리며 계정 선택·동의를 거친다. port=0 → 임의의 로컬 콜백 포트 사용.
    flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
    creds = flow.run_local_server(port=0)

    # 토큰 저장 후 소유자 전용 권한으로 제한 (NFR-1.5).
    TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
    TOKEN_FILE.chmod(0o600)
    print(f"\n토큰을 '{TOKEN_FILE}' 에 저장했습니다 (권한 600).")

    granted = set(creds.scopes or [])
    print(f"발급된 스코프: {sorted(granted)}")

    ok = True

    if SCOPES[0] not in granted:
        print(f"[실패] 요구 스코프 '{SCOPES[0]}' 가 발급되지 않았습니다.")
        ok = False

    if FORBIDDEN_SCOPE in granted:
        print(f"[실패] 전체 접근 스코프 '{FORBIDDEN_SCOPE}' 가 포함되었습니다! "
              "OAuth 동의 화면 스코프 설정을 확인하세요.")
        ok = False

    if not creds.refresh_token:
        print("[경고] refresh_token 이 없습니다. 이미 동의한 계정이라면 "
              "myaccount.google.com/connections 에서 앱 권한을 제거한 뒤 재실행하세요.")

    # 실제 접근이 되는지 프로필 조회로 확인한다.
    try:
        service = build("gmail", "v1", credentials=creds)
        profile = service.users().getProfile(userId="me").execute()
        print(f"[성공] 인증 계정: {profile.get('emailAddress')} "
              f"(총 메시지 {profile.get('messagesTotal')}개)")
    except Exception as exc:  # noqa: BLE001 - 검증 스크립트이므로 광범위 캐치
        print(f"[실패] Gmail API 호출 실패: {exc}")
        ok = False

    if ok:
        print("\n✅ 검증 완료 — gmail.modify 스코프로 정상 인증되며 "
              "전체 접근 스코프는 포함되지 않았습니다.")
        return 0

    print("\n❌ 검증 실패 — 위 메시지를 확인하세요.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
