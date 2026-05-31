"""
Smart Barcode Attendance Management System - Reports Module
===========================================================
Generates comprehensive attendance reports:
- Daily attendance reports
- Monthly attendance summaries
- Student-wise attendance reports
- Class-wise attendance reports
- Late arrival reports

Export formats:
- CSV
- Excel (.xlsx)
- PDF (future enhancement)

Dependencies:
- pandas: Data manipulation and export
- openpyxl: Excel file creation
"""

import pandas as pd
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from database import DatabaseManager, get_db


class ReportGenerator:
    """
    Generates various attendance reports and exports to multiple formats.
    """

    def __init__(self, db: DatabaseManager = None, export_dir: str = "exports/attendance_reports"):
        """
        Initialize report generator.

        Args:
            db: DatabaseManager instance
            export_dir: Directory for exported files
        """
        self.db = db or get_db()
        self.export_dir = export_dir
        os.makedirs(self.export_dir, exist_ok=True)

    def generate_daily_report(self, date: str = None) -> pd.DataFrame:
        """
        Generate daily attendance report.

        Args:
            date: Date string (YYYY-MM-DD), defaults to today

        Returns:
            DataFrame with attendance data
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        # Get all students with their attendance status for the date
        self.db.cursor.execute(
            """SELECT
                s.student_id,
                s.name as "Student Name",
                s.class as "Class",
                s.section as "Section",
                s.barcode_number as "Barcode",
                COALESCE(a.time, '--:--:--') as "Time",
                COALESCE(a.status, 'Absent') as "Status",
                s.phone_number as "Phone"
               FROM students s
               LEFT JOIN attendance a ON s.student_id = a.student_id AND a.date = ?
               ORDER BY s.class, s.section, s.name""",
            (date,)
        )

        rows = self.db.cursor.fetchall()
        data = [dict(row) for row in rows]

        df = pd.DataFrame(data)

        # Add summary row
        if not df.empty:
            present = (df["Status"] == "Present").sum()
            late = (df["Status"] == "Late").sum()
            absent = (df["Status"] == "Absent").sum()

            summary = pd.DataFrame([{
                "student_id": "",
                "Student Name": "SUMMARY",
                "Class": "",
                "Section": "",
                "Barcode": "",
                "Time": "",
                "Status": f"P:{present} L:{late} A:{absent}",
                "Phone": ""
            }])

            df = pd.concat([df, summary], ignore_index=True)

        return df

    def generate_monthly_report(self, year: int = None,
                                 month: int = None) -> pd.DataFrame:
        """
        Generate monthly attendance summary report.

        Args:
            year: Year (default current)
            month: Month 1-12 (default current)

        Returns:
            DataFrame with monthly summary per student
        """
        if year is None:
            year = datetime.now().year
        if month is None:
            month = datetime.now().month

        # Get all students
        self.db.cursor.execute(
            """SELECT student_id, name, class, section, barcode_number
               FROM students ORDER BY class, section, name"""
        )
        students = [dict(r) for r in self.db.cursor.fetchall()]

        # Get working days in month (days with any attendance)
        self.db.cursor.execute(
            """SELECT DISTINCT date FROM attendance
               WHERE strftime('%Y', date) = ? AND strftime('%m', date) = ?
               ORDER BY date""",
            (str(year), f"{month:02d}")
        )
        working_days = len(self.db.cursor.fetchall())

        # Calculate attendance for each student
        report_data = []

        for student in students:
            self.db.cursor.execute(
                """SELECT status, COUNT(*) as count
                   FROM attendance
                   WHERE student_id = ?
                   AND strftime('%Y', date) = ?
                   AND strftime('%m', date) = ?
                   GROUP BY status""",
                (student["student_id"], str(year), f"{month:02d}")
            )
            status_counts = {r["status"]: r["count"] for r in self.db.cursor.fetchall()}

            present = status_counts.get("Present", 0)
            late = status_counts.get("Late", 0)
            total_present = present + late

            rate = (total_present / working_days * 100) if working_days > 0 else 0

            report_data.append({
                "Student ID": student["student_id"],
                "Name": student["name"],
                "Class": student["class"],
                "Section": student["section"],
                "Barcode": student["barcode_number"],
                "Present": present,
                "Late": late,
                "Total Present": total_present,
                "Working Days": working_days,
                "Attendance %": round(rate, 1)
            })

        df = pd.DataFrame(report_data)

        # Add class average
        if not df.empty:
            avg_rate = df["Attendance %"].mean()
            avg_row = pd.DataFrame([{
                "Student ID": "",
                "Name": "CLASS AVERAGE",
                "Class": "",
                "Section": "",
                "Barcode": "",
                "Present": "",
                "Late": "",
                "Total Present": "",
                "Working Days": "",
                "Attendance %": round(avg_rate, 1)
            }])
            df = pd.concat([df, avg_row], ignore_index=True)

        return df

    def generate_student_report(self, student_id: int,
                                 start_date: str = None,
                                 end_date: str = None) -> pd.DataFrame:
        """
        Generate detailed attendance report for a specific student.

        Args:
            student_id: Student to report on
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            DataFrame with daily attendance records
        """
        # Get student info
        student = self.db.get_student_by_id(student_id)
        if not student:
            return pd.DataFrame()

        # Build query
        query = """SELECT date as "Date", time as "Time",
                          status as "Status", marked_by as "Marked By"
                   FROM attendance WHERE student_id = ?"""
        params = [student_id]

        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)

        query += " ORDER BY date DESC"

        self.db.cursor.execute(query, params)
        records = [dict(r) for r in self.db.cursor.fetchall()]

        df = pd.DataFrame(records)

        # Add student info as header
        if not df.empty:
            df.attrs["student_name"] = student["name"]
            df.attrs["student_class"] = student["class"]
            df.attrs["student_section"] = student["section"]

        return df

    def generate_late_report(self, year: int = None,
                              month: int = None) -> pd.DataFrame:
        """
        Generate report of late arrivals.

        Args:
            year: Filter by year
            month: Filter by month

        Returns:
            DataFrame with late arrival records
        """
        query = """SELECT
                    s.name as "Student Name",
                    s.class as "Class",
                    s.section as "Section",
                    a.date as "Date",
                    a.time as "Time",
                    s.phone_number as "Phone"
                   FROM attendance a
                   JOIN students s ON a.student_id = s.student_id
                   WHERE a.status = 'Late'"""
        params = []

        if year:
            query += " AND strftime('%Y', a.date) = ?"
            params.append(str(year))
        if month:
            query += " AND strftime('%m', a.date) = ?"
            params.append(f"{month:02d}")

        query += " ORDER BY a.date DESC, a.time DESC"

        self.db.cursor.execute(query, params)
        records = [dict(r) for r in self.db.cursor.fetchall()]

        return pd.DataFrame(records)

    def generate_class_report(self, student_class: str,
                               section: str = None,
                               month: int = None,
                               year: int = None) -> pd.DataFrame:
        """
        Generate class-wise attendance report.

        Args:
            student_class: Class to report
            section: Optional section filter
            month: Month filter
            year: Year filter

        Returns:
            DataFrame with class attendance data
        """
        if year is None:
            year = datetime.now().year
        if month is None:
            month = datetime.now().month

        # Get all dates in month with attendance
        self.db.cursor.execute(
            """SELECT DISTINCT date FROM attendance
               WHERE strftime('%Y', date) = ? AND strftime('%m', date) = ?
               ORDER BY date""",
            (str(year), f"{month:02d}")
        )
        dates = [r["date"] for r in self.db.cursor.fetchall()]

        # Get students in class
        students = self.db.get_all_students(student_class, section)

        # Build matrix: rows=students, cols=dates
        report_data = []

        for student in students:
            row = {
                "Name": student["name"],
                "Barcode": student["barcode_number"]
            }

            # Get attendance for each date
            for date in dates:
                self.db.cursor.execute(
                    """SELECT status FROM attendance
                       WHERE student_id = ? AND date = ?""",
                    (student["student_id"], date)
                )
                result = self.db.cursor.fetchone()
                row[date] = result["status"][0] if result else "A"  # P/L/A

            # Calculate totals
            present = sum(1 for d in dates if row.get(d) in ("P", "L"))
            late = sum(1 for d in dates if row.get(d) == "L")
            total_days = len(dates)

            row["Present"] = present
            row["Late"] = late
            row["Absent"] = total_days - present
            row["Rate %"] = round(present / total_days * 100, 1) if total_days > 0 else 0

            report_data.append(row)

        return pd.DataFrame(report_data)

    def export_to_csv(self, df: pd.DataFrame,
                      filename: str = None) -> str:
        """
        Export DataFrame to CSV file.

        Args:
            df: DataFrame to export
            filename: Output filename (auto-generated if None)

        Returns:
            Path to exported file
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"report_{timestamp}.csv"

        filepath = os.path.join(self.export_dir, filename)
        df.to_csv(filepath, index=False, encoding='utf-8')

        return filepath

    def export_to_excel(self, df: pd.DataFrame,
                        filename: str = None,
                        sheet_name: str = "Attendance") -> str:
        """
        Export DataFrame to Excel file with formatting.

        Args:
            df: DataFrame to export
            filename: Output filename
            sheet_name: Excel sheet name

        Returns:
            Path to exported file
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"report_{timestamp}.xlsx"

        filepath = os.path.join(self.export_dir, filename)

        # Create Excel writer with formatting
        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name=sheet_name, index=False)

            # Get workbook and worksheet
            workbook = writer.book
            worksheet = writer.sheets[sheet_name]

            # Auto-adjust column widths
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)
                worksheet.column_dimensions[column_letter].width = adjusted_width

        return filepath

    def export_comprehensive_excel(self,
                                    date: str = None,
                                    month: int = None,
                                    year: int = None,
                                    filename: str = None) -> str:
        """
        Generate comprehensive Excel report with multiple sheets.

        Sheets:
        1. Daily Summary
        2. Monthly Summary
        3. Late Arrivals
        4. Statistics

        Args:
            date: Date for daily report
            month: Month for reports
            year: Year for reports
            filename: Output filename

        Returns:
            Path to exported file
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        if month is None:
            month = datetime.now().month
        if year is None:
            year = datetime.now().year
        if filename is None:
            filename = f"comprehensive_report_{year}_{month:02d}.xlsx"

        filepath = os.path.join(self.export_dir, filename)

        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            # Sheet 1: Daily Report
            daily_df = self.generate_daily_report(date)
            daily_df.to_excel(writer, sheet_name="Daily Report", index=False)

            # Sheet 2: Monthly Report
            monthly_df = self.generate_monthly_report(year, month)
            monthly_df.to_excel(writer, sheet_name="Monthly Summary", index=False)

            # Sheet 3: Late Arrivals
            late_df = self.generate_late_report(year, month)
            if late_df.empty:
                late_df = pd.DataFrame({"Message": ["No late arrivals recorded"]})
            late_df.to_excel(writer, sheet_name="Late Arrivals", index=False)

            # Sheet 4: Statistics
            stats_data = self._generate_stats_data(year, month)
            stats_df = pd.DataFrame([stats_data])
            stats_df.to_excel(writer, sheet_name="Statistics", index=False)

            # Format all sheets
            for sheet_name in writer.sheets:
                worksheet = writer.sheets[sheet_name]
                for column in worksheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    for cell in column:
                        try:
                            if cell.value and len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    adjusted_width = min(max_length + 2, 50)
                    worksheet.column_dimensions[column_letter].width = adjusted_width

        return filepath

    def _generate_stats_data(self, year: int, month: int) -> Dict:
        """Generate summary statistics for report."""
        stats = self.db.get_attendance_stats()

        # Additional stats
        self.db.cursor.execute(
            """SELECT COUNT(*) as count FROM attendance
               WHERE strftime('%Y', date) = ? AND strftime('%m', date) = ?""",
            (str(year), f"{month:02d}")
        )
        total_records = self.db.cursor.fetchone()["count"]

        self.db.cursor.execute(
            """SELECT COUNT(DISTINCT date) as count FROM attendance
               WHERE strftime('%Y', date) = ? AND strftime('%m', date) = ?""",
            (str(year), f"{month:02d}")
        )
        working_days = self.db.cursor.fetchone()["count"]

        return {
            "Total Students": stats["total_students"],
            "Total Attendance Records (Month)": total_records,
            "Working Days (Month)": working_days,
            "Present Today": stats["present"],
            "Late Today": stats["late"],
            "Absent Today": stats["absent"],
            "Today's Attendance Rate %": stats["attendance_rate"],
            "Report Generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    def get_available_dates(self) -> List[str]:
        """Get list of dates with attendance records."""
        self.db.cursor.execute(
            "SELECT DISTINCT date FROM attendance ORDER BY date DESC"
        )
        return [r["date"] for r in self.db.cursor.fetchall()]

    def get_available_months(self) -> List[Tuple[int, int]]:
        """Get list of year/month pairs with records."""
        self.db.cursor.execute(
            """SELECT DISTINCT
                CAST(strftime('%Y', date) AS INTEGER) as year,
                CAST(strftime('%m', date) AS INTEGER) as month
               FROM attendance
               ORDER BY year DESC, month DESC"""
        )
        return [(r["year"], r["month"]) for r in self.db.cursor.fetchall()]


# Convenience functions
def quick_daily_report(date: str = None) -> pd.DataFrame:
    """Generate daily report (convenience function)."""
    gen = ReportGenerator()
    return gen.generate_daily_report(date)


def quick_monthly_report(year: int = None, month: int = None) -> pd.DataFrame:
    """Generate monthly report (convenience function)."""
    gen = ReportGenerator()
    return gen.generate_monthly_report(year, month)


if __name__ == "__main__":
    # Test reports module
    print("Testing Reports Module...")

    gen = ReportGenerator()

    # Test daily report
    daily = gen.generate_daily_report()
    print(f"Daily report shape: {daily.shape}")
    print(daily.head())

    # Test export
    csv_path = gen.export_to_csv(daily, "test_daily.csv")
    print(f"CSV exported to: {csv_path}")

    print("Reports module test complete.")
