"""Claude Session PIP — 반투명 항상-위 위젯.

5시간 / 주간 사용 한도 남은 %와 리셋까지 시간, 구독 갱신 D-day를 보여준다.
데이터: usage_api.get_usage() (서버 /api/oauth/usage).
"""
import json
import os
import glob
import shutil
import threading
import subprocess
import tkinter as tk

import usage_api

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "config.json")
PROJECTS_DIR = os.path.expanduser(r"~\.claude\projects")
CREATE_NEW_CONSOLE = 0x00000010


def find_current_session():
    """지금 활성(=가장 최근 활동) Claude 세션을 찾는다.

    반환: (session_id, cwd) 또는 None.
    가장 최근에 수정된 트랜스크립트(.jsonl)가 현재 세션이고,
    그 마지막 줄 JSON에서 sessionId / cwd 를 읽는다.
    """
    files = glob.glob(os.path.join(PROJECTS_DIR, "*", "*.jsonl"))
    if not files:
        return None
    newest = max(files, key=os.path.getmtime)
    sid = os.path.splitext(os.path.basename(newest))[0]
    cwd = None
    try:
        last = None
        with open(newest, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                s = line.strip()
                if s:
                    last = s
        if last:
            d = json.loads(last)
            sid = d.get("sessionId") or d.get("session_id") or sid
            cwd = d.get("cwd")
    except (OSError, json.JSONDecodeError):
        pass
    if not cwd or not os.path.isdir(cwd):
        cwd = os.path.expanduser("~")
    return sid, cwd


def open_terminal_for_session():
    """현재 세션을 새 터미널에서 `claude --resume <id>` 로 이어서 연다."""
    info = find_current_session()
    if not info:
        return
    sid, cwd = info
    ps_cmd = f"Set-Location -LiteralPath '{cwd}'; claude --resume {sid}"
    wt = shutil.which("wt")
    try:
        if wt:
            subprocess.Popen([wt, "-d", cwd, "powershell", "-NoExit",
                              "-Command", ps_cmd])
        else:
            subprocess.Popen(["powershell", "-NoExit", "-Command", ps_cmd],
                             creationflags=CREATE_NEW_CONSOLE)
    except OSError:
        pass

DEFAULT_CONFIG = {
    "refresh_seconds": 600,   # 10분마다 (/usage 엔드포인트 rate-limit 회피)
    "opacity": 0.90,
    "pos": None,              # [x, y] 마지막 위치
}

# 색상
BG = "#0d1117"
FG = "#e6edf3"
DIM = "#8b949e"
TRACK = "#21262d"
SEV = {
    "normal": "#3fb950",
    "warn": "#d29922",
    "critical": "#f85149",
    "unknown": "#8b949e",
}


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg.update(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return cfg


def save_config(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except OSError:
        pass


class Bar(tk.Canvas):
    """남은 % 를 채워 그리는 얇은 막대."""

    def __init__(self, master, w=150, h=8):
        super().__init__(master, width=w, height=h, bg=BG,
                         highlightthickness=0, bd=0)
        self.bw, self.bh = w, h

    def set(self, remaining_pct, color):
        self.delete("all")
        r = 4
        # 트랙
        self._round(0, 0, self.bw, self.bh, r, TRACK)
        if remaining_pct is None:
            return
        fill_w = max(r * 2, int(self.bw * remaining_pct / 100.0))
        self._round(0, 0, fill_w, self.bh, r, color)

    def _round(self, x1, y1, x2, y2, r, color):
        if x2 - x1 < 2 * r:
            r = max(0, (x2 - x1) // 2)
        self.create_rectangle(x1 + r, y1, x2 - r, y2, fill=color, outline=color)
        self.create_rectangle(x1, y1 + r, x2, y2 - r, fill=color, outline=color)
        d = 2 * r
        if r > 0:
            self.create_oval(x1, y1, x1 + d, y1 + d, fill=color, outline=color)
            self.create_oval(x2 - d, y1, x2, y1 + d, fill=color, outline=color)
            self.create_oval(x1, y2 - d, x1 + d, y2, fill=color, outline=color)
            self.create_oval(x2 - d, y2 - d, x2, y2, fill=color, outline=color)


class Row:
    """한 줄: 제목 + 우측 값 + 막대 + 리셋 텍스트."""

    def __init__(self, parent, title):
        self.frame = tk.Frame(parent, bg=BG)
        top = tk.Frame(self.frame, bg=BG)
        top.pack(fill="x")
        self.title = tk.Label(top, text=title, fg=DIM, bg=BG,
                              font=("Segoe UI", 9))
        self.title.pack(side="left")
        self.value = tk.Label(top, text="…", fg=FG, bg=BG,
                              font=("Segoe UI Semibold", 10))
        self.value.pack(side="right")
        self.bar = Bar(self.frame)
        self.bar.pack(fill="x", pady=(2, 0))
        self.sub = tk.Label(self.frame, text="", fg=DIM, bg=BG,
                            font=("Segoe UI", 8), anchor="e")
        self.sub.pack(fill="x")

    def set_block(self, block):
        if not block:
            self.value.config(text="—", fg=DIM)
            self.bar.set(None, TRACK)
            self.sub.config(text="")
            return
        if block.get("locked"):
            self.value.config(text="잠김", fg=SEV["critical"])
            self.bar.set(0, SEV["critical"])
            self.sub.config(text=str(block["locked"])[:24])
            return
        color = SEV.get(block["severity"], DIM)
        self.value.config(text=f"{block['remaining_pct']:.0f}% 남음", fg=color)
        self.bar.set(block["remaining_pct"], color)
        reset = block.get("reset")
        self.sub.config(text=(f"리셋까지 {reset}" if reset else ""))

    def set_text(self, value, sub="", color=FG):
        self.value.config(text=value, fg=color)
        self.bar.set(None, TRACK)
        self.sub.config(text=sub)


class App:
    def __init__(self):
        self.cfg = load_config()
        self.root = tk.Tk()
        self.root.overrideredirect(True)          # 테두리 없음
        self.root.attributes("-topmost", True)     # 항상 위
        self.root.attributes("-alpha", self.cfg["opacity"])
        self.root.configure(bg=BG)

        outer = tk.Frame(self.root, bg=BG, padx=12, pady=10,
                         highlightbackground="#30363d", highlightthickness=1)
        outer.pack(fill="both", expand=True)

        header = tk.Frame(outer, bg=BG)
        header.pack(fill="x", pady=(0, 6))
        tk.Label(header, text="Claude 세션", fg=FG, bg=BG,
                 font=("Segoe UI Semibold", 10)).pack(side="left")
        self.status = tk.Label(header, text="●", fg=DIM, bg=BG,
                               font=("Segoe UI", 9))
        self.status.pack(side="right")

        self.row_5h = Row(outer, "5시간")
        self.row_5h.frame.pack(fill="x", pady=3)
        self.row_7d = Row(outer, "주간")
        self.row_7d.frame.pack(fill="x", pady=3)

        self._make_menu()
        self._bind_drag(outer)
        for w in (outer, header):
            self._bind_drag_child(w)
        # 휠로 투명도 조절 (위젯 위 어디서나)
        self.root.bind_all("<MouseWheel>", self._on_wheel)

        self._place_initial()
        self._latest = None
        self._last_good = None
        self._stop = threading.Event()
        threading.Thread(target=self._worker, daemon=True).start()
        self._tick_ui()

    # ---- 위치/드래그 ----
    def _place_initial(self):
        self.root.update_idletasks()
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        pos = self.cfg.get("pos")
        if pos and len(pos) == 2:
            x, y = pos
        else:
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
            x, y = sw - w - 24, sh - h - 60
        self.root.geometry(f"+{int(x)}+{int(y)}")

    def _bind_drag(self, widget):
        widget.bind("<Button-1>", self._drag_start)
        widget.bind("<B1-Motion>", self._drag_move)
        widget.bind("<ButtonRelease-1>", self._drag_end)

    def _bind_drag_child(self, parent):
        for c in parent.winfo_children():
            if isinstance(c, tk.Label):
                self._bind_drag(c)

    def _drag_start(self, e):
        self._dx, self._dy = e.x_root - self.root.winfo_x(), e.y_root - self.root.winfo_y()

    def _drag_move(self, e):
        self.root.geometry(f"+{e.x_root - self._dx}+{e.y_root - self._dy}")

    def _drag_end(self, _):
        self.cfg["pos"] = [self.root.winfo_x(), self.root.winfo_y()]
        save_config(self.cfg)

    # ---- 우클릭 메뉴 ----
    PANEL_BG = "#161b22"

    def _make_menu(self):
        """우클릭 시 뜨는 패널: 실시간 투명도 슬라이더 + 동작 버튼."""
        p = tk.Toplevel(self.root)
        p.withdraw()
        p.overrideredirect(True)
        p.attributes("-topmost", True)
        p.configure(bg=self.PANEL_BG)
        inner = tk.Frame(p, bg=self.PANEL_BG, padx=10, pady=8,
                         highlightbackground="#30363d", highlightthickness=1)
        inner.pack(fill="both", expand=True)

        # 투명도 슬라이더 (드래그 즉시 반영)
        orow = tk.Frame(inner, bg=self.PANEL_BG)
        orow.pack(fill="x")
        tk.Label(orow, text="투명도", fg=DIM, bg=self.PANEL_BG,
                 font=("Segoe UI", 9)).pack(side="left")
        self.op_val = tk.Label(orow, text="", fg=FG, bg=self.PANEL_BG,
                               font=("Segoe UI", 9), width=4, anchor="e")
        self.op_val.pack(side="right")
        self.op_slider = tk.Scale(
            orow, from_=self.OP_MIN, to=self.OP_MAX, resolution=0.01,
            orient="horizontal", showvalue=False, bg=self.PANEL_BG, fg=FG,
            troughcolor=TRACK, highlightthickness=0, bd=0, length=150,
            sliderlength=18, width=12, sliderrelief="raised",
            activebackground=SEV["normal"], command=self._on_slider)
        self.op_slider.pack(side="left", fill="x", expand=True, padx=6)
        self.op_slider.set(self.cfg["opacity"])

        tk.Frame(inner, bg="#30363d", height=1).pack(fill="x", pady=(8, 4))

        def act(label, cmd):
            b = tk.Label(inner, text=label, fg=FG, bg=self.PANEL_BG,
                         font=("Segoe UI", 9), anchor="w", padx=6, pady=3,
                         cursor="hand2")
            b.pack(fill="x")
            b.bind("<Button-1>", lambda e: (self._hide_panel(), cmd()))
            b.bind("<Enter>", lambda e: b.config(bg="#21262d"))
            b.bind("<Leave>", lambda e: b.config(bg=self.PANEL_BG))

        act("🖥  터미널 열기 (이 세션 이어서)",
            lambda: threading.Thread(target=open_terminal_for_session,
                                     daemon=True).start())
        act("↻  지금 새로고침", self._refresh_now)
        act("✕  종료", self._quit)

        p.bind("<FocusOut>", lambda e: self._hide_panel())
        p.bind("<Escape>", lambda e: self._hide_panel())
        self.panel = p
        self.root.bind("<Button-3>", self._popup)

    def _popup(self, e):
        p = self.panel
        p.deiconify()
        p.update_idletasks()
        # 커서 위치에 뜨되 화면 밖으로 나가지 않게 보정
        w, h = p.winfo_width(), p.winfo_height()
        sw, sh = p.winfo_screenwidth(), p.winfo_screenheight()
        x = min(e.x_root, sw - w - 4)
        y = min(e.y_root, sh - h - 4)
        p.geometry(f"+{max(0, x)}+{max(0, y)}")
        p.lift()
        p.focus_force()

    def _hide_panel(self):
        if getattr(self, "panel", None) is not None:
            self.panel.withdraw()

    OP_MIN, OP_MAX = 0.25, 1.0

    def _on_slider(self, val):
        """슬라이더를 잡고 움직이는 즉시 호출 → 실시간 반영."""
        v = round(float(val), 2)
        self.cfg["opacity"] = v
        self.root.attributes("-alpha", v)
        self.op_val.config(text=f"{int(round(v * 100))}%")
        # 드래그 중 잦은 디스크 쓰기 방지: 200ms 잠잠하면 저장
        if getattr(self, "_save_after", None) is not None:
            self.root.after_cancel(self._save_after)
        self._save_after = self.root.after(200, lambda: save_config(self.cfg))

    def _on_wheel(self, e):
        # 휠 위=진하게, 아래=투명하게 → 슬라이더도 같이 움직임
        step = 0.03 if e.delta > 0 else -0.03
        v = max(self.OP_MIN, min(self.OP_MAX, round(self.cfg["opacity"] + step, 2)))
        self.op_slider.set(v)  # command(_on_slider) 자동 호출 → 실시간 반영

    def _quit(self):
        self._stop.set()
        self.root.destroy()

    # ---- 데이터 ----
    def _refresh_now(self):
        threading.Thread(target=self._fetch_once, daemon=True).start()

    def _fetch_once(self):
        self._latest = usage_api.get_usage()

    def _worker(self):
        base = max(60, int(self.cfg.get("refresh_seconds", 180)))
        backoff = base
        while not self._stop.is_set():
            res = usage_api.get_usage()
            self._latest = res
            if res.get("ok"):
                backoff = base                       # 성공 시 백오프 리셋
                wait = base
            elif res.get("kind") == "ratelimit":
                # 429: 간격을 2배씩 늘려 최대 15분까지 물러남
                backoff = min(backoff * 2, 900)
                wait = max(backoff, res.get("retry_after") or 0, 90)
            else:
                wait = base
            self._stop.wait(wait)

    def _tick_ui(self):
        if self._latest is not None:
            self._apply(self._latest)
        if not self._stop.is_set():
            self.root.after(1000, self._tick_ui)

    def _apply(self, data):
        if data.get("ok"):
            self._last_good = data
            self.status.config(fg=SEV["normal"])
            self.row_5h.set_block(data.get("five_hour"))
            self.row_7d.set_block(data.get("seven_day"))
            return
        kind = data.get("kind")
        # 429(요청 과다): 마지막 정상값을 유지하고 상태 점만 노랗게
        if kind == "ratelimit" and self._last_good:
            g = self._last_good
            self.status.config(fg=SEV["warn"])
            self.row_5h.set_block(g.get("five_hour"))
            self.row_7d.set_block(g.get("seven_day"))
            return
        msg = {"auth": "재인증 필요", "network": "연결 실패",
               "ratelimit": "요청 과다 — 대기 중"}.get(kind, data.get("error", "오류"))
        self.status.config(fg=SEV["critical"])
        self.row_5h.set_text("—", msg, DIM)
        self.row_7d.set_text("—", "", DIM)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    App().run()
