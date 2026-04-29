"""
Daily Scheduler 회귀 테스트
- DB 함수 (CRUD, carry_over, history)
- 비즈니스 로직 (날짜, 이월)
- 다국어 (I18N)
- 한글 텍스트 처리

GUI 레이어와 독립적으로 핵심 로직을 검증합니다.
"""

import os
import sqlite3
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

# 테스트용 임시 DB를 사용하도록 패치
_test_db = None


def _get_test_conn():
    conn = sqlite3.connect(_test_db)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# daily_scheduler 모듈을 import하기 전에 DB 경로 패치 준비
import daily_scheduler as ds


class BaseDBTestCase(unittest.TestCase):
    """각 테스트마다 새로운 임시 DB를 생성"""

    def setUp(self):
        global _test_db
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        _test_db = self._tmp.name
        # get_conn을 테스트용으로 교체
        self._orig_get_conn = ds.get_conn
        ds.get_conn = _get_test_conn
        ds.init_db()

    def tearDown(self):
        ds.get_conn = self._orig_get_conn
        os.unlink(self._tmp.name)


# ────────────────────────────────────────────────
# 1. 메타 데이터 테스트
# ────────────────────────────────────────────────
class TestMeta(BaseDBTestCase):

    def test_get_meta_default(self):
        self.assertIsNone(ds.get_meta("nonexistent"))
        self.assertEqual(ds.get_meta("nonexistent", "fallback"), "fallback")

    def test_set_and_get_meta(self):
        ds.set_meta("lang", "ko")
        self.assertEqual(ds.get_meta("lang"), "ko")

    def test_set_meta_overwrite(self):
        ds.set_meta("opacity", "0.8")
        ds.set_meta("opacity", "0.5")
        self.assertEqual(ds.get_meta("opacity"), "0.5")


# ────────────────────────────────────────────────
# 2. 할 일 CRUD 테스트
# ────────────────────────────────────────────────
class TestTaskCRUD(BaseDBTestCase):

    def test_add_and_fetch_task(self):
        ds.add_task("2026-04-29", "테스트 할 일")
        tasks = ds.fetch_tasks("2026-04-29")
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0][1], "테스트 할 일")
        self.assertEqual(tasks[0][2], 0)  # done=False

    def test_add_task_strips_whitespace(self):
        ds.add_task("2026-04-29", "  공백 테스트  ")
        tasks = ds.fetch_tasks("2026-04-29")
        self.assertEqual(tasks[0][1], "공백 테스트")

    def test_toggle_task(self):
        ds.add_task("2026-04-29", "완료 테스트")
        tasks = ds.fetch_tasks("2026-04-29")
        tid = tasks[0][0]

        ds.toggle_task(tid, True)
        tasks = ds.fetch_tasks("2026-04-29")
        self.assertEqual(tasks[0][2], 1)

        ds.toggle_task(tid, False)
        tasks = ds.fetch_tasks("2026-04-29")
        self.assertEqual(tasks[0][2], 0)

    def test_delete_task(self):
        ds.add_task("2026-04-29", "삭제 테스트")
        tasks = ds.fetch_tasks("2026-04-29")
        tid = tasks[0][0]

        ds.delete_task(tid)
        tasks = ds.fetch_tasks("2026-04-29")
        self.assertEqual(len(tasks), 0)

    def test_fetch_tasks_empty(self):
        tasks = ds.fetch_tasks("2026-04-29")
        self.assertEqual(tasks, [])

    def test_fetch_tasks_ordered_by_done_then_id(self):
        ds.add_task("2026-04-29", "작업1")
        ds.add_task("2026-04-29", "작업2")
        ds.add_task("2026-04-29", "작업3")
        tasks = ds.fetch_tasks("2026-04-29")
        # 작업2를 완료로
        ds.toggle_task(tasks[1][0], True)
        tasks = ds.fetch_tasks("2026-04-29")
        # 미완료(작업1, 작업3)가 먼저, 완료(작업2)가 뒤
        self.assertEqual(tasks[0][1], "작업1")
        self.assertEqual(tasks[1][1], "작업3")
        self.assertEqual(tasks[2][1], "작업2")

    def test_tasks_isolated_by_date(self):
        ds.add_task("2026-04-29", "오늘 할 일")
        ds.add_task("2026-04-30", "내일 할 일")
        self.assertEqual(len(ds.fetch_tasks("2026-04-29")), 1)
        self.assertEqual(len(ds.fetch_tasks("2026-04-30")), 1)
        self.assertEqual(ds.fetch_tasks("2026-04-29")[0][1], "오늘 할 일")


