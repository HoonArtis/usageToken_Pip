"""위젯 주변을 자유롭게 돌아다니는 요정 스프라이트 컴패니언.

assets/fairy/ 의 프레임 PNG를 투명창(Toplevel + transparentcolor)에 띄운다.
목표점을 향해 걷거나(walk) 날아서 이동하고(float), 위젯 뒤에서 옆으로
고개를 내밀고(peek), 가장자리를 손으로 잡고(hold), 두리번거리고(look),
가끔 손을 흔든다(wave). 위젯을 드래그하면 상대 위치를 유지하며 따라간다.
"""
import glob
import math
import os
import random
import tkinter as tk

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets", "fairy")
MAGIC = "#ff00fe"   # 투명 처리용 매직 컬러
TICK_MS = 100

# 상태 전이 가중치 (idle 종료 시 다음 상태 추첨)
NEXT = [("walk", 30), ("float", 18), ("look", 15), ("peek", 15),
        ("wave", 8), ("hold", 14)]
ROAM = 34           # 위젯 좌우로 이만큼까지만 벗어남(px)


def _load_frames():
    frames = {}
    for path in sorted(glob.glob(os.path.join(ASSETS, "*.png"))):
        base = os.path.splitext(os.path.basename(path))[0]
        name, _, idx = base.rpartition("_")
        frames.setdefault(name, []).append((int(idx), tk.PhotoImage(file=path)))
    return {k: [im for _, im in sorted(v)] for k, v in frames.items()}


