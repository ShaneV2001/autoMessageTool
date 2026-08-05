#!/usr/bin/env python3
"""
Appointment Reminder Texter
----------------------------
A small desktop app (NO AppleScript involved) that composes an iMessage
appointment reminder, shows you a preview to confirm, then opens Messages
and types (and optionally sends) it for you.

ONE-TIME SETUP
--------------
1. Install Python 3 if you don't have it (macOS often already has it):
   https://www.python.org/downloads/

2. Install the two libraries this script needs:
       pip3 install tkcalendar pyautogui

3. Grant Accessibility permission (this is what lets the script "type"
   for you):
       System Settings -> Privacy & Security -> Accessibility
       -> turn ON for your Terminal app (or "Python")

HOW THE AUTOMATION WORKS (no AppleScript anywhere):
    1. `open -a Messages`            -> brings Messages to the front
    2. `open imessage://<number>`    -> opens/creates that conversation
    3. pyautogui types the message text into the compose field
    4. (optional, your choice via checkbox) presses Return to send it

RUN IT
------
    python3 appointment_texter.py
"""

import re
import time
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, messagebox

try:
    from tkcalendar import DateEntry
except ImportError:
    raise SystemExit(
        "Missing dependency 'tkcalendar'.\nRun:  pip3 install tkcalendar pyautogui"
    )


APP_TITLE = "Appointment Texter"
PHONE_PLACEHOLDER = "555-555-5555"
SERVICE_PLACEHOLDER = "Data,Tablet whatever fn"


def normalize_phone(raw: str) -> str:
    """Turn whatever the user typed into a phone number Messages can use."""
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 10:
        digits = "1" + digits
    return "+" + digits


def build_message(name, date_str, time_str, services, notes):
    first_line = f"Hi {name}! This is a reminder for your appointment on {date_str} at {time_str}"
    first_line += f" for {services}." if services else "."

    lines = [first_line]
    if notes:
        lines.append(notes.strip())
    lines.append("")
    lines.append("-Shane")
    return "\n".join(lines)


