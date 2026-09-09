"""Claude 사용량 조회 — /usage가 쓰는 서버 엔드포인트를 그대로 호출.

토큰은 매 호출마다 ~/.claude/.credentials.json 에서 새로 읽는다.
(Claude Code가 토큰을 갱신하면 이 파일이 갱신되므로, 우리가 refresh를 구현할 필요가 없다.)
"""
import json
import os
import urllib.request
import urllib.error
from datetime import datetime, timezone

CRED_PATH = os.path.expanduser(r"~\.claude\.credentials.json")
USAGE_URL = "https://api.anthropic.com/api/oauth/usage"


def _read_token():
    with open(CRED_PATH, "r", encoding="utf-8") as f:
        cred = json.load(f)
    o = cred.get("claudeAiOauth", cred)
    return o["accessToken"]


def fetch_raw(timeout=20):
    """엔드포인트 원본 JSON. 실패 시 예외."""
    tok = _read_token()
    req = urllib.request.Request(
        USAGE_URL,
        headers={
            "Authorization": f"Bearer {tok}",
            "Content-Type": "application/json",
            "anthropic-beta": "oauth-2025-04-20",
            "User-Agent": "claude-session-pip/1.0",
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def _fmt_reset(iso):
    """resets_at ISO 문자열 -> 남은 시간 'Xh Ym' (지났으면 'now')."""
    if not iso:
        return None
    try:
        t = datetime.fromisoformat(iso)
    except ValueError:
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    delta = t - datetime.now(timezone.utc)
    secs = int(delta.total_seconds())
    if secs <= 0:
        return "now"
    h, m = secs // 3600, (secs % 3600) // 60
    if h >= 24:
        d = h // 24
        return f"{d}d {h % 24}h"
    if h > 0:
        return f"{h}h {m}m"
    return f"{m}m"


def _severity(util):
    """utilization(사용%) -> 색 구분용 등급."""
    if util is None:
        return "unknown"
    if util >= 90:
        return "critical"
    if util >= 70:
        return "warn"
    return "normal"


def get_usage():
    """GUI가 쓰기 좋은 형태로 정규화.

    반환:
      {"ok": True, "five_hour": {...}, "seven_day": {...}}
      또는 {"ok": False, "error": "...", "kind": "auth|network|other"}
    각 블록: {"used_pct", "remaining_pct", "reset", "severity", "locked"}
    """
    try:
        raw = fetch_raw()
    except urllib.error.HTTPError as e:
        if e.code == 429:
            try:
                ra = int(e.headers.get("Retry-After") or 0)
            except (TypeError, ValueError):
                ra = 0
            return {"ok": False, "error": "요청 과다", "kind": "ratelimit",
                    "retry_after": ra}
        kind = "auth" if e.code in (401, 403) else "other"
        return {"ok": False, "error": f"HTTP {e.code}", "kind": kind}
    except urllib.error.URLError as e:
        return {"ok": False, "error": "연결 실패", "kind": "network"}
    except FileNotFoundError:
        return {"ok": False, "error": "자격증명 없음", "kind": "auth"}
    except Exception as e:
        return {"ok": False, "error": type(e).__name__, "kind": "other"}

    def block(node):
        if not isinstance(node, dict):
            return None
        util = node.get("utilization")
        if util is None:
            return None
        util = float(util)
        return {
            "used_pct": util,
            "remaining_pct": max(0.0, 100.0 - util),
            "reset": _fmt_reset(node.get("resets_at")),
            "severity": _severity(util),
            "locked": node.get("locked_reason"),
        }

    return {
        "ok": True,
        "five_hour": block(raw.get("five_hour")),
        "seven_day": block(raw.get("seven_day")),
    }


if __name__ == "__main__":
    import pprint
    pprint.pprint(get_usage())
