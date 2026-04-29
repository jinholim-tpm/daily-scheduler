"""
Daily Scheduler - 글래스모피즘 데일리 스케줄러 GUI
- 반투명 윈도우 + 다크 테마 (투명도 저장/복원)
- 어제 미완료 할 일 자동 이월
- 체크박스로 완료 표시
- 회의록/메모 작성 + .md 내보내기
- 날짜별 히스토리 조회
- 다국어 지원 (한/영)
"""

import sys
import sqlite3
from datetime import date, timedelta, datetime
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QTextEdit, QSlider, QScrollArea,
    QFrame, QFileDialog, QMessageBox, QDialog,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QShortcut, QKeySequence

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
        "save": "저장",
        "add_child": "+ 하위 항목",
        "new_child": "새 하위 항목",
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
        "save": "Save",
        "add_child": "+ Sub-item",
        "new_child": "New sub-item",
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
                parent_id   INTEGER DEFAULT NULL,
                sort_order  INTEGER NOT NULL DEFAULT 0,
                created_at  TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (parent_id) REFERENCES tasks(id) ON DELETE CASCADE
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
        # 기존 DB 마이그레이션: parent_id, sort_order 컬럼 추가
        cols = [r[1] for r in conn.execute("PRAGMA table_info(tasks)").fetchall()]
        if "parent_id" not in cols:
            conn.execute("ALTER TABLE tasks ADD COLUMN parent_id INTEGER DEFAULT NULL")
        if "sort_order" not in cols:
            conn.execute("ALTER TABLE tasks ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 0")


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
        # 부모 태스크만 이월 (자식은 부모와 함께 이월)
        rows = conn.execute(
            "SELECT id, title FROM tasks WHERE date < ? AND done = 0 AND carried = 0 AND parent_id IS NULL",
            (today_str,),
        ).fetchall()
        for tid, title in rows:
            # 부모 이월
            conn.execute(
                "INSERT INTO tasks (date, title, done, carried, parent_id, sort_order) VALUES (?, ?, 0, 0, NULL, 0)",
                (today_str, title),
            )
            new_parent_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute("UPDATE tasks SET carried = 1 WHERE id = ?", (tid,))
            # 자식 이월
            children = conn.execute(
                "SELECT id, title FROM tasks WHERE parent_id = ? AND done = 0 AND carried = 0",
                (tid,),
            ).fetchall()
            for cid, ctitle in children:
                conn.execute(
                    "INSERT INTO tasks (date, title, done, carried, parent_id, sort_order) VALUES (?, ?, 0, 0, ?, 0)",
                    (today_str, ctitle, new_parent_id),
                )
                conn.execute("UPDATE tasks SET carried = 1 WHERE id = ?", (cid,))
        conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES ('last_carry_over', ?)",
            (today_str,),
        )
        return len(rows)


def fetch_tasks(d):
    """부모-자식 트리 구조로 반환: [(id, title, done, parent_id, sort_order, children), ...]"""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, title, done, parent_id, sort_order FROM tasks WHERE date = ? ORDER BY sort_order, id",
            (d,),
        ).fetchall()
    # 트리 구성
    parents = []
    children_map = {}
    for row in rows:
        tid, title, done, parent_id, sort_order = row
        if parent_id is None:
            parents.append({"id": tid, "title": title, "done": done,
                            "sort_order": sort_order, "children": []})
        else:
            children_map.setdefault(parent_id, []).append(
                {"id": tid, "title": title, "done": done, "sort_order": sort_order}
            )
    for p in parents:
        p["children"] = sorted(children_map.get(p["id"], []), key=lambda c: (c["sort_order"], c["id"]))
    return parents


def fetch_tasks_flat(d):
    """하위 호환: (id, title, done) 튜플 리스트 반환"""
    with get_conn() as conn:
        return conn.execute(
            "SELECT id, title, done FROM tasks WHERE date = ? ORDER BY sort_order, id",
            (d,),
        ).fetchall()


