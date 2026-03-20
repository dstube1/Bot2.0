
"""
Calibration logic and UI for determining constants in look_positions.json.
Run this as a one-time, player-assisted process.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import pyperclip
import json
import os
import pyautogui
import time
import re
import keyboard
from typing import Optional, Tuple


class CalibratorUI:
	def show_selection_buttons(self):
		self.click_btn.pack(pady=5)
		self.scan_btn.pack(pady=5)
		self.crystal_btn.pack(pady=5)
		# Ensure empty_grinder_btn is packed if it exists
		if hasattr(self, 'empty_grinder_btn') and self.empty_grinder_btn:
			self.empty_grinder_btn.pack(pady=5)

	def hide_selection_buttons(self):
		self.look_btn.pack_forget()
		self.click_btn.pack_forget()
		self.scan_btn.pack_forget()
		self.crystal_btn.pack_forget()
		# Ensure empty_grinder_btn is hidden if it exists
		if hasattr(self, 'empty_grinder_btn') and self.empty_grinder_btn:
			self.empty_grinder_btn.pack_forget()
	def __init__(self, master):
		self.master = master
		self.master.title("Calibration")
		self.master.attributes('-topmost', True)
		self.master.geometry('350x380')
		self.master.resizable(False, False)
		self.idx = 0
		self.results = []
		self.calibration_mode = None
		self.label = ttk.Label(master, text="Select calibration type:")
		self.label.pack(pady=10)
		self.mouse_calib_btn = ttk.Button(master, text="Mouse Calibration", command=lambda: self.run_external_script('mouse_calibration.py'))
		self.mouse_calib_btn.pack(pady=5)
		self.click_btn = ttk.Button(master, text="Click Calibration", command=lambda: self.run_external_script('calibrate_click.py'))
		self.click_btn.pack(pady=5)
		self.scan_btn = ttk.Button(master, text="Scan Calibration", command=lambda: self.run_external_script('calibrate_scan.py'))
		self.scan_btn.pack(pady=5)
		self.look_btn = ttk.Button(master, text="Box Calibration", command=lambda: self.run_external_script('calibrate_boxes.py'))
		self.look_btn.pack(pady=5)
		self.scan_btn = ttk.Button(master, text="Plots Calibration", command=lambda: self.run_external_script('calibrate_crop_plots.py'))
		self.scan_btn.pack(pady=5)
		self.tp_btn = ttk.Button(master, text="TP Calibration", command=lambda: self.run_external_script('calibrate_teleporters.py'))
		self.tp_btn.pack(pady=5)
		# New: capture crystal slot button
		self.crystal_btn = ttk.Button(master, text="Capture Crystal Slot", command=lambda: self.run_external_script('capture_crystal.py'))
		self.crystal_btn.pack(pady=5)
		# New: capture empty grinder slot button
		self.empty_grinder_btn = ttk.Button(master, text="Capture Empty Grinder Slot", command=lambda: self.run_external_script('capture_empty_grinder_slot.py'))
		self.empty_grinder_btn.pack(pady=5)
		self.status = ttk.Label(master, text="")
		self.status.pack(pady=5)

	def run_external_script(self, script_name):
		import subprocess
		import sys
		script_path = os.path.join(os.path.dirname(__file__), script_name)
		try:
			subprocess.Popen([sys.executable, script_path])
		except Exception as e:
			messagebox.showerror("Error", f"Failed to launch {script_name}: {e}")


def main():
	root = tk.Tk()
	CalibratorUI(root)
	root.mainloop()

if __name__ == "__main__":
	main()
