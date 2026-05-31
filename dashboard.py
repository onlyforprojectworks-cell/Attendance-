"""
Smart Barcode Attendance Management System - Dashboard Module
=============================================================
Main GUI application built with CustomTkinter.

Features:
- Modern dark theme with blue accents
- Animated loading screen
- Login screen with admin authentication
- Dashboard with statistics cards
- Student management (add/edit/delete/view)
- Barcode scanning interface with webcam preview
- Attendance viewing and management
- Reports generation and export
- Analytics charts with matplotlib
- Success/error popup animations

UI Components:
- CustomPopup: Animated popup notifications
- StatCard: Dashboard statistic cards
- StudentForm: Add/Edit student form
- ScannerFrame: Barcode scanning interface
- ReportsFrame: Report generation and export
- AnalyticsFrame: Charts and graphs
"""

import customtkinter as ctk
from PIL import Image, ImageTk
import cv2
import threading
import time
import os
from datetime import datetime, timedelta
from typing import Callable, Optional

# Import project modules
from database import DatabaseManager, get_db
from scanner import ScannerFactory, ScanResult
from attendance import AttendanceManager
from reports import ReportGenerator

# Matplotlib for analytics
try:
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    import numpy as np
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

# Theme Configuration
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# Color constants
COLORS = {
    "bg_primary": "#1a1a2e",
    "bg_secondary": "#16213e",
    "bg_card": "#0f3460",
    "accent": "#e94560",
    "accent_hover": "#ff6b6b",
    "success": "#2ecc71",
    "warning": "#f39c12",
    "info": "#3498db",
    "text_primary": "#ffffff",
    "text_secondary": "#b0b0b0",
    "border": "#2a2a4a"
}


class CustomPopup(ctk.CTkToplevel):
    """Animated popup notification."""

    def __init__(self, parent, message: str, popup_type: str = "success", duration: int = 3000):
        super().__init__(parent)

        self.message = message
        self.popup_type = popup_type
        self.duration = duration

        # Configure popup
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0)

        # Colors based on type
        colors = {
            "success": COLORS["success"],
            "error": COLORS["accent"],
            "warning": COLORS["warning"],
            "info": COLORS["info"]
        }
        self.bg_color = colors.get(popup_type, COLORS["info"])

        # Frame
        self.frame = ctk.CTkFrame(self, fg_color=self.bg_color, corner_radius=10)
        self.frame.pack(padx=2, pady=2)

        # Icon
        icons = {
            "success": "✓",
            "error": "✗",
            "warning": "⚠",
            "info": "ℹ"
        }
        icon = icons.get(popup_type, "ℹ")

        ctk.CTkLabel(
            self.frame,
            text=f"{icon}  {message}",
            font=("Helvetica", 12, "bold"),
            text_color="white"
        ).pack(padx=20, pady=15)

        # Position
        self.update_idletasks()
        x = parent.winfo_x() + parent.winfo_width() // 2 - self.winfo_width() // 2
        y = parent.winfo_y() + 50
        self.geometry(f"+{x}+{y}")

        # Animate in
        self.animate_in()

        # Auto close
        self.after(duration, self.animate_out)

    def animate_in(self):
        """Fade in animation."""
        for i in range(0, 11):
            self.attributes("-alpha", i / 10)
            self.update()
            time.sleep(0.02)

    def animate_out(self):
        """Fade out animation."""
        for i in range(10, -1, -1):
            self.attributes("-alpha", i / 10)
            self.update()
            time.sleep(0.02)
        self.destroy()


class StatCard(ctk.CTkFrame):
    """Dashboard statistic card."""

    def __init__(self, parent, title: str, value: str, color: str, icon: str = ""):
        super().__init__(parent, fg_color=COLORS["bg_card"], corner_radius=15)

        # Icon
        if icon:
            ctk.CTkLabel(
                self,
                text=icon,
                font=("Helvetica", 24),
                text_color=color
            ).pack(pady=(15, 5))

        # Value
        ctk.CTkLabel(
            self,
            text=value,
            font=("Helvetica", 28, "bold"),
            text_color=color
        ).pack()

        # Title
        ctk.CTkLabel(
            self,
            text=title,
            font=("Helvetica", 12),
            text_color=COLORS["text_secondary"]
        ).pack(pady=(5, 15))


class LoadingScreen(ctk.CTkToplevel):
    """Animated loading screen."""

    def __init__(self, parent):
        super().__init__(parent)

        self.overrideredirect(True)
        self.attributes("-topmost", True)

        # Center on parent
        self.update_idletasks()
        w, h = 400, 200
        x = parent.winfo_x() + parent.winfo_width() // 2 - w // 2
        y = parent.winfo_y() + parent.winfo_height() // 2 - h // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

        # Background
        self.configure(fg_color=COLORS["bg_primary"])

        # Logo/Title
        ctk.CTkLabel(
            self,
            text="Smart Attendance",
            font=("Helvetica", 20, "bold"),
            text_color=COLORS["accent"]
        ).pack(pady=(40, 10))

        # Loading text
        self.loading_label = ctk.CTkLabel(
            self,
            text="Loading...",
            font=("Helvetica", 12),
            text_color=COLORS["text_secondary"]
        )
        self.loading_label.pack()

        # Progress bar
        self.progress = ctk.CTkProgressBar(self, width=300)
        self.progress.pack(pady=20)
        self.progress.set(0)

        # Animate
        self.animate()

    def animate(self):
        """Animate progress bar."""
        for i in range(101):
            self.progress.set(i / 100)
            self.update()
            time.sleep(0.02)
        self.destroy()


