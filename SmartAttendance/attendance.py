"""
attendance.py — AttendanceManager
Smart Barcode Attendance Management System

All attendance business rules live here. The GUI and scanner modules
call into this layer; they never touch the database directly.
"""

from datetime import datetime
from database import DatabaseManager


class AttendanceManager:
    """
    Business-logic wrapper around DatabaseManager for attendance operations.

    Keeping rules here (rather than in the GUI or database layer) makes
    it trivial to change policies — e.g. the late threshold — in one place.
    """

    # ── Policy constants ──────────────────────────────────────────────
    LATE_HOUR:   int = 8   # Students arriving after HH:MM are marked Late
    LATE_MINUTE: int = 0

    def __init__(self, db: DatabaseManager):
        self.db = db

    # ------------------------------------------------------------------ #
    # Core scan processing                                                 #
    # ------------------------------------------------------------------ #

    def process_scan(self, barcode: str) -> dict:
        """
        Main entry point called after every successful barcode decode.

        Parameters
        ----------
        barcode : str  — raw barcode string from scanner

        Returns
        -------
        dict with keys:
            success   : bool
            student   : dict | None
            status    : 'Present' | 'Late' | None
            message   : human-readable outcome
            already   : bool  — True if attendance was already marked today
        """
        result = {
            "success": False,
            "student": None,
            "status":  None,
            "message": "",
            "already": False,
        }

        barcode = (barcode or "").strip()
        if not barcode:
            result["message"] = "Empty barcode data received."
            return result

        # ── 1. Resolve student ────────────────────────────────────────
        student = self.db.get_student_by_barcode(barcode)
        if not student:
            result["message"] = f"No student found for barcode: {barcode}"
            return result

        result["student"] = student

        # ── 2. Duplicate guard ────────────────────────────────────────
        existing = self.db.check_attendance_today(student["student_id"])
        if existing:
            result["already"]  = True
            result["success"]  = True          # we found the student — not an error
            result["status"]   = existing["status"]
            result["message"]  = (
                f"Attendance already marked today — "
                f"{existing['status']} at {existing['time']}"
            )
            return result

        # ── 3. Determine Present / Late ───────────────────────────────
        status = self._determine_status()

        # ── 4. Persist ────────────────────────────────────────────────
        ok, msg = self.db.mark_attendance(student["student_id"], status)
        result["success"] = ok
        result["status"]  = status if ok else None
        result["message"] = (
            f"Attendance marked as {status} at "
            f"{datetime.now().strftime('%H:%M:%S')}"
            if ok else msg
        )
        return result

    def _determine_status(self) -> str:
        """Return 'Present' or 'Late' based on the current wall-clock time."""
        now       = datetime.now()
        threshold = now.replace(
            hour=self.LATE_HOUR, minute=self.LATE_MINUTE,
            second=0, microsecond=0
        )
        return "Present" if now <= threshold else "Late"

    # ------------------------------------------------------------------ #
    # Query helpers used by dashboard / views                              #
    # ------------------------------------------------------------------ #

    def get_dashboard_stats(self) -> dict:
        return self.db.get_today_stats()

    def get_today_attendance(self) -> list[dict]:
        today = datetime.now().strftime("%Y-%m-%d")
        return self.db.get_attendance_by_date(today)

    def get_attendance_by_date(self, date: str) -> list[dict]:
        return self.db.get_attendance_by_date(date)

    def get_absent_students(self, date: str | None = None) -> list[dict]:
        """
        Return a list of students who have NOT been marked for the given date.
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        all_students  = {s["student_id"]: s for s in self.db.get_all_students()}
        present_ids   = {r["student_id"]
                         for r in self.db.get_attendance_by_date(date)}
        absent        = [s for sid, s in all_students.items()
                         if sid not in present_ids]
        return absent

    def get_student_attendance_percentage(self, student_id: str) -> float:
        """
        Attendance % = (days marked / total school days seen in DB) × 100.
        Uses the date range from the first attendance record to today.
        """
        records = self.db.get_student_attendance_summary(student_id)
        if not records:
            return 0.0

        from datetime import timedelta
        first_date = datetime.strptime(records[-1]["date"], "%Y-%m-%d")
        today      = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        # Count working days (Mon–Sat) in the range
        total_days = 0
        d = first_date
        while d <= today:
            if d.weekday() < 6:   # 0=Mon … 5=Sat
                total_days += 1
            d += timedelta(days=1)

        return round(len(records) / max(total_days, 1) * 100, 1)