def add_task(d, title, parent_id=None):
    with get_conn() as conn:
        # 다음 sort_order 계산
        row = conn.execute(
            "SELECT COALESCE(MAX(sort_order), -1) + 1 FROM tasks WHERE date = ? AND parent_id IS ?",
            (d, parent_id),
        ).fetchone()
        sort_order = row[0]
        conn.execute(
            "INSERT INTO tasks (date, title, parent_id, sort_order) VALUES (?, ?, ?, ?)",
            (d, title.strip(), parent_id, sort_order),
        )
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def update_task_title(tid, title):
    with get_conn() as conn:
        conn.execute("UPDATE tasks SET title = ? WHERE id = ?", (title.strip(), tid))


def toggle_task(tid, done):
    with get_conn() as conn:
        conn.execute("UPDATE tasks SET done = ? WHERE id = ?", (1 if done else 0, tid))
        # 부모를 완료하면 자식도 모두 완료
        if done:
            conn.execute("UPDATE tasks SET done = 1 WHERE parent_id = ?", (tid,))


def delete_task(tid):
    with get_conn() as conn:
        # 자식도 함께 삭제 (CASCADE 또는 수동)
        conn.execute("DELETE FROM tasks WHERE parent_id = ?", (tid,))
        conn.execute("DELETE FROM tasks WHERE id = ?", (tid,))


def reorder_task(tid, new_sort_order):
    with get_conn() as conn:
        conn.execute("UPDATE tasks SET sort_order = ? WHERE id = ?", (new_sort_order, tid))


def reparent_task(tid, new_parent_id):
    """태스크의 부모를 변경. new_parent_id=None이면 최상위로 승격."""
    with get_conn() as conn:
        # 자식을 가진 태스크를 다른 태스크의 자식으로 넣으면 안 됨 (1뎁스 제한)
        if new_parent_id is not None:
            has_children = conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE parent_id = ?", (tid,)
            ).fetchone()[0]
            if has_children:
                return False
            # 대상 부모가 이미 자식이면 안 됨
            parent_row = conn.execute(
                "SELECT parent_id FROM tasks WHERE id = ?", (new_parent_id,)
            ).fetchone()
            if parent_row and parent_row[0] is not None:
                return False
        # 새 부모 아래의 다음 sort_order
        row = conn.execute(
            "SELECT COALESCE(MAX(sort_order), -1) + 1 FROM tasks WHERE parent_id IS ?",
            (new_parent_id,),
        ).fetchone()
        conn.execute(
            "UPDATE tasks SET parent_id = ?, sort_order = ? WHERE id = ?",
            (new_parent_id, row[0], tid),
        )
        return True


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
# 공통 스타일시트
# ────────────────────────────────────────────────
STYLESHEET = f"""
QMainWindow, QWidget {{ background-color: {C["bg"]}; }}
QLabel {{ color: {C["dim1"]}; font-family: "SF Pro Text", "Helvetica Neue", sans-serif; }}
QPushButton {{
    background: transparent; border: 1px solid {C["border"]};
    color: {C["dim2"]}; padding: 4px 10px; border-radius: 4px;
    font-family: "SF Pro Text", sans-serif; font-size: 11px;
}}
QPushButton:hover {{ color: {C["text"]}; border-color: {C["dim3"]}; }}
QLineEdit {{
    background-color: {C["input_bg"]}; color: {C["text"]};
    border: 1px solid {C["border"]}; border-radius: 4px;
    padding: 7px 12px; font-size: 13px;
    font-family: "SF Pro Text", sans-serif;
    selection-background-color: #2a3a5a;
}}
QTextEdit {{
    background-color: {C["bg"]}; color: {C["dim1"]};
    border: none; padding: 12px 18px;
    font-family: "SF Mono", "Menlo", monospace; font-size: 13px;
    selection-background-color: #2a3a5a; selection-color: {C["text"]};
}}
QSlider::groove:horizontal {{
    height: 4px; background: {C["border"]}; border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {C["blue"]}; width: 12px; height: 12px;
    margin: -4px 0; border-radius: 6px;
}}
QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{
    width: 6px; background: transparent;
}}
QScrollBar::handle:vertical {{
    background: {C["dim3"]}; border-radius: 3px; min-height: 20px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
"""


