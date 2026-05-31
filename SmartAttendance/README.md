# 🎓 Smart Barcode Attendance Management System

A professional, production-ready school attendance system built with Python. Students scan their ID-card barcodes and attendance is recorded instantly in a local SQLite database. The modular architecture is designed for future migration to Arduino/ESP32 hardware with minimal code changes.

---

## ✨ Features

| Category | Details |
|---|---|
| **Scanning** | Webcam (OpenCV + pyzbar) · USB HID barcode scanners · Manual entry |
| **Dashboard** | Real-time stats: Total · Present · Absent · Late · Percentage |
| **Attendance** | Auto Present/Late marking · Duplicate prevention · Daily/monthly reports |
| **Students** | Full CRUD · Photo upload · Auto barcode generation |
| **Analytics** | 4 embedded Matplotlib charts (bar, pie, line, class-wise) |
| **Exports** | CSV and Excel (XLSX) for daily, monthly, and full data |
| **Security** | Admin login · SHA-256 password hashing · Session management |
| **UI** | Dark-themed CustomTkinter · Toast notifications · Animated splash screen |

---

## 🗂️ Project Structure

```
SmartAttendance/
├── main.py              ← Entry point + animated splash screen
├── dashboard.py         ← All GUI windows and section frames
├── database.py          ← SQLite data-access layer
├── scanner.py           ← Barcode scanning (webcam + USB + serial/ESP32)
├── attendance.py        ← Business logic (Present/Late rules)
├── reports.py           ← Chart generation + CSV/Excel export
│
├── database/
│   └── school.db        ← Auto-created on first launch
│
├── assets/              ← Place logo.png / background.png here
├── exports/
│   └── attendance_reports/   ← Generated reports saved here
│
└── requirements.txt
```

---

## 🚀 Installation & Setup

### Prerequisites
- Python 3.10 or newer
- pip

### Step 1 — Create virtual environment (recommended)

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### Step 2 — Install dependencies

```bash
pip install -r requirements.txt
```

> **Linux extra (pyzbar)**  
> ```bash
> sudo apt-get install libzbar0
> ```

> **macOS extra (pyzbar)**  
> ```bash
> brew install zbar
> ```

### Step 3 — Run the application

```bash
python main.py
```

The splash screen will appear, the database will be initialised, and 10 demo students will be seeded automatically.

---

## 🔐 Default Credentials

| Field    | Value      |
|----------|------------|
| Username | `admin`    |
| Password | `admin123` |

> Change the password after first login (database layer supports `change_password()`).

---

## 📋 Database Schema

### `students`
| Column | Type | Notes |
|---|---|---|
| student_id | TEXT PK | e.g. `STU001` |
| name | TEXT | Full name |
| class | TEXT | e.g. `10` |
| section | TEXT | e.g. `A` |
| barcode_number | TEXT UNIQUE | Printed on ID card |
| phone_number | TEXT | Guardian contact |
| photo_path | TEXT | Absolute/relative file path |
| created_at | TIMESTAMP | Auto-set |

### `attendance`
| Column | Type | Notes |
|---|---|---|
| attendance_id | INT PK | Auto-increment |
| student_id | TEXT FK | References `students` |
| date | DATE | `YYYY-MM-DD` |
| time | TIME | `HH:MM:SS` |
| status | TEXT | `Present` or `Late` |
| *(unique constraint)* | | One record per student per day |

### `admins`
| Column | Type | Notes |
|---|---|---|
| admin_id | INT PK | Auto-increment |
| username | TEXT UNIQUE | Login name |
| password_hash | TEXT | SHA-256 hex digest |
| created_at | TIMESTAMP | Auto-set |

---

## ⏰ Attendance Logic

```
Current time ≤ 08:00  →  Status = "Present"
Current time > 08:00  →  Status = "Late"
Same student scans again on the same date  →  "Already marked" (no duplicate row)
```

Change the threshold in `attendance.py`:
```python
class AttendanceManager:
    LATE_HOUR   = 8   # change to 9 for 9 AM
    LATE_MINUTE = 30  # change to 30 for half-past
```

---

## 🔌 ESP32 / Arduino Migration Guide

The scanning layer is fully isolated in `scanner.py`. To switch from webcam to ESP32:

1. **Keep** `scanner.py`, `database.py`, `attendance.py`, `reports.py`, `dashboard.py` **unchanged**.
2. In `scanner.py`, use `SerialBarcodeScanner` instead of `BarcodeScanner`:

