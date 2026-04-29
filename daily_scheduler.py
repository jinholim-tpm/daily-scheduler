"""
Daily Scheduler - 글래스모피즘 데일리 스케줄러 GUI
- 반투명 윈도우 + 다크 테마 (투명도 저장/복원)
- 어제 미완료 할 일 자동 이월
- 체크박스로 완료 표시
- 회의록/메모 작성 + .md 내보내기
- 날짜별 히스토리 조회
- 다국어 지원 (한/영)
"""

import tkinter as tk
from tkinter import messagebox, filedialog
import sqlite3
from datetime import date, timedelta, datetime
from pathlib import Path

# ────────────────────────────────────────────────
# 다국어
# ────────────────────────────────────────────────
I18N = {
    "ko": {
        "app_title": "Daily Scheduler",
        "tasks": "할 일",
        "notes": "메모",
        "history": "히스토리",
        "opacity": "투명도",
        "today": "오늘",
        "yesterday": "어제",
        "go_today": "오늘로",
        "add_placeholder": "새로운 할 일을 입력하세요...",
        "no_tasks": "할 일이 없습니다",
        "no_tasks_hint": "위 입력창에서 추가해보세요",
        "carried_over": "미완료 {n}건을 이월했습니다",
        "saved": "저장됨",
        "export_md": "MD",
        "export_success": "내보내기 완료: {path}",
        "no_records": "기록된 날짜가 없습니다.",
        "done_count": "완료",
        "lang_label": "언어",
        "weekdays": ["월", "화", "수", "목", "금", "토", "일"],
    },
    "en": {
        "app_title": "Daily Scheduler",
        "tasks": "TASKS",
        "notes": "NOTES",
        "history": "History",
        "opacity": "Opacity",
        "today": "Today",
        "yesterday": "Yesterday",
        "go_today": "Go to Today",
        "add_placeholder": "Add a new task...",
        "no_tasks": "No tasks yet",
        "no_tasks_hint": "Add one above to get started",
        "carried_over": "Carried over {n} incomplete task(s)",
        "saved": "Saved",
        "export_md": "MD",
        "export_success": "Exported: {path}",
        "no_records": "No records found.",
        "done_count": "done",
        "lang_label": "Lang",
        "weekdays": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    },
}

# ────────────────────────────────────────────────
# 컬러 팔레트 (TPM-OS Glass Design System 기반)
# ────────────────────────────────────────────────
C = {
    "bg":           "#1a1a2e",
    "surface":      "#1f1f36",
    "surface_md":   "#24243d",
    "surface_strong": "#2a2a44",
    "border":       "#2e2e4a",
    "border_md":    "#363658",
    "text":         "#ffffff",
    "dim1":         "#dcdce6",
    "dim2":         "#8888a4",
    "dim3":         "#5a5a78",
    "blue":         "#90cdf4",
    "green":        "#68d391",
    "red":          "#fc8181",
    "amber":        "#fbd38d",
    "purple":       "#c4b5fd",
    "teal":         "#4fd1c5",
    "hover":        "#24243d",
    "input_bg":     "#1e1e35",
    "divider":      "#2a2a44",
    "note_bg":      "#1c1c32",
}