class LoginScreen(ctk.CTkFrame):
    """Admin login screen."""

    def __init__(self, parent, on_login_success):
        super().__init__(parent, fg_color=COLORS["bg_primary"])
        self.parent = parent
        self.on_login_success = on_login_success

        self.build_ui()

    def build_ui(self):
        """Build login form."""
        # Center container
        container = ctk.CTkFrame(self, fg_color=COLORS["bg_secondary"], corner_radius=20)
        container.place(relx=0.5, rely=0.5, anchor="center")

        # Title
        ctk.CTkLabel(
            container,
            text="Smart Attendance",
            font=("Helvetica", 24, "bold"),
            text_color=COLORS["accent"]
        ).pack(pady=(30, 5))

        ctk.CTkLabel(
            container,
            text="Management System",
            font=("Helvetica", 14),
            text_color=COLORS["text_secondary"]
        ).pack()

        # Lock icon
        ctk.CTkLabel(
            container,
            text="🔒",
            font=("Helvetica", 40)
        ).pack(pady=20)

        # Username
        ctk.CTkLabel(
            container,
            text="Username",
            font=("Helvetica", 12),
            text_color=COLORS["text_secondary"]
        ).pack(pady=(10, 2), padx=40, anchor="w")

        self.username_entry = ctk.CTkEntry(
            container,
            width=300,
            height=35,
            font=("Helvetica", 12)
        )
        self.username_entry.pack(padx=40)

        # Password
        ctk.CTkLabel(
            container,
            text="Password",
            font=("Helvetica", 12),
            text_color=COLORS["text_secondary"]
        ).pack(pady=(15, 2), padx=40, anchor="w")

        self.password_entry = ctk.CTkEntry(
            container,
            width=300,
            height=35,
            show="●",
            font=("Helvetica", 12)
        )
        self.password_entry.pack(padx=40)
        self.password_entry.bind("<Return>", lambda e: self.login())

        # Login button
        ctk.CTkButton(
            container,
            text="Login",
            width=300,
            height=40,
            font=("Helvetica", 14, "bold"),
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            command=self.login
        ).pack(pady=25)

        # Default credentials hint
        ctk.CTkLabel(
            container,
            text="Default: admin / admin123",
            font=("Helvetica", 10),
            text_color=COLORS["text_secondary"]
        ).pack(pady=(0, 20))

    def login(self):
        """Verify credentials and login."""
        username = self.username_entry.get()
        password = self.password_entry.get()

        db = get_db()
        admin = db.verify_admin(username, password)

        if admin:
            CustomPopup(self, "Login successful!", "success")
            self.on_login_success()
        else:
            CustomPopup(self, "Invalid username or password!", "error")


class DashboardHome(ctk.CTkFrame):
    """Main dashboard with statistics."""

    def __init__(self, parent, show_frame_callback):
        super().__init__(parent, fg_color=COLORS["bg_primary"])
        self.show_frame = show_frame_callback

        self.build_ui()
        self.refresh_stats()

    def build_ui(self):
        """Build dashboard UI."""
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=20)

        ctk.CTkLabel(
            header,
            text="Dashboard",
            font=("Helvetica", 24, "bold"),
            text_color=COLORS["text_primary"]
        ).pack(side="left")

        # Date display
        self.date_label = ctk.CTkLabel(
            header,
            text=datetime.now().strftime("%A, %B %d, %Y"),
            font=("Helvetica", 14),
            text_color=COLORS["text_secondary"]
        )
        self.date_label.pack(side="right")

        # Statistics cards frame
        cards_frame = ctk.CTkFrame(self, fg_color="transparent")
        cards_frame.pack(fill="x", padx=20, pady=10)

        # Create stat cards
        self.stat_cards = {}

        stats_config = [
            ("Total Students", "0", COLORS["info"], "👥", "total"),
            ("Present Today", "0", COLORS["success"], "✓", "present"),
            ("Absent Today", "0", COLORS["accent"], "✗", "absent"),
            ("Late Today", "0", COLORS["warning"], "⏰", "late"),
        ]

        for title, value, color, icon, key in stats_config:
            card = StatCard(cards_frame, title, value, color, icon)
            card.pack(side="left", expand=True, fill="both", padx=5)
            self.stat_cards[key] = card

        # Attendance percentage
        percent_frame = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=15)
        percent_frame.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(
            percent_frame,
            text="Today's Attendance Rate",
            font=("Helvetica", 16, "bold"),
            text_color=COLORS["text_primary"]
        ).pack(pady=(15, 5))

        self.percentage_label = ctk.CTkLabel(
            percent_frame,
            text="0%",
            font=("Helvetica", 36, "bold"),
            text_color=COLORS["success"]
        )
        self.percentage_label.pack(pady=5)

        self.progress_bar = ctk.CTkProgressBar(percent_frame, width=400, height=20)
        self.progress_bar.pack(pady=(5, 15))
        self.progress_bar.set(0)

        # Quick action buttons
        actions_frame = ctk.CTkFrame(self, fg_color="transparent")
        actions_frame.pack(fill="x", padx=20, pady=20)

        actions = [
            ("Scan Barcode", "📷", "scanner"),
            ("Add Student", "👤+", "add_student"),
            ("View Students", "📋", "view_students"),
            ("View Attendance", "📊", "attendance"),
            ("Reports", "📈", "reports"),
        ]

        for text, icon, frame_name in actions:
            btn = ctk.CTkButton(
                actions_frame,
                text=f"{icon}  {text}",
                width=150,
                height=50,
                font=("Helvetica", 12, "bold"),
                fg_color=COLORS["bg_card"],
                hover_color=COLORS["bg_secondary"],
                command=lambda f=frame_name: self.show_frame(f)
            )
            btn.pack(side="left", expand=True, padx=5)

        # Recent activity
        activity_frame = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=15)
        activity_frame.pack(fill="both", expand=True, padx=20, pady=10)

        ctk.CTkLabel(
            activity_frame,
            text="Recent Activity",
            font=("Helvetica", 16, "bold"),
            text_color=COLORS["text_primary"]
        ).pack(pady=(15, 10), anchor="w", padx=15)

        self.activity_list = ctk.CTkScrollableFrame(activity_frame, fg_color="transparent")
        self.activity_list.pack(fill="both", expand=True, padx=15, pady=10)

        # Refresh button
        ctk.CTkButton(
            self,
            text="🔄 Refresh",
            width=120,
            height=35,
            font=("Helvetica", 12),
            fg_color=COLORS["bg_card"],
            hover_color=COLORS["bg_secondary"],
            command=self.refresh_stats
        ).pack(pady=10)

    def refresh_stats(self):
        """Refresh dashboard statistics."""
        db = get_db()
        stats = db.get_attendance_stats()

        # Update cards
        self.stat_cards["total"].winfo_children()[1].configure(text=str(stats["total_students"]))
        self.stat_cards["present"].winfo_children()[1].configure(text=str(stats["present"]))
        self.stat_cards["absent"].winfo_children()[1].configure(text=str(stats["absent"]))
        self.stat_cards["late"].winfo_children()[1].configure(text=str(stats["late"]))

        # Update percentage
        rate = stats["attendance_rate"]
        self.percentage_label.configure(text=f"{rate}%")
        self.progress_bar.set(rate / 100)

        # Update color based on rate
        if rate >= 90:
            color = COLORS["success"]
        elif rate >= 75:
            color = COLORS["warning"]
        else:
            color = COLORS["accent"]

        self.percentage_label.configure(text_color=color)
        self.progress_bar.configure(progress_color=color)

        # Refresh recent activity
        for widget in self.activity_list.winfo_children():
            widget.destroy()

        recent = db.get_today_attendance()[:10]

        if not recent:
            ctk.CTkLabel(
                self.activity_list,
                text="No attendance records today",
                font=("Helvetica", 12),
                text_color=COLORS["text_secondary"]
            ).pack(pady=20)
        else:
            for record in recent:
                status_color = COLORS["success"] if record["status"] == "Present" else COLORS["warning"]

                row = ctk.CTkFrame(self.activity_list, fg_color=COLORS["bg_secondary"])
                row.pack(fill="x", pady=2)

                ctk.CTkLabel(
                    row,
                    text=record["name"],
                    font=("Helvetica", 12, "bold"),
                    text_color=COLORS["text_primary"]
                ).pack(side="left", padx=10, pady=5)

                ctk.CTkLabel(
                    row,
                    text=f"{record['class']}-{record['section']}",
                    font=("Helvetica", 10),
                    text_color=COLORS["text_secondary"]
                ).pack(side="left", padx=5)

                ctk.CTkLabel(
                    row,
                    text=record["status"],
                    font=("Helvetica", 10, "bold"),
                    text_color=status_color
                ).pack(side="right", padx=10)

                ctk.CTkLabel(
                    row,
                    text=record["time"],
                    font=("Helvetica", 10),
                    text_color=COLORS["text_secondary"]
                ).pack(side="right", padx=5)


