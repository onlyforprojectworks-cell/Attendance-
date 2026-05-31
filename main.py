"""
Smart Barcode Attendance Management System
===========================================
Main entry point for the application.

Usage:
    python main.py              - Launch GUI application
    python main.py --scan       - Quick barcode scan test
    python main.py --report     - Generate daily report
    python main.py --backup     - Backup database
    python main.py --reset      - Reset database (WARNING: Deletes all data)

For ESP32/Arduino integration:
    The scanner.py module provides ESP32Scanner class for future hardware migration.
    See scanner.py documentation for serial/WiFi protocol details.
"""

import sys
import os
import argparse
from datetime import datetime

# Ensure project modules can be imported
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import DatabaseManager, get_db
from scanner import quick_scan_webcam
from attendance import quick_mark
from reports import quick_daily_report, ReportGenerator


def print_banner():
    """Print application banner."""
    banner = """
    ╔══════════════════════════════════════════════════════════════╗
    ║                                                              ║
    ║          SMART BARCODE ATTENDANCE MANAGEMENT SYSTEM          ║
    ║                                                              ║
    ║              Modern • Efficient • Hardware-Ready             ║
    ║                                                              ║
    ╚══════════════════════════════════════════════════════════════╝
    """
    print(banner)


def launch_gui():
    """Launch the graphical user interface."""
    print("Launching Smart Attendance GUI...")

    try:
        import customtkinter as ctk
        from dashboard import SmartAttendanceApp

        app = SmartAttendanceApp()
        app.mainloop()

    except ImportError as e:
        print(f"Error: Missing GUI dependency - {e}")
        print("\nPlease install required packages:")
        print("  pip install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        print(f"Error launching GUI: {e}")
        sys.exit(1)


def quick_scan_test():
    """Test barcode scanning."""
    print("Testing barcode scanner...")
    print("Show barcode to camera (timeout: 30 seconds)")

    result = quick_scan_webcam(timeout=30)

    if result:
        print(f"\n✓ Barcode detected!")
        print(f"  Data: {result.barcode_data}")
        print(f"  Type: {result.barcode_type}")
        print(f"  Time: {result.timestamp}")

        # Try to mark attendance
        success, message, record = quick_mark(result.barcode_data)
        print(f"\n  Attendance: {message}")
    else:
        print("\n✗ No barcode detected within timeout period")


def generate_daily_report():
    """Generate and display daily report."""
    print("Generating daily attendance report...\n")

    report = quick_daily_report()

    if report.empty:
        print("No attendance records found for today.")
    else:
        print(report.to_string())
        print(f"\nTotal records: {len(report)}")


def backup_database():
    """Create database backup."""
    print("Creating database backup...")

    db = get_db()
    backup_path = db.backup_database()

    print(f"✓ Backup created: {backup_path}")


def reset_database():
    """Reset database (WARNING: Destructive operation)."""
    print("WARNING: This will delete all data!")
    confirm = input("Type 'RESET' to confirm: ")

    if confirm == "RESET":
        db_path = "database/school.db"

        if os.path.exists(db_path):
            # Create backup first
            backup_path = f"database/backup_before_reset_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            import shutil
            shutil.copy2(db_path, backup_path)
            print(f"Backup created: {backup_path}")

            # Remove database file
            os.remove(db_path)
            print("✓ Database reset. New database will be created on next run.")
        else:
            print("No existing database found.")
    else:
        print("Reset cancelled.")


def show_system_info():
    """Display system information."""
    print_banner()

    print("System Information:")
    print(f"  Python: {sys.version}")
    print(f"  Platform: {sys.platform}")
    print(f"  Working Directory: {os.getcwd()}")

    # Check dependencies
    print("\nDependencies:")
    deps = [
        ("customtkinter", "GUI Framework"),
        ("PIL", "Image Processing"),
        ("cv2", "Computer Vision"),
        ("pyzbar", "Barcode Detection"),
        ("pandas", "Data Processing"),
        ("matplotlib", "Charts & Graphs"),
        ("numpy", "Numerical Computing"),
    ]

    for module, purpose in deps:
        try:
            __import__(module)
            status = "✓ Installed"
        except ImportError:
            status = "✗ Not installed"
        print(f"  {module:15} - {purpose:20} [{status}]")

    # Database info
    print("\nDatabase:")
    db = get_db()
    stats = db.get_attendance_stats()
    print(f"  Total Students: {stats['total_students']}")
    print(f"  Present Today:  {stats['present']}")
    print(f"  Late Today:     {stats['late']}")
    print(f"  Absent Today:   {stats['absent']}")
    print(f"  Attendance Rate: {stats['attendance_rate']}%")


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Smart Barcode Attendance Management System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py              Launch GUI
  python main.py --scan       Test barcode scanning
  python main.py --report     Generate daily report
  python main.py --backup     Backup database
  python main.py --info       Show system info
        """
    )

    parser.add_argument(
        "--scan",
        action="store_true",
        help="Test barcode scanning"
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Generate daily report"
    )
    parser.add_argument(
        "--backup",
        action="store_true",
        help="Backup database"
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset database (WARNING: Destructive)"
    )
    parser.add_argument(
        "--info",
        action="store_true",
        help="Show system information"
    )
    parser.add_argument(
        "--cli",
        action="store_true",
        help="Use command-line interface (no GUI)"
    )

    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_arguments()

    # Handle command-line only options
    if args.info:
        show_system_info()
        return

    if args.reset:
        reset_database()
        return

    if args.backup:
        backup_database()
        return

    if args.report:
        generate_daily_report()
        return

    if args.scan:
        quick_scan_test()
        return

    # Default: Launch GUI
    launch_gui()


if __name__ == "__main__":
    main()
