"""
dashboard.py — SmartAttendanceDashboard
Smart Barcode Attendance Management System

The entire GUI lives here. Built with CustomTkinter for a modern,
dark-themed look. Navigation is handled by a fixed left sidebar;
the right area swaps between section frames.
"""

import os
import time
import threading
import tkinter as tk
from tkinter import messagebox, filedialog
from datetime import datetime
from functools import partial

import customtkinter as ctk
from PIL import Image, ImageTk, ImageDraw

# Local modules
from database   import DatabaseManager
from scanner    import BarcodeScanner
from attendance import AttendanceManager
from reports    import ReportsManager

# ── Matplotlib embedding ──────────────────────────────────────────────
import matplotlib
matplotlib.use("Agg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


# ══════════════════════════════════════════════════════════════════════
# Palette & typography
# ══════════════════════════════════════════════════════════════════════
COLORS = {
    "bg_main":    "#0d1117",
    "bg_sidebar": "#010409",
    "bg_card":    "#161b22",
    "bg_input":   "#21262d",
    "border":     "#30363d",
    "accent":     "#58a6ff",
    "accent2":    "#1f6feb",
    "green":      "#3fb950",
    "yellow":     "#d29922",
    "red":        "#f85149",
    "text_main":  "#e6edf3",
    "text_dim":   "#8b949e",
    "text_muted": "#484f58",
    "white":      "#ffffff",
}

FONT_FAMILY = "Segoe UI"


def col(key):
    return COLORS[key]


# ══════════════════════════════════════════════════════════════════════
# Re-usable widget helpers
# ══════════════════════════════════════════════════════════════════════

def make_card(parent, **kwargs) -> ctk.CTkFrame:
    defaults = dict(
        fg_color=col("bg_card"),
        border_width=1,
        border_color=col("border"),
        corner_radius=10,
    )
    defaults.update(kwargs)
    return ctk.CTkFrame(parent, **defaults)


def label(parent, text, size=13, weight="normal",
          color=None, **kwargs) -> ctk.CTkLabel:
    return ctk.CTkLabel(
        parent, text=text,
        font=(FONT_FAMILY, size, weight),
        text_color=color or col("text_main"),
        **kwargs,
    )


def btn(parent, text, command, width=140, height=36,
        fg=None, hover=None, **kwargs) -> ctk.CTkButton:
    return ctk.CTkButton(
        parent, text=text, command=command,
        width=width, height=height,
        fg_color=fg or col("accent2"),
        hover_color=hover or col("accent"),
        text_color=col("white"),
        font=(FONT_FAMILY, 13, "bold"),
        corner_radius=8,
        **kwargs,
    )


def entry(parent, placeholder="", width=250, **kwargs) -> ctk.CTkEntry:
    return ctk.CTkEntry(
        parent, placeholder_text=placeholder,
        width=width, height=36,
        fg_color=col("bg_input"),
        border_color=col("border"),
        text_color=col("text_main"),
        placeholder_text_color=col("text_muted"),
        font=(FONT_FAMILY, 13),
        corner_radius=8,
        **kwargs,
    )


def separator(parent, color=None) -> ctk.CTkFrame:
    return ctk.CTkFrame(parent, height=1,
                        fg_color=color or col("border"), corner_radius=0)


def placeholder_avatar(size: int = 80) -> Image.Image:
    """Create a circular grey placeholder avatar."""
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([0, 0, size - 1, size - 1], fill="#21262d", outline="#30363d", width=2)
    # Simple person silhouette
    head_r = size // 6
    cx = size // 2
    draw.ellipse([cx - head_r, size // 6, cx + head_r, size // 6 + head_r * 2],
                 fill="#484f58")
    draw.ellipse([cx - size // 4, size // 2, cx + size // 4, size - size // 8],
                 fill="#484f58")
    return img


# ══════════════════════════════════════════════════════════════════════
# Popup notifications
# ══════════════════════════════════════════════════════════════════════

class ToastPopup(ctk.CTkToplevel):
    """
    Non-blocking toast notification that auto-dismisses after `ms` ms.
    kind: 'success' | 'error' | 'info' | 'warning'
    """
    KIND_COLORS = {
        "success": ("#3fb950", "✅"),
        "error":   ("#f85149", "❌"),
        "info":    ("#58a6ff", "ℹ️"),
        "warning": ("#d29922", "⚠️"),
    }

    def __init__(self, parent, title: str, message: str,
                 kind: str = "info", ms: int = 3000):
        super().__init__(parent)
        color, icon = self.KIND_COLORS.get(kind, ("#58a6ff", "ℹ️"))

        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(fg_color=col("bg_card"))

        # Position bottom-right of parent
        pw, ph = parent.winfo_width(), parent.winfo_height()
        px, py = parent.winfo_rootx(),  parent.winfo_rooty()
        self.geometry(f"340x90+{px + pw - 355}+{py + ph - 105}")

        outer = ctk.CTkFrame(self, fg_color=col("bg_card"),
                             border_width=2, border_color=color,
                             corner_radius=10)
        outer.pack(fill="both", expand=True, padx=2, pady=2)

        ctk.CTkLabel(outer, text=f"  {icon}  {title}",
                     font=(FONT_FAMILY, 13, "bold"),
                     text_color=color).pack(anchor="w", padx=12, pady=(10, 2))
        ctk.CTkLabel(outer, text=message,
                     font=(FONT_FAMILY, 11),
                     text_color=col("text_dim"),
                     wraplength=300, justify="left").pack(anchor="w",
                                                          padx=12, pady=(0, 10))

        self.after(ms, self.destroy)


# ══════════════════════════════════════════════════════════════════════
# Stat card widget
# ══════════════════════════════════════════════════════════════════════

class StatCard(ctk.CTkFrame):
    def __init__(self, parent, title: str, value: str,
                 subtitle: str = "", accent_color: str = None, **kwargs):
        super().__init__(parent,
                         fg_color=col("bg_card"),
                         border_width=1, border_color=col("border"),
                         corner_radius=12, **kwargs)
        ac = accent_color or col("accent")

        ctk.CTkFrame(self, height=3, fg_color=ac,
                     corner_radius=2).pack(fill="x", padx=0, pady=(0, 0))

        label(self, title, 11, "normal", col("text_dim")).pack(
            anchor="w", padx=16, pady=(10, 0))
        self._val_lbl = label(self, value, 28, "bold", ac)
        self._val_lbl.pack(anchor="w", padx=16, pady=(2, 0))
        if subtitle:
            label(self, subtitle, 10, "normal", col("text_muted")).pack(
                anchor="w", padx=16, pady=(0, 10))
        else:
            ctk.CTkFrame(self, height=10, fg_color="transparent").pack()

    def update_value(self, value: str, subtitle: str = ""):
        self._val_lbl.configure(text=value)


# ══════════════════════════════════════════════════════════════════════
# Section frames
# ══════════════════════════════════════════════════════════════════════

class SectionBase(ctk.CTkFrame):
    """All section frames inherit from this."""

    def __init__(self, parent, db: DatabaseManager,
                 attendance: AttendanceManager, reports: ReportsManager,
                 notify, **kwargs):
        super().__init__(parent,
                         fg_color=col("bg_main"), corner_radius=0, **kwargs)
        self.db         = db
        self.attendance = attendance
        self.reports    = reports
        self.notify     = notify   # callable(title, msg, kind)
        self._build()

    def _build(self):
        pass  # override in subclasses

    def refresh(self):
        pass  # called when section is activated


# ──────────────────────────────────────────────────────────────────────
# Home / Dashboard section
# ──────────────────────────────────────────────────────────────────────

class HomeSection(SectionBase):

    def _build(self):
        # Header
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=24, pady=(20, 0))
        label(hdr, "Dashboard", 22, "bold").pack(side="left")
        self._clock_lbl = label(hdr, "", 12, "normal", col("text_dim"))
        self._clock_lbl.pack(side="right")
        self._update_clock()

        separator(self).pack(fill="x", padx=24, pady=12)

        # Stat cards row
        card_row = ctk.CTkFrame(self, fg_color="transparent")
        card_row.pack(fill="x", padx=24, pady=(0, 16))
        for i in range(5):
            card_row.columnconfigure(i, weight=1, uniform="cards")

        self._cards = {}
        card_defs = [
            ("total",      "Total Students",    "0", col("accent")),
            ("present",    "Present Today",     "0", col("green")),
            ("absent",     "Absent Today",      "0", col("red")),
            ("late",       "Late Arrivals",     "0", col("yellow")),
            ("percentage", "Attendance %",      "0%", col("accent")),
        ]
        for i, (key, title, val, ac) in enumerate(card_defs):
            c = StatCard(card_row, title, val, accent_color=ac)
            c.grid(row=0, column=i, padx=6, pady=4, sticky="nsew")
            self._cards[key] = c

        # Charts row
        charts_row = ctk.CTkFrame(self, fg_color="transparent")
        charts_row.pack(fill="both", expand=True, padx=24, pady=(0, 20))
        charts_row.columnconfigure(0, weight=3)
        charts_row.columnconfigure(1, weight=2)
        charts_row.rowconfigure(0, weight=1)

        # Weekly bar
        self._bar_card = make_card(charts_row)
        self._bar_card.grid(row=0, column=0, padx=(0, 10), sticky="nsew")
        self._bar_canvas_widget = None

        # Pie
        self._pie_card = make_card(charts_row)
        self._pie_card.grid(row=0, column=1, sticky="nsew")
        self._pie_canvas_widget = None

    def _update_clock(self):
        self._clock_lbl.configure(
            text=datetime.now().strftime("%A, %d %B %Y   %H:%M:%S")
        )
        self.after(1000, self._update_clock)

    def refresh(self):
        stats = self.db.get_today_stats()
        self._cards["total"].update_value(str(stats["total"]))
        self._cards["present"].update_value(str(stats["present"]))
        self._cards["absent"].update_value(str(stats["absent"]))
        self._cards["late"].update_value(str(stats["late"]))
        self._cards["percentage"].update_value(f"{stats['percentage']}%")
        self._draw_bar()
        self._draw_pie()

    def _draw_bar(self):
        fig = self.reports.chart_weekly_bar()
        self._embed_figure(fig, self._bar_card, "_bar_canvas_widget")
        plt_close(fig)

    def _draw_pie(self):
        fig = self.reports.chart_today_pie()
        self._embed_figure(fig, self._pie_card, "_pie_canvas_widget")
        plt_close(fig)

    def _embed_figure(self, fig, card, attr_name):
        old = getattr(self, attr_name, None)
        if old:
            old.get_tk_widget().destroy()
        canvas = FigureCanvasTkAgg(fig, master=card)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=4, pady=4)
        setattr(self, attr_name, canvas)


def plt_close(fig):
    try:
        import matplotlib.pyplot as plt
        plt.close(fig)
    except Exception:
        pass


# ──────────────────────────────────────────────────────────────────────
# Scanner section
# ──────────────────────────────────────────────────────────────────────

class ScannerSection(SectionBase):

    def _build(self):
        self._scanner      = BarcodeScanner()
        self._scan_active  = False
        self._preview_job  = None

        # Layout: camera left, result right
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=24, pady=20)
        body.columnconfigure(0, weight=5)
        body.columnconfigure(1, weight=4)
        body.rowconfigure(0, weight=1)

        # ── Left: camera preview ──────────────────────────────────────
        cam_card = make_card(body)
        cam_card.grid(row=0, column=0, padx=(0, 12), sticky="nsew")

        label(cam_card, "📷  Webcam Scanner", 14, "bold").pack(
            anchor="w", padx=16, pady=(14, 0))
        separator(cam_card).pack(fill="x", padx=16, pady=8)

        self._cam_label = ctk.CTkLabel(
            cam_card, text="Camera preview will appear here",
            font=(FONT_FAMILY, 12), text_color=col("text_dim"),
            fg_color=col("bg_input"), corner_radius=8, width=420, height=300,
        )
        self._cam_label.pack(padx=16, pady=(0, 8))

        btn_row = ctk.CTkFrame(cam_card, fg_color="transparent")
        btn_row.pack(pady=(0, 14))
        self._start_btn = btn(btn_row, "▶  Start Camera",
                              self._toggle_scan, fg=col("green"),
                              hover="#2ea043", width=160)
        self._start_btn.pack(side="left", padx=8)
        btn(btn_row, "🔄  Reset", self._reset_result,
            fg=col("bg_input"), hover=col("border"), width=100).pack(side="left", padx=8)

        # ── USB input ─────────────────────────────────────────────────
        usb_card = make_card(cam_card)
        usb_card.pack(fill="x", padx=16, pady=(0, 14))
        label(usb_card, "USB Barcode Scanner Input", 11, "normal",
              col("text_dim")).pack(anchor="w", padx=12, pady=(8, 4))
        usb_row = ctk.CTkFrame(usb_card, fg_color="transparent")
        usb_row.pack(fill="x", padx=12, pady=(0, 10))
        self._usb_entry = entry(usb_row, "Scan or type barcode, then press Enter", width=320)
        self._usb_entry.pack(side="left", padx=(0, 8))
        self._usb_entry.bind("<Return>", self._on_usb_enter)
        btn(usb_row, "Submit", self._on_usb_submit, width=90).pack(side="left")

        # ── Right: result panel ───────────────────────────────────────
        res_card = make_card(body)
        res_card.grid(row=0, column=1, sticky="nsew")

        label(res_card, "Scan Result", 14, "bold").pack(
            anchor="w", padx=16, pady=(14, 0))
        separator(res_card).pack(fill="x", padx=16, pady=8)

        self._photo_label = ctk.CTkLabel(
            res_card, text="", width=120, height=120, corner_radius=10,
            fg_color=col("bg_input"),
        )
        self._photo_label.pack(pady=(8, 4))
        self._set_placeholder_photo()

        self._result_name  = label(res_card, "—", 18, "bold")
        self._result_name.pack()
        self._result_class = label(res_card, "", 12, "normal", col("text_dim"))
        self._result_class.pack()

        separator(res_card).pack(fill="x", padx=16, pady=10)

        # Detail grid
        det = ctk.CTkFrame(res_card, fg_color="transparent")
        det.pack(fill="x", padx=16)
        self._detail_rows = {}
        for i, field in enumerate(["Student ID", "Barcode", "Phone", "Time", "Status"]):
            label(det, field, 11, "normal", col("text_dim")).grid(
                row=i, column=0, sticky="w", pady=3)
            lbl = label(det, "—", 11, "bold")
            lbl.grid(row=i, column=1, sticky="w", padx=12, pady=3)
            self._detail_rows[field] = lbl

        separator(res_card).pack(fill="x", padx=16, pady=10)

        self._status_banner = ctk.CTkLabel(
            res_card, text="Waiting for scan…",
            font=(FONT_FAMILY, 13, "bold"),
            text_color=col("text_dim"),
            fg_color=col("bg_input"),
            corner_radius=8, height=44, width=260,
        )
        self._status_banner.pack(pady=(0, 16))

    # ── Scanner control ───────────────────────────────────────────────

    def _toggle_scan(self):
        if self._scan_active:
            self._stop_scan()
        else:
            self._start_scan()

    def _start_scan(self):
        ok = self._scanner.start_webcam(self._on_barcode_detected)
        if ok:
            self._scan_active = True
            self._start_btn.configure(text="⏹  Stop Camera",
                                      fg_color=col("red"), hover_color="#b91c1c")
            self._preview_loop()
        else:
            self.notify("Camera Error",
                        "Could not open webcam. Check connection or use USB input.",
                        "error")

    def _stop_scan(self):
        self._scan_active = False
        self._scanner.stop()
        if self._preview_job:
            self.after_cancel(self._preview_job)
            self._preview_job = None
        self._cam_label.configure(image=None,
                                  text="Camera preview will appear here")
        self._start_btn.configure(text="▶  Start Camera",
                                  fg_color=col("green"), hover_color="#2ea043")

    def _preview_loop(self):
        if not self._scan_active:
            return
        frame = self._scanner.get_latest_frame()
        if frame is not None:
            import cv2
            rgb   = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img   = Image.fromarray(rgb).resize((420, 300), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            self._cam_label.configure(image=photo, text="")
            self._cam_label._image_ref = photo   # prevent GC
        self._preview_job = self.after(40, self._preview_loop)

    # ── Barcode callbacks ─────────────────────────────────────────────

    def _on_barcode_detected(self, barcode: str):
        """Called from scanner thread → schedule GUI update on main thread."""
        self.after(0, partial(self._process_barcode, barcode))

    def _on_usb_enter(self, _event=None):
        self._on_usb_submit()

    def _on_usb_submit(self):
        raw = self._usb_entry.get()
        cleaned = self._scanner.process_usb_input(raw)
        if cleaned:
            self._usb_entry.delete(0, "end")
            self._process_barcode(cleaned)
        else:
            self.notify("Input Error", "Enter a valid barcode string.", "warning")

    def _process_barcode(self, barcode: str):
        result = self.attendance.process_scan(barcode)
        self._show_result(result)
        if result["success"] and not result["already"]:
            self.notify(
                "Attendance Marked",
                f"{result['student']['name']} — {result['status']}",
                "success",
            )
        elif result["already"]:
            self.notify("Already Marked", result["message"], "info")
        else:
            self.notify("Scan Error", result["message"], "error")

    def _show_result(self, result: dict):
        student = result.get("student")
        if not student:
            self._reset_result()
            self._status_banner.configure(
                text=result["message"],
                text_color=col("red"),
                fg_color="#2d1b1b",
            )
            return

        # Photo
        photo_path = student.get("photo_path", "")
        self._set_student_photo(photo_path)

        # Labels
        self._result_name.configure(text=student["name"])
        self._result_class.configure(
            text=f"Class {student['class']} — Section {student['section']}"
        )
        details = {
            "Student ID": student["student_id"],
            "Barcode":    student["barcode_number"],
            "Phone":      student.get("phone_number", "—"),
            "Time":       datetime.now().strftime("%H:%M:%S"),
            "Status":     result.get("status") or "—",
        }
        status_colors = {"Present": col("green"), "Late": col("yellow")}
        for field, value in details.items():
            color = (status_colors.get(value, col("text_main"))
                     if field == "Status" else col("text_main"))
            self._detail_rows[field].configure(text=value, text_color=color)

        if result["already"]:
            self._status_banner.configure(
                text="⚠  Already Marked Today",
                text_color=col("yellow"),
                fg_color="#2d2415",
            )
        elif result["success"]:
            self._status_banner.configure(
                text="✅  Attendance Marked Successfully",
                text_color=col("green"),
                fg_color="#0d2117",
            )
        else:
            self._status_banner.configure(
                text=f"❌  {result['message']}",
                text_color=col("red"),
                fg_color="#2d1b1b",
            )

    def _set_placeholder_photo(self):
        img   = placeholder_avatar(120)
        photo = ctk.CTkImage(light_image=img, dark_image=img, size=(120, 120))
        self._photo_label.configure(image=photo, text="")
        self._photo_label._img_ref = photo

    def _set_student_photo(self, path: str):
        try:
            if path and os.path.exists(path):
                raw = Image.open(path).convert("RGBA")
                # Circular crop
                size = min(raw.size)
                raw  = raw.crop(((raw.width - size) // 2,
                                 (raw.height - size) // 2,
                                 (raw.width + size) // 2,
                                 (raw.height + size) // 2))
                raw  = raw.resize((120, 120), Image.LANCZOS)
                mask = Image.new("L", (120, 120), 0)
                ImageDraw.Draw(mask).ellipse([0, 0, 119, 119], fill=255)
                raw.putalpha(mask)
                photo = ctk.CTkImage(light_image=raw, dark_image=raw, size=(120, 120))
                self._photo_label.configure(image=photo, text="")
                self._photo_label._img_ref = photo
                return
        except Exception:
            pass
        self._set_placeholder_photo()

    def _reset_result(self):
        self._set_placeholder_photo()
        self._result_name.configure(text="—")
        self._result_class.configure(text="")
        for lbl in self._detail_rows.values():
            lbl.configure(text="—", text_color=col("text_main"))
        self._status_banner.configure(text="Waiting for scan…",
                                      text_color=col("text_dim"),
                                      fg_color=col("bg_input"))

    def on_hide(self):
        if self._scan_active:
            self._stop_scan()


# ──────────────────────────────────────────────────────────────────────
# Add Student section
# ──────────────────────────────────────────────────────────────────────

class AddStudentSection(SectionBase):

    def _build(self):
        scroll = ctk.CTkScrollableFrame(self, fg_color=col("bg_main"))
        scroll.pack(fill="both", expand=True, padx=24, pady=20)

        label(scroll, "Add New Student", 22, "bold").pack(anchor="w", pady=(0, 4))
        label(scroll, "Fill in the student details below.",
              12, "normal", col("text_dim")).pack(anchor="w")
        separator(scroll).pack(fill="x", pady=12)

        body = ctk.CTkFrame(scroll, fg_color="transparent")
        body.pack(fill="x")
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)

        # Photo panel (right column, spans rows)
        photo_card = make_card(body)
        photo_card.grid(row=0, column=1, rowspan=6, padx=(12, 0),
                        pady=4, sticky="nsew")
        label(photo_card, "Student Photo", 13, "bold").pack(pady=(14, 8))

        self._photo_img_label = ctk.CTkLabel(
            photo_card, text="Click below to upload",
            width=180, height=180,
            fg_color=col("bg_input"), corner_radius=10,
            text_color=col("text_dim"),
        )
        self._photo_img_label.pack(pady=8)
        btn(photo_card, "📁  Upload Photo", self._upload_photo,
            width=160, fg=col("bg_input"), hover=col("border")).pack(pady=4)
        self._photo_path_var = tk.StringVar(value="")

        # Barcode panel
        separator(photo_card).pack(fill="x", padx=16, pady=10)
        label(photo_card, "Barcode Preview", 12, "normal",
              col("text_dim")).pack()
        self._barcode_preview = ctk.CTkLabel(
            photo_card, text="—", width=180, height=60,
            fg_color=col("bg_input"), corner_radius=8,
            text_color=col("accent"), font=(FONT_FAMILY, 18, "bold"),
        )
        self._barcode_preview.pack(pady=8)
        btn(photo_card, "🎲  Auto-generate", self._auto_barcode,
            width=160, fg=col("bg_input"), hover=col("border")).pack(pady=(0, 14))

        # Form fields
        fields = [
            ("Student ID",     "e.g. STU011",          "student_id"),
            ("Full Name",      "e.g. Rahul Kumar",      "name"),
            ("Class",          "e.g. 10",               "class_"),
            ("Section",        "e.g. A",                "section"),
            ("Barcode Number", "e.g. BAR011",           "barcode"),
            ("Phone Number",   "e.g. 9876543200",       "phone"),
        ]
        self._field_vars: dict[str, ctk.CTkEntry] = {}
        form_card = make_card(body)
        form_card.grid(row=0, column=0, pady=4, sticky="nsew")

        for i, (lbl_text, placeholder, key) in enumerate(fields):
            row_frame = ctk.CTkFrame(form_card, fg_color="transparent")
            row_frame.pack(fill="x", padx=16, pady=4)
            label(row_frame, lbl_text, 12, "normal",
                  col("text_dim")).pack(anchor="w", pady=(4, 0))
            e = entry(row_frame, placeholder, width=340)
            e.pack(anchor="w")
            self._field_vars[key] = e
            if key == "barcode":
                e.bind("<KeyRelease>", self._preview_barcode)

        # Buttons
        action_row = ctk.CTkFrame(form_card, fg_color="transparent")
        action_row.pack(fill="x", padx=16, pady=(12, 16))
        btn(action_row, "💾  Save Student", self._save_student,
            width=170, fg=col("green"), hover="#2ea043").pack(side="left", padx=(0, 8))
        btn(action_row, "🔄  Clear Form", self._clear_form,
            width=130, fg=col("bg_input"), hover=col("border")).pack(side="left")

    def _upload_photo(self):
        path = filedialog.askopenfilename(
            title="Select Student Photo",
            filetypes=[("Image Files", "*.jpg *.jpeg *.png *.bmp")]
        )
        if path:
            self._photo_path_var.set(path)
            img   = Image.open(path).resize((180, 180), Image.LANCZOS)
            photo = ctk.CTkImage(light_image=img, dark_image=img, size=(180, 180))
            self._photo_img_label.configure(image=photo, text="")
            self._photo_img_label._img_ref = photo

    def _auto_barcode(self):
        sid = self._field_vars["student_id"].get().strip() or f"STU{int(time.time())%10000:04d}"
        code = f"BAR{sid[-4:].upper()}" if len(sid) >= 4 else f"BAR{int(time.time())%10000:04d}"
        self._field_vars["barcode"].delete(0, "end")
        self._field_vars["barcode"].insert(0, code)
        self._barcode_preview.configure(text=code)

    def _preview_barcode(self, _=None):
        code = self._field_vars["barcode"].get().strip()
        self._barcode_preview.configure(text=code if code else "—")

    def _save_student(self):
        vals = {k: e.get().strip() for k, e in self._field_vars.items()}
        required = ["student_id", "name", "class_", "section", "barcode"]
        if any(not vals[r] for r in required):
            self.notify("Validation Error",
                        "Student ID, Name, Class, Section, and Barcode are required.",
                        "error")
            return

        ok, msg = self.db.add_student(
            vals["student_id"], vals["name"], vals["class_"],
            vals["section"], vals["barcode"],
            vals["phone"], self._photo_path_var.get(),
        )
        if ok:
            self.notify("Student Added", f"{vals['name']} saved successfully.", "success")
            self._clear_form()
        else:
            self.notify("Save Error", msg, "error")

    def _clear_form(self):
        for e in self._field_vars.values():
            e.delete(0, "end")
        self._photo_path_var.set("")
        self._photo_img_label.configure(image=None, text="Click below to upload")
        self._barcode_preview.configure(text="—")


# ──────────────────────────────────────────────────────────────────────
# View Students section
# ──────────────────────────────────────────────────────────────────────

class ViewStudentsSection(SectionBase):

    def _build(self):
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=24, pady=(20, 0))
        label(top, "Student Records", 22, "bold").pack(side="left")
        btn(top, "➕  Add Student", lambda: None, width=140,
            fg=col("green"), hover="#2ea043").pack(side="right")

        search_row = ctk.CTkFrame(self, fg_color="transparent")
        search_row.pack(fill="x", padx=24, pady=10)
        self._search_entry = entry(search_row, "🔍  Search by name, ID or class…", width=400)
        self._search_entry.pack(side="left")
        self._search_entry.bind("<KeyRelease>", self._on_search)
        label(search_row, "", 12, "normal", col("text_dim")).pack(side="right")
        self._count_lbl = label(search_row, "0 students", 12, "normal", col("text_dim"))
        self._count_lbl.pack(side="right", padx=8)

        separator(self).pack(fill="x", padx=24, pady=4)

        # Table header
        cols = [
            ("ID",      80),  ("Name",   180), ("Class", 70),
            ("Section", 70),  ("Barcode",120), ("Phone", 120), ("Actions", 120),
        ]
        hdr = ctk.CTkFrame(self, fg_color=col("bg_card"), corner_radius=0)
        hdr.pack(fill="x", padx=24)
        for col_name, w in cols:
            label(hdr, col_name, 11, "bold", col("text_dim"), width=w).pack(
                side="left", padx=4, pady=8)

        separator(self).pack(fill="x", padx=24)

        # Scrollable rows
        self._scroll = ctk.CTkScrollableFrame(
            self, fg_color=col("bg_main"), corner_radius=0
        )
        self._scroll.pack(fill="both", expand=True, padx=24, pady=(0, 12))
        self._all_students: list[dict] = []
        self._cols = cols

    def refresh(self):
        self._all_students = self.db.get_all_students()
        self._render_rows(self._all_students)

    def _on_search(self, _=None):
        q = self._search_entry.get().strip().lower()
        filtered = [s for s in self._all_students if
                    q in s["name"].lower() or
                    q in s["student_id"].lower() or
                    q in s["class"].lower()]
        self._render_rows(filtered)

    def _render_rows(self, students: list[dict]):
        for w in self._scroll.winfo_children():
            w.destroy()
        self._count_lbl.configure(text=f"{len(students)} student(s)")
        for i, s in enumerate(students):
            bg = col("bg_card") if i % 2 == 0 else col("bg_main")
            row = ctk.CTkFrame(self._scroll, fg_color=bg, corner_radius=0, height=38)
            row.pack(fill="x")
            row.pack_propagate(False)
            data = [s["student_id"], s["name"], s["class"],
                    s["section"], s["barcode_number"], s.get("phone_number","—")]
            widths = [w for _, w in self._cols]
            for val, w in zip(data, widths[:-1]):
                label(row, str(val), 11, width=w).pack(side="left", padx=4)
            # Delete button
            del_btn = ctk.CTkButton(
                row, text="Delete", width=80, height=24,
                fg_color="#2d1b1b", hover_color="#7f1d1d",
                text_color=col("red"), font=(FONT_FAMILY, 11),
                corner_radius=6,
                command=partial(self._confirm_delete, s["student_id"], s["name"])
            )
            del_btn.pack(side="left", padx=8)

    def _confirm_delete(self, student_id: str, name: str):
        if messagebox.askyesno("Confirm Delete",
                               f"Delete student '{name}'?\nThis cannot be undone.",
                               icon="warning"):
            ok, msg = self.db.delete_student(student_id)
            if ok:
                self.notify("Deleted", f"{name} removed.", "success")
                self.refresh()
            else:
                self.notify("Error", msg, "error")


# ──────────────────────────────────────────────────────────────────────
# View Attendance section
# ──────────────────────────────────────────────────────────────────────

class AttendanceSection(SectionBase):

    def _build(self):
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=24, pady=(20, 0))
        label(top, "Attendance Records", 22, "bold").pack(side="left")

        filter_row = ctk.CTkFrame(self, fg_color="transparent")
        filter_row.pack(fill="x", padx=24, pady=10)
        label(filter_row, "Date:", 12, "normal", col("text_dim")).pack(side="left", padx=(0,6))
        self._date_entry = entry(filter_row, "YYYY-MM-DD", width=160)
        self._date_entry.insert(0, datetime.now().strftime("%Y-%m-%d"))
        self._date_entry.pack(side="left", padx=(0, 8))
        btn(filter_row, "🔍  Load", self._load_attendance,
            width=100, fg=col("accent2")).pack(side="left")
        self._summary_lbl = label(filter_row, "", 12, "normal", col("text_dim"))
        self._summary_lbl.pack(side="right")

        separator(self).pack(fill="x", padx=24, pady=4)

        # Table header
        cols = [("ID", 60), ("Student ID", 100), ("Name", 180),
                ("Class",70), ("Section",70), ("Time", 100), ("Status", 90)]
        hdr = ctk.CTkFrame(self, fg_color=col("bg_card"), corner_radius=0)
        hdr.pack(fill="x", padx=24)
        for col_name, w in cols:
            label(hdr, col_name, 11, "bold", col("text_dim"), width=w).pack(
                side="left", padx=4, pady=8)

        separator(self).pack(fill="x", padx=24)

        self._scroll = ctk.CTkScrollableFrame(
            self, fg_color=col("bg_main"), corner_radius=0)
        self._scroll.pack(fill="both", expand=True, padx=24, pady=(0, 12))
        self._cols = cols

    def refresh(self):
        self._load_attendance()

    def _load_attendance(self):
        date = self._date_entry.get().strip()
        try:
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            self.notify("Invalid Date", "Use format YYYY-MM-DD", "warning")
            return

        records = self.db.get_attendance_by_date(date)
        for w in self._scroll.winfo_children():
            w.destroy()

        present = sum(1 for r in records if r["status"] == "Present")
        late    = sum(1 for r in records if r["status"] == "Late")
        self._summary_lbl.configure(
            text=f"Present: {present}  |  Late: {late}  |  Total: {len(records)}"
        )

        status_colors = {"Present": col("green"), "Late": col("yellow")}
        for i, r in enumerate(records):
            bg = col("bg_card") if i % 2 == 0 else col("bg_main")
            row = ctk.CTkFrame(self._scroll, fg_color=bg, corner_radius=0, height=36)
            row.pack(fill="x")
            row.pack_propagate(False)
            data = [r["attendance_id"], r["student_id"], r["name"],
                    r["class"], r["section"], r["time"], r["status"]]
            widths = [w for _, w in self._cols]
            for j, (val, w) in enumerate(zip(data, widths)):
                c = status_colors.get(str(val), col("text_main"))
                label(row, str(val), 11, color=c if j == 6 else col("text_main")).pack(
                    side="left", padx=4, width=w)

        if not records:
            label(self._scroll, "No attendance records for this date.",
                  13, "normal", col("text_dim")).pack(pady=40)


