
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

def get_gacha_crystal_png(region: Optional[Tuple[int,int,int,int]] = None, output_path: str = None) -> bool:
	"""Capture the first-slot crystal image and save it as assets/Gacha_Crystal.png.

	If region is not provided, attempts to load `first_slot_own` region from
	`config/scan_windows.json` (under the `other` array). Region is expected as
	[x1, y1, x2, y2]. Converts to (left, top, width, height) for screenshot.

	Args:
		region: Optional explicit (x1, y1, x2, y2) capture rectangle.
		output_path: Optional override for output file path.
	Returns:
		True on success, False otherwise.
	"""
	try:
		if output_path is None:
			output_path = os.path.join(os.path.dirname(__file__), '..', 'assets', 'Gacha_Crystal.png')
		os.makedirs(os.path.dirname(output_path), exist_ok=True)

		# Auto-load region if not supplied
		if region is None:
			scan_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'scan_windows.json')
			if not os.path.exists(scan_path):
				print("get_gacha_crystal_png: scan_windows.json not found; provide region manually.")
				return False
			try:
				with open(scan_path, 'r') as f:
					scan_data = json.load(f)
				others = scan_data.get('other', [])
				entry = next((o for o in others if o.get('name') == 'first_slot_own'), None)
				if not entry:
					print("get_gacha_crystal_png: 'first_slot_own' entry missing in scan_windows.json")
					return False
				reg = entry.get('window') or entry.get('region')
				if not (isinstance(reg, (list, tuple)) and len(reg) == 4):
					print("get_gacha_crystal_png: invalid region format for first_slot_own")
					return False
				region = tuple(int(v) for v in reg)
			except Exception as e:
				print(f"get_gacha_crystal_png: failed loading region: {e}")
				return False

		x1, y1, x2, y2 = region
		width = x2 - x1
		height = y2 - y1
		if width <= 0 or height <= 0:
			print("get_gacha_crystal_png: computed non-positive width/height")
			return False

		# Small delay to allow user to ensure the inventory slot is visible
		print(f"Capturing crystal slot region {region} -> {output_path} in 5 seconds...")
		time.sleep(5)
		shot = pyautogui.screenshot(region=(x1, y1, width, height))
		shot.save(output_path)
		print("Gacha_Crystal.png saved.")
		return True
	except Exception as e:
		print(f"get_gacha_crystal_png: capture failed: {e}")
		return False

def get_empty_grinder_slot_png(region: Optional[Tuple[int,int,int,int]] = None, output_path: str = None) -> bool:
	"""Capture the grinder's first slot when empty and save it as assets/Empty_Grinder_Slot.png.

	If region is not provided, attempts to load `first_slot_grinder` region from
	`config/scan_windows.json` (under the `other` array). Region is expected as
	[x1, y1, x2, y2]. Converts to (left, top, width, height) for screenshot.

	Args:
		region: Optional explicit (x1, y1, x2, y2) capture rectangle.
		output_path: Optional override for output file path.
	Returns:
		True on success, False otherwise.
	"""
	try:
		if output_path is None:
			output_path = os.path.join(os.path.dirname(__file__), '..', 'assets', 'Empty_Grinder_Slot.png')
		os.makedirs(os.path.dirname(output_path), exist_ok=True)

		# Auto-load region if not supplied
		if region is None:
			scan_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'scan_windows.json')
			if not os.path.exists(scan_path):
				print("get_empty_grinder_slot_png: scan_windows.json not found; provide region manually.")
				return False
			try:
				with open(scan_path, 'r') as f:
					scan_data = json.load(f)
				others = scan_data.get('other', [])
				entry = next((o for o in others if o.get('name') == 'first_slot_grinder'), None)
				if not entry:
					print("get_empty_grinder_slot_png: 'first_slot_grinder' entry missing in scan_windows.json")
					return False
				reg = entry.get('window') or entry.get('region')
				if not (isinstance(reg, (list, tuple)) and len(reg) == 4):
					print("get_empty_grinder_slot_png: invalid region format for first_slot_grinder")
					return False
				region = tuple(int(v) for v in reg)
			except Exception as e:
				print(f"get_empty_grinder_slot_png: failed loading region: {e}")
				return False

		x1, y1, x2, y2 = region
		width = x2 - x1
		height = y2 - y1
		if width <= 0 or height <= 0:
			print("get_empty_grinder_slot_png: computed non-positive width/height")
			return False

		print(f"Capturing grinder empty slot region {region} -> {output_path} in 5 seconds...")
		time.sleep(5)
		shot = pyautogui.screenshot(region=(x1, y1, width, height))
		shot.save(output_path)
		print("Empty_Grinder_Slot.png saved.")
		return True
	except Exception as e:
		print(f"get_empty_grinder_slot_png: capture failed: {e}")
		return False