# ────────────────────────────────────────────────
# GUI
# ────────────────────────────────────────────────
class SchedulerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Daily Scheduler")
        self.resize(1060, 700)
        self.setMinimumSize(900, 580)
        self.setStyleSheet(STYLESHEET)

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
        self.setWindowOpacity(self._opacity)

        self.today_str = date.today().isoformat()
        self.current_date = self.today_str

        self._build_ui()
        self._setup_shortcuts()
        self.refresh_all()

    def _tx(self, key, **kwargs):
        text = self.t.get(key, key)
        if kwargs:
            text = text.format(**kwargs)
        return text

    # ── 단축키 ───────────────────────────────────
    def _setup_shortcuts(self):
        QShortcut(QKeySequence.StandardKey.Save, self, self._save_note_now)

    # ── UI 빌드 ──────────────────────────────────
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── 상단 바 ──
        topbar = QWidget()
        topbar.setFixedHeight(50)
        tb_layout = QHBoxLayout(topbar)
        tb_layout.setContentsMargins(24, 8, 24, 8)

        # 날짜 네비게이션
        self.prev_btn = QPushButton("<")
        self.prev_btn.setFixedSize(30, 30)
        self.prev_btn.setStyleSheet(f"font-weight: bold; font-size: 14px; border: none; color: {C['dim2']};")
        self.prev_btn.clicked.connect(self.prev_day)

        self.date_label = QLabel()
        self.date_label.setStyleSheet(f"color: {C['text']}; font-size: 15px; font-weight: bold;")

        self.next_btn = QPushButton(">")
        self.next_btn.setFixedSize(30, 30)
        self.next_btn.setStyleSheet(f"font-weight: bold; font-size: 14px; border: none; color: {C['dim2']};")
        self.next_btn.clicked.connect(self.next_day)

        self.today_badge = QPushButton()
        self.today_badge.setStyleSheet(f"border: none; color: {C['blue']}; font-size: 11px;")
        self.today_badge.setCursor(Qt.CursorShape.PointingHandCursor)
        self.today_badge.clicked.connect(self.go_today)

        tb_layout.addWidget(self.prev_btn)
        tb_layout.addWidget(self.date_label)
        tb_layout.addWidget(self.next_btn)
        tb_layout.addWidget(self.today_badge)
        tb_layout.addStretch()

        # 오른쪽 컨트롤
        self.lang_label = QLabel()
        self.lang_label.setStyleSheet(f"color: {C['dim3']}; font-size: 11px;")
        self.lang_btn = QPushButton()
        self.lang_btn.setStyleSheet(f"border: none; color: {C['dim2']}; font-size: 11px;")
        self.lang_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.lang_btn.clicked.connect(self._toggle_lang)

        self.opacity_title = QLabel()
        self.opacity_title.setStyleSheet(f"color: {C['dim3']}; font-size: 11px;")

        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(30, 100)
        self.opacity_slider.setValue(int(self._opacity * 100))
        self.opacity_slider.setFixedWidth(80)
        self.opacity_slider.valueChanged.connect(self._on_opacity_change)

        self.opacity_label = QLabel(f"{int(self._opacity * 100)}%")
        self.opacity_label.setStyleSheet(f"color: {C['dim2']}; font-size: 11px;")
        self.opacity_label.setFixedWidth(35)

        self.hist_btn = QPushButton()
        self.hist_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.hist_btn.clicked.connect(self.show_history)

        tb_layout.addWidget(self.lang_label)
        tb_layout.addWidget(self.lang_btn)
        tb_layout.addSpacing(12)
        tb_layout.addWidget(self.opacity_title)
        tb_layout.addWidget(self.opacity_slider)
        tb_layout.addWidget(self.opacity_label)
        tb_layout.addSpacing(12)
        tb_layout.addWidget(self.hist_btn)

        main_layout.addWidget(topbar)

        # 구분선
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet(f"color: {C['divider']};")
        divider.setFixedHeight(1)
        main_layout.addWidget(divider)

        # ── 본문 ──
        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(24, 12, 24, 12)
        body_layout.setSpacing(12)

        # ── 왼쪽: Tasks ──
        left = QWidget()
        left.setStyleSheet("")
        left.setObjectName("left")
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        # Task 헤더
        lh = QWidget()
        lh_layout = QHBoxLayout(lh)
        lh_layout.setContentsMargins(18, 12, 18, 0)
        self.tasks_title = QLabel()
        self.tasks_title.setStyleSheet(f"color: {C['dim2']}; font-size: 11px;")
        self.task_count_label = QLabel()
        self.task_count_label.setStyleSheet(f"color: {C['dim3']}; font-size: 11px;")
        lh_layout.addWidget(self.tasks_title)
        lh_layout.addStretch()
        lh_layout.addWidget(self.task_count_label)
        left_layout.addWidget(lh)


        # 입력
        input_layout = QHBoxLayout()
        input_layout.setContentsMargins(18, 16, 18, 16)
        self.task_entry = QLineEdit()
        self.task_entry.returnPressed.connect(self.on_add_task)
        add_btn = QPushButton("+")
        add_btn.setFixedSize(30, 30)
        add_btn.setStyleSheet(f"border: none; color: {C['blue']}; font-size: 18px; font-weight: bold;")
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.clicked.connect(self.on_add_task)
        input_layout.addWidget(self.task_entry)
        input_layout.addWidget(add_btn)
        left_layout.addLayout(input_layout)

        # 할 일 리스트 (스크롤)
        self.task_scroll = QScrollArea()
        self.task_scroll.setWidgetResizable(True)
        self.task_list_widget = QWidget()
        self.task_list_layout = QVBoxLayout(self.task_list_widget)
        self.task_list_layout.setContentsMargins(0, 0, 0, 0)
        self.task_list_layout.setSpacing(0)
        self.task_list_layout.addStretch()
        self.task_scroll.setWidget(self.task_list_widget)
        left_layout.addWidget(self.task_scroll)

        # ── 오른쪽: Notes ──
        right = QWidget()
        right.setStyleSheet("")
        right.setObjectName("right")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # Note 헤더
        rh = QWidget()
        rh_layout = QHBoxLayout(rh)
        rh_layout.setContentsMargins(18, 12, 18, 0)
        self.notes_title = QLabel()
        self.notes_title.setStyleSheet(f"color: {C['dim2']}; font-size: 11px;")
        rh_layout.addWidget(self.notes_title)
        rh_layout.addStretch()

        self.note_status_label = QLabel()
        self.note_status_label.setStyleSheet(f"color: {C['dim3']}; font-size: 11px;")
        rh_layout.addWidget(self.note_status_label)

        self.save_btn = QPushButton()
        self.save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_btn.setStyleSheet(f"border: none; color: {C['dim3']}; font-size: 11px;")
        self.save_btn.clicked.connect(self._save_note_now)
        rh_layout.addWidget(self.save_btn)

        self.export_btn = QPushButton()
        self.export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.export_btn.setStyleSheet(f"border: none; color: {C['dim3']}; font-size: 11px;")
        self.export_btn.clicked.connect(self._export_md)
        rh_layout.addWidget(self.export_btn)

        right_layout.addWidget(rh)


        # 메모 텍스트
        self.note_text = QTextEdit()
        self.note_text.setAcceptRichText(False)
        right_layout.addWidget(self.note_text)

        body_layout.addWidget(left, 1)
        body_layout.addWidget(right, 1)
        main_layout.addWidget(body, 1)

        # ── 상태바 ──
        self.status = QLabel()
        self.status.setStyleSheet(f"color: {C['dim3']}; font-size: 11px; padding: 4px 24px;")
        main_layout.addWidget(self.status)

        # 초기 텍스트
        self._apply_lang_texts()

    # ── 다국어 텍스트 적용 ───────────────────────
    def _apply_lang_texts(self):
        self.t = I18N[self.lang]
        self.tasks_title.setText(self._tx("tasks"))
        self.notes_title.setText(self._tx("notes"))
        self.hist_btn.setText(self._tx("history"))
        self.opacity_title.setText(self._tx("opacity"))
        self.export_btn.setText(self._tx("export_md"))
        self.save_btn.setText(self._tx("save"))
        self.lang_label.setText(self._tx("lang_label"))
        self.lang_btn.setText("EN" if self.lang == "ko" else "KO")
        self.task_entry.setPlaceholderText(self._tx("add_placeholder"))

    def _toggle_lang(self):
        self.lang = "en" if self.lang == "ko" else "ko"
        set_meta("lang", self.lang)
        self._apply_lang_texts()
        self._update_date_label()
        self._refresh_tasks()

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
        self.date_label.setText(f"{d.year}. {d.month:02d}. {d.day:02d}  ({wd})")

        if self.current_date == self.today_str:
            self.today_badge.setText(self._tx("today"))
            self.today_badge.setStyleSheet(f"border: none; color: {C['blue']}; font-size: 11px;")
        elif self.current_date == (date.today() - timedelta(days=1)).isoformat():
            self.today_badge.setText(self._tx("yesterday"))
            self.today_badge.setStyleSheet(f"border: none; color: {C['amber']}; font-size: 11px;")
        else:
            self.today_badge.setText(self._tx("go_today"))
            self.today_badge.setStyleSheet(f"border: none; color: {C['dim3']}; font-size: 11px;")

    def _refresh_tasks(self):
        # 기존 위젯 제거
        while self.task_list_layout.count():
            item = self.task_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        tasks = fetch_tasks(self.current_date)
        # 전체 카운트 (부모 + 자식)
        total = 0
        done_count = 0
        for p in tasks:
            total += 1
            if p["done"]:
                done_count += 1
            for ch in p["children"]:
                total += 1
                if ch["done"]:
                    done_count += 1

        if total > 0:
            self.task_count_label.setText(f"{done_count}/{total} {self._tx('done_count')}")
        else:
            self.task_count_label.setText("")

        if not tasks:
            empty = QLabel(f"{self._tx('no_tasks')}\n{self._tx('no_tasks_hint')}")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet(f"color: {C['dim3']}; font-size: 13px; padding: 40px;")
            self.task_list_layout.addWidget(empty)
        else:
            self._drag_source = None
            for i, task in enumerate(tasks):
                self._create_task_row(task, indent=0, index=i, total=len(tasks))
                for j, child in enumerate(task["children"]):
                    self._create_task_row(child, indent=1, parent_id=task["id"],
                                          index=j, total=len(task["children"]))
                # 하위 태스크 추가 버튼
                add_child_row = QWidget()
                acr_layout = QHBoxLayout(add_child_row)
                acr_layout.setContentsMargins(48, 2, 18, 2)
                add_child_btn = QPushButton(self._tx("add_child"))
                add_child_btn.setStyleSheet(
                    f"border: none; color: {C['dim3']}; font-size: 11px; text-align: left; padding: 2px 0;"
                )
                add_child_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                add_child_btn.clicked.connect(
                    lambda checked=False, pid=task["id"]: self._add_child_inline(pid)
                )
                acr_layout.addWidget(add_child_btn)
                acr_layout.addStretch()
                self.task_list_layout.addWidget(add_child_row)

                # 구분선 (부모 그룹 간)
                self.task_list_layout.addSpacing(8)
                div = QFrame()
                div.setFrameShape(QFrame.Shape.HLine)
                div.setStyleSheet(f"color: {C['divider']};")
                div.setFixedHeight(1)
                self.task_list_layout.addWidget(div)
                self.task_list_layout.addSpacing(8)

        self.task_list_layout.addStretch()

    def _create_task_row(self, task, indent=0, parent_id=None, index=0, total=1):
        tid = task["id"]
        title = task["title"]
        done = bool(task["done"])

        row = QWidget()
        row.setProperty("task_id", tid)
        row.setStyleSheet(f"QWidget {{ background: transparent; }} QWidget:hover {{ background: {C['hover']}; }}")
        row_layout = QHBoxLayout(row)
        left_margin = 18 + (30 * indent)
        row_layout.setContentsMargins(left_margin, 9, 18, 9)

        # 드래그 핸들
        drag_handle = QPushButton("≡")
        drag_handle.setFixedSize(24, 28)
        drag_handle.setStyleSheet(
            f"border: none; color: {C['dim3']}; font-size: 16px; font-weight: bold; padding: 0;"
        )
        drag_handle.setCursor(Qt.CursorShape.OpenHandCursor)
        drag_handle.mousePressEvent = lambda e, t=tid, idx=index: self._drag_start(t, idx, e)
        drag_handle.mouseMoveEvent = lambda e, t=tid, idx=index, tot=total, pid=parent_id: \
            self._drag_move(t, idx, tot, pid, e)
        drag_handle.mouseReleaseEvent = lambda e: self._drag_end(e)

        # 체크박스
        cb = QPushButton()
        cb.setFixedSize(24, 24)
        if done:
            cb.setText("✓")
            cb.setStyleSheet(
                f"QPushButton {{ background: {C['green']}; color: {C['bg']}; border: none; "
                f"border-radius: 5px; font-size: 15px; font-weight: bold; padding: 0; }}"
            )
        else:
            cb.setText("")
            cb.setStyleSheet(
                f"QPushButton {{ background: transparent; border: 2px solid {C['dim3']}; "
                f"border-radius: 5px; padding: 0; }}"
                f"QPushButton:hover {{ border-color: {C['blue']}; }}"
            )
        cb.setCursor(Qt.CursorShape.PointingHandCursor)
        cb.clicked.connect(lambda checked=False, t=tid, d=done: (toggle_task(t, not d), self._refresh_tasks()))

        # 텍스트 (클릭으로 인라인 편집)
        lbl = QLabel(title)
        lbl.setMinimumHeight(28)
        if done:
            lbl.setStyleSheet(f"color: {C['dim3']}; font-size: 13px; text-decoration: line-through; padding: 0 4px;")
        else:
            lbl.setStyleSheet(f"color: {C['dim1']}; font-size: 13px; padding: 0 4px;")
        lbl.setCursor(Qt.CursorShape.IBeamCursor)
        lbl.mousePressEvent = lambda e, t=tid, tit=title, l=lbl, rl=row_layout: \
            self._start_inline_edit(t, tit, l, rl)

        # 삭제 버튼 (항상 보이지만 평소엔 희미하게)
        del_btn = QPushButton("\u00d7")
        del_btn.setFixedSize(24, 24)
        del_btn.setStyleSheet(
            f"QPushButton {{ border: none; color: {C['dim3']}; font-size: 16px; padding: 0; }}"
            f"QPushButton:hover {{ color: {C['red']}; }}"
        )
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.clicked.connect(lambda checked=False, t=tid: (delete_task(t), self._refresh_tasks()))

        row_layout.addWidget(drag_handle)
        row_layout.addSpacing(4)
        row_layout.addWidget(cb)
        row_layout.addSpacing(8)
        row_layout.addWidget(lbl, 1)
        row_layout.addWidget(del_btn)

        self.task_list_layout.addWidget(row)

        if getattr(self, '_auto_edit_tid', None) == tid:
            self._start_inline_edit(tid, title, lbl, row_layout)

    def _start_inline_edit(self, tid, title, label, row_layout):
        """라벨을 QLineEdit으로 교체해서 인라인 편집"""
        edit = QLineEdit(title)
        edit.setStyleSheet(
            f"background: {C['input_bg']}; color: {C['text']}; border: 1px solid {C['blue']}; "
            f"border-radius: 3px; padding: 3px 6px; font-size: 13px;"
        )
        edit.selectAll()

        # 라벨 자리에 에디트 삽입
        idx = row_layout.indexOf(label)
        row_layout.removeWidget(label)
        label.hide()
        row_layout.insertWidget(idx, edit, 1)
        edit.setFocus()

        def finish_edit():
            new_title = edit.text().strip()
            if new_title and new_title != title:
                update_task_title(tid, new_title)
            self._refresh_tasks()

        edit.returnPressed.connect(finish_edit)
        edit.editingFinished.connect(finish_edit)

    def _add_child_inline(self, parent_id):
        """하위 태스크 인라인 추가"""
        new_id = add_task(self.current_date, self._tx("new_child"), parent_id=parent_id)
        self._auto_edit_tid = new_id
        self._refresh_tasks()
        self._auto_edit_tid = None

    # ── 드래그 앤 드롭 (순서 변경 + 부모 변경) ──────
    def _drag_start(self, tid, index, event):
        # 원본 행 찾기
        source_row = None
        for i in range(self.task_list_layout.count()):
            w = self.task_list_layout.itemAt(i).widget()
            if w and w.property("task_id") == tid:
                source_row = w
                break

        # parent_id + title 조회
        cur_parent_id = None
        title = ""
        with get_conn() as conn:
            row = conn.execute("SELECT parent_id, title FROM tasks WHERE id = ?", (tid,)).fetchone()
            if row:
                cur_parent_id, title = row[0], row[1]

        self._drag_source = {
            "tid": tid, "index": index,
            "start_x": event.globalPosition().x(),
            "start_y": event.globalPosition().y(),
            "parent_id": cur_parent_id,
        }

        # 원본 행 흐리게
        if source_row:
            source_row.setStyleSheet(f"background: {C['surface']}; opacity: 0.3;")

        # 플로팅 드래그 위젯 생성
        self._drag_widget = QLabel(f"  ≡  {title}")
        self._drag_widget.setParent(self)
        self._drag_widget.setStyleSheet(
            f"background: {C['surface_strong']}; color: {C['text']}; "
            f"border: 1px solid {C['blue']}; border-radius: 6px; "
            f"padding: 8px 14px; font-size: 13px;"
        )
        self._drag_widget.setFixedHeight(38)
        self._drag_widget.adjustSize()
        # 마우스 위치에 표시
        local_pos = self.mapFromGlobal(event.globalPosition().toPoint())
        self._drag_widget.move(local_pos.x() - 20, local_pos.y() - 19)
        self._drag_widget.show()
        self._drag_widget.raise_()

    def _drag_move(self, tid, index, total, parent_id, event):
        if not self._drag_source or self._drag_source["tid"] != tid:
            return
        # 플로팅 위젯을 마우스 따라 이동
        if hasattr(self, '_drag_widget') and self._drag_widget:
            local_pos = self.mapFromGlobal(event.globalPosition().toPoint())
            self._drag_widget.move(local_pos.x() - 20, local_pos.y() - 19)

    def _drag_end(self, event):
        if not self._drag_source:
            return
        source = self._drag_source
        self._drag_source = None

        # 플로팅 위젯 제거
        if hasattr(self, '_drag_widget') and self._drag_widget:
            self._drag_widget.deleteLater()
            self._drag_widget = None

        tid = source["tid"]
        parent_id = source.get("parent_id")
        dx = event.globalPosition().x() - source["start_x"]
        dy = event.globalPosition().y() - source["start_y"]

        indent_threshold = 50
        row_height = 40
        action = None

        if abs(dx) > indent_threshold and abs(dx) > abs(dy):
            if dx > 0:
                action = "indent"
            else:
                action = "outdent"
        elif abs(dy) > row_height / 2:
            action = "reorder"

        if action == "indent":
            tasks = fetch_tasks(self.current_date)
            prev_parent = None
            for p in tasks:
                if p["id"] == tid:
                    break
                prev_parent = p
            if prev_parent and parent_id is None:
                reparent_task(tid, prev_parent["id"])

        elif action == "outdent":
            if parent_id is not None:
                reparent_task(tid, None)

        elif action == "reorder":
            steps = int(dy / row_height)
            with get_conn() as conn:
                siblings = conn.execute(
                    "SELECT id FROM tasks WHERE date = ? AND parent_id IS ? ORDER BY sort_order, id",
                    (self.current_date, parent_id),
                ).fetchall()
            ids = [r[0] for r in siblings]
            if tid in ids:
                old_pos = ids.index(tid)
                new_index = max(0, min(len(ids) - 1, old_pos + steps))
                if new_index != old_pos:
                    ids.pop(old_pos)
                    ids.insert(new_index, tid)
                    for order, task_id in enumerate(ids):
                        reorder_task(task_id, order)
                    action = "done"

        if action:
            self._refresh_tasks()

    def on_add_task(self):
        title = self.task_entry.text().strip()
        if not title:
            return
        add_task(self.current_date, title)
        self.task_entry.clear()
        self._refresh_tasks()
        self.task_entry.setFocus()

    # ── 메모 ─────────────────────────────────────
    def _refresh_note(self):
        self.note_text.setPlainText(fetch_note(self.current_date))
        self.note_status_label.setText("")

    def _save_note_now(self):
        content = self.note_text.toPlainText()
        save_note(self.current_date, content)
        now = datetime.now().strftime("%H:%M:%S")
        self.note_status_label.setText(f"{self._tx('saved')} {now}")

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
            for p in tasks:
                check = "x" if p["done"] else " "
                lines.append(f"- [{check}] {p['title']}")
                for ch in p["children"]:
                    check = "x" if ch["done"] else " "
                    lines.append(f"  - [{check}] {ch['title']}")
            lines.append("")

        if note_content.strip():
            lines.append(f"## {self._tx('notes')}")
            lines.append("")
            lines.append(note_content)
            lines.append("")

        md_text = "\n".join(lines)
        default_name = f"daily_{d}.md"

        filepath, _ = QFileDialog.getSaveFileName(
            self, self._tx("export_md"), default_name,
            "Markdown (*.md);;All Files (*.*)"
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
            QMessageBox.information(self, self._tx("history"), self._tx("no_records"))
            return

        dlg = QDialog(self)
        dlg.setWindowTitle(self._tx("history"))
        dlg.resize(340, 480)
        dlg.setStyleSheet(STYLESHEET)
        dlg.setWindowOpacity(self._opacity)

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QLabel(self._tx("history"))
        header.setStyleSheet(f"color: {C['dim2']}; font-size: 11px; padding: 12px 18px;")
        layout.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(0, 0, 0, 0)
        inner_layout.setSpacing(0)

        for i, d_str in enumerate(dates):
            d = datetime.strptime(d_str, "%Y-%m-%d").date()
            wd = self.t["weekdays"][d.weekday()]
            label_text = f"{d.year}. {d.month:02d}. {d.day:02d}  ({wd})"

            row = QPushButton(label_text)
            row.setStyleSheet(f"""
                QPushButton {{
                    text-align: left; border: none; padding: 10px 18px;
                    color: {C['dim1']}; font-size: 13px;
                }}
                QPushButton:hover {{ background: {C['hover']}; }}
            """)
            row.setCursor(Qt.CursorShape.PointingHandCursor)

            def make_jump(idx):
                def jump():
                    self._save_note_now()
                    self.current_date = dates[idx]
                    self.refresh_all()
                    dlg.close()
                return jump

            row.clicked.connect(make_jump(i))
            inner_layout.addWidget(row)

            if i < len(dates) - 1:
                div = QFrame()
                div.setFrameShape(QFrame.Shape.HLine)
                div.setStyleSheet(f"color: {C['divider']};")
                div.setFixedHeight(1)
                inner_layout.addWidget(div)

        inner_layout.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll)
        dlg.exec()

    # ── 투명도 ───────────────────────────────────
    def _on_opacity_change(self, value):
        alpha = value / 100.0
        self._opacity = alpha
        self.setWindowOpacity(alpha)
        self.opacity_label.setText(f"{value}%")

    # ── 기타 ────────────────────────────────────
    def _set_status(self, text):
        self.status.setText(text)

    def closeEvent(self, event):
        self._save_note_now()
        set_meta("opacity", f"{self._opacity:.2f}")
        set_meta("lang", self.lang)
        event.accept()


# ────────────────────────────────────────────────
# 실행
# ────────────────────────────────────────────────
def main():
    init_db()
    app = QApplication(sys.argv)
    window = SchedulerApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
