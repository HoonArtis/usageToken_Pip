"""Codex 사용량 조회 — 로컬 세션 파일에서 마지막 rate_limits 이벤트를 읽는다.

Codex CLI는 매 응답마다 ~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl 에
rate_limits(사용 %, 윈도우 길이, 리셋 시각)를 기록한다.
네트워크 호출 없이 최신 파일 몇 개를 뒤에서부터 훑어 가장 최근 값을 쓴다.
"""
import glob
import json
import os
from datetime import datetime, timezone

from usage_api import _severity

SESSIONS_DIR = os.path.expanduser(r"~\.codex\sessions")
TAIL_BYTES = 2 * 1024 * 1024   # 파일 끝에서 이만큼만 읽어 스캔
SCAN_FILES = 5                 # 최근 파일 몇 개까지 확인할지


def _tail_lines(path, size=TAIL_BYTES):
    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END)
        end = f.tell()
        f.seek(max(0, end - size))
        data = f.read()
    text = data.decode("utf-8", "replace")
    lines = text.splitlines()
    # 중간부터 읽었으면 첫 줄은 잘린 조각일 수 있음
    if end > size and lines:
        lines = lines[1:]
    return lines


def _find_latest_rate_limits():
    """최근 세션 파일들에서 마지막 rate_limits 이벤트를 찾는다.

    반환: (rate_limits dict, 이벤트 timestamp 문자열) 또는 None.
    """
    files = glob.glob(os.path.join(SESSIONS_DIR, "*", "*", "*", "*.jsonl"))
    files.sort(key=os.path.getmtime, reverse=True)
    for path in files[:SCAN_FILES]:
        try:
            lines = _tail_lines(path)
        except OSError:
            continue
        for line in reversed(lines):
            if '"rate_limits"' not in line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            rl = (d.get("payload") or {}).get("rate_limits")
            if isinstance(rl, dict):
                return rl, d.get("timestamp")
    return None


def _fmt_window(minutes):
    """window_minutes -> '5시간' / '주간' 같은 라벨."""
    if not minutes:
        return "한도"
    m = int(minutes)
    if m % 1440 == 0:
        d = m // 1440
        return "주간" if d == 7 else f"{d}일"
    if m % 60 == 0:
        return f"{m // 60}시간"
    return f"{m}분"


def _fmt_reset(epoch):
    """resets_at(unix 초) -> 남은 시간 'Xh Ym' (지났으면 'now')."""
    if not epoch:
        return None
    delta = datetime.fromtimestamp(int(epoch), tz=timezone.utc) - datetime.now(timezone.utc)
    secs = int(delta.total_seconds())
    if secs <= 0:
        return "now"
    h, m = secs // 3600, (secs % 3600) // 60
    if h >= 24:
        return f"{h // 24}d {h % 24}h"
    if h > 0:
        return f"{h}h {m}m"
    return f"{m}m"


def _fmt_asof(iso):
    """이벤트 timestamp(UTC ISO) -> 현지 시각 'HH:MM' 또는 'M/D HH:MM'."""
    if not iso:
        return None
    try:
        t = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone()
    except ValueError:
        return None
    now = datetime.now().astimezone()
    if t.date() == now.date():
        return t.strftime("%H:%M")
    return f"{t.month}/{t.day} {t.strftime('%H:%M')}"


def get_usage():
    """GUI가 쓰기 좋은 형태로 정규화 (usage_api.get_usage()와 유사).

    반환:
      {"ok": True, "windows": [{"label", "used_pct", "remaining_pct",
                                "reset", "severity", "locked"}],
       "asof": "13:05"}
      또는 {"ok": False, "error": "...", "kind": "nodata|other"}
    """
    try:
        found = _find_latest_rate_limits()
    except Exception as e:
        return {"ok": False, "error": type(e).__name__, "kind": "other"}
    if not found:
        return {"ok": False, "error": "Codex 기록 없음", "kind": "nodata"}
    rl, ts = found

    windows = []
    for node in (rl.get("primary"), rl.get("secondary")):
        if not isinstance(node, dict):
            continue
        util = node.get("used_percent")
        if util is None:
            continue
        util = float(util)
        locked = None
        if rl.get("rate_limit_reached_type"):
            locked = str(rl["rate_limit_reached_type"])
        windows.append({
            "label": _fmt_window(node.get("window_minutes")),
            "used_pct": util,
            "remaining_pct": max(0.0, 100.0 - util),
            "reset": _fmt_reset(node.get("resets_at")),
            "severity": _severity(util),
            "locked": locked,
        })
    if not windows:
        return {"ok": False, "error": "Codex 기록 없음", "kind": "nodata"}
    return {"ok": True, "windows": windows, "asof": _fmt_asof(ts)}


if __name__ == "__main__":
    import pprint
    pprint.pprint(get_usage())