class ScannerFrame(ctk.CTkFrame):
    """Barcode scanning interface."""

    def __init__(self, parent):
        super().__init__(parent, fg_color=COLORS["bg_primary"])
        self.parent = parent

        self.scanner = None
        self.camera_active = False
        self.last_scan_result = None

        self.build_ui()

    def build_ui(self):
        """Build scanner UI."""
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=20)

        ctk.CTkLabel(
            header,
            text="Barcode Scanner",
            font=("Helvetica", 24, "bold"),
            text_color=COLORS["text_primary"]
        ).pack(side="left")

        # Main content
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=20, pady=10)

        # Left: Camera preview or manual input
        left_frame = ctk.CTkFrame(content, fg_color=COLORS["bg_secondary"], corner_radius=15)
        left_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))

        # Camera preview label
        self.preview_label = ctk.CTkLabel(
            left_frame,
            text="Camera Preview\n(Start camera to scan)",
            font=("Helvetica", 14),
            text_color=COLORS["text_secondary"]
        )
        self.preview_label.pack(expand=True)

        # Camera controls
        cam_controls = ctk.CTkFrame(left_frame, fg_color="transparent")
        cam_controls.pack(fill="x", padx=15, pady=15)

        self.camera_btn = ctk.CTkButton(
            cam_controls,
            text="Start Camera",
            width=150,
            height=40,
            font=("Helvetica", 12, "bold"),
            fg_color=COLORS["success"],
            command=self.toggle_camera
        )
        self.camera_btn.pack(side="left", padx=5)

        ctk.CTkButton(
            cam_controls,
            text="Capture",
            width=100,
            height=40,
            font=("Helvetica", 12),
            fg_color=COLORS["info"],
            command=self.capture_frame
        ).pack(side="left", padx=5)

        # Right: Manual input and results
        right_frame = ctk.CTkFrame(content, fg_color=COLORS["bg_secondary"], corner_radius=15)
        right_frame.pack(side="right", fill="both", expand=True, padx=(10, 0))

        # Manual barcode entry
        ctk.CTkLabel(
            right_frame,
            text="Manual Barcode Entry",
            font=("Helvetica", 16, "bold"),
            text_color=COLORS["text_primary"]
        ).pack(pady=(20, 10))

        self.barcode_entry = ctk.CTkEntry(
            right_frame,
            width=280,
            height=40,
            font=("Helvetica", 14),
            placeholder_text="Enter barcode number..."
        )
        self.barcode_entry.pack(pady=10)
        self.barcode_entry.bind("<Return>", lambda e: self.manual_scan())

        ctk.CTkButton(
            right_frame,
            text="Mark Attendance",
            width=280,
            height=40,
            font=("Helvetica", 12, "bold"),
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            command=self.manual_scan
        ).pack(pady=10)

        # Separator
        ctk.CTkFrame(right_frame, height=2, fg_color=COLORS["border"]).pack(fill="x", padx=20, pady=15)

        # Scan result display
        ctk.CTkLabel(
            right_frame,
            text="Scan Result",
            font=("Helvetica", 16, "bold"),
            text_color=COLORS["text_primary"]
        ).pack(pady=10)

        self.result_frame = ctk.CTkFrame(right_frame, fg_color=COLORS["bg_card"], corner_radius=10)
        self.result_frame.pack(fill="both", expand=True, padx=15, pady=10)

        self.result_label = ctk.CTkLabel(
            self.result_frame,
            text="Scan a barcode to see results",
            font=("Helvetica", 12),
            text_color=COLORS["text_secondary"]
        )
        self.result_label.pack(expand=True)

        # Status
        self.status_label = ctk.CTkLabel(
            self,
            text="Ready to scan",
            font=("Helvetica", 12),
            text_color=COLORS["text_secondary"]
        )
        self.status_label.pack(pady=10)

    def toggle_camera(self):
        """Start or stop camera."""
        if not self.camera_active:
            self.start_camera()
        else:
            self.stop_camera()

    def start_camera(self):
        """Start webcam scanning."""
        try:
            self.scanner = ScannerFactory.create_scanner(
                "webcam",
                on_scan_callback=self.on_barcode_scanned
            )

            if self.scanner.start():
                self.camera_active = True
                self.camera_btn.configure(
                    text="Stop Camera",
                    fg_color=COLORS["accent"]
                )
                self.status_label.configure(
                    text="Camera active - Show barcode to scan",
                    text_color=COLORS["success"]
                )
                self.update_preview()
            else:
                self.status_label.configure(
                    text="Could not start camera",
                    text_color=COLORS["accent"]
                )

        except Exception as e:
            self.status_label.configure(
                text=f"Camera error: {str(e)}",
                text_color=COLORS["accent"]
            )

    def stop_camera(self):
        """Stop webcam scanning."""
        if self.scanner:
            self.scanner.stop()
            self.scanner = None

        self.camera_active = False
        self.camera_btn.configure(
            text="Start Camera",
            fg_color=COLORS["success"]
        )
        self.preview_label.configure(text="Camera Preview\n(Start camera to scan)")
        self.status_label.configure(
            text="Camera stopped",
            text_color=COLORS["text_secondary"]
        )

    def update_preview(self):
        """Update camera preview in GUI."""
        if self.camera_active and self.scanner:
            try:
                # Get frame bytes
                frame_bytes = self.scanner.get_frame_for_tkinter()

                if frame_bytes:
                    # Convert to PIL Image
                    from io import BytesIO
                    image = Image.open(BytesIO(frame_bytes))
                    photo = ImageTk.PhotoImage(image=image)

                    self.preview_label.configure(image=photo, text="")
                    self.preview_label.image = photo  # Keep reference

            except Exception as e:
                pass

            # Schedule next update
            self.after(30, self.update_preview)

    def on_barcode_scanned(self, result: ScanResult):
        """Handle scanned barcode."""
        self.after(0, lambda: self.process_barcode(result.barcode_data))

    def manual_scan(self):
        """Process manual barcode entry."""
        barcode = self.barcode_entry.get().strip()
        if barcode:
            self.process_barcode(barcode)
            self.barcode_entry.delete(0, "end")

    def process_barcode(self, barcode_number: str):
        """Process barcode and mark attendance."""
        manager = AttendanceManager()
        success, message, record = manager.mark_attendance_by_barcode(barcode_number)

        self.show_result(success, message, record)

    def show_result(self, success: bool, message: str, record: dict):
        """Display scan result."""
        # Clear previous result
        for widget in self.result_frame.winfo_children():
            widget.destroy()

        if success and record:
            # Success display
            bg_color = COLORS["success"] if record.get("status") == "Present" else COLORS["warning"]

            ctk.CTkLabel(
                self.result_frame,
                text="✓ Attendance Marked",
                font=("Helvetica", 16, "bold"),
                text_color=bg_color
            ).pack(pady=(15, 5))

            # Student info
            info_text = f"""
Name: {record.get('student_name', 'N/A')}
Class: {record.get('student_class', 'N/A')} - {record.get('student_section', 'N/A')}
Time: {record.get('time', 'N/A')}
Status: {record.get('status', 'N/A')}
            """

            ctk.CTkLabel(
                self.result_frame,
                text=info_text,
                font=("Helvetica", 12),
                text_color=COLORS["text_primary"]
            ).pack(pady=5)

            CustomPopup(self, message, "success")

        else:
            # Error display
            ctk.CTkLabel(
                self.result_frame,
                text="✗ Error",
                font=("Helvetica", 16, "bold"),
                text_color=COLORS["accent"]
            ).pack(pady=(15, 5))

            ctk.CTkLabel(
                self.result_frame,
                text=message,
                font=("Helvetica", 12),
                text_color=COLORS["text_primary"]
            ).pack(pady=5)

            CustomPopup(self, message, "error")

        self.status_label.configure(text=message)

    def capture_frame(self):
        """Capture current frame as image."""
        if self.scanner:
            path = self.scanner.capture_snapshot()
            if path:
                CustomPopup(self, f"Snapshot saved: {path}", "success")

    def destroy(self):
        """Cleanup on destroy."""
        self.stop_camera()
        super().destroy()


