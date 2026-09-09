"""Claude/Codex Session PIP — 반투명 항상-위 위젯.

Claude(5시간/주간)와 Codex 사용 한도의 남은 %와 리셋까지 시간을 보여준다.
헤더의 Claude/Codex 탭 클릭 또는 우클릭 메뉴로 표시 대상을 고른다.
데이터: claude_usage.get_usage() (서버), codex_usage.get_usage() (로컬 세션 파일).
"""
import ctypes
import json
import os
import threading
import tkinter as tk

import claude_usage
import codex_usage
import fairy

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                      # 저장소 루트 (src/ 상위)
CONFIG_PATH = os.path.join(ROOT, "config.json")

DEFAULT_CONFIG = {
    "refresh_seconds": 600,   # 10분마다 (/usage 엔드포인트 rate-limit 회피)
    "opacity": 0.90,
    "pos": None,              # [x, y] 마지막 위치
    "provider": "claude",     # claude | codex | both
    "fairy": True,            # 요정 컴패니언 표시
}

# 색상
BG = "#0d1117"
FG = "#e6edf3"
DIM = "#8b949e"
FAINT = "#6e7681"
TRACK = "#21262d"
BORDER = "#30363d"
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
    if cfg.get("provider") not in ("claude", "codex", "both"):
        cfg["provider"] = "claude"
    return cfg


def save_config(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except OSError:
        pass


def round_corners(win):
    """Windows 11 DWM으로 창 모서리를 둥글게 (미지원 OS면 조용히 무시)."""
    try:
        win.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(win.winfo_id())
        if not hwnd:
            hwnd = win.winfo_id()
        DWMWA_WINDOW_CORNER_PREFERENCE = 33
        DWMWCP_ROUND = 2
        pref = ctypes.c_int(DWMWCP_ROUND)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_WINDOW_CORNER_PREFERENCE,
            ctypes.byref(pref), ctypes.sizeof(pref))
    except (OSError, AttributeError):
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


class Slider(tk.Canvas):
    """tk.Scale 대신 쓰는 커스텀 슬라이더 (트랙 + 원형 노브)."""

    PAD = 8  # 노브가 잘리지 않게 좌우 여백

    def __init__(self, master, vmin, vmax, value, command,
                 w=160, h=20, bg=BG, fill="#3fb950"):
        super().__init__(master, width=w, height=h, bg=bg,
                         highlightthickness=0, bd=0)
        self.vmin, self.vmax = vmin, vmax
        self.command = command
        self.w, self.h = w, h
        self.fill = fill
        self.value = value
        self.bind("<Button-1>", self._on_point)
        self.bind("<B1-Motion>", self._on_point)
        self._draw()

    def set(self, v):
        self.value = max(self.vmin, min(self.vmax, v))
        self._draw()
        if self.command:
            self.command(self.value)

    def _on_point(self, e):
        span = self.w - 2 * self.PAD
        frac = (e.x - self.PAD) / max(1, span)
        frac = max(0.0, min(1.0, frac))
        self.set(self.vmin + frac * (self.vmax - self.vmin))

    def _draw(self):
        self.delete("all")
        cy = self.h // 2
        x1, x2 = self.PAD, self.w - self.PAD
        frac = (self.value - self.vmin) / (self.vmax - self.vmin)
        kx = x1 + frac * (x2 - x1)
        # 트랙 / 채움
        self.create_line(x1, cy, x2, cy, fill=TRACK, width=4, capstyle="round")
        if kx > x1:
            self.create_line(x1, cy, kx, cy, fill=self.fill, width=4,
                             capstyle="round")
        # 노브
        r = 6
        self.create_oval(kx - r, cy - r, kx + r, cy + r,
                         fill=FG, outline=BORDER)


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

    def set_block(self, block, asof=None):
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
        sub = f"리셋까지 {reset}" if reset else ""
        if asof:
            sub = f"{sub} · {asof} 기준" if sub else f"{asof} 기준"
        self.sub.config(text=sub)

    def set_text(self, value, sub="", color=FG):
        self.value.config(text=value, fg=color)
        self.bar.set(None, TRACK)
        self.sub.config(text=sub)

    def set_pending(self):
        self.value.config(text="…", fg=DIM)
        self.bar.set(None, TRACK)
        self.sub.config(text="")