# ────────────────────────────────────────────────
# 데이터베이스
# ────────────────────────────────────────────────
DB_PATH = Path.home() / "daily_scheduler.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS tasks (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                date        TEXT NOT NULL,
                title       TEXT NOT NULL,
                done        INTEGER NOT NULL DEFAULT 0,
                carried     INTEGER NOT NULL DEFAULT 0,
                created_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            );
            CREATE INDEX IF NOT EXISTS idx_tasks_date ON tasks(date);
            CREATE TABLE IF NOT EXISTS notes (
                date        TEXT PRIMARY KEY,
                content     TEXT NOT NULL DEFAULT '',
                updated_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            );
            CREATE TABLE IF NOT EXISTS meta (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
        """)


def get_meta(key, default=None):
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row[0] if row else default


def set_meta(key, value):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (key, str(value))
        )


def carry_over_tasks(today_str):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT value FROM meta WHERE key = 'last_carry_over'"
        ).fetchone()
        if row and row[0] == today_str:
            return 0
        rows = conn.execute(
            "SELECT id, title FROM tasks WHERE date < ? AND done = 0 AND carried = 0",
            (today_str,),
        ).fetchall()
        for tid, title in rows:
            conn.execute(
                "INSERT INTO tasks (date, title, done, carried) VALUES (?, ?, 0, 0)",
                (today_str, title),
            )
            conn.execute("UPDATE tasks SET carried = 1 WHERE id = ?", (tid,))
        conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES ('last_carry_over', ?)",
            (today_str,),
        )
        return len(rows)


def fetch_tasks(d):
    with get_conn() as conn:
        return conn.execute(
            "SELECT id, title, done FROM tasks WHERE date = ? ORDER BY done, id",
            (d,),
        ).fetchall()


def add_task(d, title):
    with get_conn() as conn:
        conn.execute("INSERT INTO tasks (date, title) VALUES (?, ?)", (d, title.strip()))


def toggle_task(tid, done):
    with get_conn() as conn:
        conn.execute("UPDATE tasks SET done = ? WHERE id = ?", (1 if done else 0, tid))


def delete_task(tid):
    with get_conn() as conn:
        conn.execute("DELETE FROM tasks WHERE id = ?", (tid,))


def fetch_note(d):
    with get_conn() as conn:
        row = conn.execute("SELECT content FROM notes WHERE date = ?", (d,)).fetchone()
        return row[0] if row else ""


def save_note(d, content):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO notes (date, content, updated_at)
            VALUES (?, ?, datetime('now','localtime'))
            ON CONFLICT(date) DO UPDATE SET
                content = excluded.content, updated_at = excluded.updated_at""",
            (d, content),
        )


def fetch_history_dates(limit=60):
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT DISTINCT d FROM (
                SELECT date AS d FROM tasks UNION
                SELECT date AS d FROM notes WHERE content != ''
            ) ORDER BY d DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [r[0] for r in rows]


