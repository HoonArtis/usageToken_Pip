# Claude Session PIP

화면 구석에 항상 떠 있는 **반투명 위젯**으로 Claude 사용 한도가 얼마나 남았는지 실시간으로 보여줍니다.
Claude Code의 `/usage` 가 쓰는 것과 **동일한 서버 값**(진짜 %)을 사용합니다.

> A tiny always-on-top, semi-transparent desktop widget (Windows) that shows how much of your
> Claude usage limit is left — using the same server data as Claude Code's `/usage`.

---

## 무엇을 보여주나

| 항목 | 표시 |
|------|------|
| **5시간** | 5시간 사용 블록의 남은 % + 리셋까지 남은 시간 |
| **주간** | 7일 한도의 남은 % + 리셋까지 남은 시간 |

- 상태 점 색: 정상(초록) / 주의(노랑, 70%+ 사용) / 위험(빨강, 90%+ 사용)
- 데이터 출처: `GET https://api.anthropic.com/api/oauth/usage` (Claude Code `/usage` 와 동일)

---

## 요구 사항

- **Windows** 10/11
- **Python 3.x** — [python.org](https://www.python.org/downloads/) 설치 시 **"Add Python to PATH" 체크**
  (표준 라이브러리 `tkinter`, `urllib` 만 사용 — 추가 설치 필요 없음)
- **Claude Code 로그인 상태** — 토큰을 `~/.claude/.credentials.json` 에서 읽습니다.
  (Claude Code 를 한 번이라도 로그인해 사용한 적이 있으면 됩니다)

---

## 설치 & 실행

1. 이 저장소를 다운로드 (초록색 **Code → Download ZIP**) 후 압축 해제, 또는:
   ```bash
   git clone https://github.com/b-hyoung/claude-session-pip.git
   ```
2. 폴더 안의 **`install.bat` 을 더블클릭**
   - 바탕화면 아이콘 + 시작프로그램(로그인 시 자동 실행) 등록
   - 위젯 즉시 실행

그게 전부입니다. 화면 **오른쪽 아래**에 위젯이 뜹니다.

### 수동 실행 (설치 없이)
- `run.bat` 더블클릭, 또는 터미널에서:
  ```powershell
  pythonw pip_widget.py
  ```

---

## 사용법

| 동작 | 방법 |
|------|------|
| 위치 이동 | 위젯을 **드래그** (위치 자동 저장) |
| 투명도 조절 | 위젯 위에서 **마우스 휠**, 또는 **우클릭 → 슬라이더** 드래그 (실시간) |
| 지금 이 세션 터미널로 열기 | **우클릭 → 🖥 터미널 열기** (`claude --resume`) |
| 새로고침 | **우클릭 → ↻ 지금 새로고침** |
| 종료 | **우클릭 → ✕ 종료** |

---

## 설정 (`config.json`)

첫 실행 시 자동 생성됩니다. 필요하면 수정 후 위젯을 재실행하세요.

```json
{
  "refresh_seconds": 600,   // 갱신 주기(초). 기본 10분
  "opacity": 0.9,           // 투명도 0.25~1.0
  "pos": [x, y]             // 마지막 위치 (자동 저장)
}
```

> **왜 10분?** `/api/oauth/usage` 엔드포인트에는 rate-limit 이 있어, 너무 자주 호출하면
> `HTTP 429` 가 납니다. 위젯은 기본 10분 간격이며, 429 가 나면 자동으로 백오프(간격을
> 늘림)하면서 마지막 정상값을 계속 보여줍니다.

---

## 제거

- **`uninstall.bat` 더블클릭** — 위젯 종료 + 바로가기 삭제 (소스 폴더는 그대로)

---

## 개인정보 / 보안

- OAuth 토큰은 **로컬 `~/.claude/.credentials.json` 에서만 읽습니다.**
- 토큰은 **Anthropic 공식 API(`api.anthropic.com`) 외 어디로도 전송되지 않습니다.**
- 저장소/코드에 토큰이나 개인정보가 포함되지 않습니다. (`config.json` 은 `.gitignore` 처리)

---

## 파일 구성

```
pip_widget.py    위젯 본체 (tkinter GUI)
usage_api.py     /api/oauth/usage 호출 + 정규화
install.bat      설치 (바로가기 + 자동실행 등록)
uninstall.bat    제거
run.bat          설치 없이 바로 실행
config.json      개인 설정 (자동 생성)
```

## License

MIT