# ──────────────────────────────────────────────────────────────────────
# Reports section
# ──────────────────────────────────────────────────────────────────────

class ReportsSection(SectionBase):

    def _build(self):
        label(self, "Reports & Analytics", 22, "bold").pack(
            anchor="w", padx=24, pady=(20, 4))
        separator(self).pack(fill="x", padx=24, pady=8)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=24, pady=0)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)
        body.rowconfigure(1, weight=1)

        # Chart containers
        self._chart_frames = {}
        positions = [
            ("bar",   "7-Day Attendance", 0, 0),
            ("pie",   "Today Distribution", 0, 1),
            ("line",  "Monthly Trend",     1, 0),
            ("class", "Class-wise Today",  1, 1),
        ]
        for key, title, r, c in positions:
            card = make_card(body)
            card.grid(row=r, column=c, padx=6, pady=6, sticky="nsew")
            label(card, title, 12, "bold", col("text_dim")).pack(
                anchor="w", padx=12, pady=(8, 0))
            self._chart_frames[key] = card

        # Export buttons
        exp = make_card(self)
        exp.pack(fill="x", padx=24, pady=(8, 16))
        label(exp, "Export Reports", 13, "bold").pack(anchor="w", padx=16, pady=(10, 6))
        row = ctk.CTkFrame(exp, fg_color="transparent")
        row.pack(padx=16, pady=(0, 12))
        export_btns = [
            ("📋  Daily CSV",    partial(self._export, "daily",   "csv")),
            ("📋  Daily Excel",  partial(self._export, "daily",   "xlsx")),
            ("📊  Monthly CSV",  partial(self._export, "monthly", "csv")),
            ("📊  Monthly Excel",partial(self._export, "monthly", "xlsx")),
            ("📦  Full Export",  partial(self._export, "full",    "xlsx")),
        ]
        for txt, cmd in export_btns:
            btn(row, txt, cmd, width=140,
                fg=col("bg_input"), hover=col("border")).pack(side="left", padx=4)

        self._canvas_refs = {}

    def refresh(self):
        thread = threading.Thread(target=self._draw_all, daemon=True)
        thread.start()

    def _draw_all(self):
        import matplotlib.pyplot as plt
        chart_fns = {
            "bar":   self.reports.chart_weekly_bar,
            "pie":   self.reports.chart_today_pie,
            "line":  self.reports.chart_monthly_trend,
            "class": self.reports.chart_classwise,
        }
        for key, fn in chart_fns.items():
            try:
                fig = fn()
                self.after(0, partial(self._embed, key, fig))
            except Exception as e:
                print(f"Chart error [{key}]: {e}")

    def _embed(self, key: str, fig):
        import matplotlib.pyplot as plt
        card = self._chart_frames[key]
        old  = self._canvas_refs.get(key)
        if old:
            try:
                old.get_tk_widget().destroy()
            except Exception:
                pass
        canvas = FigureCanvasTkAgg(fig, master=card)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=4, pady=4)
        self._canvas_refs[key] = canvas
        plt.close(fig)

    def _export(self, report_type: str, fmt: str):
        try:
            if report_type == "daily":
                df = self.reports.get_daily_dataframe()
                path = self.reports.export_daily_report(fmt=fmt)
            elif report_type == "monthly":
                df = self.reports.get_monthly_dataframe()
                path = self.reports.export_monthly_report(fmt=fmt)
            else:
                df   = self.reports.get_full_dataframe()
                fname = f"full_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                path = (self.reports.export_csv(df, fname)
                        if fmt == "csv" else self.reports.export_excel(df, fname))
            self.notify("Export Complete", f"Saved → {path}", "success")
        except Exception as e:
            self.notify("Export Error", str(e), "error")