class StudentForm(ctk.CTkFrame):
    """Add/Edit student form."""

    def __init__(self, parent, student_id: int = None):
        super().__init__(parent, fg_color=COLORS["bg_primary"])
        self.parent = parent
        self.student_id = student_id
        self.db = get_db()
        self.photo_path = ""

        self.build_ui()

        if student_id:
            self.load_student_data()

    def build_ui(self):
        """Build student form."""
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=20)

        title = "Edit Student" if self.student_id else "Add New Student"
        ctk.CTkLabel(
            header,
            text=title,
            font=("Helvetica", 24, "bold"),
            text_color=COLORS["text_primary"]
        ).pack(side="left")

        # Form container
        form = ctk.CTkFrame(self, fg_color=COLORS["bg_secondary"], corner_radius=15)
        form.pack(fill="both", expand=True, padx=20, pady=10)

        # Form fields
        fields = [
            ("Full Name", "name", "Enter student name..."),
            ("Class", "class", "e.g., 10"),
            ("Section", "section", "e.g., A"),
            ("Barcode Number", "barcode", "Scan or enter barcode..."),
            ("Phone Number", "phone", "Optional contact number..."),
        ]

        self.entries = {}

        for label_text, key, placeholder in fields:
            frame = ctk.CTkFrame(form, fg_color="transparent")
            frame.pack(fill="x", padx=20, pady=8)

            ctk.CTkLabel(
                frame,
                text=label_text,
                font=("Helvetica", 12),
                text_color=COLORS["text_secondary"],
                width=120
            ).pack(side="left")

            entry = ctk.CTkEntry(
                frame,
                width=350,
                height=35,
                font=("Helvetica", 12),
                placeholder_text=placeholder
            )
            entry.pack(side="left", padx=10)
            self.entries[key] = entry

        # Photo upload
        photo_frame = ctk.CTkFrame(form, fg_color="transparent")
        photo_frame.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(
            photo_frame,
            text="Photo",
            font=("Helvetica", 12),
            text_color=COLORS["text_secondary"],
            width=120
        ).pack(side="left")

        self.photo_btn = ctk.CTkButton(
            photo_frame,
            text="Upload Photo",
            width=150,
            height=35,
            command=self.upload_photo
        )
        self.photo_btn.pack(side="left", padx=10)

        self.photo_label = ctk.CTkLabel(
            photo_frame,
            text="No photo selected",
            font=("Helvetica", 10),
            text_color=COLORS["text_secondary"]
        )
        self.photo_label.pack(side="left", padx=10)

        # Generate barcode button
        barcode_frame = ctk.CTkFrame(form, fg_color="transparent")
        barcode_frame.pack(fill="x", padx=20, pady=5)

        ctk.CTkButton(
            barcode_frame,
            text="Generate Barcode",
            width=150,
            height=35,
            fg_color=COLORS["info"],
            command=self.generate_barcode
        ).pack(side="left", padx=(130, 10))

        # Buttons
        btn_frame = ctk.CTkFrame(form, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=20)

        ctk.CTkButton(
            btn_frame,
            text="Save Student",
            width=150,
            height=40,
            font=("Helvetica", 12, "bold"),
            fg_color=COLORS["success"],
            command=self.save_student
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            btn_frame,
            text="Clear",
            width=100,
            height=40,
            fg_color=COLORS["bg_card"],
            command=self.clear_form
        ).pack(side="left", padx=5)

    def upload_photo(self):
        """Open file dialog to select student photo."""
        from tkinter import filedialog

        filepath = filedialog.askopenfilename(
            title="Select Student Photo",
            filetypes=[("Image files", "*.jpg *.jpeg *.png")]
        )

        if filepath:
            self.photo_path = filepath
            self.photo_label.configure(text=os.path.basename(filepath))

    def generate_barcode(self):
        """Generate unique barcode for student."""
        import random

        # Generate barcode: STU + timestamp + random
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        random_num = random.randint(1000, 9999)
        barcode = f"STU{timestamp}{random_num}"

        self.entries["barcode"].delete(0, "end")
        self.entries["barcode"].insert(0, barcode)

    def save_student(self):
        """Save student to database."""
        name = self.entries["name"].get().strip()
        student_class = self.entries["class"].get().strip()
        section = self.entries["section"].get().strip()
        barcode = self.entries["barcode"].get().strip()
        phone = self.entries["phone"].get().strip()

        # Validation
        if not all([name, student_class, section, barcode]):
            CustomPopup(self, "Please fill all required fields!", "error")
            return

        # Copy photo to assets if provided
        photo_dest = ""
        if self.photo_path:
            os.makedirs("assets/student_photos", exist_ok=True)
            ext = os.path.splitext(self.photo_path)[1]
            photo_dest = f"assets/student_photos/{barcode}{ext}"
            try:
                from shutil import copy2
                copy2(self.photo_path, photo_dest)
            except Exception as e:
                CustomPopup(self, f"Error copying photo: {e}", "warning")
                photo_dest = ""

        # Save to database
        if self.student_id:
            success, message = self.db.update_student(
                self.student_id,
                name=name,
                class_=student_class,
                section=section,
                barcode_number=barcode,
                phone_number=phone,
                photo_path=photo_dest
            )
        else:
            success, message = self.db.add_student(
                name=name,
                student_class=student_class,
                section=section,
                barcode_number=barcode,
                phone_number=phone,
                photo_path=photo_dest
            )

        if success:
            CustomPopup(self, message, "success")
            self.clear_form()
        else:
            CustomPopup(self, message, "error")

    def load_student_data(self):
        """Load existing student data for editing."""
        student = self.db.get_student_by_id(self.student_id)
        if student:
            self.entries["name"].insert(0, student["name"])
            self.entries["class"].insert(0, student["class"])
            self.entries["section"].insert(0, student["section"])
            self.entries["barcode"].insert(0, student["barcode_number"])
            self.entries["phone"].insert(0, student.get("phone_number", ""))

            if student.get("photo_path"):
                self.photo_path = student["photo_path"]
                self.photo_label.configure(text=os.path.basename(student["photo_path"]))

    def clear_form(self):
        """Clear all form fields."""
        for entry in self.entries.values():
            entry.delete(0, "end")
        self.photo_path = ""
        self.photo_label.configure(text="No photo selected")