class CalibratorUI:
	def show_selection_buttons(self):
		self.look_btn.pack(pady=5)
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
		self.master.title("Calibration - Look Positions")
		self.master.attributes('-topmost', True)
		self.master.geometry('350x260')
		self.master.resizable(False, False)
		self.idx = 0
		self.results = []
		self.calibration_mode = None
		self.label = ttk.Label(master, text="Select calibration type:")
		self.label.pack(pady=10)
		self.look_btn = ttk.Button(master, text="Look Calibration", command=lambda: self.start_calibration('look'))
		self.look_btn.pack(pady=5)
		self.click_btn = ttk.Button(master, text="Click Calibration", command=lambda: self.start_calibration('click'))
		self.click_btn.pack(pady=5)
		self.scan_btn = ttk.Button(master, text="Scan Calibration", command=lambda: self.start_calibration('scan'))
		self.scan_btn.pack(pady=5)
		# New: capture crystal slot button
		self.crystal_btn = ttk.Button(master, text="Capture Crystal Slot", command=self.capture_crystal)
		self.crystal_btn.pack(pady=5)
		# New: capture empty grinder slot button
		self.empty_grinder_btn = ttk.Button(master, text="Capture Empty Grinder Slot", command=self.capture_empty_grinder_slot)
		self.empty_grinder_btn.pack(pady=5)
		self.status = ttk.Label(master, text="")
		self.status.pack(pady=5)
		crop_plot_targets = [
			{"name": f"crop_plot_{i}", "desc": f"Look at Crop Plot {i} and press Calibrate"}
			for i in range(1, 25)
		]
		self.targets = {
			'look': [
				{"name": "gacha_1", "desc": "Look at Gacha 1 and press Calibrate"},
				{"name": "gacha_2", "desc": "Look at Gacha 2 and press Calibrate"},
			] + crop_plot_targets,
			'click': [
				{"name": "tp_textfield", "desc": "Click on TP textfield"},
				{"name": "choose_top_tp", "desc": "Click on Choose Top TP"},
				{"name": "teleport_button", "desc": "Click on Teleport button"},
				{"name": "textfield_left", "desc": "Click on Own Inventory textfield"},
				{"name": "textfield_right", "desc": "Click on Other Inventory textfield"},
				{"name": "take_all", "desc": "Click on Take All button"},
				{"name": "store_all", "desc": "Click on Store All button"},
				{"name": "drop_all", "desc": "Click on Drop All button"}
			],
			'scan': []
		}

		# Crouch flag (only relevant for crop plot look calibration)
		self.crouch_var = tk.BooleanVar(value=False)
		self.crouch_check = ttk.Checkbutton(self.master, text="Crouch required", variable=self.crouch_var)
		# Initially hidden; shown when a crop_plot_* target is active
		self.update_ui()

	def start_calibration(self, mode):
		self.calibration_mode = mode
		self.idx = 0
		self.results = []
		self.hide_selection_buttons()
		if hasattr(self, 'cal_btn') and self.cal_btn:
			self.cal_btn.destroy()
		if mode == 'look':
			self.cal_btn = ttk.Button(self.master, text="Calibrate (F8 Hotkey)", command=self.calibrate_look)
			self.cal_btn.pack(pady=5)
			keyboard.add_hotkey('F8', self.calibrate_look)
		elif mode == 'click':
			self.cal_btn = ttk.Button(self.master, text="Calibrate Click (F8 Hotkey)", command=self.calibrate_click)
			self.cal_btn.pack(pady=5)
			keyboard.add_hotkey('F8', self.calibrate_click)
		elif mode == 'scan':
			self.label.config(text="Scan Calibration (not implemented)")
			return
		self.update_ui()

	def save_click_results(self):
		try:
			save_path = os.path.join(os.path.dirname(__file__), '../config/click_positions.json')
			# Load existing click positions
			if os.path.exists(save_path):
				with open(save_path, 'r') as f:
					existing = json.load(f)
				clicks = existing.get('inventories', [])
			else:
				clicks = []
			click_dict = {entry['name']: entry for entry in clicks}
			for result in self.click_results:
				click_dict[result['name']] = result
			new_clicks = list(click_dict.values())
			with open(save_path, 'w') as f:
				json.dump({'inventories': new_clicks}, f, indent=2)
			messagebox.showinfo("Saved", f"Click calibration data saved to {save_path}")
		except Exception as e:
			messagebox.showerror("Error", f"Failed to save click calibration data: {e}")

	def update_ui(self):
		if self.calibration_mode is None:
			self.label.config(text="Select calibration type:")
			self.status.config(text="")
			self.show_selection_buttons()
			if hasattr(self, 'cal_btn') and self.cal_btn:
				self.cal_btn.pack_forget()
			return
		targets = self.targets.get(self.calibration_mode, [])
		if self.idx < len(targets):
			self.label.config(text=targets[self.idx]["desc"])
			self.status.config(text=f"Target {self.idx+1} of {len(targets)}")
			if self.cal_btn:
				self.cal_btn.config(state=tk.NORMAL)
			# Show crouch checkbox when calibrating crop plots
			current_name = targets[self.idx]["name"]
			if self.calibration_mode == 'look' and current_name.startswith('crop_plot_'):
				self.crouch_check.pack(pady=4)
			else:
				self.crouch_check.pack_forget()
		else:
			self.label.config(text=f"{self.calibration_mode.capitalize()} Calibration complete!")
			self.status.config(text=f"All {self.calibration_mode} targets calibrated.")
			if self.cal_btn:
				self.cal_btn.config(state=tk.DISABLED)
				self.cal_btn.pack_forget()
			if self.calibration_mode == 'look':
				self.save_look_results()
			elif self.calibration_mode == 'click':
				self.save_click_results()
			self.calibration_mode = None
			self.idx = 0
			self.results = []
			self.update_ui()

	def calibrate_look(self):
		try:
			pyautogui.press('tab')
			pyautogui.typewrite('ccc')
			pyautogui.press('enter')
			self.status.config(text="Waiting for clipboard...")
			self.master.update()
			time.sleep(0.5)
			clip = pyperclip.paste()
			pos, view = self.parse_clipboard(clip)
			targets = self.targets.get('look', [])
			name = targets[self.idx]["name"]
			entry = {"name": name, "position": pos, "view_direction": view}
			# Attach crouch for crop plots
			if name.startswith('crop_plot_'):
				entry["crouch"] = bool(self.crouch_var.get())
			self.results.append(entry)
			self.status.config(text="Captured!")
			if self.cal_btn:
				self.cal_btn.config(state=tk.DISABLED)
			self.idx += 1
			self.update_ui()
		except Exception as e:
			messagebox.showerror("Error", f"Failed to run ccc or read clipboard: {e}")

	def next_target(self):
		self.idx += 1
		self.update_ui()

	def parse_clipboard(self, clip):
		try:
			self.status.config(text="Waiting for clipboard...")
			self.master.update()
			time.sleep(0.5)  # Wait for clipboard to update
			clipboard_data = pyperclip.paste()
			print(f"Clipboard data: {clipboard_data}")  # Debugging: Print the clipboard data
			# Extract pos, yaw, pitch from the clipboard data
			data_parts = clipboard_data.strip().split()
			pos_str = data_parts[-3]
			yaw_str = data_parts[-2]
			pitch_str = data_parts[-1]
			pos = float(pos_str)
			yaw = float(yaw_str)
			pitch = float(pitch_str)
			print(f"Pos: {pos}, Yaw: {yaw}, Pitch: {pitch}")
			return pos, (yaw, pitch)
		except Exception as e:
			print(f"An error occurred: {e}")
			messagebox.showerror("Error", f"Failed to run ccc or read clipboard: {e}")
			return None, (None, None)

	def calibrate_click(self):
		try:
			x, y = pyautogui.position()
			targets = self.targets.get('click', [])
			self.results.append({
				"name": targets[self.idx]["name"],
				"position": (x, y)
			})
			self.status.config(text="Captured!")
			if self.cal_btn:
				self.cal_btn.config(state=tk.DISABLED)
			self.idx += 1
			self.update_ui()
		except Exception as e:
			messagebox.showerror("Error", f"Failed to capture click position: {e}")

	def capture_crystal(self):
		"""UI handler to capture the gacha crystal slot image using get_gacha_crystal_png()."""
		self.status.config(text="Capturing crystal slot...")
		self.master.update()
		ok = get_gacha_crystal_png()
		if ok:
			messagebox.showinfo("Captured", "Saved assets/Gacha_Crystal.png")
			self.status.config(text="Crystal slot captured.")
		else:
			messagebox.showerror("Error", "Crystal capture failed. Ensure scan_windows.json has first_slot_own.")
			self.status.config(text="Capture failed.")

	def capture_empty_grinder_slot(self):
		"""UI handler to capture the empty grinder slot image using get_empty_grinder_slot_png()."""
		self.status.config(text="Capturing empty grinder slot...")
		self.master.update()
		ok = get_empty_grinder_slot_png()
		if ok:
			messagebox.showinfo("Captured", "Saved assets/Empty_Grinder_Slot.png")
			self.status.config(text="Empty grinder slot captured.")
		else:
			messagebox.showerror("Error", "Empty grinder capture failed. Ensure scan_windows.json has first_slot_grinder.")
			self.status.config(text="Capture failed.")

	def save_look_results(self):
		"""Save look calibration results.
		- gacha_* entries -> config/gacha_sets.json (gacha1_view_direction / gacha2_view_direction)
		- crop_plot_* entries -> config/crop_plot_look_positions.json (target_name + view_direction + crouch)
		"""
		try:
			# Load gacha_sets.json for gacha view directions
			gs_path = os.path.join(os.path.dirname(__file__), '../config/gacha_sets.json')
			if os.path.exists(gs_path):
				with open(gs_path, 'r') as f:
					gacha_sets_data = json.load(f)
			else:
				gacha_sets_data = {"gacha_sets": []}
			# Ensure at least one box exists to attach views; if not, create a default
			if not gacha_sets_data.get('gacha_sets'):
				gacha_sets_data['gacha_sets'].append({
					"name": "box_1",
					"tp_box": "",
					"tp_plots_gacha1": "",
					"tp_plots_gacha2": "",
					"gacha1_view_direction": {"yaw": 0.0, "pitch": 0.0},
					"gacha2_view_direction": {"yaw": 0.0, "pitch": 0.0}
				})
			# For now, write to the first box entry
			box_entry = gacha_sets_data['gacha_sets'][0]

			# Save crop plots to crop_plot_look_positions.json
			cp_path = os.path.join(os.path.dirname(__file__), '../config/crop_plot_look_positions.json')
			if os.path.exists(cp_path):
				with open(cp_path, 'r') as f:
					existing_cp = json.load(f)
				cp_items = existing_cp.get('crop_plot_look_positions', [])
			else:
				cp_items = []
			cp_dict = {e.get('target_name', e.get('name')): e for e in cp_items}

			for result in self.results:
				name = result['name']
				if name.startswith('crop_plot_'):
					cp_dict[name] = {
						'target_name': name,
						'view_direction': result['view_direction'],
						'crouch': bool(result.get('crouch', False))
					}
				else:
					# gacha view directions saved into gacha_sets.json
					if name == 'gacha_1':
						box_entry['gacha1_view_direction'] = {
							'yaw': float(result['view_direction'][0]),
							'pitch': float(result['view_direction'][1])
						}
					elif name == 'gacha_2':
						box_entry['gacha2_view_direction'] = {
							'yaw': float(result['view_direction'][0]),
							'pitch': float(result['view_direction'][1])
						}

			with open(gs_path, 'w') as f:
				json.dump(gacha_sets_data, f, indent=2)
			with open(cp_path, 'w') as f:
				json.dump({'crop_plot_look_positions': list(cp_dict.values())}, f, indent=2)
			messagebox.showinfo("Saved", "Gacha and crop plot look positions saved.")
		except Exception as e:
			messagebox.showerror("Error", f"Failed to save calibration data: {e}")

	def save_click_results(self):
		"""Save click calibration results to click_positions.json."""
		try:
			save_path = os.path.join(os.path.dirname(__file__), '../config/click_positions.json')
			if os.path.exists(save_path):
				with open(save_path, 'r') as f:
					existing = json.load(f)
				clicks = existing.get('inventories', [])
			else:
				clicks = []
			click_dict = {entry['name']: entry for entry in clicks}
			for result in self.results:
				click_dict[result['name']] = result
			new_clicks = list(click_dict.values())
			with open(save_path, 'w') as f:
				json.dump({'inventories': new_clicks}, f, indent=2)
			messagebox.showinfo("Saved", f"Click calibration data saved to {save_path}")
		except Exception as e:
			messagebox.showerror("Error", f"Failed to save click calibration data: {e}")


def main():
	root = tk.Tk()
	CalibratorUI(root)
	root.mainloop()

if __name__ == "__main__":
	main()
