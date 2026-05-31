# Smart Barcode Attendance Management System

A modern, professional attendance management system for schools and educational institutions. Features barcode-based student identification, real-time attendance tracking, comprehensive reporting, and analytics dashboard. Designed with hardware migration path for ESP32/Arduino integration.

## Features

- **Barcode Scanning**: Webcam-based barcode scanning using OpenCV and pyzbar
- **USB Scanner Support**: Compatible with USB barcode scanners
- **Student Management**: Add, edit, delete, and search student records
- **Automatic Attendance**: Instant attendance marking with barcode scan
- **Late Detection**: Automatic late marking after configurable time threshold
- **Duplicate Prevention**: Prevents multiple attendance entries per day
- **Dark Theme UI**: Modern professional interface with blue accent colors
- **Reports**: Daily, monthly, and student-wise attendance reports
- **Export**: CSV and Excel export capabilities
- **Analytics**: Visual charts and attendance statistics
- **Admin Security**: Password-protected admin login
- **Hardware Ready**: Modular architecture for ESP32/Arduino migration

## Technology Stack

- **Python 3.8+**
- **CustomTkinter** - Modern GUI framework
- **SQLite** - Embedded database
- **OpenCV** - Computer vision for barcode scanning
- **pyzbar** - Barcode decoding
- **Pandas** - Data processing and reports
- **Matplotlib** - Charts and analytics

## Project Structure

```
SmartAttendance/
│
├── main.py              # Application entry point
├── database.py          # Database operations (SQLite)
├── scanner.py           # Barcode scanning (OpenCV/pyzbar)
├── attendance.py        # Attendance logic and rules
├── reports.py           # Report generation and export
├── dashboard.py         # GUI application (CustomTkinter)
│
├── database/
│   └── school.db        # SQLite database file
│
├── assets/
│   ├── logo.png         # Application logo
│   ├── background.png   # Background image
│   └── student_photos/  # Student photo storage
│
├── exports/
│   └── attendance_reports/  # Exported reports
│
└── requirements.txt     # Python dependencies
```

## Installation

### Prerequisites

- Python 3.8 or higher
- Webcam (for barcode scanning)
- USB barcode scanner (optional)

### Step 1: Clone or Download

```bash
cd SmartAttendance
```

### Step 2: Create Virtual Environment (Recommended)

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/macOS
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Run Application

```bash
python main.py
```

Default login credentials:
- **Username**: `admin`
- **Password**: `admin123`

> **Security Note**: Change default credentials after first login.

## Usage Guide

### 1. Dashboard

The main dashboard displays:
- Total students enrolled
- Present today count
- Absent today count
- Late arrivals count
- Attendance percentage with progress bar
- Recent activity feed

### 2. Scanning Barcodes

**Using Webcam:**
1. Navigate to "Scan Barcode"
2. Click "Start Camera"
3. Show student ID barcode to camera
4. Attendance is marked automatically

**Manual Entry:**
1. Enter barcode number in the text field
2. Click "Mark Attendance"

### 3. Adding Students

1. Navigate to "Add Student"
2. Fill in student details (Name, Class, Section, Barcode)
3. Click "Generate Barcode" for auto-generation
4. Upload student photo (optional)
5. Click "Save Student"

### 4. Viewing Attendance

1. Navigate to "Attendance"
2. Select date (defaults to today)
3. View attendance list with status indicators

### 5. Generating Reports

1. Navigate to "Reports"
2. Select report type (Daily/Monthly/Student/Late)
3. Choose date range
4. Select export format (CSV/Excel)
5. Click "Generate Report"

### 6. Analytics

View visual charts:
- Daily attendance trends
- Attendance distribution (pie chart)
- Late arrivals trend line

## Attendance Rules

| Time | Status |
|------|--------|
| Before 8:00 AM | Present |
| 8:00 AM - 8:15 AM | Present (grace period) |
| After 8:15 AM | Late |

These rules are configurable in `attendance.py` via `AttendanceConfig`.

## Database Schema

### Students Table
| Column | Type | Description |
|--------|------|-------------|
| student_id | INTEGER PK | Auto-increment ID |
| name | TEXT | Student full name |
| class | TEXT | Class/grade |
| section | TEXT | Section |
| barcode_number | TEXT UNIQUE | Student barcode |
| phone_number | TEXT | Contact number |
| photo_path | TEXT | Path to photo file |
| created_at | TIMESTAMP | Creation timestamp |

### Attendance Table
| Column | Type | Description |
|--------|------|-------------|
| attendance_id | INTEGER PK | Auto-increment ID |
| student_id | INTEGER FK | Reference to students |
| date | TEXT | Attendance date |
| time | TEXT | Attendance time |
| status | TEXT | Present/Late/Absent |
| marked_by | TEXT | Who marked it |

## Hardware Migration (ESP32/Arduino)

The system is designed for easy hardware migration:

### Current Architecture
```
Scanner (scanner.py) → Database (database.py) → GUI (dashboard.py)
```

### ESP32 Migration Path
```
ESP32 Scanner → Serial/WiFi → Scanner Module → Database → GUI
```

The `ESP32Scanner` class in `scanner.py` provides the interface:
- Serial communication via USB/UART
- WiFi communication via HTTP/WebSocket
- Same callback-based architecture

### ESP32 Implementation Steps

1. Flash ESP32 with barcode scanner firmware
2. Uncomment `pyserial` in `requirements.txt`
3. Change scanner type in dashboard:
   ```python
   scanner = ScannerFactory.create_scanner("esp32", port="COM3")
   ```

