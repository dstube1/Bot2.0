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
from tasks import FertilizeBoxTask, FeedBoxTask, MajorTask


class BotUI:
	def __init__(self, master: tk.Tk):
		self.master = master
		self.master.title("ARK Bot Controller")

		# Task selections
		self.feed_var = tk.BooleanVar(value=False)
		self.empty_var = tk.BooleanVar(value=False)

		ttk.Label(master, text="Select tasks:").grid(row=0, column=0, sticky="w", padx=10, pady=(10, 0))
		ttk.Checkbutton(master, text="Feed Gachas", variable=self.feed_var).grid(row=1, column=0, sticky="w", padx=20)
		ttk.Checkbutton(master, text="Empty Crop Plots", variable=self.empty_var).grid(row=2, column=0, sticky="w", padx=20)

		# Action buttons
		ttk.Button(master, text="Start Bot", command=self.start_bot).grid(row=3, column=0, padx=10, pady=10, sticky="w")
		ttk.Button(master, text="Run Calibration", command=self.run_calibration).grid(row=3, column=1, padx=10, pady=10, sticky="w")

	def start_bot(self):
		selected = []
		if self.feed_var.get():
			selected.append("feed")
		if self.empty_var.get():
			selected.append("empty")

		if not selected:
			messagebox.showwarning("No Tasks", "Please select at least one task.")
			return

		# Run tasks in the background to keep UI responsive
		threading.Thread(target=self._run_tasks, args=(selected,), daemon=True).start()

	def _run_tasks(self, selected):
		try:
			# Initialize core components
			bot_state = BotState()
			player_input = PlayerInput()
			inventory = InventoryManager()

			# Load positions
			look_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'config', 'look_positions.json'))
			with open(look_path, 'r') as f:
				cfg = json.load(f)
			gachas = cfg.get('gachas', [])
			crop_plots = cfg.get('crop_plots', [])

			tasks = []
			if 'fertilize' in selected:
				tasks.append(FertilizeBoxTask(bot_state, player_input, inventory, crop_plots))
			if 'feed' in selected:
				tasks.append(FeedBoxTask(bot_state, player_input, inventory, gachas, crop_plots))

			if not tasks:
				self.master.after(0, lambda: messagebox.showwarning("No Tasks", "No tasks were created."))
				return

			MajorTask(tasks).run()
			self.master.after(0, lambda: messagebox.showinfo("Done", "Selected tasks completed."))
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

