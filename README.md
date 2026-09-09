# Claude/Codex Session PIP

화면 구석에 항상 떠 있는 **반투명 위젯**으로 **Claude와 Codex 사용 한도**가 얼마나 남았는지 보여줍니다.
Claude는 Claude Code의 `/usage` 가 쓰는 것과 **동일한 서버 값**, Codex는 **로컬 세션 기록**을 사용합니다.
덤으로 위젯 주변을 기웃거리는 요정 컴패니언 🧚 이 있습니다.

> A tiny always-on-top, semi-transparent desktop widget (Windows) that shows how much of your
> **Claude & Codex** usage limits are left — with a little fairy sprite companion.

---

## 무엇을 보여주나

| 항목 | 표시 | 출처 |
|------|------|------|
| **Claude 5시간** | 5시간 블록 남은 % + 리셋까지 시간 | `GET api.anthropic.com/api/oauth/usage` (`/usage` 와 동일) |
| **Claude 주간** | 7일 한도 남은 % + 리셋까지 시간 | 〃 |
| **Codex** | 한도 남은 % + 리셋까지 시간 + 데이터 기준 시각 | `~/.codex/sessions/**.jsonl` 의 `rate_limits` (로컬, 네트워크 호출 없음) |

- 헤더의 **Claude / Codex 탭 클릭** 또는 **우클릭 → 표시(Claude/Codex/둘 다)** 로 전환
- 상태 점 색: 정상(초록) / 주의(노랑, 70%+ 사용) / 위험(빨강, 90%+ 사용)
- Codex 값은 "마지막으로 Codex를 쓴 시점" 기준이라 `13:35 기준` 처럼 시각을 함께 표시

---

## 요구 사항

- **Windows** 10/11 (둥근 모서리는 Windows 11에서만)
- **Python 3.x** — [python.org](https://www.python.org/downloads/) 설치 시 **"Add Python to PATH" 체크**
  (표준 라이브러리 `tkinter`, `urllib` 만 사용 — 추가 설치 필요 없음)
- **Claude Code 로그인 상태** — 토큰을 `~/.claude/.credentials.json` 에서 읽습니다
- (선택) **Codex CLI** — 쓴 적이 있으면 자동으로 사용량이 잡힙니다

---

## 설치 & 실행

1. 이 저장소를 다운로드 (초록색 **Code → Download ZIP**) 후 압축 해제, 또는:
   ```bash
   git clone https://github.com/HoonArtis/usageToken_Pip.git
   ```
2. 폴더 안의 **`install.bat` 을 더블클릭**
   - 바탕화면 아이콘 + 시작프로그램(로그인 시 자동 실행) 등록
   - 위젯 즉시 실행

### 수동 실행 (설치 없이)
- `run.bat` 더블클릭, 또는 터미널에서:
  ```powershell
  pythonw src\pip_widget.py
  ```

---

## 사용법

| 동작 | 방법 |
|------|------|
| 표시 대상 전환 | 헤더 **Claude / Codex 클릭**, 또는 **우클릭 → 표시** 세그먼트 |
| 위치 이동 | 위젯을 **드래그** (위치 자동 저장) |
| 투명도 조절 | 위젯 위에서 **마우스 휠**, 또는 **우클릭 → 슬라이더** (실시간) |
| 요정 켜기/끄기 | **우클릭 → 🧚 요정 표시/숨기기** |
| 새로고침 | **우클릭 → ↻ 지금 새로고침** |
| 종료 | **우클릭 → ✕ 종료** |

요정은 위젯 주변을 걷고, 날고, 뒤에서 고개를 내밀고, 가장자리에 매달립니다. 클릭하면 손을 흔듭니다.

---

## 설정 (`config.json`)

첫 실행 시 저장소 루트에 자동 생성됩니다.

```json
{
  "refresh_seconds": 600,   // 갱신 주기(초). 기본 10분
  "opacity": 0.9,           // 투명도 0.25~1.0
  "pos": [x, y],            // 마지막 위치 (자동 저장)
  "provider": "both",       // claude | codex | both
  "fairy": true             // 요정 컴패니언 표시
}
```

> **왜 10분?** `/api/oauth/usage` 엔드포인트에는 rate-limit 이 있어, 너무 자주 호출하면
> `HTTP 429` 가 납니다. 429 가 나면 자동 백오프하면서 마지막 정상값을 계속 보여줍니다.
> (Codex는 로컬 파일이라 부담 없음)

---

## 제거

- **`uninstall.bat` 더블클릭** — 위젯 종료 + 바로가기 삭제 (소스 폴더는 그대로)

---

## 개인정보 / 보안

- OAuth 토큰은 **로컬 `~/.claude/.credentials.json` 에서만 읽습니다.**
- 토큰은 **Anthropic 공식 API(`api.anthropic.com`) 외 어디로도 전송되지 않습니다.**
- Codex 사용량은 **로컬 파일만 읽으며 아무것도 전송하지 않습니다.**
- `config.json` 은 `.gitignore` 처리되어 저장소에 올라가지 않습니다.

---

## 폴더 구조

```
usageToken_Pip/
├─ run.bat                      ★ 설치 없이 바로 실행
├─ install.bat / uninstall.bat  ★ 설치 / 제거
├─ config.json                  개인 설정 (자동 생성, git 제외)
│
├─ src/                         코드
│  ├─ pip_widget.py             진입점 — 위젯 UI (tkinter)
│  ├─ claude_usage.py           Claude 사용량 (/api/oauth/usage)
│  ├─ codex_usage.py            Codex 사용량 (~/.codex 세션 파일)
│  └─ fairy.py                  요정 컴패니언 (상태머신 애니메이션)
│
├─ assets/fairy/                요정 스프라이트 프레임 (48px PNG)
├─ scripts/                     install.ps1 · uninstall.ps1 (bat이 호출)
└─ tools/extract_fairy.py       스프라이트 시트 → 프레임 추출 (재생성용)
```

## License

MIT