# ────────────────────────────────────────────────
# GUI
# ────────────────────────────────────────────────
class SchedulerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Daily Scheduler")
        self.root.geometry("1060x700")
        self.root.minsize(900, 580)
        self.root.configure(bg=C["bg"])

        # 언어 설정 로드
        saved_lang = get_meta("lang", "ko")
        self.lang = saved_lang if saved_lang in I18N else "ko"
        self.t = I18N[self.lang]

        # 투명도 로드
        saved_opacity = get_meta("opacity", "1.0")
        try:
            self._opacity = float(saved_opacity)
        except ValueError:
            self._opacity = 1.0
        self._opacity = max(0.3, min(1.0, self._opacity))
        try:
            self.root.attributes("-alpha", self._opacity)
        except tk.TclError:
            pass

        self.today_str = date.today().isoformat()
        self.current_date = self.today_str
        self._note_save_after_id = None

        self._build_ui()
        self.refresh_all()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _tx(self, key, **kwargs):
        """현재 언어로 텍스트 반환"""
        text = self.t.get(key, key)
        if kwargs:
            text = text.format(**kwargs)
        return text

    # ── UI 빌드 ──────────────────────────────────
    def _build_ui(self):
        # ── 상단 바 ──
        topbar = tk.Frame(self.root, bg=C["bg"], padx=24, pady=10)
        topbar.pack(fill=tk.X)

        # 날짜 네비게이션
        nav = tk.Frame(topbar, bg=C["bg"])
        nav.pack(side=tk.LEFT)

        self._make_nav_btn(nav, "<", self.prev_day).pack(side=tk.LEFT)

        self.date_label = tk.Label(nav, text="", fg=C["text"], bg=C["bg"],
                                   font=("SF Pro Display", 15, "bold"))
        self.date_label.pack(side=tk.LEFT, padx=10)

        self._make_nav_btn(nav, ">", self.next_day).pack(side=tk.LEFT)

        self.today_badge = tk.Label(nav, text="", fg=C["blue"], bg=C["bg"],
                                    font=("SF Pro Text", 9), cursor="pointinghand",
                                    padx=10, pady=2)
        self.today_badge.pack(side=tk.LEFT, padx=(14, 0))
        self.today_badge.bind("<Button-1>", lambda e: self.go_today())

        # 오른쪽 컨트롤
        right_controls = tk.Frame(topbar, bg=C["bg"])
        right_controls.pack(side=tk.RIGHT)

        # 언어 전환
        self.lang_label = tk.Label(right_controls, text="", fg=C["dim3"], bg=C["bg"],
                                   font=("SF Pro Text", 9))
        self.lang_label.pack(side=tk.LEFT, padx=(0, 4))

        self.lang_btn = tk.Label(right_controls, text="", fg=C["dim2"], bg=C["bg"],
                                 font=("SF Pro Text", 9), cursor="pointinghand")
        self.lang_btn.pack(side=tk.LEFT, padx=(0, 16))
        self.lang_btn.bind("<Button-1>", lambda e: self._toggle_lang())
        self.lang_btn.bind("<Enter>", lambda e: self.lang_btn.config(fg=C["text"]))
        self.lang_btn.bind("<Leave>", lambda e: self.lang_btn.config(fg=C["dim2"]))

        # 투명도
        self.opacity_title = tk.Label(right_controls, text="", fg=C["dim3"], bg=C["bg"],
                                      font=("SF Pro Text", 9))
        self.opacity_title.pack(side=tk.LEFT, padx=(0, 4))

        self.opacity_var = tk.DoubleVar(value=self._opacity)
        self.opacity_scale = tk.Scale(
            right_controls, from_=0.3, to=1.0, resolution=0.01,
            orient=tk.HORIZONTAL, length=80,
            variable=self.opacity_var, command=self._on_opacity_change,
            bg=C["bg"], fg=C["dim2"], troughcolor=C["border"],
            highlightthickness=0, bd=0, sliderrelief="flat",
            activebackground=C["blue"], font=("SF Pro Text", 8),
            showvalue=False,
        )
        self.opacity_scale.pack(side=tk.LEFT, padx=(0, 2))

        self.opacity_label = tk.Label(right_controls, text=f"{int(self._opacity * 100)}%",
                                      fg=C["dim2"], bg=C["bg"],
                                      font=("SF Pro Text", 9), width=4)
        self.opacity_label.pack(side=tk.LEFT, padx=(0, 16))

        # 히스토리 버튼
        self.hist_btn = tk.Label(right_controls, text="", fg=C["dim2"], bg=C["bg"],
                                 font=("SF Pro Text", 10), cursor="pointinghand",
                                 padx=10, pady=3)
        self.hist_btn.pack(side=tk.LEFT)
        self.hist_btn.bind("<Button-1>", lambda e: self.show_history())
        self.hist_btn.bind("<Enter>", lambda e: self.hist_btn.config(fg=C["text"]))
        self.hist_btn.bind("<Leave>", lambda e: self.hist_btn.config(fg=C["dim2"]))

        # 구분선
        tk.Frame(self.root, bg=C["divider"], height=1).pack(fill=tk.X, padx=24)

        # ── 본문 ──
        body = tk.Frame(self.root, bg=C["bg"], padx=24, pady=12)
        body.pack(fill=tk.BOTH, expand=True)
        body.columnconfigure(0, weight=1, uniform="col")
        body.columnconfigure(1, weight=1, uniform="col")
        body.rowconfigure(0, weight=1)

        # ── 왼쪽: Tasks ──
        left = self._glass_card(body)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        lh = tk.Frame(left, bg=C["bg"])
        lh.pack(fill=tk.X, padx=18, pady=(12, 0))
        self.tasks_title = tk.Label(lh, text="", fg=C["dim2"], bg=C["bg"],
                                    font=("SF Pro Text", 9), anchor="w")
        self.tasks_title.pack(side=tk.LEFT)
        self.task_count_label = tk.Label(lh, text="", fg=C["dim3"], bg=C["bg"],
                                         font=("SF Pro Text", 9))
        self.task_count_label.pack(side=tk.RIGHT)

        tk.Frame(left, bg=C["divider"], height=1).pack(fill=tk.X, padx=18, pady=(8, 0))

        # 입력
        input_frame = tk.Frame(left, bg=C["bg"], padx=18, pady=10)
        input_frame.pack(fill=tk.X)

        input_inner = tk.Frame(input_frame, bg=C["input_bg"],
                               highlightbackground=C["border"], highlightthickness=1)
        input_inner.pack(fill=tk.X)

        self.task_entry = tk.Entry(
            input_inner, font=("SF Pro Text", 11),
            bg=C["input_bg"], fg=C["text"], insertbackground=C["blue"],
            relief="flat", bd=0, highlightthickness=0,
        )
        self.task_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=7, padx=12)
        self.task_entry.config(fg=C["dim3"])
        self.task_entry.bind("<FocusIn>", self._on_entry_focus_in)
        self.task_entry.bind("<FocusOut>", self._on_entry_focus_out)
        self.task_entry.bind("<Return>", lambda e: self.on_add_task())

        add_btn = tk.Label(input_inner, text=" + ", font=("SF Pro Text", 14),
                           fg=C["blue"], bg=C["input_bg"], cursor="pointinghand")
        add_btn.pack(side=tk.RIGHT, padx=(0, 6))
        add_btn.bind("<Button-1>", lambda e: self.on_add_task())

        # 할 일 리스트
        self.task_canvas = tk.Canvas(left, bg=C["bg"], highlightthickness=0, bd=0)
        self.task_canvas.pack(fill=tk.BOTH, expand=True)

        self.task_list_frame = tk.Frame(self.task_canvas, bg=C["bg"])
        self.task_canvas.create_window((0, 0), window=self.task_list_frame,
                                       anchor="nw", tags="frame")
        self.task_list_frame.bind(
            "<Configure>",
            lambda e: self.task_canvas.configure(scrollregion=self.task_canvas.bbox("all")),
        )
        self.task_canvas.bind(
            "<Configure>",
            lambda e: self.task_canvas.itemconfig("frame", width=e.width),
        )
        self.task_canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        # ── 오른쪽: Notes ──
        right = self._glass_card(body)
        right.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        rh = tk.Frame(right, bg=C["bg"])
        rh.pack(fill=tk.X, padx=18, pady=(12, 0))
        self.notes_title = tk.Label(rh, text="", fg=C["dim2"], bg=C["bg"],
                                    font=("SF Pro Text", 9), anchor="w")
        self.notes_title.pack(side=tk.LEFT)

        # Export MD 버튼
        self.export_btn = tk.Label(rh, text="", fg=C["dim3"], bg=C["bg"],
                                   font=("SF Pro Text", 9), cursor="pointinghand", padx=6)
        self.export_btn.pack(side=tk.RIGHT, padx=(8, 0))
        self.export_btn.bind("<Button-1>", lambda e: self._export_md())
        self.export_btn.bind("<Enter>", lambda e: self.export_btn.config(fg=C["blue"]))
        self.export_btn.bind("<Leave>", lambda e: self.export_btn.config(fg=C["dim3"]))

        self.note_status_label = tk.Label(rh, text="", fg=C["dim3"], bg=C["bg"],
                                          font=("SF Pro Text", 9))
        self.note_status_label.pack(side=tk.RIGHT)

        tk.Frame(right, bg=C["divider"], height=1).pack(fill=tk.X, padx=18, pady=(8, 0))

        self.note_text = tk.Text(
            right, wrap="word", font=("SF Mono", 11), undo=True,
            bg=C["bg"], fg=C["dim1"], insertbackground=C["blue"],
            relief="flat", bd=0, padx=18, pady=12,
            selectbackground="#2a3a5a", selectforeground=C["text"],
            highlightthickness=0,
        )
        self.note_text.pack(fill=tk.BOTH, expand=True)
        self.note_text.bind("<<Modified>>", self._on_note_modified)

        # ── 상태바 ──
        self.status = tk.Label(self.root, text="", font=("SF Pro Text", 9),
                               fg=C["dim3"], bg=C["bg"], anchor="w", padx=24, pady=4)
        self.status.pack(fill=tk.X)

        # 초기 텍스트 세팅
        self._apply_lang_texts()

    # ── 다국어 텍스트 적용 ───────────────────────
    def _apply_lang_texts(self):
        self.t = I18N[self.lang]
        self.tasks_title.config(text=self._tx("tasks"))
        self.notes_title.config(text=self._tx("notes"))
        self.hist_btn.config(text=self._tx("history"))
        self.opacity_title.config(text=self._tx("opacity"))
        self.export_btn.config(text=self._tx("export_md"))
        self.lang_label.config(text=self._tx("lang_label"))
        self.lang_btn.config(text="EN" if self.lang == "ko" else "KO")
        # placeholder 갱신
        if self.task_entry.get() in [I18N["ko"]["add_placeholder"],
                                      I18N["en"]["add_placeholder"], ""]:
            self.task_entry.delete(0, tk.END)
            self.task_entry.insert(0, self._tx("add_placeholder"))
            self.task_entry.config(fg=C["dim3"])

    def _toggle_lang(self):
        self.lang = "en" if self.lang == "ko" else "ko"
        set_meta("lang", self.lang)
        self._apply_lang_texts()
        self._update_date_label()
        self._refresh_tasks()

    # ── 헬퍼 위젯 ────────────────────────────────
    def _glass_card(self, parent):
        return tk.Frame(parent, bg=C["bg"], highlightbackground=C["border"],
                        highlightthickness=1)

    def _make_nav_btn(self, parent, text, command):
        btn = tk.Label(parent, text=f" {text} ", font=("SF Pro Text", 12, "bold"),
                       fg=C["dim2"], bg=C["bg"], cursor="pointinghand")
        btn.bind("<Button-1>", lambda e: command())
        btn.bind("<Enter>", lambda e: btn.config(fg=C["text"]))
        btn.bind("<Leave>", lambda e: btn.config(fg=C["dim2"]))
        return btn

    # ── placeholder ──────────────────────────────
    def _on_entry_focus_in(self, event):
        if self.task_entry.get() == self._tx("add_placeholder"):
            self.task_entry.delete(0, tk.END)
            self.task_entry.config(fg=C["text"])

    def _on_entry_focus_out(self, event):
        if not self.task_entry.get().strip():
            self.task_entry.delete(0, tk.END)
            self.task_entry.insert(0, self._tx("add_placeholder"))
            self.task_entry.config(fg=C["dim3"])

    def _on_mousewheel(self, event):
        x, y = self.root.winfo_pointerxy()
        widget = self.root.winfo_containing(x, y)
        if widget is None:
            return
        w = widget
        while w is not None:
            if w == self.task_canvas:
                self.task_canvas.yview_scroll(int(-1 * (event.delta)), "units")
                return
            w = w.master

    # ── 데이터 갱신 ──────────────────────────────
    def refresh_all(self):
        if self.current_date == self.today_str:
            n = carry_over_tasks(self.today_str)
            if n > 0:
                self._set_status(self._tx("carried_over", n=n))
            else:
                self._set_status("")
        self._update_date_label()
        self._refresh_tasks()
        self._refresh_note()

    def _update_date_label(self):
        d = datetime.strptime(self.current_date, "%Y-%m-%d").date()
        wd = self.t["weekdays"][d.weekday()]
        self.date_label.config(text=f"{d.year}. {d.month:02d}. {d.day:02d}  ({wd})")

        if self.current_date == self.today_str:
            self.today_badge.config(text=self._tx("today"), fg=C["blue"])
        elif self.current_date == (date.today() - timedelta(days=1)).isoformat():
            self.today_badge.config(text=self._tx("yesterday"), fg=C["amber"])
        else:
            self.today_badge.config(text=self._tx("go_today"), fg=C["dim3"])

    def _refresh_tasks(self):
        for w in self.task_list_frame.winfo_children():
            w.destroy()

        tasks = fetch_tasks(self.current_date)
        done_count = sum(1 for _, _, d in tasks if d)
        total = len(tasks)
        if total > 0:
            self.task_count_label.config(
                text=f"{done_count}/{total} {self._tx('done_count')}"
            )
        else:
            self.task_count_label.config(text="")

        if not tasks:
            empty = tk.Frame(self.task_list_frame, bg=C["bg"])
            empty.pack(fill=tk.BOTH, expand=True, pady=40)
            tk.Label(empty, text=self._tx("no_tasks"), font=("SF Pro Text", 11),
                     fg=C["dim3"], bg=C["bg"]).pack()
            tk.Label(empty, text=self._tx("no_tasks_hint"),
                     font=("SF Pro Text", 10), fg=C["divider"], bg=C["bg"]).pack(pady=(3, 0))
            return

        for tid, title, done in tasks:
            self._create_task_row(tid, title, bool(done))

    def _create_task_row(self, tid, title, done):
        row = tk.Frame(self.task_list_frame, bg=C["bg"], padx=18, pady=0)
        row.pack(fill=tk.X)

        inner = tk.Frame(row, bg=C["bg"], pady=7)
        inner.pack(fill=tk.X)

        # 상태 도트
        dot_canvas = tk.Canvas(inner, width=18, height=18, bg=C["bg"], highlightthickness=0)
        dot_canvas.pack(side=tk.LEFT, padx=(0, 8))
        if done:
            dot_canvas.create_oval(5, 5, 13, 13, fill=C["green"], outline="")
        else:
            dot_canvas.create_oval(5, 5, 13, 13, fill="", outline=C["dim3"], width=1.5)

        def on_toggle(e=None):
            toggle_task(tid, not done)
            self._refresh_tasks()

        dot_canvas.bind("<Button-1>", on_toggle)
        dot_canvas.config(cursor="pointinghand")

        fg = C["dim3"] if done else C["dim1"]
        fnt = ("SF Pro Text", 11, "overstrike") if done else ("SF Pro Text", 11)
        lbl = tk.Label(inner, text=title, font=fnt, fg=fg, bg=C["bg"], anchor="w")
        lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)
        lbl.bind("<Button-1>", on_toggle)
        lbl.config(cursor="pointinghand")

        del_btn = tk.Label(inner, text="\u00d7", font=("SF Pro Text", 12),
                           fg=C["bg"], bg=C["bg"], cursor="pointinghand")
        del_btn.pack(side=tk.RIGHT, padx=(6, 0))

        all_widgets = [row, inner, lbl, dot_canvas, del_btn]

        def show_hover(e):
            del_btn.config(fg=C["red"])
            for w in all_widgets:
                try:
                    w.config(bg=C["hover"])
                except tk.TclError:
                    pass

        def hide_hover(e):
            del_btn.config(fg=C["bg"])
            for w in all_widgets:
                try:
                    w.config(bg=C["bg"])
                except tk.TclError:
                    pass

        for w in all_widgets:
            w.bind("<Enter>", show_hover)
            w.bind("<Leave>", hide_hover)

        del_btn.bind("<Button-1>", lambda e, _tid=tid: self._on_delete_task(_tid))
        tk.Frame(self.task_list_frame, bg=C["divider"], height=1).pack(fill=tk.X, padx=18)

    def _on_delete_task(self, tid):
        delete_task(tid)
        self._refresh_tasks()

    def on_add_task(self):
        title = self.task_entry.get().strip()
        if not title or title == self._tx("add_placeholder"):
            return
        add_task(self.current_date, title)
        self.task_entry.delete(0, tk.END)
        self._refresh_tasks()
        self.task_entry.focus_set()

    # ── 메모 ─────────────────────────────────────
    def _refresh_note(self):
        self.note_text.unbind("<<Modified>>")
        self.note_text.delete("1.0", tk.END)
        self.note_text.insert("1.0", fetch_note(self.current_date))
        self.note_text.edit_modified(False)
        self.note_text.bind("<<Modified>>", self._on_note_modified)
        self.note_status_label.config(text="")

    def _on_note_modified(self, event=None):
        if not self.note_text.edit_modified():
            return
        if self._note_save_after_id:
            self.root.after_cancel(self._note_save_after_id)
        self._note_save_after_id = self.root.after(1000, self._save_note_now)
        self.note_text.edit_modified(False)

    def _save_note_now(self):
        content = self.note_text.get("1.0", "end-1c")
        save_note(self.current_date, content)
        now = datetime.now().strftime("%H:%M:%S")
        self.note_status_label.config(text=f"{self._tx('saved')} {now}")

    # ── .md 내보내기 ─────────────────────────────
    def _export_md(self):
        self._save_note_now()
        d = self.current_date
        tasks = fetch_tasks(d)
        note_content = fetch_note(d)

        d_obj = datetime.strptime(d, "%Y-%m-%d").date()
        wd = self.t["weekdays"][d_obj.weekday()]

        lines = [f"# {d} ({wd})", ""]

        if tasks:
            lines.append(f"## {self._tx('tasks')}")
            lines.append("")
            for _, title, done in tasks:
                check = "x" if done else " "
                lines.append(f"- [{check}] {title}")
            lines.append("")

        if note_content.strip():
            lines.append(f"## {self._tx('notes')}")
            lines.append("")
            lines.append(note_content)
            lines.append("")

        md_text = "\n".join(lines)
        default_name = f"daily_{d}.md"

        filepath = filedialog.asksaveasfilename(
            parent=self.root,
            defaultextension=".md",
            filetypes=[("Markdown", "*.md"), ("All Files", "*.*")],
            initialfile=default_name,
        )
        if not filepath:
            return

        Path(filepath).write_text(md_text, encoding="utf-8")
        self._set_status(self._tx("export_success", path=filepath))

    # ── 날짜 이동 ────────────────────────────────
    def _shift_date(self, days):
        self._save_note_now()
        d = datetime.strptime(self.current_date, "%Y-%m-%d").date()
        self.current_date = (d + timedelta(days=days)).isoformat()
        self.refresh_all()

    def prev_day(self):
        self._shift_date(-1)

    def next_day(self):
        self._shift_date(1)

    def go_today(self):
        self._save_note_now()
        self.current_date = self.today_str
        self.refresh_all()

    # ── 히스토리 ─────────────────────────────────
    def show_history(self):
        dates = fetch_history_dates()
        if not dates:
            messagebox.showinfo(self._tx("history"), self._tx("no_records"))
            return

        win = tk.Toplevel(self.root)
        win.title(self._tx("history"))
        win.geometry("340x480")
        win.configure(bg=C["bg"])
        try:
            win.attributes("-alpha", self._opacity)
        except tk.TclError:
            pass

        tk.Label(win, text=self._tx("history"), fg=C["dim2"], bg=C["bg"],
                 font=("SF Pro Text", 9), padx=18, pady=12, anchor="w").pack(fill=tk.X)
        tk.Frame(win, bg=C["divider"], height=1).pack(fill=tk.X, padx=18)

        canvas = tk.Canvas(win, bg=C["bg"], highlightthickness=0)
        canvas.pack(fill=tk.BOTH, expand=True)
        inner = tk.Frame(canvas, bg=C["bg"])
        canvas.create_window((0, 0), window=inner, anchor="nw", tags="frame")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig("frame", width=e.width))

        for i, d_str in enumerate(dates):
            d = datetime.strptime(d_str, "%Y-%m-%d").date()
            wd = self.t["weekdays"][d.weekday()]
            label_text = f"{d.year}. {d.month:02d}. {d.day:02d}  ({wd})"

            row = tk.Frame(inner, bg=C["bg"], padx=18, pady=7)
            row.pack(fill=tk.X)

            lbl = tk.Label(row, text=label_text, font=("SF Pro Text", 11),
                           fg=C["dim1"], bg=C["bg"], anchor="w", cursor="pointinghand")
            lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)

            if d_str == self.today_str:
                tk.Label(row, text=self._tx("today"), font=("SF Pro Text", 9),
                         fg=C["blue"], bg=C["bg"], padx=4).pack(side=tk.RIGHT)

            def make_jump(idx):
                def jump(e=None):
                    self._save_note_now()
                    self.current_date = dates[idx]
                    self.refresh_all()
                    win.destroy()
                return jump

            row.bind("<Button-1>", make_jump(i))
            lbl.bind("<Button-1>", make_jump(i))

            def make_hover(r, l):
                def enter(e):
                    r.config(bg=C["hover"])
                    l.config(bg=C["hover"])
                def leave(e):
                    r.config(bg=C["bg"])
                    l.config(bg=C["bg"])
                return enter, leave

            enter_fn, leave_fn = make_hover(row, lbl)
            for w in (row, lbl):
                w.bind("<Enter>", enter_fn)
                w.bind("<Leave>", leave_fn)

            if i < len(dates) - 1:
                tk.Frame(inner, bg=C["divider"], height=1).pack(fill=tk.X, padx=18)

    # ── 투명도 ───────────────────────────────────
    def _on_opacity_change(self, value):
        alpha = float(value)
        self._opacity = alpha
        try:
            self.root.attributes("-alpha", alpha)
        except tk.TclError:
            pass
        self.opacity_label.config(text=f"{int(alpha * 100)}%")

    # ── 기타 ────────────────────────────────────
    def _set_status(self, text):
        self.status.config(text=text)

    def _on_close(self):
        self._save_note_now()
        set_meta("opacity", f"{self._opacity:.2f}")
        set_meta("lang", self.lang)
        self.root.destroy()


# ────────────────────────────────────────────────
# 실행
# ────────────────────────────────────────────────
def main():
    init_db()
    root = tk.Tk()
    SchedulerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
