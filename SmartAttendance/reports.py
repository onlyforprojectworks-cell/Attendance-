"""
reports.py — ReportsManager
Smart Barcode Attendance Management System

Generates CSV/Excel exports and Matplotlib charts consumed by the GUI.
All charts use the project's dark colour palette so they embed cleanly
inside the dark-themed dashboard.
"""

import os
from datetime import datetime, timedelta

import pandas as pd
import matplotlib
matplotlib.use("Agg")          # non-interactive backend; must come before pyplot
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

from database import DatabaseManager


# ── Palette (mirrors the GUI theme) ──────────────────────────────────
BG_DARK   = "#0d1117"
BG_CARD   = "#161b22"
ACCENT    = "#58a6ff"
ACCENT2   = "#1f6feb"
GREEN     = "#3fb950"
YELLOW    = "#d29922"
RED       = "#f85149"
TEXT_DIM  = "#8b949e"
TEXT_MAIN = "#e6edf3"


class ReportsManager:
    """
    Handles all report generation:
      • CSV / Excel export
      • Bar chart   — last-N-days attendance
      • Pie chart   — today's Present / Late / Absent split
      • Line chart  — monthly trend
      • Heatmap     — class-level attendance matrix
    """

    def __init__(self, db: DatabaseManager):
        self.db          = db
        self.export_path = "exports/attendance_reports"
        os.makedirs(self.export_path, exist_ok=True)

    # ================================================================== #
    # DATA FRAMES                                                          #
    # ================================================================== #

    def get_daily_dataframe(self, date: str | None = None) -> pd.DataFrame:
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        records = self.db.get_attendance_by_date(date)
        return pd.DataFrame(records) if records else pd.DataFrame()

    def get_monthly_dataframe(self, year: int | None = None,
                              month: int | None = None) -> pd.DataFrame:
        if year  is None: year  = datetime.now().year
        if month is None: month = datetime.now().month
        records = self.db.get_all_attendance()
        if not records:
            return pd.DataFrame()
        df = pd.DataFrame(records)
        df["date"] = pd.to_datetime(df["date"])
        mask = (df["date"].dt.year == year) & (df["date"].dt.month == month)
        return df[mask].copy()

    def get_student_dataframe(self, student_id: str) -> pd.DataFrame:
        records = self.db.get_student_attendance_summary(student_id)
        return pd.DataFrame(records) if records else pd.DataFrame()

    def get_full_dataframe(self) -> pd.DataFrame:
        records = self.db.get_all_attendance()
        return pd.DataFrame(records) if records else pd.DataFrame()

    # ================================================================== #
    # EXPORTS                                                              #
    # ================================================================== #

    def export_csv(self, df: pd.DataFrame, filename: str) -> str:
        path = os.path.join(self.export_path, f"{filename}.csv")
        df.to_csv(path, index=False)
        return path

    def export_excel(self, df: pd.DataFrame, filename: str) -> str:
        path = os.path.join(self.export_path, f"{filename}.xlsx")
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Attendance")
            ws = writer.sheets["Attendance"]
            # Auto-fit columns
            for col in ws.columns:
                max_len = max(len(str(cell.value or "")) for cell in col) + 2
                ws.column_dimensions[col[0].column_letter].width = min(max_len, 40)
        return path

    def export_daily_report(self, date: str | None = None,
                            fmt: str = "csv") -> str:
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        df = self.get_daily_dataframe(date)
        fname = f"daily_{date}"
        return self.export_csv(df, fname) if fmt == "csv" else self.export_excel(df, fname)

    def export_monthly_report(self, year: int | None = None,
                              month: int | None = None,
                              fmt: str = "csv") -> str:
        if year  is None: year  = datetime.now().year
        if month is None: month = datetime.now().month
        df    = self.get_monthly_dataframe(year, month)
        fname = f"monthly_{year}_{str(month).zfill(2)}"
        return self.export_csv(df, fname) if fmt == "csv" else self.export_excel(df, fname)

    # ================================================================== #
    # CHARTS                                                               #
    # ================================================================== #

    def _base_fig(self, w: float = 9, h: float = 4.5):
        """Return a pre-styled (fig, ax) pair."""
        fig, ax = plt.subplots(figsize=(w, h), facecolor=BG_DARK)
        ax.set_facecolor(BG_CARD)
        for spine in ax.spines.values():
            spine.set_edgecolor("#30363d")
        ax.tick_params(colors=TEXT_DIM, labelsize=9)
        ax.xaxis.label.set_color(TEXT_DIM)
        ax.yaxis.label.set_color(TEXT_DIM)
        return fig, ax

    # ── 1. Bar: last-N-days ──────────────────────────────────────────
    def chart_weekly_bar(self, days: int = 7) -> plt.Figure:
        """Stacked bar (Present + Late) for the last `days` calendar days."""
        labels, present_vals, late_vals = [], [], []

        for i in range(days - 1, -1, -1):
            d = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            records = self.db.get_attendance_by_date(d)
            labels.append(d[5:])   # MM-DD
            present_vals.append(sum(1 for r in records if r["status"] == "Present"))
            late_vals.append(   sum(1 for r in records if r["status"] == "Late"))

        x   = list(range(len(labels)))
        fig, ax = self._base_fig(9, 4.5)

        bars_p = ax.bar(x, present_vals, color=GREEN,  label="Present",
                        width=0.55, edgecolor="#0d1117", linewidth=0.8)
        bars_l = ax.bar(x, late_vals,    color=YELLOW, label="Late",
                        bottom=present_vals,
                        width=0.55, edgecolor="#0d1117", linewidth=0.8)

        for bar, p, l in zip(bars_p, present_vals, late_vals):
            total = p + l
            if total > 0:
                ax.text(bar.get_x() + bar.get_width() / 2, total + 0.15,
                        str(total), ha="center", va="bottom",
                        color=TEXT_MAIN, fontsize=9, fontweight="bold")

        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=30, ha="right")
        ax.set_ylabel("Students", color=TEXT_DIM)
        ax.set_title(f"Attendance — Last {days} Days",
                     color=TEXT_MAIN, fontsize=13, fontweight="bold", pad=12)
        ax.legend(handles=[
            mpatches.Patch(color=GREEN,  label="Present"),
            mpatches.Patch(color=YELLOW, label="Late"),
        ], facecolor=BG_CARD, edgecolor="#30363d", labelcolor=TEXT_MAIN, fontsize=9)
        ax.grid(axis="y", color="#21262d", linewidth=0.8)
        ax.set_axisbelow(True)
        plt.tight_layout(pad=1.5)
        return fig

    # ── 2. Pie: today's distribution ─────────────────────────────────
    def chart_today_pie(self) -> plt.Figure:
        stats = self.db.get_today_stats()
        labels = ["Present", "Late", "Absent"]
        sizes  = [stats["present"], stats["late"], stats["absent"]]
        colors = [GREEN, YELLOW, RED]

        if sum(sizes) == 0:
            sizes = [0, 0, 1]   # show an empty-state placeholder

        fig, ax = plt.subplots(figsize=(5.5, 5), facecolor=BG_DARK)
        wedges, texts, autotexts = ax.pie(
            sizes, labels=labels, colors=colors,
            explode=[0.04] * 3, autopct="%1.1f%%",
            startangle=90,
            wedgeprops={"edgecolor": BG_DARK, "linewidth": 2},
            textprops={"color": TEXT_MAIN, "fontsize": 11},
        )
        for at in autotexts:
            at.set_fontsize(10)
            at.set_fontweight("bold")
            at.set_color(BG_DARK)

        ax.set_title("Today's Attendance",
                     color=TEXT_MAIN, fontsize=13, fontweight="bold", pad=14)
        plt.tight_layout(pad=1.2)
        return fig

    # ── 3. Line: monthly trend ────────────────────────────────────────
    def chart_monthly_trend(self, year: int | None = None,
                            month: int | None = None) -> plt.Figure:
        if year  is None: year  = datetime.now().year
        if month is None: month = datetime.now().month
        data = self.db.get_monthly_attendance(year, month)

        fig, ax = self._base_fig(9, 4)

        if data:
            days   = [d["date"][8:] for d in data]   # DD
            counts = [d["count"] for d in data]
            x      = list(range(len(days)))

            ax.plot(x, counts, color=ACCENT, linewidth=2.5,
                    marker="o", markersize=6,
                    markerfacecolor=ACCENT2, markeredgecolor=ACCENT)
            ax.fill_between(x, counts, alpha=0.15, color=ACCENT)

            ax.set_xticks(x)
            ax.set_xticklabels(days, rotation=30, ha="right")
        else:
            ax.text(0.5, 0.5, "No data for this month",
                    transform=ax.transAxes, ha="center", va="center",
                    color=TEXT_DIM, fontsize=12)

        month_name = datetime(year, month, 1).strftime("%B %Y")
        ax.set_title(f"Monthly Trend — {month_name}",
                     color=TEXT_MAIN, fontsize=13, fontweight="bold", pad=12)
        ax.set_ylabel("Students Present", color=TEXT_DIM)
        ax.grid(color="#21262d", linewidth=0.8)
        ax.set_axisbelow(True)
        plt.tight_layout(pad=1.5)
        return fig

    # ── 4. Horizontal bar: class-wise attendance ──────────────────────
    def chart_classwise(self) -> plt.Figure:
        """Attendance percentage grouped by class."""
        students   = self.db.get_all_students()
        today      = datetime.now().strftime("%Y-%m-%d")
        attendance = self.db.get_attendance_by_date(today)
        marked_ids = {r["student_id"] for r in attendance}

        from collections import defaultdict
        class_total   = defaultdict(int)
        class_present = defaultdict(int)

        for s in students:
            cls = f"{s['class']}-{s['section']}"
            class_total[cls] += 1
            if s["student_id"] in marked_ids:
                class_present[cls] += 1

        if not class_total:
            fig, ax = self._base_fig(8, 4)
            ax.text(0.5, 0.5, "No data available",
                    transform=ax.transAxes, ha="center", va="center",
                    color=TEXT_DIM, fontsize=12)
            ax.set_title("Class-wise Attendance", color=TEXT_MAIN,
                         fontsize=13, fontweight="bold")
            return fig

        labels = sorted(class_total.keys())
        pcts   = [round(class_present[c] / class_total[c] * 100, 1)
                  for c in labels]
        bar_colors = [GREEN if p >= 75 else YELLOW if p >= 50 else RED
                      for p in pcts]

        fig, ax = self._base_fig(8, max(4, len(labels) * 0.7))
        y = list(range(len(labels)))
        bars = ax.barh(y, pcts, color=bar_colors,
                       edgecolor="#0d1117", linewidth=0.8, height=0.55)
        for bar, pct in zip(bars, pcts):
            ax.text(min(pct + 1, 98), bar.get_y() + bar.get_height() / 2,
                    f"{pct}%", va="center", color=TEXT_MAIN,
                    fontsize=9, fontweight="bold")

        ax.set_yticks(y)
        ax.set_yticklabels(labels)
        ax.set_xlim(0, 105)
        ax.set_xlabel("Attendance %", color=TEXT_DIM)
        ax.set_title("Class-wise Attendance Today",
                     color=TEXT_MAIN, fontsize=13, fontweight="bold", pad=12)
        ax.grid(axis="x", color="#21262d", linewidth=0.8)
        ax.set_axisbelow(True)
        ax.axvline(75, color=RED, linestyle="--", linewidth=1.2,
                   label="75% threshold", alpha=0.7)
        ax.legend(facecolor=BG_CARD, edgecolor="#30363d",
                  labelcolor=TEXT_MAIN, fontsize=9)
        plt.tight_layout(pad=1.5)
        return fig
