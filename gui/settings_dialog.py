"""
settings_dialog.py — PiCamPro Settings Popup
=============================================
A modal dialog for app-level settings:
  • Storage path display
  • Snapshot format (JPEG / PNG)
  • About section
"""

import tkinter as tk
from tkinter import ttk, filedialog
import platform
import sys
import logging

log = logging.getLogger(__name__)

C_BG     = "#0d1117"
C_PANEL  = "#161b22"
C_BORDER = "#21262d"
C_TEXT   = "#e6edf3"
C_MUTED  = "#8b949e"
C_ACCENT = "#00d4aa"
C_BTN    = "#21262d"
C_BTN_HV = "#30363d"

FONT     = ("Segoe UI", 10)
FONT_SM  = ("Segoe UI", 9)
FONT_H   = ("Segoe UI", 12, "bold")


class SettingsDialog(tk.Toplevel):
    """
    Modal settings dialog.  Returns chosen settings through public attributes
    after the user clicks OK.
    """

    def __init__(self, parent,
                 current_storage_path: str,
                 current_snap_format: str = "jpg"):
        super().__init__(parent)
        self.title("PiCamPro — Settings")
        self.resizable(False, False)
        self.configure(bg=C_BG)
        self.grab_set()  # modal

        # Result holders
        self.storage_path  = current_storage_path
        self.snap_format   = tk.StringVar(value=current_snap_format)
        self.accepted      = False

        self._build_ui()
        self._centre_on_parent(parent)

    # ------------------------------------------------------------------

    def _build_ui(self):
        # ── Title ──
        tk.Label(self, text="⚙  Settings", bg=C_BG, fg=C_ACCENT,
                 font=FONT_H).pack(pady=(18, 10), padx=20, anchor="w")

        tk.Frame(self, bg=C_BORDER, height=1).pack(fill=tk.X, padx=20)

        body = tk.Frame(self, bg=C_BG)
        body.pack(fill=tk.BOTH, expand=True, padx=20, pady=12)

        # ── Storage path ──
        tk.Label(body, text="Storage Path", bg=C_BG, fg=C_MUTED,
                 font=FONT_SM).grid(row=0, column=0, sticky="w", pady=(8, 2))

        path_row = tk.Frame(body, bg=C_BG)
        path_row.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        body.columnconfigure(0, weight=1)

        self._path_var = tk.StringVar(value=self.storage_path)
        path_entry = tk.Entry(
            path_row, textvariable=self._path_var,
            bg=C_PANEL, fg=C_TEXT, insertbackground=C_TEXT,
            relief=tk.FLAT, font=FONT_SM, width=36
        )
        path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=5, padx=(0, 6))

        browse_btn = tk.Button(
            path_row, text="Browse", command=self._browse,
            bg=C_BTN, fg=C_TEXT, activebackground=C_BTN_HV,
            relief=tk.FLAT, font=FONT_SM, padx=8, pady=4, cursor="hand2"
        )
        browse_btn.pack(side=tk.LEFT)

        # ── Snapshot format ──
        tk.Label(body, text="Snapshot Format", bg=C_BG, fg=C_MUTED,
                 font=FONT_SM).grid(row=2, column=0, sticky="w", pady=(4, 2))

        fmt_row = tk.Frame(body, bg=C_BG)
        fmt_row.grid(row=3, column=0, sticky="w", pady=(0, 12))
        for fmt in ["jpg", "png"]:
            tk.Radiobutton(
                fmt_row, text=fmt.upper(),
                variable=self.snap_format, value=fmt,
                bg=C_BG, fg=C_TEXT, selectcolor=C_PANEL,
                activebackground=C_BG, font=FONT_SM
            ).pack(side=tk.LEFT, padx=(0, 16))

        # ── About ──
        tk.Frame(body, bg=C_BORDER, height=1).grid(
            row=4, column=0, sticky="ew", pady=10)

        about_text = (
            "PiCamPro  v1.0.0\n"
            "Universal Raspberry Pi Camera Viewer\n"
            f"Python {sys.version.split()[0]}  |  "
            f"{platform.machine()}  |  {platform.system()}"
        )
        tk.Label(body, text=about_text, bg=C_BG, fg=C_MUTED,
                 font=("Segoe UI", 8), justify=tk.LEFT).grid(
            row=5, column=0, sticky="w")

        # ── Buttons ──
        tk.Frame(self, bg=C_BORDER, height=1).pack(fill=tk.X, padx=20)

        btn_row = tk.Frame(self, bg=C_BG)
        btn_row.pack(fill=tk.X, padx=20, pady=12)

        cancel_btn = tk.Button(
            btn_row, text="Cancel", command=self.destroy,
            bg=C_BTN, fg=C_TEXT, activebackground=C_BTN_HV,
            relief=tk.FLAT, font=FONT, padx=16, pady=6, cursor="hand2"
        )
        cancel_btn.pack(side=tk.RIGHT, padx=(6, 0))

        ok_btn = tk.Button(
            btn_row, text="  Save  ", command=self._save,
            bg=C_ACCENT, fg="#000", activebackground="#00b894",
            relief=tk.FLAT, font=("Segoe UI", 10, "bold"),
            padx=16, pady=6, cursor="hand2"
        )
        ok_btn.pack(side=tk.RIGHT)

    def _browse(self):
        path = filedialog.askdirectory(
            initialdir=self.storage_path,
            title="Choose storage folder"
        )
        if path:
            self._path_var.set(path)

    def _save(self):
        self.storage_path = self._path_var.get()
        self.accepted = True
        self.destroy()

    def _centre_on_parent(self, parent):
        self.update_idletasks()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        w  = self.winfo_reqwidth()
        h  = self.winfo_reqheight()
        x  = px + (pw - w) // 2
        y  = py + (ph - h) // 2
        self.geometry(f"+{x}+{y}")