class App:
    def __init__(self):
        self.cfg = load_config()
        self.root = tk.Tk()
        self.root.overrideredirect(True)          # 테두리 없음
        self.root.attributes("-topmost", True)     # 항상 위
        self.root.attributes("-alpha", self.cfg["opacity"])
        self.root.configure(bg=BG)

        outer = tk.Frame(self.root, bg=BG, padx=12, pady=10,
                         highlightbackground=BORDER, highlightthickness=1)
        outer.pack(fill="both", expand=True)

        header = tk.Frame(outer, bg=BG)
        header.pack(fill="x", pady=(0, 6))
        tabs = tk.Frame(header, bg=BG)
        tabs.pack(side="left")
        self.tab_labels = {}
        for key, name in (("claude", "Claude"), ("codex", "Codex")):
            lbl = tk.Label(tabs, text=name, bg=BG, fg=DIM,
                           font=("Segoe UI Semibold", 10), cursor="hand2")
            lbl.pack(side="left", padx=(0, 10))
            lbl.bind("<Button-1>", lambda e, k=key: self._set_provider(k))
            self.tab_labels[key] = lbl
        self.status = tk.Label(header, text="●", fg=DIM, bg=BG,
                               font=("Segoe UI", 9))
        self.status.pack(side="right")

        self.rows_frame = tk.Frame(outer, bg=BG)
        self.rows_frame.pack(fill="x")
        self._rows = {}          # {title: Row} (표시 순서 = _row_titles)
        self._row_titles = []

        self._make_menu()
        self._bind_drag(outer)
        for w in (outer, header):
            self._bind_drag_child(w)
        # 휠로 투명도 조절 (위젯 위 어디서나)
        self.root.bind_all("<MouseWheel>", self._on_wheel)

        self._update_tabs()
        self._place_initial()
        round_corners(self.root)

        self.fairy = fairy.Fairy(self.root)
        if self.cfg.get("fairy"):
            self.fairy.show()
        self._latest = {"claude": None, "codex": None}
        self._last_good = None    # claude 마지막 정상값 (429 대비)
        self._stop = threading.Event()
        self._wake = threading.Event()
        threading.Thread(target=self._worker, daemon=True).start()
        self._tick_ui()

    # ---- 프로바이더 선택 ----
    def _active(self):
        mode = self.cfg.get("provider", "claude")
        return ("claude", "codex") if mode == "both" else (mode,)

    def _set_provider(self, mode):
        if mode == self.cfg.get("provider"):
            return
        self.cfg["provider"] = mode
        save_config(self.cfg)
        self._update_tabs()
        self._apply()
        self._refresh_now()

    def _update_tabs(self):
        mode = self.cfg.get("provider", "claude")
        for key, lbl in self.tab_labels.items():
            on = mode in (key, "both")
            lbl.config(fg=FG if on else FAINT)
        if hasattr(self, "seg_labels"):
            for key, lbl in self.seg_labels.items():
                on = mode == key
                lbl.config(bg=BORDER if on else self.PANEL_BG,
                           fg=FG if on else DIM)

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
    PANEL_HOVER = "#21262d"

    def _make_menu(self):
        """우클릭 패널: 표시 대상 선택 + 투명도 슬라이더 + 동작 버튼."""
        p = tk.Toplevel(self.root)
        p.withdraw()
        p.overrideredirect(True)
        p.attributes("-topmost", True)
        p.configure(bg=self.PANEL_BG)
        inner = tk.Frame(p, bg=self.PANEL_BG, padx=14, pady=12,
                         highlightbackground=BORDER, highlightthickness=1)
        inner.pack(fill="both", expand=True)

        def section(text, pady=(0, 5)):
            tk.Label(inner, text=text, fg=FAINT, bg=self.PANEL_BG,
                     font=("Segoe UI", 8), anchor="w").pack(fill="x", pady=pady)

        def divider():
            tk.Frame(inner, bg=BORDER, height=1).pack(fill="x", pady=(10, 8))

        # -- 표시 대상 (세그먼트 컨트롤) --
        section("표시")
        seg = tk.Frame(inner, bg=BG, highlightbackground=BORDER,
                       highlightthickness=1)
        seg.pack(fill="x")
        self.seg_labels = {}
        for key, name in (("claude", "Claude"), ("codex", "Codex"),
                          ("both", "둘 다")):
            lbl = tk.Label(seg, text=name, fg=DIM, bg=self.PANEL_BG,
                           font=("Segoe UI", 9), padx=10, pady=4,
                           cursor="hand2")
            lbl.pack(side="left", fill="x", expand=True)
            lbl.bind("<Button-1>", lambda e, k=key: self._set_provider(k))
            lbl.bind("<Enter>", lambda e, k=key, w=lbl: (
                self.cfg.get("provider") != k
                and w.config(bg=self.PANEL_HOVER)))
            lbl.bind("<Leave>", lambda e, k=key, w=lbl: (
                self.cfg.get("provider") != k
                and w.config(bg=self.PANEL_BG)))
            self.seg_labels[key] = lbl

        divider()

        # -- 투명도 --
        orow = tk.Frame(inner, bg=self.PANEL_BG)
        orow.pack(fill="x")
        tk.Label(orow, text="투명도", fg=FAINT, bg=self.PANEL_BG,
                 font=("Segoe UI", 8)).pack(side="left")
        self.op_val = tk.Label(orow, text="", fg=FG, bg=self.PANEL_BG,
                               font=("Segoe UI", 8), anchor="e")
        self.op_val.pack(side="right")
        self.op_slider = Slider(inner, self.OP_MIN, self.OP_MAX,
                                self.cfg["opacity"], self._on_slider,
                                w=170, bg=self.PANEL_BG)
        self.op_slider.pack(fill="x", pady=(4, 0))
        self.op_val.config(text=f"{int(round(self.cfg['opacity'] * 100))}%")

        divider()

        # -- 동작 --
        def act(label, cmd):
            b = tk.Label(inner, text=label, fg=FG, bg=self.PANEL_BG,
                         font=("Segoe UI", 9), anchor="w", padx=8, pady=5,
                         cursor="hand2")
            b.pack(fill="x")
            b.bind("<Button-1>", lambda e: (self._hide_panel(), cmd()))
            b.bind("<Enter>", lambda e: b.config(bg=self.PANEL_HOVER))
            b.bind("<Leave>", lambda e: b.config(bg=self.PANEL_BG))

        act("🧚  요정 표시/숨기기", self._toggle_fairy)
        act("↻  지금 새로고침", self._refresh_now)
        act("✕  종료", self._quit)

        p.bind("<FocusOut>", lambda e: self._hide_panel())
        p.bind("<Escape>", lambda e: self._hide_panel())
        self.panel = p
        self.root.bind("<Button-3>", self._popup)

    def _popup(self, e):
        p = self.panel
        self._update_tabs()   # 세그먼트 선택 상태 최신화
        p.deiconify()
        p.update_idletasks()
        round_corners(p)
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

    def _toggle_fairy(self):
        self.fairy.toggle()
        self.cfg["fairy"] = self.fairy.visible
        save_config(self.cfg)

    def _quit(self):
        self._stop.set()
        self.root.destroy()

    # ---- 데이터 ----
    def _refresh_now(self):
        self._wake.set()

    def _worker(self):
        base = max(60, int(self.cfg.get("refresh_seconds", 180)))
        backoff = base
        while not self._stop.is_set():
            active = self._active()
            wait = base
            if "claude" in active:
                res = claude_usage.get_usage()
                self._latest["claude"] = res
                if res.get("ok"):
                    backoff = base                   # 성공 시 백오프 리셋
                elif res.get("kind") == "ratelimit":
                    # 429: 간격을 2배씩 늘려 최대 15분까지 물러남
                    backoff = min(backoff * 2, 900)
                    wait = max(backoff, res.get("retry_after") or 0, 90)
            if "codex" in active:
                self._latest["codex"] = codex_usage.get_usage()
            self._wake.wait(wait)
            self._wake.clear()

    def _tick_ui(self):
        self._apply()
        if not self._stop.is_set():
            self.root.after(1000, self._tick_ui)

    # 상태 점 우선순위: 오류 > 경고 > 정상 > 대기
    _DOT_RANK = {"err": 3, "warn": 2, "ok": 1, None: 0}

    def _apply(self):
        active = self._active()
        prefix = {"claude": "Claude ", "codex": "Codex "} if len(active) > 1 \
            else {"claude": "", "codex": ""}
        specs, dots = [], []
        if "claude" in active:
            s, d = self._claude_specs(prefix["claude"])
            specs += s
            dots.append(d)
        if "codex" in active:
            s, d = self._codex_specs(prefix["codex"])
            specs += s
            dots.append(d)

        dot = max(dots, key=lambda d: self._DOT_RANK[d])
        self.status.config(fg={"err": SEV["critical"], "warn": SEV["warn"],
                               "ok": SEV["normal"]}.get(dot, DIM))

        self._ensure_rows([t for t, _, _ in specs])
        for title, kind, payload in specs:
            row = self._rows[title]
            if kind == "block":
                block, asof = payload
                row.set_block(block, asof)
            elif kind == "text":
                row.set_text(*payload)
            else:
                row.set_pending()

    def _claude_specs(self, prefix):
        """반환: ([(title, kind, payload)], dot)"""
        t5, t7 = f"{prefix}5시간", f"{prefix}주간"
        data = self._latest["claude"]
        if data is None:
            return [(t5, "pending", None), (t7, "pending", None)], None
        if data.get("ok"):
            self._last_good = data
            return [(t5, "block", (data.get("five_hour"), None)),
                    (t7, "block", (data.get("seven_day"), None))], "ok"
        kind = data.get("kind")
        # 429(요청 과다): 마지막 정상값을 유지하고 상태 점만 노랗게
        if kind == "ratelimit" and self._last_good:
            g = self._last_good
            return [(t5, "block", (g.get("five_hour"), None)),
                    (t7, "block", (g.get("seven_day"), None))], "warn"
        msg = {"auth": "재인증 필요", "network": "연결 실패",
               "ratelimit": "요청 과다 — 대기 중"}.get(kind, data.get("error", "오류"))
        return [(t5, "text", ("—", msg, DIM)),
                (t7, "text", ("—", "", DIM))], "err"

    def _codex_specs(self, prefix):
        """반환: ([(title, kind, payload)], dot)"""
        data = self._latest["codex"]
        title = "Codex"
        if data is None:
            return [(title, "pending", None)], None
        if not data.get("ok"):
            dot = "warn" if data.get("kind") == "nodata" else "err"
            return [(title, "text", ("—", data.get("error", "오류"), DIM))], dot
        asof = data.get("asof")
        specs = [(f"{prefix}{w['label']}", "block", (w, asof))
                 for w in data["windows"]]
        return specs, "ok"

    def _ensure_rows(self, titles):
        """표시할 행 제목이 바뀌면 행들을 다시 만든다."""
        if titles == self._row_titles:
            return
        for row in self._rows.values():
            row.frame.destroy()
        self._rows = {}
        for t in titles:
            row = Row(self.rows_frame, t)
            row.frame.pack(fill="x", pady=3)
            self._rows[t] = row
        self._row_titles = titles

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    App().run()
