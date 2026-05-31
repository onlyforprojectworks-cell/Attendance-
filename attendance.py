"""
Smart Barcode Attendance Management System - Attendance Module
==============================================================
Handles attendance marking logic including:
- Time-based status determination (Present vs Late)
- Duplicate prevention
- Attendance validation
- Bulk operations
- Integration with database and scanner modules

Late Attendance Logic:
----------------------
- Before 08:00:00 AM -> Present
- After 08:00:00 AM  -> Late

This can be configured via the settings.
"""

from datetime import datetime, time, timedelta
from typing import Tuple, Optional, Dict
from dataclasses import dataclass

from database import DatabaseManager, get_db


@dataclass
class AttendanceConfig:
    """Configuration for attendance rules."""
    present_before: time = time(8, 0, 0)  # 8:00 AM
    late_grace_minutes: int = 15  # 15 minutes grace period
    allow_multiple_marks: bool = False  # Prevent duplicate daily marks
    auto_mark_absent: bool = False  # Auto-mark absent at end of day


class AttendanceManager:
    """
    Manages all attendance-related operations.
    Central controller for marking, validating, and querying attendance.
    """

    def __init__(self, db: DatabaseManager = None, config: AttendanceConfig = None):
        """
        Initialize attendance manager.

        Args:
            db: DatabaseManager instance (creates default if None)
            config: AttendanceConfig with timing rules
        """
        self.db = db or get_db()
        self.config = config or AttendanceConfig()

    def determine_status(self, check_time: datetime = None) -> str:
        """
        Determine attendance status based on time.

        Rules:
        - Before 08:00:00 -> Present
        - 08:00:00 to 08:15:00 -> Present (grace period)
        - After 08:15:00 -> Late

        Args:
            check_time: Time to check (defaults to current time)

        Returns:
            'Present' or 'Late'
        """
        if check_time is None:
            check_time = datetime.now()

        current_time = check_time.time()

        # Calculate grace period end time
        present_cutoff = self.config.present_before
        grace_end = (
            datetime.combine(datetime.today(), present_cutoff) +
            timedelta(minutes=self.config.late_grace_minutes)
        ).time()

        if current_time <= grace_end:
            return "Present"
        else:
            return "Late"

    def mark_attendance_by_barcode(self, barcode_number: str,
                                    marked_by: str = "System") -> Tuple[bool, str, Optional[Dict]]:
        """
        Main entry point: Mark attendance by scanning barcode.

        Flow:
        1. Find student by barcode
        2. Check if already marked today
        3. Determine status (Present/Late) based on time
        4. Save to database

        Args:
            barcode_number: Scanned barcode
            marked_by: Who/what marked the attendance

        Returns:
            Tuple of (success, message, attendance_record)
        """
        # Step 1: Find student
        student = self.db.get_student_by_barcode(barcode_number)

        if not student:
            return False, f"No student found with barcode: {barcode_number}", None

        # Step 2: Check if already marked today
        existing = self.db.check_attendance_status(student["student_id"])

        if existing:
            return (
                False,
                f"Attendance already marked today at {existing['time']} ({existing['status']})",
                existing
            )

        # Step 3: Determine status based on current time
        status = self.determine_status()

        # Step 4: Mark attendance
        success, message, record = self.db.mark_attendance(
            student_id=student["student_id"],
            status=status,
            marked_by=marked_by
        )

        if success and record:
            # Enrich record with full student info
            record["student_name"] = student["name"]
            record["student_class"] = student["class"]
            record["student_section"] = student["section"]
            record["photo_path"] = student.get("photo_path", "")
            return True, f"Attendance marked: {status}", record

        return False, message, None

    def mark_manual_attendance(self, student_id: int,
                                status: str = "Present",
                                date: str = None,
                                time_str: str = None,
                                marked_by: str = "Admin") -> Tuple[bool, str, Optional[Dict]]:
        """
        Manually mark attendance for a student (admin override).

        Args:
            student_id: Student to mark
            status: 'Present', 'Late', or 'Absent'
            date: Date override (YYYY-MM-DD)
            time_str: Time override (HH:MM:SS)
            marked_by: Who marked it

        Returns:
            Tuple of (success, message, record)
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        if time_str is None:
            time_str = datetime.now().strftime("%H:%M:%S")

        # Check if already marked
        existing = self.db.cursor.execute(
            "SELECT * FROM attendance WHERE student_id = ? AND date = ?",
            (student_id, date)
        ).fetchone()

        if existing:
            return False, "Attendance already marked for this date", dict(existing)

        try:
            self.db.cursor.execute(
                """INSERT INTO attendance (student_id, date, time, status, marked_by)
                   VALUES (?, ?, ?, ?, ?)""",
                (student_id, date, time_str, status, marked_by)
            )
            self.db.conn.commit()

            # Get the record
            self.db.cursor.execute(
                """SELECT a.*, s.name, s.class, s.section, s.photo_path
                   FROM attendance a
                   JOIN students s ON a.student_id = s.student_id
                   WHERE a.attendance_id = last_insert_rowid()"""
            )
            record = dict(self.db.cursor.fetchone())
            return True, f"Manual attendance marked: {status}", record

        except Exception as e:
            return False, f"Error: {str(e)}", None

    def get_today_summary(self) -> Dict:
        """
        Get comprehensive attendance summary for today.

        Returns:
            Dictionary with statistics and lists
        """
        today = datetime.now().strftime("%Y-%m-%d")

        # Get basic stats
        stats = self.db.get_attendance_stats(today)

        # Get present students
        present_list = self.db.cursor.execute(
            """SELECT s.student_id, s.name, s.class, s.section,
                      a.time, a.status, s.photo_path
               FROM attendance a
               JOIN students s ON a.student_id = s.student_id
               WHERE a.date = ? AND (a.status = 'Present' OR a.status = 'Late')
               ORDER BY a.time DESC""",
            (today,)
        ).fetchall()

        # Get absent students
        absent_list = self.db.cursor.execute(
            """SELECT s.student_id, s.name, s.class, s.section, s.photo_path
               FROM students s
               WHERE s.student_id NOT IN (
                   SELECT student_id FROM attendance WHERE date = ?
               )
               ORDER BY s.class, s.section, s.name""",
            (today,)
        ).fetchall()

        return {
            "stats": stats,
            "present": [dict(r) for r in present_list],
            "absent": [dict(r) for r in absent_list],
            "date": today
        }

    def get_student_summary(self, student_id: int,
                            month: int = None,
                            year: int = None) -> Dict:
        """
        Get attendance summary for a specific student.

        Args:
            student_id: Student to query
            month: Filter by month (1-12)
            year: Filter by year

        Returns:
            Dictionary with attendance summary
        """
        if month is None:
            month = datetime.now().month
        if year is None:
            year = datetime.now().year

        # Get student info
        student = self.db.get_student_by_id(student_id)
        if not student:
            return {}

        # Get monthly attendance
        attendance = self.db.get_student_attendance(student_id)

        # Filter by month/year
        month_records = [
            r for r in attendance
            if r["date"].startswith(f"{year}-{month:02d}")
        ]

        present_count = sum(1 for r in month_records if r["status"] == "Present")
        late_count = sum(1 for r in month_records if r["status"] == "Late")
        total_marked = len(month_records)

        # Calculate working days (approximate)
        if month_records:
            first_date = datetime.strptime(month_records[-1]["date"], "%Y-%m-%d")
            last_date = datetime.strptime(month_records[0]["date"], "%Y-%m-%d")
            working_days = (last_date - first_date).days + 1
        else:
            working_days = 0

        attendance_rate = (total_marked / working_days * 100) if working_days > 0 else 0

        return {
            "student": student,
            "month": month,
            "year": year,
            "present": present_count,
            "late": late_count,
            "total_marked": total_marked,
            "working_days": working_days,
            "attendance_rate": round(attendance_rate, 1),
            "records": month_records
        }

    def get_class_attendance(self, student_class: str,
                              section: str = None,
                              date: str = None) -> Dict:
        """
        Get attendance for an entire class.

        Args:
            student_class: Class to query
            section: Optional section filter
            date: Date to query (default today)

        Returns:
            Dictionary with class attendance data
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        # Get all students in class
        students = self.db.get_all_students(student_class, section)

        # Get attendance for date
        attendance = self.db.get_attendance_by_date(date)
        attendance_dict = {a["student_id"]: a for a in attendance}

        # Combine data
        results = []
        present_count = 0
        late_count = 0
        absent_count = 0

        for student in students:
            student_id = student["student_id"]
            att = attendance_dict.get(student_id)

            if att:
                status = att["status"]
                if status == "Present":
                    present_count += 1
                elif status == "Late":
                    late_count += 1
            else:
                status = "Absent"
                absent_count += 1

            results.append({
                **student,
                "status": status,
                "time": att["time"] if att else "--:--:--"
            })

        total = len(students)
        rate = ((present_count + late_count) / total * 100) if total > 0 else 0

        return {
            "class": student_class,
            "section": section,
            "date": date,
            "total_students": total,
            "present": present_count,
            "late": late_count,
            "absent": absent_count,
            "attendance_rate": round(rate, 1),
            "students": results
        }

    def update_config(self, **kwargs) -> None:
        """
        Update attendance configuration.

        Args:
            **kwargs: present_before (time), late_grace_minutes (int), etc.
        """
        if "present_before" in kwargs:
            self.config.present_before = kwargs["present_before"]
        if "late_grace_minutes" in kwargs:
            self.config.late_grace_minutes = kwargs["late_grace_minutes"]
        if "allow_multiple_marks" in kwargs:
            self.config.allow_multiple_marks = kwargs["allow_multiple_marks"]


# Convenience function for quick attendance marking
def quick_mark(barcode_number: str) -> Tuple[bool, str, Optional[Dict]]:
    """
    Quick mark attendance by barcode.

    Args:
        barcode_number: Student barcode

    Returns:
        Tuple of (success, message, record)
    """
    manager = AttendanceManager()
    return manager.mark_attendance_by_barcode(barcode_number)


if __name__ == "__main__":
    # Test attendance module
    print("Testing Attendance Module...")

    manager = AttendanceManager()

    # Test status determination
    test_time = datetime.now().replace(hour=7, minute=30)
    status = manager.determine_status(test_time)
    print(f"7:30 AM status: {status}")

    test_time = datetime.now().replace(hour=8, minute=30)
    status = manager.determine_status(test_time)
    print(f"8:30 AM status: {status}")

    # Test summary
    summary = manager.get_today_summary()
    print(f"Today's stats: {summary['stats']}")

    print("Attendance module test complete.")