class Fairy:
    def __init__(self, root):
        self.root = root
        self.win = tk.Toplevel(root)
        self.win.withdraw()
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        try:
            self.win.attributes("-transparentcolor", MAGIC)
        except tk.TclError:
            pass
        self.win.configure(bg=MAGIC)
        self.label = tk.Label(self.win, bg=MAGIC, bd=0)
        self.label.pack()
        self.label.bind("<Button-1>", lambda e: self._enter("wave"))

        try:
            self.frames = _load_frames()
        except tk.TclError:
            self.frames = {}
        self.ok = bool(self.frames.get("idle"))
        self.h = self.frames["idle"][0].height() if self.ok else 48

        self.visible = False
        self.state = "idle"
        self.ticks = 0            # 현재 상태 경과 틱
        self.duration = 20        # 현재 상태 지속 틱
        self.rel_x = 40.0         # 발 중심의 위젯 좌측 기준 오프셋
        self.rel_y = 0.0          # 서있는 선 기준 세로 오프셋 (위로 -)
        self.dir = 1
        self.walked = 0.0         # walk 프레임 진행용 누적 이동량
        self.cur_y = None         # 세로 위치 보간용 (상태 전환 점프 방지)
        self._after = None

    # ---- 표시/숨김 ----
    def show(self):
        if not self.ok or self.visible:
            return
        self.visible = True
        self.cur_y = None           # 재표시 시 이전 위치에서 미끄러지지 않게
        self.win.deiconify()
        self.win.lower(self.root)   # 위젯 뒤에 서도록 (peek 연출)
        self._enter("idle")
        self._tick()

    def hide(self):
        self.visible = False
        if self._after is not None:
            self.win.after_cancel(self._after)
            self._after = None
        self.win.withdraw()

    def toggle(self):
        (self.hide if self.visible else self.show)()

    # ---- 상태 머신 ----
    def _enter(self, state):
        self.state = state
        self.ticks = 0
        self.duration = {
            "idle": random.randint(12, 45),
            "walk": 600,   # 도착하면 스스로 끝남
            "float": random.randint(50, 90),
            "look": random.randint(20, 45),
            "peek": random.randint(40, 60),
            "wave": len(self.frames.get("wave", [])) * 2 + 4,
            "hold": random.randint(30, 70),
        }.get(state, 20)
        aw = self.root.winfo_width()
        if state == "walk":
            self.target = self._pick_spot(aw)
            if abs(self.target - self.rel_x) < 25:
                self.target = self._pick_spot(aw)
            self.speed = random.uniform(1.6, 3.2)
        elif state == "float":
            self.target = self._pick_spot(aw)
            self.fty = -random.uniform(self.h * 0.4, self.h * 1.2)  # 떠오를 높이
        elif state == "peek":
            self.peek_side = random.choice((-1, 1))
        elif state == "hold":
            # 순간이동 금지: 가까운 쪽 가장자리로 목표만 잡고 걸어가서 잡는다
            self.target = 2.0 if self.rel_x < aw / 2 else float(aw - 2)

    def _top_ok(self):
        return self.root.winfo_y() - self.h + 2 >= 0

    def _pick_spot(self, aw):
        """이동 목표 x. 위에 설 수 있으면 위쪽 어디든, 아니면(위젯이 화면
        상단이라 중간 높이에 서면) 몸이 보이는 좌/우 옆자리만 고른다."""
        if self._top_ok():
            return random.uniform(-ROAM, aw + ROAM)
        side = random.choice((-1, 1))
        off = random.uniform(6, ROAM)
        return -off if side < 0 else aw + off

    def _next_state(self):
        if self.state != "idle":
            aw = self.root.winfo_width()
            # 중간 높이 모드에서 위젯 뒤(가려진 위치)에 멈추면 사라진 것처럼
            # 보이므로, 옆자리까지 걸어 나온 뒤에 쉬게 한다
            if not self._top_ok() and 10 < self.rel_x < aw - 10:
                self._enter("walk")
            else:
                self._enter("idle")
            return
        total = sum(w for _, w in NEXT)
        r = random.uniform(0, total)
        for name, w in NEXT:
            r -= w
            if r <= 0:
                self._enter(name)
                return

    def _anchor(self):
        return (self.root.winfo_x(), self.root.winfo_y(),
                self.root.winfo_width(), self.root.winfo_height())

    def _tick(self):
        if not self.visible:
            return
        try:
            self._step()
        except tk.TclError:
            return   # 창이 닫히는 중
        self._after = self.win.after(TICK_MS, self._tick)

    def _step(self):
        ax, ay, aw, ah = self._anchor()
        s, h = self.state, self.h
        # 위젯 위에 설 공간이 없으면(화면 상단에 붙어 있으면) 위젯 중간
        # 높이의 옆자리에 떠 있는다 (아래로 내려가지 않음)
        top_ok = self._top_ok()
        stand_y = (ay - h + 2) if top_ok else (ay + max(0, (ah - h) // 3))
        bob = math.sin(self.ticks * 0.35) * 1.2   # 잔잔한 숨쉬기 흔들림
        done = False

        if s == "walk":
            dx = self.target - self.rel_x
            self.dir = 1 if dx > 0 else -1
            step = min(abs(dx), self.speed) * self.dir
            self.rel_x += step
            self.walked += abs(step)
            seq = self.frames.get("walkr" if self.dir > 0 else "walk") \
                or self.frames["idle"]
            img = seq[int(self.walked / 3.5) % len(seq)]
            y = stand_y
            done = abs(dx) < 2
        elif s == "float":
            # 목표점으로 부드럽게 날아가기 (마지막엔 착지)
            landing = self.ticks > self.duration * 0.72
            ty = 0.0 if landing else self.fty
            self.rel_x += (self.target - self.rel_x) * 0.06
            self.rel_y += (ty - self.rel_y) * 0.10
            seq = self.frames.get("look") or self.frames["idle"]
            img = seq[(self.ticks // 4) % len(seq)]
            y = stand_y + self.rel_y + bob * 2
            done = landing and abs(self.rel_y) < 2
        elif s == "look":
            seq = self.frames.get("look") or self.frames["idle"]
            img = seq[(self.ticks // 3) % len(seq)]
            y = stand_y + bob
        elif s == "wave":
            seq = self.frames.get("wave") or self.frames["idle"]
            img = seq[min(self.ticks // 2, len(seq) - 1)]
            y = stand_y
        elif s == "peek":
            seq = self.frames.get("look") or self.frames["idle"]
            img = seq[(self.ticks // 4) % len(seq)]
            # 위젯 뒤 중앙에 숨었다가 옆으로 스윽 나왔다 들어감 (0..1..0, ease)
            t = self.ticks / max(1, self.duration - 1)
            out = math.sin(min(t, 1 - t) * 2 * math.pi / 2)
            reach = aw / 2 + img.width() / 2 - 10
            # 현재 위치에서 경로로 스르륵 수렴 (진입 순간이동 방지)
            desired = aw / 2 + self.peek_side * out * reach
            self.rel_x += (desired - self.rel_x) * 0.25
            y = ay + max(0, (ah - h) // 2) + bob
        elif s == "hold":
            dx = self.target - self.rel_x
            if abs(dx) > 3:
                # 아직 가장자리 전이면 걸어가는 모션으로 접근
                self.dir = 1 if dx > 0 else -1
                step = min(abs(dx), 2.4) * self.dir
                self.rel_x += step
                self.walked += abs(step)
                seq = self.frames.get("walkr" if self.dir > 0 else "walk") \
                    or self.frames["idle"]
                img = seq[int(self.walked / 3.5) % len(seq)]
                self.ticks -= 1   # 잡는 시간은 도착 후부터 계산
            else:
                seq = self.frames.get("wave") or self.frames["idle"]
                img = seq[3 % len(seq)]       # 손 든 프레임으로 잡는 포즈
            # 손이 위젯 가장자리에 걸치게 살짝 더 겹친다
            y = (ay - h + h // 4) if top_ok else stand_y
        else:  # idle
            seq = self.frames["idle"]
            img = seq[(self.ticks // 5) % len(seq)]
            y = stand_y + bob

        if s != "float":
            self.rel_y = 0.0
        if self.cur_y is None:
            self.cur_y = float(y)
        self.cur_y += (y - self.cur_y) * 0.3   # 상태 전환 시 세로 점프 방지
        x = ax + self.rel_x - img.width() / 2
        self.label.configure(image=img)
        self.win.geometry(f"+{int(x)}+{max(0, int(self.cur_y))}")
        self.win.lower(self.root)   # 항상 위젯 뒤에 있도록 재보정

        self.ticks += 1
        if done or self.ticks >= self.duration:
            self._next_state()