class ViewStudentsFrame(ctk.CTkFrame):
    """View and manage students."""

    def __init__(self, parent):
        super().__init__(parent, fg_color=COLORS["bg_primary"])
        self.parent = parent
        self.db = get_db()

        self.build_ui()
        self.load_students()

    def build_ui(self):
        """Build students list UI."""
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=20)

        ctk.CTkLabel(
            header,
            text="Students",
            font=("Helvetica", 24, "bold"),
            text_color=COLORS["text_primary"]
        ).pack(side="left")

        # Search
        self.search_entry = ctk.CTkEntry(
            header,
            width=250,
            height=35,
            placeholder_text="Search students..."
        )
        self.search_entry.pack(side="right", padx=5)
        self.search_entry.bind("<KeyRelease>", lambda e: self.search_students())

        # Filters
        filters = ctk.CTkFrame(self, fg_color="transparent")
        filters.pack(fill="x", padx=20, pady=5)

        self.class_filter = ctk.CTkOptionMenu(
            filters,
            values=["All Classes"] + self.db.get_classes(),
            width=150,
            command=lambda x: self.load_students()
        )
        self.class_filter.pack(side="left", padx=5)

        self.section_filter = ctk.CTkOptionMenu(
            filters,
            values=["All Sections"] + self.db.get_sections(),
            width=150,
            command=lambda x: self.load_students()
        )
        self.section_filter.pack(side="left", padx=5)

        ctk.CTkButton(
            filters,
            text="Refresh",
            width=100,
            command=self.load_students
        ).pack(side="left", padx=5)

        # Students list
        self.list_frame = ctk.CTkScrollableFrame(
            self,
            fg_color=COLORS["bg_secondary"]
        )
        self.list_frame.pack(fill="both", expand=True, padx=20, pady=10)

        # Headers
        headers = ctk.CTkFrame(self.list_frame, fg_color=COLORS["bg_card"])
        headers.pack(fill="x", pady=(0, 5))

        for col, width in [("Name", 150), ("Class", 80), ("Section", 80),
                           ("Barcode", 150), ("Phone", 120), ("Actions", 150)]:
            ctk.CTkLabel(
                headers,
                text=col,
                font=("Helvetica", 11, "bold"),
                width=width
            ).pack(side="left", padx=5)

    def load_students(self):
        """Load students into list."""
        # Clear existing
        for widget in self.list_frame.winfo_children()[1:]:
            widget.destroy()

        # Get filter values
        class_filter = self.class_filter.get()
        section_filter = self.section_filter.get()

        class_filter = None if class_filter == "All Classes" else class_filter
        section_filter = None if section_filter == "All Sections" else section_filter

        students = self.db.get_all_students(class_filter, section_filter)

        if not students:
            ctk.CTkLabel(
                self.list_frame,
                text="No students found",
                text_color=COLORS["text_secondary"]
            ).pack(pady=20)
            return

        for student in students:
            row = ctk.CTkFrame(self.list_frame, fg_color="transparent")
            row.pack(fill="x", pady=2)

            ctk.CTkLabel(row, text=student["name"], width=150).pack(side="left", padx=5)
            ctk.CTkLabel(row, text=student["class"], width=80).pack(side="left", padx=5)
            ctk.CTkLabel(row, text=student["section"], width=80).pack(side="left", padx=5)
            ctk.CTkLabel(row, text=student["barcode_number"], width=150).pack(side="left", padx=5)
            ctk.CTkLabel(row, text=student.get("phone_number", ""), width=120).pack(side="left", padx=5)

            # Actions
            btn_frame = ctk.CTkFrame(row, fg_color="transparent", width=150)
            btn_frame.pack(side="left", padx=5)

            ctk.CTkButton(
                btn_frame,
                text="Edit",
                width=60,
                height=25,
                font=("Helvetica", 10),
                fg_color=COLORS["info"],
                command=lambda s=student: self.edit_student(s)
            ).pack(side="left", padx=2)

            ctk.CTkButton(
                btn_frame,
                text="Delete",
                width=60,
                height=25,
                font=("Helvetica", 10),
                fg_color=COLORS["accent"],
                command=lambda s=student: self.delete_student(s)
            ).pack(side="left", padx=2)

    def search_students(self):
        """Search students."""
        query = self.search_entry.get().strip()

        if not query:
            self.load_students()
            return

        # Clear existing
        for widget in self.list_frame.winfo_children()[1:]:
            widget.destroy()

        students = self.db.search_students(query)

        for student in students:
            row = ctk.CTkFrame(self.list_frame, fg_color="transparent")
            row.pack(fill="x", pady=2)

            ctk.CTkLabel(row, text=student["name"], width=150).pack(side="left", padx=5)
            ctk.CTkLabel(row, text=student["class"], width=80).pack(side="left", padx=5)
            ctk.CTkLabel(row, text=student["section"], width=80).pack(side="left", padx=5)
            ctk.CTkLabel(row, text=student["barcode_number"], width=150).pack(side="left", padx=5)
            ctk.CTkLabel(row, text=student.get("phone_number", ""), width=120).pack(side="left", padx=5)

    def edit_student(self, student: dict):
        """Open edit form for student."""
        CustomPopup(self, f"Edit student: {student['name']}", "info")

    def delete_student(self, student: dict):
        """Delete student after confirmation."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Confirm Delete")
        dialog.geometry("300x150")
        dialog.configure(fg_color=COLORS["bg_primary"])

        ctk.CTkLabel(
            dialog,
            text=f"Delete {student['name']}?",
            font=("Helvetica", 14, "bold")
        ).pack(pady=20)

        def confirm_delete():
            success, message = self.db.delete_student(student["student_id"])
            if success:
                CustomPopup(self, message, "success")
                self.load_students()
            else:
                CustomPopup(self, message, "error")
            dialog.destroy()

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=10)

        ctk.CTkButton(
            btn_frame,
            text="Delete",
            fg_color=COLORS["accent"],
            command=confirm_delete
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            btn_frame,
            text="Cancel",
            command=dialog.destroy
        ).pack(side="left", padx=5)


class AttendanceViewFrame(ctk.CTkFrame):
    """View attendance records."""

    def __init__(self, parent):
        super().__init__(parent, fg_color=COLORS["bg_primary"])
        self.parent = parent
        self.db = get_db()

        self.build_ui()
        self.load_attendance()

    def build_ui(self):
        """Build attendance view UI."""
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=20)

        ctk.CTkLabel(
            header,
            text="Attendance Records",
            font=("Helvetica", 24, "bold"),
            text_color=COLORS["text_primary"]
        ).pack(side="left")

        # Date filter
        self.date_entry = ctk.CTkEntry(
            header,
            width=150,
            height=35,
            placeholder_text="YYYY-MM-DD"
        )
        self.date_entry.insert(0, datetime.now().strftime("%Y-%m-%d"))
        self.date_entry.pack(side="right", padx=5)

        ctk.CTkButton(
            header,
            text="Load",
            width=80,
            height=35,
            command=self.load_attendance
        ).pack(side="right", padx=5)

        # Summary cards
        cards = ctk.CTkFrame(self, fg_color="transparent")
        cards.pack(fill="x", padx=20, pady=10)

        self.present_card = StatCard(cards, "Present", "0", COLORS["success"])
        self.present_card.pack(side="left", expand=True, fill="both", padx=5)

        self.late_card = StatCard(cards, "Late", "0", COLORS["warning"])
        self.late_card.pack(side="left", expand=True, fill="both", padx=5)

        self.absent_card = StatCard(cards, "Absent", "0", COLORS["accent"])
        self.absent_card.pack(side="left", expand=True, fill="both", padx=5)

        # Attendance list
        self.list_frame = ctk.CTkScrollableFrame(
            self,
            fg_color=COLORS["bg_secondary"]
        )
        self.list_frame.pack(fill="both", expand=True, padx=20, pady=10)

    def load_attendance(self):
        """Load attendance for selected date."""
        date = self.date_entry.get().strip() or datetime.now().strftime("%Y-%m-%d")

        # Clear existing
        for widget in self.list_frame.winfo_children():
            widget.destroy()

        # Get stats
        stats = self.db.get_attendance_stats(date)
        self.present_card.winfo_children()[1].configure(text=str(stats["present"]))
        self.late_card.winfo_children()[1].configure(text=str(stats["late"]))
        self.absent_card.winfo_children()[1].configure(text=str(stats["absent"]))

        # Get records
        records = self.db.get_attendance_by_date(date)

        if not records:
            ctk.CTkLabel(
                self.list_frame,
                text="No attendance records for this date",
                text_color=COLORS["text_secondary"]
            ).pack(pady=20)
            return

        for record in records:
            row = ctk.CTkFrame(self.list_frame, fg_color=COLORS["bg_card"])
            row.pack(fill="x", pady=2)

            ctk.CTkLabel(
                row,
                text=record["name"],
                font=("Helvetica", 12, "bold"),
                width=150
            ).pack(side="left", padx=10, pady=5)

            ctk.CTkLabel(row, text=record["class"], width=60).pack(side="left", padx=5)
            ctk.CTkLabel(row, text=record["section"], width=60).pack(side="left", padx=5)
            ctk.CTkLabel(row, text=record["time"], width=80).pack(side="left", padx=5)

            status_color = COLORS["success"] if record["status"] == "Present" else COLORS["warning"]
            ctk.CTkLabel(
                row,
                text=record["status"],
                font=("Helvetica", 11, "bold"),
                text_color=status_color,
                width=80
            ).pack(side="left", padx=5)


class ReportsFrame(ctk.CTkFrame):
    """Reports generation and export."""

    def __init__(self, parent):
        super().__init__(parent, fg_color=COLORS["bg_primary"])
        self.parent = parent
        self.report_gen = ReportGenerator()

        self.build_ui()

    def build_ui(self):
        """Build reports UI."""
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=20)

        ctk.CTkLabel(
            header,
            text="Reports",
            font=("Helvetica", 24, "bold"),
            text_color=COLORS["text_primary"]
        ).pack(side="left")

        # Report type selection
        options_frame = ctk.CTkFrame(self, fg_color=COLORS["bg_secondary"], corner_radius=15)
        options_frame.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(
            options_frame,
            text="Report Type",
            font=("Helvetica", 14, "bold")
        ).pack(pady=(15, 10))

        self.report_type = ctk.CTkOptionMenu(
            options_frame,
            values=[
                "Daily Report",
                "Monthly Report",
                "Student Report",
                "Late Arrivals",
                "Comprehensive Report"
            ],
            width=300,
            font=("Helvetica", 12)
        )
        self.report_type.pack(pady=5)

        # Date/Month selection
        filter_frame = ctk.CTkFrame(options_frame, fg_color="transparent")
        filter_frame.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(filter_frame, text="Date (YYYY-MM-DD):").pack(side="left", padx=5)
        self.date_entry = ctk.CTkEntry(filter_frame, width=150, placeholder_text="2024-01-01")
        self.date_entry.insert(0, datetime.now().strftime("%Y-%m-%d"))
        self.date_entry.pack(side="left", padx=5)

        ctk.CTkLabel(filter_frame, text="Month:").pack(side="left", padx=(20, 5))
        self.month_entry = ctk.CTkEntry(filter_frame, width=80, placeholder_text="1-12")
        self.month_entry.insert(0, str(datetime.now().month))
        self.month_entry.pack(side="left", padx=5)

        ctk.CTkLabel(filter_frame, text="Year:").pack(side="left", padx=(20, 5))
        self.year_entry = ctk.CTkEntry(filter_frame, width=80, placeholder_text="2024")
        self.year_entry.insert(0, str(datetime.now().year))
        self.year_entry.pack(side="left", padx=5)

        # Student ID (for student report)
        student_frame = ctk.CTkFrame(options_frame, fg_color="transparent")
        student_frame.pack(fill="x", padx=20, pady=5)

        ctk.CTkLabel(student_frame, text="Student ID:").pack(side="left", padx=5)
        self.student_id_entry = ctk.CTkEntry(student_frame, width=150, placeholder_text="Enter student ID")
        self.student_id_entry.pack(side="left", padx=5)

        # Export format
        format_frame = ctk.CTkFrame(options_frame, fg_color="transparent")
        format_frame.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(format_frame, text="Export Format:").pack(side="left", padx=5)
        self.export_format = ctk.CTkOptionMenu(
            format_frame,
            values=["CSV", "Excel"],
            width=120
        )
        self.export_format.pack(side="left", padx=5)

        # Generate button
        ctk.CTkButton(
            options_frame,
            text="Generate Report",
            width=200,
            height=40,
            font=("Helvetica", 14, "bold"),
            fg_color=COLORS["accent"],
            command=self.generate_report
        ).pack(pady=20)

        # Preview area
        preview_frame = ctk.CTkFrame(self, fg_color=COLORS["bg_secondary"], corner_radius=15)
        preview_frame.pack(fill="both", expand=True, padx=20, pady=10)

        ctk.CTkLabel(
            preview_frame,
            text="Report Preview",
            font=("Helvetica", 16, "bold")
        ).pack(pady=(15, 10))

        self.preview_text = ctk.CTkTextbox(
            preview_frame,
            font=("Courier", 11),
            wrap="none"
        )
        self.preview_text.pack(fill="both", expand=True, padx=15, pady=10)

    def generate_report(self):
        """Generate and export report."""
        report_type = self.report_type.get()
        date = self.date_entry.get().strip()
        month = int(self.month_entry.get() or datetime.now().month)
        year = int(self.year_entry.get() or datetime.now().year)
        student_id = self.student_id_entry.get().strip()
        export_format = self.export_format.get()

        try:
            if report_type == "Daily Report":
                df = self.report_gen.generate_daily_report(date)
            elif report_type == "Monthly Report":
                df = self.report_gen.generate_monthly_report(year, month)
            elif report_type == "Student Report":
                if not student_id:
                    CustomPopup(self, "Please enter Student ID!", "error")
                    return
                df = self.report_gen.generate_student_report(int(student_id))
            elif report_type == "Late Arrivals":
                df = self.report_gen.generate_late_report(year, month)
            elif report_type == "Comprehensive Report":
                path = self.report_gen.export_comprehensive_excel(
                    date=date, month=month, year=year
                )
                CustomPopup(self, f"Comprehensive report exported!\n{path}", "success")
                self.preview_text.delete("1.0", "end")
                self.preview_text.insert("1.0", f"Comprehensive report exported to:\n{path}")
                return

            # Preview
            self.preview_text.delete("1.0", "end")
            self.preview_text.insert("1.0", df.to_string())

            # Export
            if export_format == "CSV":
                path = self.report_gen.export_to_csv(df)
            else:
                path = self.report_gen.export_to_excel(df)

            CustomPopup(self, f"Report exported!\n{path}", "success")

        except Exception as e:
            CustomPopup(self, f"Error: {str(e)}", "error")


class AnalyticsFrame(ctk.CTkFrame):
    """Attendance analytics with charts."""

    def __init__(self, parent):
        super().__init__(parent, fg_color=COLORS["bg_primary"])
        self.parent = parent
        self.db = get_db()

        self.build_ui()

    def build_ui(self):
        """Build analytics UI."""
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=20)

        ctk.CTkLabel(
            header,
            text="Analytics Dashboard",
            font=("Helvetica", 24, "bold"),
            text_color=COLORS["text_primary"]
        ).pack(side="left")

        if not MATPLOTLIB_AVAILABLE:
            ctk.CTkLabel(
                self,
                text="Matplotlib not available. Install for charts.",
                text_color=COLORS["accent"]
            ).pack(pady=50)
            return

        # Charts container
        charts_frame = ctk.CTkFrame(self, fg_color="transparent")
        charts_frame.pack(fill="both", expand=True, padx=20, pady=10)

        # Daily attendance chart
        chart1_frame = ctk.CTkFrame(charts_frame, fg_color=COLORS["bg_secondary"])
        chart1_frame.pack(side="top", fill="both", expand=True, pady=5)

        ctk.CTkLabel(
            chart1_frame,
            text="Daily Attendance (Current Month)",
            font=("Helvetica", 14, "bold")
        ).pack(pady=5)

        self.chart1_canvas = None
        self.create_daily_chart(chart1_frame)

        # Bottom charts
        bottom_frame = ctk.CTkFrame(charts_frame, fg_color="transparent")
        bottom_frame.pack(side="top", fill="both", expand=True, pady=5)

        # Attendance by class
        chart2_frame = ctk.CTkFrame(bottom_frame, fg_color=COLORS["bg_secondary"])
        chart2_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))

        ctk.CTkLabel(
            chart2_frame,
            text="Today's Attendance",
            font=("Helvetica", 14, "bold")
        ).pack(pady=5)

        self.create_pie_chart(chart2_frame)

        # Late arrivals chart
        chart3_frame = ctk.CTkFrame(bottom_frame, fg_color=COLORS["bg_secondary"])
        chart3_frame.pack(side="right", fill="both", expand=True, padx=(5, 0))

        ctk.CTkLabel(
            chart3_frame,
            text="Late Arrivals Trend",
            font=("Helvetica", 14, "bold")
        ).pack(pady=5)

        self.create_late_chart(chart3_frame)

        # Refresh button
        ctk.CTkButton(
            self,
            text="Refresh Charts",
            width=150,
            command=self.refresh_charts
        ).pack(pady=10)

    def create_daily_chart(self, parent):
        """Create daily attendance bar chart."""
        try:
            fig = Figure(figsize=(10, 4), facecolor=COLORS["bg_secondary"])
            ax = fig.add_subplot(111)
            ax.set_facecolor(COLORS["bg_secondary"])

            # Get data
            now = datetime.now()
            monthly_stats = self.db.get_monthly_stats(now.year, now.month)

            if monthly_stats:
                dates = [s["date"][-2:] for s in monthly_stats]  # Day only
                present = [s["present"] for s in monthly_stats]
                late = [s["late"] for s in monthly_stats]

                x = range(len(dates))
                ax.bar(x, present, label="Present", color=COLORS["success"], alpha=0.8)
                ax.bar(x, late, bottom=present, label="Late", color=COLORS["warning"], alpha=0.8)

                ax.set_xlabel("Day", color="white")
                ax.set_ylabel("Students", color="white")
                ax.set_title(f"Daily Attendance - {now.strftime('%B %Y')}", color="white")
                ax.tick_params(colors="white")
                ax.legend(facecolor=COLORS["bg_secondary"], edgecolor="white", labelcolor="white")
            else:
                ax.text(0.5, 0.5, "No data available",
                       ha="center", va="center", color="white", transform=ax.transAxes)

            fig.tight_layout()

            canvas = FigureCanvasTkAgg(fig, master=parent)
            canvas.draw()
            canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=5)
            self.chart1_canvas = canvas

        except Exception as e:
            ctk.CTkLabel(parent, text=f"Chart error: {e}", text_color=COLORS["accent"]).pack()

    def create_pie_chart(self, parent):
        """Create today's attendance pie chart."""
        try:
            fig = Figure(figsize=(5, 4), facecolor=COLORS["bg_secondary"])
            ax = fig.add_subplot(111)
            ax.set_facecolor(COLORS["bg_secondary"])

            stats = self.db.get_attendance_stats()
            sizes = [stats["present"], stats["late"], stats["absent"]]
            labels = ["Present", "Late", "Absent"]
            colors = [COLORS["success"], COLORS["warning"], COLORS["accent"]]

            if sum(sizes) > 0:
                ax.pie(sizes, labels=labels, colors=colors, autopct="%1.1f%%",
                      textprops={"color": "white"})
                ax.set_title("Today's Status", color="white")
            else:
                ax.text(0.5, 0.5, "No data",
                       ha="center", va="center", color="white", transform=ax.transAxes)

            canvas = FigureCanvasTkAgg(fig, master=parent)
            canvas.draw()
            canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=5)

        except Exception as e:
            ctk.CTkLabel(parent, text=f"Chart error: {e}", text_color=COLORS["accent"]).pack()

    def create_late_chart(self, parent):
        """Create late arrivals trend chart."""
        try:
            fig = Figure(figsize=(5, 4), facecolor=COLORS["bg_secondary"])
            ax = fig.add_subplot(111)
            ax.set_facecolor(COLORS["bg_secondary"])

            now = datetime.now()
            monthly_stats = self.db.get_monthly_stats(now.year, now.month)

            if monthly_stats:
                dates = [s["date"][-2:] for s in monthly_stats]
                late = [s["late"] for s in monthly_stats]

                ax.plot(dates, late, marker="o", color=COLORS["warning"], linewidth=2)
                ax.set_xlabel("Day", color="white")
                ax.set_ylabel("Late Count", color="white")
                ax.set_title("Late Arrivals Trend", color="white")
                ax.tick_params(colors="white")
                ax.grid(True, alpha=0.3)
            else:
                ax.text(0.5, 0.5, "No data available",
                       ha="center", va="center", color="white", transform=ax.transAxes)

            fig.tight_layout()

            canvas = FigureCanvasTkAgg(fig, master=parent)
            canvas.draw()
            canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=5)

        except Exception as e:
            ctk.CTkLabel(parent, text=f"Chart error: {e}", text_color=COLORS["accent"]).pack()

    def refresh_charts(self):
        """Refresh all charts."""
        for widget in self.winfo_children():
            widget.destroy()
        self.build_ui()


