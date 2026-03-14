"""
Basic UI for selecting tasks, starting the bot routine, and launching calibration.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import sys
import os
import json
import threading

from base import BotState, PlayerInput, InventoryManager
from tasks import MajorTask
from run_bot import run_bot


class BotUI:
	def __init__(self, master: tk.Tk):
		self.master = master
		self.master.title("ARK Gacha Bot 2.0")

		# Task selections
		self.feed_var = tk.BooleanVar(value=True)
		self.crack_var = tk.BooleanVar(value=True)
		self.start_with_crack_var = tk.BooleanVar(value=False)
		self.cycles_var = tk.StringVar(value="20")
		self.overlay_var = tk.BooleanVar(value=True)
		self.eat_twice_var = tk.BooleanVar(value=False)

		ttk.Label(master, text="Select tasks:").grid(row=0, column=0, sticky="w", padx=10, pady=(10, 0))
		ttk.Checkbutton(master, text="Feed Gachas", variable=self.feed_var).grid(row=1, column=0, sticky="w", padx=20)
		ttk.Checkbutton(master, text="Crack Crystals", variable=self.crack_var).grid(row=2, column=0, sticky="w", padx=20)
		ttk.Checkbutton(master, text="Start with Crack", variable=self.start_with_crack_var).grid(row=1, column=1, sticky="w", padx=10)
		ttk.Checkbutton(master, text="Feed twice", variable=self.eat_twice_var).grid(row=2, column=1, sticky="w", padx=10)

		ttk.Label(master, text="Cycles (0 = infinite):").grid(row=3, column=0, sticky="w", padx=10, pady=(10, 0))
		self.cycles_entry = ttk.Entry(master, textvariable=self.cycles_var, width=8)
		self.cycles_entry.grid(row=3, column=1, sticky="w", padx=10, pady=(10, 0))

		ttk.Checkbutton(master, text="Show Overlay", variable=self.overlay_var).grid(row=4, column=0, sticky="w", padx=10, pady=(10, 0))

		# Action buttons
		ttk.Button(master, text="Start Bot", command=self.start_bot).grid(row=5, column=0, padx=10, pady=10, sticky="w")
		ttk.Button(master, text="Run Calibration", command=self.run_calibration).grid(row=5, column=1, padx=10, pady=10, sticky="w")

	def start_bot(self):
		selected = []
		if self.feed_var.get():
			selected.append("feed")
		if self.crack_var.get():
			selected.append("crack")

		try:
			cycles = int(self.cycles_var.get())
			if cycles < 0:
				raise ValueError
		except ValueError:
			messagebox.showerror("Invalid Input", "Cycles must be a non-negative integer.")
			return

		if not selected:
			messagebox.showwarning("No Tasks", "Please select at least one task.")
			return

		show_overlay = self.overlay_var.get()
		start_with_crack = self.start_with_crack_var.get()
		eat_twice = self.eat_twice_var.get()
		threading.Thread(target=self._run_tasks, args=(selected, cycles, show_overlay, start_with_crack, eat_twice), daemon=True).start()

	def _run_tasks(self, selected, cycles=20, show_overlay=True, start_with_crack=False, eat_twice=False):
		try:
			def ui_callback(kind, msg):
				if kind == 'error':
					self.master.after(0, lambda: messagebox.showerror("Error", msg))
				elif kind == 'done':
					self.master.after(0, lambda: messagebox.showinfo("Done", msg))
			# Placeholder for overlay_callback, to be implemented in run_bot.py
			overlay_callback = None
			if show_overlay:
				from tkinter import Toplevel, Label
				overlay = Toplevel(self.master)
				overlay.title('Bot Overlay')
				overlay.geometry('+0+0')
				overlay.attributes('-topmost', True)
				overlay.overrideredirect(True)
				label = Label(overlay, text='', font=('Arial', 14), bg='black', fg='lime')
				label.pack(anchor='nw', fill='both', expand=True)
				def overlay_callback(text):
					label.config(text=text)
					overlay.update_idletasks()
					# Always position at bottom left
					screen_height = overlay.winfo_screenheight()
					overlay_height = overlay.winfo_height()
					overlay.geometry(f'+0+{screen_height - overlay_height}')
				overlay_callback('Bot started...')
			run_bot(selected, cycles, ui_callback, overlay_callback, start_with_crack=start_with_crack, eat_twice=eat_twice)
		except Exception as e:
			self.master.after(0, lambda: messagebox.showerror("Error", f"Failed to run tasks: {e}"))

	def run_calibration(self):
		# Run calibration script in a separate process using the same Python interpreter
		cal_path = os.path.join(os.path.dirname(__file__), "..", "calibration", "calibrator.py")
		cal_path = os.path.abspath(cal_path)
		if not os.path.exists(cal_path):
			messagebox.showerror("Not Found", "Calibration script not found.")
			return
		try:
			subprocess.Popen([sys.executable, cal_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
			messagebox.showinfo("Calibration", "Calibration started in a separate process.")
		except Exception as e:
			messagebox.showerror("Error", f"Failed to start calibration: {e}")


def launch_ui():
	root = tk.Tk()
	BotUI(root)
	root.mainloop()