```python
# dashboard.py → ScannerSection._build()
# Replace:
self._scanner = BarcodeScanner()
# With:
from scanner import SerialBarcodeScanner
self._scanner = SerialBarcodeScanner(port="COM3", baud=9600)
```

3. Install `pyserial`:
```bash
pip install pyserial
```

4. Flash your ESP32 with this Arduino sketch:
```cpp
#include <HardwareSerial.h>
// Assuming a barcode scanner module wired to UART2
void setup() { Serial.begin(9600); }
void loop() {
    if (Serial2.available()) {
        String code = Serial2.readStringUntil('\n');
        code.trim();
        if (code.length() > 0) Serial.println(code);
    }
}
```

---

## 📊 Demo Barcodes (pre-seeded students)

| Barcode | Student Name | Class |
|---------|-------------|-------|
| BAR001  | Aditya Sharma  | 10-A |
| BAR002  | Priya Patel    | 10-A |
| BAR003  | Rahul Verma    | 10-B |
| BAR004  | Sneha Singh    | 10-B |
| BAR005  | Arjun Nair     | 11-A |
| BAR006  | Kavya Reddy    | 11-A |
| BAR007  | Rohan Mehta    | 11-B |
| BAR008  | Divya Joshi    | 11-B |
| BAR009  | Kiran Kumar    | 12-A |
| BAR010  | Meera Iyer     | 12-A |

Type any of these barcodes in the **USB Scanner Input** field on the Scan screen, then press Enter.

---

## 🛠️ Troubleshooting

| Issue | Fix |
|---|---|
| `ModuleNotFoundError: pyzbar` | Linux: `sudo apt-get install libzbar0` / macOS: `brew install zbar` |
| Camera not opening | Check index in `BarcodeScanner(camera_index=0)` — try `1` or `2` |
| `openpyxl` not found | `pip install openpyxl` |
| Database locked | Ensure only one instance of the app is running |
| Blank charts | Resize the window; charts redraw on section activation |

---

## 🎓 Viva Questions & Answers

**Q1: Why SQLite and not MySQL/PostgreSQL?**  
A: SQLite is zero-configuration, serverless, and file-based — ideal for a local school system. The `DatabaseManager` interface can be swapped for any RDBMS without touching other modules.

**Q2: How is duplicate attendance prevented?**  
A: The `attendance` table has a `UNIQUE(student_id, date)` constraint. `mark_attendance()` catches `sqlite3.IntegrityError` and returns a user-friendly message.

**Q3: How does the barcode scanner work?**  
A: OpenCV captures frames from the webcam at ~30 fps. `pyzbar.decode()` finds and decodes any barcode symbology (Code128, QR, EAN, etc.) in each frame. A 2.5-second cooldown prevents the same code firing twice in quick succession.

**Q4: What is the Present/Late cut-off and where is it configured?**  
A: 08:00 AM by default. Set `LATE_HOUR` and `LATE_MINUTE` in `AttendanceManager` (attendance.py).

**Q5: How are passwords stored?**  
A: As SHA-256 hex digests. Plain-text passwords are never stored or logged.

**Q6: How would you migrate this to ESP32 hardware?**  
A: Replace `BarcodeScanner` with `SerialBarcodeScanner` in the scanner section. The ESP32 sends scanned barcodes over UART; Python reads them via `pyserial`. All business logic, database operations, and GUI code remain unchanged.

**Q7: What OOP principles are used?**  
A: Encapsulation (each module is a class), Inheritance (`SectionBase` → all section frames; `BarcodeScanner` → `SerialBarcodeScanner`), Single Responsibility (each class has one job), and Dependency Injection (managers are passed into GUI sections rather than instantiated inside them).

**Q8: How does the export feature work?**  
A: `ReportsManager` uses `pandas.DataFrame` to build tabular data from database queries, then calls `DataFrame.to_csv()` or `DataFrame.to_excel()` (via openpyxl) to write files to the `exports/` folder.

**Q9: How are charts embedded in the GUI?**  
A: Matplotlib figures are rendered off-screen and embedded using `FigureCanvasTkAgg` from `matplotlib.backends.backend_tkagg`. Charts are redrawn on a background thread to keep the UI responsive.

**Q10: Why use threading for the scanner?**  
A: OpenCV's `VideoCapture.read()` is a blocking call. Running it on the main thread would freeze the GUI. The scanner runs on a `daemon=True` background thread and uses `root.after()` to safely dispatch scan events back to the tkinter main loop.

---

## 📄 License

MIT License — free for educational and personal use.