class AppointmentTexter(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("460x600")
        self.resizable(False, False)

        self.container = ttk.Frame(self, padding=16)
        self.container.pack(fill="both", expand=True)

        self.form_frame = None
        self.preview_frame = None
        self.pending = {}

        self.build_form()

    # ---------------- FORM SCREEN ----------------
    def build_form(self):
        if self.preview_frame:
            self.preview_frame.destroy()
            self.preview_frame = None

        f = ttk.Frame(self.container)
        f.pack(fill="both", expand=True)
        self.form_frame = f

        ttk.Label(f, text="Customer Name").pack(anchor="w")
        self.name_entry = ttk.Entry(f)
        self.name_entry.pack(fill="x", pady=(0, 10))

        ttk.Label(f, text="Phone Number").pack(anchor="w")
        self.phone_entry = ttk.Entry(f)
        self.phone_entry.insert(0, PHONE_PLACEHOLDER)
        self.phone_entry.pack(fill="x", pady=(0, 10))

        ttk.Label(f, text="Appointment Date").pack(anchor="w")
        self.date_entry = DateEntry(f, date_pattern="mm/dd/yyyy")
        self.date_entry.pack(anchor="w", pady=(0, 10))

        ttk.Label(f, text="Appointment Time").pack(anchor="w")
        time_row = ttk.Frame(f)
        time_row.pack(anchor="w", pady=(0, 10))

        self.hour_spin = ttk.Spinbox(time_row, from_=1, to=12, width=3,
                                      wrap=True, format="%02.0f")
        self.hour_spin.set("09")
        self.hour_spin.pack(side="left")

        ttk.Label(time_row, text=":").pack(side="left")

        self.minute_spin = ttk.Spinbox(
            time_row, values=[f"{m:02d}" for m in range(0, 60, 5)],
            width=3, wrap=True
        )
        self.minute_spin.set("00")
        self.minute_spin.pack(side="left")

        self.ampm = ttk.Combobox(time_row, values=["AM", "PM"], width=4, state="readonly")
        self.ampm.set("AM")
        self.ampm.pack(side="left", padx=(6, 0))

        ttk.Label(f, text="Service(s)").pack(anchor="w")
        self.service_entry = ttk.Entry(f)
        self.service_entry.insert(0, SERVICE_PLACEHOLDER)
        self.service_entry.pack(fill="x", pady=(0, 10))

        ttk.Label(f, text="Additional Note (optional)").pack(anchor="w")
        self.notes_text = tk.Text(f, height=5)
        self.notes_text.pack(fill="x", pady=(0, 14))

        ttk.Button(f, text="Preview Message \u2192", command=self.go_preview).pack(fill="x")

    def go_preview(self):
        name = self.name_entry.get().strip()
        phone_raw = self.phone_entry.get().strip()

        if not name:
            messagebox.showerror(APP_TITLE, "Please enter the customer's name.")
            return
        if not phone_raw or phone_raw == PHONE_PLACEHOLDER:
            messagebox.showerror(APP_TITLE, "Please enter a phone number.")
            return

        phone = normalize_phone(phone_raw)
        if len(phone) < 11:
            messagebox.showerror(APP_TITLE, "That phone number doesn't look right.")
            return

        date_str = self.date_entry.get_date().strftime("%A, %B %d")
        time_str = f"{self.hour_spin.get()}:{self.minute_spin.get()} {self.ampm.get()}"

        services = self.service_entry.get().strip()
        if services == SERVICE_PLACEHOLDER:
            services = ""
        notes = self.notes_text.get("1.0", "end").strip()

        message = build_message(name, date_str, time_str, services, notes)
        self.pending = {"phone": phone, "message": message}
        self.show_preview()

    # ---------------- PREVIEW SCREEN ----------------
    def show_preview(self):
        self.form_frame.pack_forget()

        f = ttk.Frame(self.container)
        f.pack(fill="both", expand=True)
        self.preview_frame = f

        ttk.Label(f, text="Review before sending:", font=("", 12, "bold")).pack(anchor="w", pady=(0, 8))
        ttk.Label(f, text=f"To: {self.pending['phone']}").pack(anchor="w")

        preview_box = tk.Text(f, height=10, wrap="word")
        preview_box.insert("1.0", self.pending["message"])
        preview_box.configure(state="disabled")
        preview_box.pack(fill="both", expand=True, pady=10)

        ttk.Label(
            f,
            text="Uncheck to leave it typed in Messages for you to send yourself:",
            wraplength=400,
            foreground="gray",
        ).pack(anchor="w", pady=(4, 2))

        self.auto_send_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            f,
            text="Send automatically after typing",
            variable=self.auto_send_var,
        ).pack(anchor="w", pady=(0, 10))

        self.status_label = ttk.Label(f, text="", foreground="gray")
        self.status_label.pack(anchor="w")

        btn_row = ttk.Frame(f)
        btn_row.pack(fill="x", pady=(10, 0))
        ttk.Button(btn_row, text="\u2190 Edit", command=self.go_edit).pack(side="left")
        self.confirm_btn = ttk.Button(btn_row, text="Confirm & Send", command=self.confirm_send)
        self.confirm_btn.pack(side="right")

    def go_edit(self):
        self.preview_frame.pack_forget()
        self.form_frame.pack(fill="both", expand=True)

    def confirm_send(self):
        self.confirm_btn.configure(state="disabled")
        threading.Thread(target=self._run_automation, daemon=True).start()

    def _set_status(self, text):
        self.status_label.configure(text=text)
        self.update_idletasks()

    def _run_automation(self):
        try:
            import pyautogui
            pyautogui.FAILSAFE = True  # safety: yank mouse to a screen corner to abort
        except ImportError:
            messagebox.showerror(APP_TITLE, "pyautogui is not installed.\nRun: pip3 install pyautogui")
            self.confirm_btn.configure(state="normal")
            return

        phone = self.pending["phone"]
        message = self.pending["message"]
        auto_send = self.auto_send_var.get()

        self._set_status("Opening Messages\u2026")
        subprocess.run(["open", "-a", "Messages"])
        time.sleep(1.2)

        self._set_status("Opening conversation\u2026")
        subprocess.run(["open", f"imessage://{phone}"])
        time.sleep(2.2)  # give Messages time to load & focus the compose field

        self._set_status("Typing message\u2026")
        segments = message.split("\n")
        for i, seg in enumerate(segments):
            if seg:
                pyautogui.write(seg, interval=0.01)
            if i < len(segments) - 1:
                pyautogui.hotkey("option", "return")  # newline WITHOUT sending

        if auto_send:
            self._set_status("Sending\u2026")
            time.sleep(0.3)
            pyautogui.press("return")
            self._set_status("Sent \u2713")
        else:
            self._set_status("Typed \u2014 review it in Messages and press Return to send.")

        time.sleep(0.5)
        self.confirm_btn.configure(state="normal")


if __name__ == "__main__":
    AppointmentTexter().mainloop()