## Command Line Options

```bash
# Launch GUI (default)
python main.py

# Quick barcode scan test
python main.py --scan

# Generate daily report
python main.py --report

# Backup database
python main.py --backup

# Show system info
python main.py --info

# Reset database (WARNING: Destructive)
python main.py --reset
```

## Configuration

### Attendance Timing
Edit `AttendanceConfig` in `attendance.py`:
```python
config = AttendanceConfig(
    present_before=time(8, 0),      # 8:00 AM cutoff
    late_grace_minutes=15,           # 15 min grace period
    allow_multiple_marks=False       # Prevent duplicates
)
```

### Theme Customization
Edit `COLORS` dictionary in `dashboard.py`:
```python
COLORS = {
    "bg_primary": "#1a1a2e",
    "bg_secondary": "#16213e",
    "accent": "#e94560",
    "success": "#2ecc71",
    ...
}
```

## API Reference

### DatabaseManager
```python
from database import DatabaseManager

db = DatabaseManager("database/school.db")

# Student operations
db.add_student(name, class, section, barcode, phone, photo)
student = db.get_student_by_barcode("STU123456")
students = db.get_all_students(class_filter, section_filter)
db.update_student(student_id, **fields)
db.delete_student(student_id)

# Attendance operations
db.mark_attendance(student_id, status)
db.check_attendance_status(student_id)
db.get_today_attendance()
db.get_attendance_stats(date)

# Admin
db.verify_admin(username, password)
```

### Scanner
```python
from scanner import ScannerFactory

# Webcam scanning
scanner = ScannerFactory.create_scanner("webcam")
scanner.start()
scanner.stop()

# USB scanning
scanner = ScannerFactory.create_scanner("usb")
scanner.on_key_input(char)  # Call for each keypress

# ESP32 (future)
scanner = ScannerFactory.create_scanner("esp32", port="COM3")
```

### AttendanceManager
```python
from attendance import AttendanceManager

manager = AttendanceManager()
status = manager.determine_status()  # "Present" or "Late"
success, message, record = manager.mark_attendance_by_barcode("STU123456")
summary = manager.get_today_summary()
```

### ReportGenerator
```python
from reports import ReportGenerator

gen = ReportGenerator()
df = gen.generate_daily_report("2024-01-15")
df = gen.generate_monthly_report(2024, 1)
df = gen.generate_student_report(student_id)
path = gen.export_to_csv(df, "report.csv")
path = gen.export_to_excel(df, "report.xlsx")
path = gen.export_comprehensive_excel(year=2024, month=1)
```

## Troubleshooting

### Camera Not Working
```bash
# Check camera index
python -c "import cv2; print(cv2.VideoCapture(0).isOpened())"

# Try different camera index
# Edit scanner.py: camera_index=1
```

### Barcode Not Detecting
- Ensure good lighting
- Hold barcode steady
- Try closer/further distance
- Check barcode quality

### Database Locked
- Close other instances of the application
- Check file permissions on `database/school.db`

### Import Errors
```bash
# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

## Development

### Adding New Features

1. **New Report Type**: Extend `ReportGenerator` in `reports.py`
2. **New Scanner**: Inherit from `BaseScanner` in `scanner.py`
3. **New UI Page**: Add frame class in `dashboard.py`

### Testing

```bash
# Test database
python database.py

# Test scanner
python scanner.py

# Test attendance logic
python attendance.py

# Test reports
python reports.py
```

## Viva Questions & Answers

### Q1: What is the purpose of this system?
**A:** To automate student attendance tracking using barcode scanning, replacing manual roll calls with an efficient digital system.

### Q2: Why use barcodes instead of biometric?
**A:** Barcodes are cost-effective, easy to implement, don't raise privacy concerns, and can be printed on existing ID cards.

### Q3: How does the system prevent duplicate attendance?
**A:** The database enforces a UNIQUE constraint on (student_id, date) combination, preventing multiple entries per day.

### Q4: What is the late attendance logic?
**A:** Students arriving before 8:00 AM are marked Present. After 8:15 AM (with 15-minute grace), they are marked Late.

### Q5: How is the system prepared for ESP32 migration?
**A:** The scanner.py uses an abstract BaseScanner class. The ESP32Scanner implements the same interface, allowing seamless hardware swap without changing other modules.

### Q6: What database is used and why?
**A:** SQLite is used because it's serverless, zero-configuration, and perfect for standalone desktop applications.

### Q7: How are reports generated?
**A:** Pandas DataFrames query the database, then export to CSV/Excel using pandas built-in methods with openpyxl for formatting.

### Q8: What security features are implemented?
**A:** Admin login with password protection, database constraints to prevent data corruption, and input validation on all forms.

### Q9: How does the barcode scanning work?
**A:** OpenCV captures webcam frames, pyzbar decodes barcodes from the frames, and the scanner module handles the detection with cooldown to prevent duplicates.

### Q10: What design patterns are used?
**A:** Factory pattern (ScannerFactory), Singleton (DatabaseManager), Observer pattern (scan callbacks), and Template Method (BaseScanner).

## License

This project is for educational purposes.

## Author

Developed as a complete school attendance management solution with modern Python practices and hardware migration capabilities.

## Version History

- **v1.0.0** - Initial release
  - GUI with dark theme
  - Barcode scanning (webcam/USB)
  - Student CRUD operations
  - Attendance marking with late detection
  - Daily/Monthly/Student reports
  - CSV/Excel export
  - Analytics dashboard
  - Admin authentication
  - ESP32 migration-ready architecture