# ────────────────────────────────────────────────
# 3. 메모 CRUD 테스트
# ────────────────────────────────────────────────
class TestNoteCRUD(BaseDBTestCase):

    def test_fetch_note_empty(self):
        self.assertEqual(ds.fetch_note("2026-04-29"), "")

    def test_save_and_fetch_note(self):
        ds.save_note("2026-04-29", "오늘의 메모")
        self.assertEqual(ds.fetch_note("2026-04-29"), "오늘의 메모")

    def test_save_note_overwrite(self):
        ds.save_note("2026-04-29", "첫 번째")
        ds.save_note("2026-04-29", "두 번째")
        self.assertEqual(ds.fetch_note("2026-04-29"), "두 번째")

    def test_note_with_korean_special_chars(self):
        content = "한글 테스트: ㄱㄴㄷ ㅏㅓㅗ 가나다 ~!@#$%"
        ds.save_note("2026-04-29", content)
        self.assertEqual(ds.fetch_note("2026-04-29"), content)

    def test_note_with_multiline(self):
        content = "첫째 줄\n둘째 줄\n셋째 줄"
        ds.save_note("2026-04-29", content)
        self.assertEqual(ds.fetch_note("2026-04-29"), content)

    def test_note_empty_string(self):
        ds.save_note("2026-04-29", "내용")
        ds.save_note("2026-04-29", "")
        self.assertEqual(ds.fetch_note("2026-04-29"), "")


# ────────────────────────────────────────────────
# 4. 이월 (carry_over) 테스트
# ────────────────────────────────────────────────
class TestCarryOver(BaseDBTestCase):

    def test_carry_over_incomplete_tasks(self):
        ds.add_task("2026-04-28", "미완료 작업1")
        ds.add_task("2026-04-28", "미완료 작업2")
        count = ds.carry_over_tasks("2026-04-29")
        self.assertEqual(count, 2)

        # 오늘 날짜에 이월된 작업 확인
        tasks = ds.fetch_tasks("2026-04-29")
        titles = [t[1] for t in tasks]
        self.assertIn("미완료 작업1", titles)
        self.assertIn("미완료 작업2", titles)

    def test_carry_over_skips_completed_tasks(self):
        ds.add_task("2026-04-28", "완료된 작업")
        tasks = ds.fetch_tasks("2026-04-28")
        ds.toggle_task(tasks[0][0], True)

        count = ds.carry_over_tasks("2026-04-29")
        self.assertEqual(count, 0)
        self.assertEqual(len(ds.fetch_tasks("2026-04-29")), 0)

    def test_carry_over_idempotent(self):
        ds.add_task("2026-04-28", "미완료 작업")
        ds.carry_over_tasks("2026-04-29")
        # 두 번째 호출은 중복 이월하지 않아야 함
        count = ds.carry_over_tasks("2026-04-29")
        self.assertEqual(count, 0)
        self.assertEqual(len(ds.fetch_tasks("2026-04-29")), 1)

    def test_carry_over_marks_original_as_carried(self):
        ds.add_task("2026-04-28", "이월 대상")
        ds.carry_over_tasks("2026-04-29")
        # 원본이 carried=1로 마킹되어 재이월 방지
        with _get_test_conn() as conn:
            row = conn.execute(
                "SELECT carried FROM tasks WHERE date = '2026-04-28'"
            ).fetchone()
            self.assertEqual(row[0], 1)

    def test_carry_over_mixed_dates(self):
        ds.add_task("2026-04-26", "이틀 전 작업")
        ds.add_task("2026-04-27", "어제 작업")
        ds.add_task("2026-04-28", "오늘 이전 작업")
        count = ds.carry_over_tasks("2026-04-29")
        self.assertEqual(count, 3)