class SmartAttendanceApp(ctk.CTk):
    """Main application window."""

    def __init__(self):
        super().__init__()

        # Window configuration
        self.title("Smart Barcode Attendance Management System")
        self.geometry("1200x800")
        self.minsize(1000, 700)

        # Set theme
        self.configure(fg_color=COLORS["bg_primary"])

        # Initialize database
        self.db = get_db()

        # Show loading screen
        self.show_loading()

        # Build UI after loading
        self.after(2500, self.build_ui)

    def show_loading(self):
        """Show loading screen."""
        self.loading = LoadingScreen(self)

    def build_ui(self):
        """Build main application UI."""
        # Create container
        self.container = ctk.CTkFrame(self, fg_color=COLORS["bg_primary"])
        self.container.pack(fill="both", expand=True)

        # Show login screen first
        self.show_login()

    def show_login(self):
        """Show login screen."""
        # Clear container
        for widget in self.container.winfo_children():
            widget.destroy()

        login = LoginScreen(self.container, self.show_main_app)
        login.pack(fill="both", expand=True)

    def show_main_app(self):
        """Show main application with sidebar and content."""
        # Clear container
        for widget in self.container.winfo_children():
            widget.destroy()

        # Sidebar
        self.sidebar = ctk.CTkFrame(
            self.container,
            width=200,
            fg_color=COLORS["bg_secondary"]
        )
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        # Logo
        ctk.CTkLabel(
            self.sidebar,
            text="📚 Smart\nAttendance",
            font=("Helvetica", 16, "bold"),
            text_color=COLORS["accent"]
        ).pack(pady=(30, 20))

        # Navigation buttons
        nav_items = [
            ("Dashboard", "dashboard", "🏠"),
            ("Scan Barcode", "scanner", "📷"),
            ("Add Student", "add_student", "👤+"),
            ("View Students", "view_students", "📋"),
            ("Attendance", "attendance", "📊"),
            ("Reports", "reports", "📈"),
            ("Analytics", "analytics", "📉"),
        ]

        self.nav_buttons = {}

        for text, frame_name, icon in nav_items:
            btn = ctk.CTkButton(
                self.sidebar,
                text=f"{icon}  {text}",
                width=180,
                height=40,
                font=("Helvetica", 12),
                fg_color="transparent",
                hover_color=COLORS["bg_card"],
                anchor="w",
                command=lambda f=frame_name: self.show_frame(f)
            )
            btn.pack(pady=2, padx=10)
            self.nav_buttons[frame_name] = btn

        # Separator
        ctk.CTkFrame(self.sidebar, height=2, fg_color=COLORS["border"]).pack(fill="x", padx=15, pady=15)

        # Exit button
        ctk.CTkButton(
            self.sidebar,
            text="🚪 Exit",
            width=180,
            height=40,
            font=("Helvetica", 12),
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            command=self.quit
        ).pack(pady=10)

        # Version
        ctk.CTkLabel(
            self.sidebar,
            text="v1.0.0",
            font=("Helvetica", 10),
            text_color=COLORS["text_secondary"]
        ).pack(side="bottom", pady=10)

        # Content area
        self.content = ctk.CTkFrame(self.container, fg_color=COLORS["bg_primary"])
        self.content.pack(side="right", fill="both", expand=True)

        # Frames dictionary
        self.frames = {}

        # Create frames
        for frame_name, FrameClass in [
            ("dashboard", DashboardHome),
            ("scanner", ScannerFrame),
            ("add_student", StudentForm),
            ("view_students", ViewStudentsFrame),
            ("attendance", AttendanceViewFrame),
            ("reports", ReportsFrame),
            ("analytics", AnalyticsFrame),
        ]:
            frame = FrameClass(self.content)
            self.frames[frame_name] = frame

        # Show dashboard by default
        self.show_frame("dashboard")

    def show_frame(self, frame_name: str):
        """Show specified frame."""
        # Hide all frames
        for frame in self.frames.values():
            frame.pack_forget()

        # Show selected frame
        if frame_name in self.frames:
            self.frames[frame_name].pack(fill="both", expand=True)

        # Update button states
        for name, btn in self.nav_buttons.items():
            if name == frame_name:
                btn.configure(fg_color=COLORS["bg_card"])
            else:
                btn.configure(fg_color="transparent")


if __name__ == "__main__":
    app = SmartAttendanceApp()
    app.mainloop()
