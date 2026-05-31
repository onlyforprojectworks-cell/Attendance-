"""
Smart Barcode Attendance Management System - Database Module
============================================================
Handles all SQLite database operations including:
- Student CRUD operations
- Attendance marking and retrieval
- Report data queries
- Database initialization and schema management

This module is designed to be hardware-agnostic for easy ESP32 migration.
"""

import sqlite3
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import shutil


class DatabaseManager:
    """
    Central database manager for the attendance system.
    Uses SQLite for local storage with future migration path to cloud/remote DB.
    """

    def __init__(self, db_path: str = "database/school.db"):
        """
        Initialize database connection and ensure tables exist.

        Args:
            db_path: Relative or absolute path to SQLite database file
        """
        # Ensure database directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        self.db_path = db_path
        self.conn = None
        self.cursor = None
        self.connect()
        self._init_tables()
        self._seed_admin()

    def connect(self) -> None:
        """Establish database connection with row factory for dict-like access."""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()

    def close(self) -> None:
        """Safely close database connection."""
        if self.conn:
            self.conn.close()

    def _init_tables(self) -> None:
        """Initialize all required database tables if they don't exist."""

        # Students table - stores all student information
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS students (
                student_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                class TEXT NOT NULL,
                section TEXT NOT NULL,
                barcode_number TEXT UNIQUE NOT NULL,
                phone_number TEXT,
                photo_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Attendance table - stores daily attendance records
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS attendance (
                attendance_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                time TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('Present', 'Late', 'Absent')),
                marked_by TEXT DEFAULT 'System',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES students(student_id),
                UNIQUE(student_id, date)
            )
        """)

        # Admin table - stores admin credentials
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS admin (
                admin_id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                full_name TEXT,
                last_login TIMESTAMP
            )
        """)

        # Settings table - system configuration
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                setting_key TEXT PRIMARY KEY,
                setting_value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self.conn.commit()

    def _seed_admin(self) -> None:
        """Seed default admin account if no admin exists."""
        self.cursor.execute("SELECT COUNT(*) FROM admin")
        if self.cursor.fetchone()[0] == 0:
            # Default: admin/admin123 - should be changed in production
            self.cursor.execute(
                "INSERT INTO admin (username, password, full_name) VALUES (?, ?, ?)",
                ("admin", "admin123", "System Administrator")
            )
            self.conn.commit()

    # ==================== STUDENT OPERATIONS ====================

    def add_student(self, name: str, student_class: str, section: str,
                    barcode_number: str, phone_number: str = "",
                    photo_path: str = "") -> Tuple[bool, str]:
        """
        Add a new student to the database.

        Args:
            name: Student full name
            student_class: Class/grade (e.g., '10', '11', '12')
            section: Section (e.g., 'A', 'B', 'C')
            barcode_number: Unique barcode/RFID identifier
            phone_number: Optional contact number
            photo_path: Optional path to student photo

        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            self.cursor.execute(
                """INSERT INTO students (name, class, section, barcode_number,
                    phone_number, photo_path)
                    VALUES (?, ?, ?, ?, ?, ?)""",
                (name, student_class, section, barcode_number,
                 phone_number, photo_path)
            )
            self.conn.commit()
            return True, f"Student '{name}' added successfully!"
        except sqlite3.IntegrityError:
            return False, f"Barcode '{barcode_number}' already exists!"
        except Exception as e:
            return False, f"Error adding student: {str(e)}"

    def get_student_by_barcode(self, barcode_number: str) -> Optional[Dict]:
        """
        Retrieve student by barcode number.

        Args:
            barcode_number: The barcode to search for

        Returns:
            Student dictionary or None if not found
        """
        self.cursor.execute(
            "SELECT * FROM students WHERE barcode_number = ?",
            (barcode_number,)
        )
        row = self.cursor.fetchone()
        return dict(row) if row else None

    def get_student_by_id(self, student_id: int) -> Optional[Dict]:
        """Retrieve student by internal ID."""
        self.cursor.execute(
            "SELECT * FROM students WHERE student_id = ?",
            (student_id,)
        )
        row = self.cursor.fetchone()
        return dict(row) if row else None

    def get_all_students(self, student_class: str = None,
                         section: str = None) -> List[Dict]:
        """
        Get all students with optional filtering.

        Args:
            student_class: Filter by class (optional)
            section: Filter by section (optional)

        Returns:
            List of student dictionaries
        """
        query = "SELECT * FROM students WHERE 1=1"
        params = []

        if student_class:
            query += " AND class = ?"
            params.append(student_class)
        if section:
            query += " AND section = ?"
            params.append(section)

        query += " ORDER BY class, section, name"

        self.cursor.execute(query, params)
        return [dict(row) for row in self.cursor.fetchall()]

    def update_student(self, student_id: int, **kwargs) -> Tuple[bool, str]:
        """
        Update student information.

        Args:
            student_id: The student to update
            **kwargs: Fields to update (name, class, section, etc.)

        Returns:
            Tuple of (success: bool, message: str)
        """
        allowed_fields = {'name', 'class', 'section', 'barcode_number',
                          'phone_number', 'photo_path'}
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}

        if not updates:
            return False, "No valid fields to update"

        try:
            set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
            values = list(updates.values()) + [student_id]

            self.cursor.execute(
                f"UPDATE students SET {set_clause}, updated_at = CURRENT_TIMESTAMP
                 WHERE student_id = ?",
                values
            )
            self.conn.commit()
            return True, "Student updated successfully!"
        except sqlite3.IntegrityError:
            return False, "Barcode number already exists!"
        except Exception as e:
            return False, f"Error updating student: {str(e)}"

    def delete_student(self, student_id: int) -> Tuple[bool, str]:
        """
        Delete a student and their attendance records.

        Args:
            student_id: The student to delete

        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            # Get photo path before deletion
            self.cursor.execute(
                "SELECT photo_path FROM students WHERE student_id = ?",
                (student_id,)
            )
            result = self.cursor.fetchone()
            photo_path = result['photo_path'] if result else None

            # Delete attendance records first (foreign key)
            self.cursor.execute(
                "DELETE FROM attendance WHERE student_id = ?",
                (student_id,)
            )

            # Delete student
            self.cursor.execute(
                "DELETE FROM students WHERE student_id = ?",
                (student_id,)
            )

            # Delete photo file if exists
            if photo_path and os.path.exists(photo_path):
                os.remove(photo_path)

            self.conn.commit()
            return True, "Student deleted successfully!"
        except Exception as e:
            return False, f"Error deleting student: {str(e)}"

    def search_students(self, query: str) -> List[Dict]:
        """
        Search students by name, barcode, or class.

        Args:
            query: Search string

        Returns:
            List of matching students
        """
        search_term = f"%{query}%"
        self.cursor.execute(
            """SELECT * FROM students
               WHERE name LIKE ? OR barcode_number LIKE ?
               OR class LIKE ? OR section LIKE ?
               ORDER BY name""",
            (search_term, search_term, search_term, search_term)
        )
        return [dict(row) for row in self.cursor.fetchall()]

    # ==================== ATTENDANCE OPERATIONS ====================

    def mark_attendance(self, student_id: int, status: str = "Present",
                        marked_by: str = "System") -> Tuple[bool, str, Optional[Dict]]:
        """
        Mark attendance for a student.

        Args:
            student_id: The student to mark
            status: 'Present', 'Late', or 'Absent'
            marked_by: Who marked the attendance

        Returns:
            Tuple of (success: bool, message: str, record: dict or None)
        """
        today = datetime.now().strftime("%Y-%m-%d")
        current_time = datetime.now().strftime("%H:%M:%S")

        # Check if already marked today
        self.cursor.execute(
            """SELECT * FROM attendance
               WHERE student_id = ? AND date = ?""",
            (student_id, today)
        )

        if self.cursor.fetchone():
            return False, "Attendance already marked for today!", None

        try:
            self.cursor.execute(
                """INSERT INTO attendance (student_id, date, time, status, marked_by)
                   VALUES (?, ?, ?, ?, ?)""",
                (student_id, today, current_time, status, marked_by)
            )
            self.conn.commit()

            # Get the created record with student info
            self.cursor.execute(
                """SELECT a.*, s.name, s.class, s.section, s.photo_path
                   FROM attendance a
                   JOIN students s ON a.student_id = s.student_id
                   WHERE a.attendance_id = last_insert_rowid()"""
            )
            record = dict(self.cursor.fetchone())
            return True, f"Attendance marked as {status}!", record

        except Exception as e:
            return False, f"Error marking attendance: {str(e)}", None

    def check_attendance_status(self, student_id: int) -> Optional[Dict]:
        """
        Check if student has attendance marked today.

        Args:
            student_id: The student to check

        Returns:
            Attendance record or None
        """
        today = datetime.now().strftime("%Y-%m-%d")
        self.cursor.execute(
            """SELECT a.*, s.name, s.class, s.section, s.photo_path
               FROM attendance a
               JOIN students s ON a.student_id = s.student_id
               WHERE a.student_id = ? AND a.date = ?""",
            (student_id, today)
        )
        row = self.cursor.fetchone()
        return dict(row) if row else None

    def get_today_attendance(self) -> List[Dict]:
        """Get all attendance records for today."""
        today = datetime.now().strftime("%Y-%m-%d")
        self.cursor.execute(
            """SELECT a.*, s.name, s.class, s.section, s.photo_path
               FROM attendance a
               JOIN students s ON a.student_id = s.student_id
               WHERE a.date = ?
               ORDER BY a.time DESC""",
            (today,)
        )
        return [dict(row) for row in self.cursor.fetchall()]

    def get_attendance_by_date(self, date: str) -> List[Dict]:
        """Get attendance for a specific date."""
        self.cursor.execute(
            """SELECT a.*, s.name, s.class, s.section
               FROM attendance a
               JOIN students s ON a.student_id = s.student_id
               WHERE a.date = ?
               ORDER BY a.time""",
            (date,)
        )
        return [dict(row) for row in self.cursor.fetchall()]

    def get_attendance_by_month(self, year: int, month: int) -> List[Dict]:
        """Get attendance for a specific month."""
        self.cursor.execute(
            """SELECT a.*, s.name, s.class, s.section
               FROM attendance a
               JOIN students s ON a.student_id = s.student_id
               WHERE strftime('%Y', a.date) = ?
               AND strftime('%m', a.date) = ?
               ORDER BY a.date, a.time""",
            (str(year), f"{month:02d}")
        )
        return [dict(row) for row in self.cursor.fetchall()]

    def get_student_attendance(self, student_id: int,
                                start_date: str = None,
                                end_date: str = None) -> List[Dict]:
        """Get attendance history for a specific student."""
        query = """SELECT * FROM attendance WHERE student_id = ?"""
        params = [student_id]

        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)

        query += " ORDER BY date DESC"

        self.cursor.execute(query, params)
        return [dict(row) for row in self.cursor.fetchall()]

    def get_attendance_stats(self, date: str = None) -> Dict:
        """
        Get attendance statistics for a specific date.

        Args:
            date: Date string (YYYY-MM-DD), defaults to today

        Returns:
            Dictionary with present, late, absent counts and percentage
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        # Total students
        self.cursor.execute("SELECT COUNT(*) as count FROM students")
        total = self.cursor.fetchone()["count"]

        # Present count
        self.cursor.execute(
            """SELECT COUNT(*) as count FROM attendance
               WHERE date = ? AND status = 'Present'""",
            (date,)
        )
        present = self.cursor.fetchone()["count"]

        # Late count
        self.cursor.execute(
            """SELECT COUNT(*) as count FROM attendance
               WHERE date = ? AND status = 'Late'""",
            (date,)
        )
        late = self.cursor.fetchone()["count"]

        # Calculate absent
        absent = total - present - late
        attendance_rate = ((present + late) / total * 100) if total > 0 else 0

        return {
            "total_students": total,
            "present": present,
            "late": late,
            "absent": absent,
            "attendance_rate": round(attendance_rate, 1),
            "date": date
        }

    def get_monthly_stats(self, year: int, month: int) -> List[Dict]:
        """Get daily attendance statistics for a month."""
        self.cursor.execute(
            """SELECT date,
                   COUNT(CASE WHEN status = 'Present' THEN 1 END) as present,
                   COUNT(CASE WHEN status = 'Late' THEN 1 END) as late,
                   COUNT(*) as total
               FROM attendance
               WHERE strftime('%Y', date) = ?
               AND strftime('%m', date) = ?
               GROUP BY date
               ORDER BY date""",
            (str(year), f"{month:02d}")
        )
        return [dict(row) for row in self.cursor.fetchall()]

    # ==================== ADMIN OPERATIONS ====================

    def verify_admin(self, username: str, password: str) -> Optional[Dict]:
        """
        Verify admin credentials.

        Args:
            username: Admin username
            password: Admin password

        Returns:
            Admin dict if valid, None otherwise
        """
        self.cursor.execute(
            "SELECT * FROM admin WHERE username = ? AND password = ?",
            (username, password)
        )
        row = self.cursor.fetchone()

        if row:
            # Update last login
            self.cursor.execute(
                "UPDATE admin SET last_login = CURRENT_TIMESTAMP WHERE admin_id = ?",
                (row["admin_id"],)
            )
            self.conn.commit()
            return dict(row)
        return None

    def change_password(self, admin_id: int, new_password: str) -> bool:
        """Change admin password."""
        try:
            self.cursor.execute(
                "UPDATE admin SET password = ? WHERE admin_id = ?",
                (new_password, admin_id)
            )
            self.conn.commit()
            return True
        except Exception:
            return False

    # ==================== UTILITY OPERATIONS ====================

    def get_classes(self) -> List[str]:
        """Get list of all unique classes."""
        self.cursor.execute(
            "SELECT DISTINCT class FROM students ORDER BY class"
        )
        return [row["class"] for row in self.cursor.fetchall()]

    def get_sections(self, student_class: str = None) -> List[str]:
        """Get list of sections, optionally filtered by class."""
        if student_class:
            self.cursor.execute(
                "SELECT DISTINCT section FROM students WHERE class = ? ORDER BY section",
                (student_class,)
            )
        else:
            self.cursor.execute(
                "SELECT DISTINCT section FROM students ORDER BY section"
            )
        return [row["section"] for row in self.cursor.fetchall()]

    def backup_database(self, backup_path: str = None) -> str:
        """
        Create a backup of the database.

        Args:
            backup_path: Destination path for backup

        Returns:
            Path to backup file
        """
        if backup_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"database/backup_{timestamp}.db"

        self.conn.commit()  # Ensure all changes are written
        shutil.copy2(self.db_path, backup_path)
        return backup_path

    def export_to_csv(self, query: str, params: tuple = (),
                      output_path: str = "exports/attendance_reports/export.csv") -> str:
        """
        Export query results to CSV file.

        Args:
            query: SQL query to execute
            params: Query parameters
            output_path: Destination CSV path

        Returns:
            Path to exported file
        """
        import csv

        self.cursor.execute(query, params)
        rows = self.cursor.fetchall()

        if not rows:
            return None

        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows([dict(row) for row in rows])

        return output_path

    def __del__(self):
        """Destructor to ensure connection is closed."""
        self.close()


# Singleton instance for application-wide use
db_instance = None


def get_db(db_path: str = "database/school.db") -> DatabaseManager:
    """
    Get or create database singleton instance.

    Args:
        db_path: Path to database file

    Returns:
        DatabaseManager instance
    """
    global db_instance
    if db_instance is None:
        db_instance = DatabaseManager(db_path)
    return db_instance


def reset_db() -> None:
    """Reset the singleton instance (useful for testing)."""
    global db_instance
    db_instance = None


if __name__ == "__main__":
    # Test the database module
    db = DatabaseManager()

    # Add test student
    success, msg = db.add_student(
        name="John Doe",
        student_class="10",
        section="A",
        barcode_number="TEST001",
        phone_number="1234567890"
    )
    print(f"Add student: {msg}")

    # Get student by barcode
    student = db.get_student_by_barcode("TEST001")
    print(f"Found student: {student}")

    # Mark attendance
    if student:
        success, msg, record = db.mark_attendance(student["student_id"])
        print(f"Mark attendance: {msg}")

    # Get stats
    stats = db.get_attendance_stats()
    print(f"Stats: {stats}")

    db.close()