# ══════════════════════════════════════════════════════════════════════
# Main Dashboard window
# ══════════════════════════════════════════════════════════════════════

class SmartAttendanceDashboard(ctk.CTk):
    """
    Root window. Owns the sidebar + swappable content area.
    Sections are created once and shown/hidden as needed.
    """

    NAV_ITEMS = [
        ("🏠", "Dashboard",  "home"),
        ("📷", "Scan",       "scan"),
        ("➕", "Add Student","add"),
        ("👥", "Students",   "students"),
        ("📋", "Attendance", "attendance"),
        ("📊", "Reports",    "reports"),
    ]

    def __init__(self, username: str = "admin"):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.username = username
        self.title("Smart Attendance Management System")
        self.geometry("1280x800")
        self.minsize(1100, 700)
        self.configure(fg_color=col("bg_main"))

        # Shared modules
        self._db         = DatabaseManager()
        self._attendance = AttendanceManager(self._db)
        self._reports    = ReportsManager(self._db)

        self._sections:   dict[str, SectionBase] = {}
        self._nav_btns:   dict[str, ctk.CTkButton] = {}
        self._active_key: str = ""

        self._build_layout()
        self._build_sidebar()
        self._build_sections()
        self._switch_section("home")
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── Layout scaffolding ────────────────────────────────────────────

    def _build_layout(self):
        self._sidebar = ctk.CTkFrame(
            self, width=220, fg_color=col("bg_sidebar"),
            corner_radius=0, border_width=0,
        )
        self._sidebar.pack(side="left", fill="y")
        self._sidebar.pack_propagate(False)

        self._content = ctk.CTkFrame(self, fg_color=col("bg_main"), corner_radius=0)
        self._content.pack(side="left", fill="both", expand=True)

    def _build_sidebar(self):
        # Logo area
        logo_frame = ctk.CTkFrame(self._sidebar, fg_color="transparent")
        logo_frame.pack(fill="x", pady=(20, 10))

        logo_icon = ctk.CTkLabel(
            logo_frame, text="🎓",
            font=(FONT_FAMILY, 32), width=48, height=48,
        )
        logo_icon.pack()
        label(logo_frame, "SmartAttend", 15, "bold", col("accent")).pack()
        label(logo_frame, "School Edition", 10, "normal", col("text_muted")).pack()

        separator(self._sidebar, col("border")).pack(fill="x", padx=16, pady=10)

        # Nav buttons
        nav_frame = ctk.CTkFrame(self._sidebar, fg_color="transparent")
        nav_frame.pack(fill="x", padx=8)

        for icon, name, key in self.NAV_ITEMS:
            b = ctk.CTkButton(
                nav_frame,
                text=f"  {icon}  {name}",
                anchor="w",
                width=200, height=42,
                fg_color="transparent",
                hover_color=col("bg_card"),
                text_color=col("text_dim"),
                font=(FONT_FAMILY, 13),
                corner_radius=8,
                command=partial(self._switch_section, key),
            )
            b.pack(fill="x", pady=2)
            self._nav_btns[key] = b

        # Bottom: user info + logout
        separator(self._sidebar, col("border")).pack(
            fill="x", padx=16, pady=10, side="bottom"
        )
        footer = ctk.CTkFrame(self._sidebar, fg_color="transparent")
        footer.pack(side="bottom", fill="x", padx=12, pady=12)

        label(footer, f"👤  {self.username}", 12, "bold", col("text_dim")).pack(
            anchor="w", pady=(0, 4))
        ctk.CTkButton(
            footer, text="⎋  Logout", anchor="w",
            width=196, height=36,
            fg_color="transparent", hover_color="#2d1b1b",
            text_color=col("red"), font=(FONT_FAMILY, 12),
            corner_radius=8, command=self._logout,
        ).pack(fill="x")

    def _build_sections(self):
        kwargs = dict(
            db=self._db, attendance=self._attendance,
            reports=self._reports, notify=self._notify,
        )
        section_classes = {
            "home":       HomeSection,
            "scan":       ScannerSection,
            "add":        AddStudentSection,
            "students":   ViewStudentsSection,
            "attendance": AttendanceSection,
            "reports":    ReportsSection,
        }
        for key, cls in section_classes.items():
            frame = cls(self._content, **kwargs)
            frame.place(relx=0, rely=0, relwidth=1, relheight=1)
            frame.lower()
            self._sections[key] = frame

    # ── Navigation ────────────────────────────────────────────────────

    def _switch_section(self, key: str):
        # Hide active scanner if leaving scan section
        if self._active_key == "scan" and key != "scan":
            scanner_section = self._sections.get("scan")
            if hasattr(scanner_section, "on_hide"):
                scanner_section.on_hide()

        # Update sidebar highlight
        if self._active_key:
            self._nav_btns[self._active_key].configure(
                fg_color="transparent", text_color=col("text_dim"))
        self._nav_btns[key].configure(
            fg_color=col("bg_card"), text_color=col("text_main"))

        self._active_key = key
        self._sections[key].lift()
        self._sections[key].refresh()

    # ── Notifications ─────────────────────────────────────────────────

    def _notify(self, title: str, message: str, kind: str = "info"):
        try:
            ToastPopup(self, title, message, kind)
        except Exception:
            pass

    # ── Window lifecycle ──────────────────────────────────────────────

    def _logout(self):
        if messagebox.askyesno("Logout", "Return to login screen?"):
            scanner_sec = self._sections.get("scan")
            if hasattr(scanner_sec, "on_hide"):
                scanner_sec.on_hide()
            self.destroy()
            _launch_login()

    def _on_close(self):
        scanner_sec = self._sections.get("scan")
        if hasattr(scanner_sec, "on_hide"):
            scanner_sec.on_hide()
        self.destroy()


