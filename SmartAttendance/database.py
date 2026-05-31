"""
database.py — DatabaseManager
Smart Barcode Attendance Management System

Handles all SQLite database operations. Designed with a modular
interface so it can be consumed identically by a future ESP32/Arduino
hardware layer — just swap the scanner, keep this module unchanged.
"""

import sqlite3
import os
import hashlib
from datetime import datetime


class DatabaseManager:
    """
    Central data-access layer.
    All queries go through this class; no raw SQL anywhere else in the project.
    """

    def __init__(self, db_path: str = "database/school.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._initialize_database()

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row          # rows behave like dicts
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _initialize_database(self):
        """Create all tables and seed the default admin on first run."""
        with self._get_connection() as conn:
            c = conn.cursor()

            # ── Students ──────────────────────────────────────────────
            c.execute("""
                CREATE TABLE IF NOT EXISTS students (
                    student_id      TEXT PRIMARY KEY,
                    name            TEXT NOT NULL,
                    class           TEXT NOT NULL,
                    section         TEXT NOT NULL,
                    barcode_number  TEXT UNIQUE NOT NULL,
                    phone_number    TEXT DEFAULT '',
                    photo_path      TEXT DEFAULT '',
                    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # ── Attendance ────────────────────────────────────────────
            c.execute("""
                CREATE TABLE IF NOT EXISTS attendance (
                    attendance_id  INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id     TEXT    NOT NULL,
                    date           DATE    NOT NULL,
                    time           TIME    NOT NULL,
                    status         TEXT    NOT NULL
                                   CHECK(status IN ('Present','Late')),
                    FOREIGN KEY (student_id) REFERENCES students(student_id)
                                   ON DELETE CASCADE,
                    UNIQUE(student_id, date)            -- one record per day
                )
            """)

            # ── Admins ────────────────────────────────────────────────
            c.execute("""
                CREATE TABLE IF NOT EXISTS admins (
                    admin_id       INTEGER PRIMARY KEY AUTOINCREMENT,
                    username       TEXT UNIQUE NOT NULL,
                    password_hash  TEXT NOT NULL,
                    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Seed default admin: admin / admin123
            default_hash = hashlib.sha256("admin123".encode()).hexdigest()
            c.execute("""
                INSERT OR IGNORE INTO admins (username, password_hash)
                VALUES (?, ?)
            """, ("admin", default_hash))

            conn.commit()

    # ================================================================== #
    # STUDENT OPERATIONS                                                   #
    # ================================================================== #

    def add_student(self, student_id: str, name: str, class_: str,
                    section: str, barcode_number: str,
                    phone_number: str = "", photo_path: str = "") -> tuple:
        """Insert a new student. Returns (bool, message)."""
        try:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT INTO students
                        (student_id, name, class, section,
                         barcode_number, phone_number, photo_path)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (student_id, name, class_, section,
                      barcode_number, phone_number, photo_path))
                conn.commit()
            return True, "Student added successfully"
        except sqlite3.IntegrityError as e:
            if "student_id" in str(e):
                return False, "Student ID already exists"
            if "barcode_number" in str(e):
                return False, "Barcode number already registered"
            return False, str(e)
        except Exception as e:
            return False, f"Unexpected error: {e}"

    def get_student_by_barcode(self, barcode: str) -> dict | None:
        """Look up a student by their barcode number."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM students WHERE barcode_number = ?", (barcode,)
            ).fetchone()
        return dict(row) if row else None

    def get_student_by_id(self, student_id: str) -> dict | None:
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM students WHERE student_id = ?", (student_id,)
            ).fetchone()
        return dict(row) if row else None

    def get_all_students(self) -> list[dict]:
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM students ORDER BY name"
            ).fetchall()
        return [dict(r) for r in rows]

    def update_student(self, student_id: str, **kwargs) -> tuple:
        """Update arbitrary student fields by keyword. Returns (bool, message)."""
        if not kwargs:
            return False, "No fields to update"
        fields = ", ".join(f"{k} = ?" for k in kwargs)
        values = list(kwargs.values()) + [student_id]
        try:
            with self._get_connection() as conn:
                conn.execute(
                    f"UPDATE students SET {fields} WHERE student_id = ?", values
                )
                conn.commit()
            return True, "Student updated successfully"
        except Exception as e:
            return False, str(e)

    def delete_student(self, student_id: str) -> tuple:
        try:
            with self._get_connection() as conn:
                conn.execute(
                    "DELETE FROM students WHERE student_id = ?", (student_id,)
                )
                conn.commit()
            return True, "Student deleted successfully"
        except Exception as e:
            return False, str(e)

    def get_student_count(self) -> int:
        with self._get_connection() as conn:
            return conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]

    # ================================================================== #
    # ATTENDANCE OPERATIONS                                                #
    # ================================================================== #

    def mark_attendance(self, student_id: str, status: str) -> tuple:
        """
        Record attendance for today.
        Raises no exception; returns (bool, message) so callers stay clean.
        """
        today = datetime.now().strftime("%Y-%m-%d")
        now   = datetime.now().strftime("%H:%M:%S")
        try:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT INTO attendance (student_id, date, time, status)
                    VALUES (?, ?, ?, ?)
                """, (student_id, today, now, status))
                conn.commit()
            return True, "Attendance marked successfully"
        except sqlite3.IntegrityError:
            return False, "Attendance already marked for today"
        except Exception as e:
            return False, f"Database error: {e}"

    def check_attendance_today(self, student_id: str) -> dict | None:
        """Return today's attendance record for a student, or None."""
        today = datetime.now().strftime("%Y-%m-%d")
        with self._get_connection() as conn:
            row = conn.execute("""
                SELECT * FROM attendance
                WHERE student_id = ? AND date = ?
            """, (student_id, today)).fetchone()
        return dict(row) if row else None

    def get_attendance_by_date(self, date: str) -> list[dict]:
        """All attendance records for a given date (YYYY-MM-DD)."""
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT a.attendance_id, a.student_id, s.name,
                       s.class, s.section, a.date, a.time, a.status
                FROM   attendance a
                JOIN   students   s ON a.student_id = s.student_id
                WHERE  a.date = ?
                ORDER  BY a.time
            """, (date,)).fetchall()
        return [dict(r) for r in rows]

    def get_all_attendance(self) -> list[dict]:
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT a.attendance_id, a.student_id, s.name,
                       s.class, s.section, a.date, a.time, a.status
                FROM   attendance a
                JOIN   students   s ON a.student_id = s.student_id
                ORDER  BY a.date DESC, a.time DESC
            """).fetchall()
        return [dict(r) for r in rows]

    def get_student_attendance_summary(self, student_id: str) -> list[dict]:
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM attendance
                WHERE  student_id = ?
                ORDER  BY date DESC
            """, (student_id,)).fetchall()
        return [dict(r) for r in rows]

    def get_today_stats(self) -> dict:
        """
        Returns a dict with total, present, late, absent, percentage.
        Powers the dashboard stat cards.
        """
        today = datetime.now().strftime("%Y-%m-%d")
        with self._get_connection() as conn:
            total   = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
            present = conn.execute("""
                SELECT COUNT(*) FROM attendance
                WHERE date = ? AND status = 'Present'
            """, (today,)).fetchone()[0]
            late    = conn.execute("""
                SELECT COUNT(*) FROM attendance
                WHERE date = ? AND status = 'Late'
            """, (today,)).fetchone()[0]

        marked     = present + late
        absent     = max(0, total - marked)
        percentage = round((marked / total * 100) if total > 0 else 0, 1)

        return {
            "total":      total,
            "present":    present,
            "late":       late,
            "absent":     absent,
            "percentage": percentage,
        }

    def get_monthly_attendance(self, year: int, month: int) -> list[dict]:
        """Day-level aggregation for charting."""
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT date, COUNT(*) AS count
                FROM   attendance
                WHERE  strftime('%Y', date) = ?
                  AND  strftime('%m', date) = ?
                GROUP  BY date
                ORDER  BY date
            """, (str(year), str(month).zfill(2))).fetchall()
        return [dict(r) for r in rows]

    def get_attendance_range(self, start_date: str, end_date: str) -> list[dict]:
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT a.*, s.name, s.class, s.section
                FROM   attendance a
                JOIN   students   s ON a.student_id = s.student_id
                WHERE  a.date BETWEEN ? AND ?
                ORDER  BY a.date, a.time
            """, (start_date, end_date)).fetchall()
        return [dict(r) for r in rows]

    # ================================================================== #
    # ADMIN OPERATIONS                                                     #
    # ================================================================== #

    def verify_admin(self, username: str, password: str) -> bool:
        pw_hash = hashlib.sha256(password.encode()).hexdigest()
        with self._get_connection() as conn:
            row = conn.execute("""
                SELECT 1 FROM admins
                WHERE username = ? AND password_hash = ?
            """, (username, pw_hash)).fetchone()
        return row is not None

    def change_password(self, username: str,
                        old_password: str, new_password: str) -> tuple:
        if not self.verify_admin(username, old_password):
            return False, "Current password is incorrect"
        new_hash = hashlib.sha256(new_password.encode()).hexdigest()
        try:
            with self._get_connection() as conn:
                conn.execute("""
                    UPDATE admins SET password_hash = ?
                    WHERE username = ?
                """, (new_hash, username))
                conn.commit()
            return True, "Password changed successfully"
        except Exception as e:
            return False, str(e)

    # ================================================================== #
    # SEED / DEMO DATA                                                     #
    # ================================================================== #

    def seed_demo_data(self):
        """
        Populate the database with 10 sample students so the app is
        immediately usable out of the box.
        """
        students = [
            ("STU001", "Aditya Sharma",   "10", "A", "BAR001", "9876543210"),
            ("STU002", "Priya Patel",     "10", "A", "BAR002", "9876543211"),
            ("STU003", "Rahul Verma",     "10", "B", "BAR003", "9876543212"),
            ("STU004", "Sneha Singh",     "10", "B", "BAR004", "9876543213"),
            ("STU005", "Arjun Nair",      "11", "A", "BAR005", "9876543214"),
            ("STU006", "Kavya Reddy",     "11", "A", "BAR006", "9876543215"),
            ("STU007", "Rohan Mehta",     "11", "B", "BAR007", "9876543216"),
            ("STU008", "Divya Joshi",     "11", "B", "BAR008", "9876543217"),
            ("STU009", "Kiran Kumar",     "12", "A", "BAR009", "9876543218"),
            ("STU010", "Meera Iyer",      "12", "A", "BAR010", "9876543219"),
        ]
        for s in students:
            self.add_student(*s)
