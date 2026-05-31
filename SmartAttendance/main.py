"""
main.py — Application Entry Point
Smart Barcode Attendance Management System

Run this file to start the application:
    python main.py

On first launch:
  • The SQLite database is created automatically.
  • Ten demo students are seeded so the app is usable immediately.
  • Default admin credentials: admin / admin123

Startup sequence:
  1. Show an animated loading/splash screen
  2. Initialise the database in the background
  3. Transition to the login window
"""

import os
import sys
import time
import threading
import tkinter as tk

# ── Validate Python version ───────────────────────────────────────────
if sys.version_info < (3, 10):
    print("ERROR: Python 3.10 or newer is required.")
    sys.exit(1)

# ── Ensure working directory is the project root ──────────────────────
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import customtkinter as ctk
from database  import DatabaseManager
from dashboard import LoginWindow


# ══════════════════════════════════════════════════════════════════════
# Animated splash / loading screen
# ══════════════════════════════════════════════════════════════════════

class SplashScreen(ctk.CTk):
    """
    A 2-second branded splash screen that plays while the DB initialises.
    """

    _STEPS = [
        "Initialising database…",
        "Loading modules…",
        "Seeding demo data…",
        "Starting dashboard…",
    ]

    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.overrideredirect(True)     # borderless window
        self.attributes("-topmost", True)

        # Centre on screen
        w, h = 540, 360
        sw   = self.winfo_screenwidth()
        sh   = self.winfo_screenheight()
        x    = (sw - w) // 2
        y    = (sh - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.configure(fg_color="#0d1117")

        self._build()
        self._step_index = 0
        self._init_done  = False

        # Run heavy init in background
        threading.Thread(target=self._background_init, daemon=True).start()
        # Animate progress bar
        self.after(200, self._tick)

    def _build(self):
        # Top accent bar
        ctk.CTkFrame(self, height=4, fg_color="#58a6ff",
                     corner_radius=0).pack(fill="x")

        ctk.CTkLabel(self, text="🎓",
                     font=("Segoe UI", 56)).pack(pady=(30, 4))

        ctk.CTkLabel(self, text="SmartAttend",
                     font=("Segoe UI", 28, "bold"),
                     text_color="#58a6ff").pack()

        ctk.CTkLabel(self, text="Barcode Attendance Management System",
                     font=("Segoe UI", 12),
                     text_color="#8b949e").pack(pady=(2, 30))

        # Progress bar
        self._progress = ctk.CTkProgressBar(self, width=420, height=6,
                                            fg_color="#21262d",
                                            progress_color="#58a6ff",
                                            corner_radius=3)
        self._progress.pack()
        self._progress.set(0)

        # Status label
        self._status_lbl = ctk.CTkLabel(
            self, text="Starting up…",
            font=("Segoe UI", 11),
            text_color="#484f58",
        )
        self._status_lbl.pack(pady=(10, 0))

        # Version tag
        ctk.CTkLabel(self, text="v1.0.0  •  © 2025 SmartAttend",
                     font=("Segoe UI", 9),
                     text_color="#21262d").pack(side="bottom", pady=12)

    def _background_init(self):
        """Heavy work that runs off the main thread."""
        db = DatabaseManager()
        db.seed_demo_data()
        # Brief pause so the splash is visible even on fast machines
        time.sleep(1.6)
        self._init_done = True

    def _tick(self):
        if self._step_index < len(self._STEPS):
            progress = (self._step_index + 1) / (len(self._STEPS) + 1)
            self._progress.set(progress)
            self._status_lbl.configure(text=self._STEPS[self._step_index])
            self._step_index += 1
            self.after(400, self._tick)
        elif self._init_done:
            self._progress.set(1.0)
            self._status_lbl.configure(text="Ready!", text_color="#3fb950")
            self.after(400, self._launch_login)
        else:
            self.after(100, self._tick)   # wait for background thread

    def _launch_login(self):
        self.destroy()
        app = LoginWindow()
        app.mainloop()


# ══════════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════════

def main():
    # Create required directories if absent
    for directory in ["database", "assets", "exports/attendance_reports"]:
        os.makedirs(directory, exist_ok=True)

    splash = SplashScreen()
    splash.mainloop()


if __name__ == "__main__":
    main()