# ────────────────────────────────────────────────
# 5. 히스토리 테스트
# ────────────────────────────────────────────────
class TestHistory(BaseDBTestCase):

    def test_history_empty(self):
        self.assertEqual(ds.fetch_history_dates(), [])

    def test_history_from_tasks(self):
        ds.add_task("2026-04-28", "작업")
        ds.add_task("2026-04-29", "작업")
        dates = ds.fetch_history_dates()
        self.assertEqual(dates, ["2026-04-29", "2026-04-28"])  # DESC 정렬

    def test_history_from_notes(self):
        ds.save_note("2026-04-27", "메모")
        dates = ds.fetch_history_dates()
        self.assertIn("2026-04-27", dates)

    def test_history_excludes_empty_notes(self):
        ds.save_note("2026-04-27", "")
        ds.add_task("2026-04-29", "작업")
        dates = ds.fetch_history_dates()
        self.assertNotIn("2026-04-27", dates)

    def test_history_no_duplicates(self):
        ds.add_task("2026-04-29", "작업1")
        ds.add_task("2026-04-29", "작업2")
        ds.save_note("2026-04-29", "메모")
        dates = ds.fetch_history_dates()
        self.assertEqual(dates.count("2026-04-29"), 1)

    def test_history_limit(self):
        for i in range(10):
            d = (date(2026, 4, 1) + timedelta(days=i)).isoformat()
            ds.add_task(d, f"작업{i}")
        dates = ds.fetch_history_dates(limit=5)
        self.assertEqual(len(dates), 5)

    def test_history_desc_order(self):
        ds.add_task("2026-04-01", "작업")
        ds.add_task("2026-04-15", "작업")
        ds.add_task("2026-04-10", "작업")
        dates = ds.fetch_history_dates()
        self.assertEqual(dates, ["2026-04-15", "2026-04-10", "2026-04-01"])


# ────────────────────────────────────────────────
# 6. 다국어 (I18N) 테스트
# ────────────────────────────────────────────────
class TestI18N(unittest.TestCase):

    def test_all_keys_present_in_both_languages(self):
        ko_keys = set(ds.I18N["ko"].keys())
        en_keys = set(ds.I18N["en"].keys())
        self.assertEqual(ko_keys, en_keys,
                         f"누락된 키: ko-en={ko_keys - en_keys}, en-ko={en_keys - ko_keys}")

    def test_weekdays_count(self):
        self.assertEqual(len(ds.I18N["ko"]["weekdays"]), 7)
        self.assertEqual(len(ds.I18N["en"]["weekdays"]), 7)

    def test_format_placeholders(self):
        # carried_over에 {n} 플레이스홀더가 있어야 함
        self.assertIn("{n}", ds.I18N["ko"]["carried_over"])
        self.assertIn("{n}", ds.I18N["en"]["carried_over"])
        # export_success에 {path} 플레이스홀더가 있어야 함
        self.assertIn("{path}", ds.I18N["ko"]["export_success"])
        self.assertIn("{path}", ds.I18N["en"]["export_success"])

    def test_format_works(self):
        text = ds.I18N["ko"]["carried_over"].format(n=3)
        self.assertIn("3", text)


# ────────────────────────────────────────────────
# 7. 한글 텍스트 무결성 테스트
# ────────────────────────────────────────────────
class TestKoreanText(BaseDBTestCase):

    def test_korean_task_roundtrip(self):
        ds.add_task("2026-04-29", "한글 작업 테스트")
        tasks = ds.fetch_tasks("2026-04-29")
        self.assertEqual(tasks[0][1], "한글 작업 테스트")

    def test_korean_note_roundtrip(self):
        content = "가나다라마바사 아자차카타파하"
        ds.save_note("2026-04-29", content)
        self.assertEqual(ds.fetch_note("2026-04-29"), content)

    def test_korean_composing_chars(self):
        """자모 단위 한글도 정상 저장/조회"""
        content = "ㄱㄴㄷㄹㅁㅂㅅ ㅏㅓㅗㅜㅡㅣ"
        ds.save_note("2026-04-29", content)
        self.assertEqual(ds.fetch_note("2026-04-29"), content)

    def test_mixed_korean_english(self):
        ds.add_task("2026-04-29", "회의 at 3pm 준비")
        tasks = ds.fetch_tasks("2026-04-29")
        self.assertEqual(tasks[0][1], "회의 at 3pm 준비")

    def test_korean_emoji_mixed(self):
        content = "오늘 할 일 완료! 🎉✅"
        ds.save_note("2026-04-29", content)
        self.assertEqual(ds.fetch_note("2026-04-29"), content)


# ────────────────────────────────────────────────
# 8. 컬러 팔레트 테스트
# ────────────────────────────────────────────────
class TestColorPalette(unittest.TestCase):

    def test_all_colors_are_hex(self):
        for key, value in ds.C.items():
            self.assertTrue(value.startswith("#"),
                            f"C['{key}'] = {value!r} is not a hex color")

    def test_required_colors_exist(self):
        required = ["bg", "text", "blue", "green", "red", "border", "divider"]
        for key in required:
            self.assertIn(key, ds.C, f"필수 컬러 '{key}'가 누락됨")


if __name__ == "__main__":
    unittest.main()