# ══════════════════════════════════════════════════════════════════════
# Login window
# ══════════════════════════════════════════════════════════════════════

class LoginWindow(ctk.CTk):

    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title("Smart Attendance — Login")
        self.geometry("480x560")
        self.resizable(False, False)
        self.configure(fg_color=col("bg_main"))

        self._db = DatabaseManager()
        self._build()

    def _build(self):
        # Hero area
        hero = ctk.CTkFrame(self, fg_color=col("bg_card"),
                            corner_radius=0, height=180)
        hero.pack(fill="x")
        hero.pack_propagate(False)

        ctk.CTkLabel(hero, text="🎓", font=(FONT_FAMILY, 52)).pack(pady=(28, 4))
        label(hero, "SmartAttend", 24, "bold", col("accent")).pack()
        label(hero, "Barcode Attendance System", 12, "normal",
              col("text_dim")).pack(pady=(2, 0))

        # Card
        card = make_card(self)
        card.pack(fill="x", padx=40, pady=30)

        label(card, "Administrator Login", 16, "bold").pack(pady=(20, 4))
        label(card, "Default: admin / admin123", 11, "normal",
              col("text_muted")).pack(pady=(0, 16))

        # Username
        un_frame = ctk.CTkFrame(card, fg_color="transparent")
        un_frame.pack(fill="x", padx=24, pady=(0, 10))
        label(un_frame, "Username", 12, "normal", col("text_dim")).pack(anchor="w")
        self._username_entry = entry(un_frame, "Enter username", width=370)
        self._username_entry.pack(fill="x", expand=True)
        self._username_entry.insert(0, "admin")

        # Password
        pw_frame = ctk.CTkFrame(card, fg_color="transparent")
        pw_frame.pack(fill="x", padx=24, pady=(0, 16))
        label(pw_frame, "Password", 12, "normal", col("text_dim")).pack(anchor="w")
        self._password_entry = entry(pw_frame, "Enter password", width=370)
        self._password_entry.configure(show="●")
        self._password_entry.pack(fill="x", expand=True)
        self._password_entry.bind("<Return>", lambda _: self._login())

        btn(card, "🔓  Login", self._login,
            width=370, height=44, fg=col("accent2"),
            hover=col("accent")).pack(padx=24, pady=(0, 20))

        self._error_lbl = label(card, "", 11, "normal", col("red"))
        self._error_lbl.pack(pady=(0, 12))

    def _login(self):
        username = self._username_entry.get().strip()
        password = self._password_entry.get()

        if not username or not password:
            self._error_lbl.configure(text="Username and password are required.")
            return

        if self._db.verify_admin(username, password):
            self.destroy()
            app = SmartAttendanceDashboard(username=username)
            app.mainloop()
        else:
            self._error_lbl.configure(text="Invalid credentials. Please try again.")
            self._password_entry.delete(0, "end")


def _launch_login():
    login = LoginWindow()
    login.mainloop()


# ══════════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    _launch_login()
