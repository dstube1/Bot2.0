

import sys
import threading
import keyboard  # pip install keyboard
import json
import os
from PyQt5.QtWidgets import QApplication, QWidget, QLabel
from PyQt5.QtCore import Qt, QRect, QPoint
from PyQt5.QtGui import QPainter, QPen, QColor, QGuiApplication, QFont

class TransparentOverlay(QWidget):
	def set_instruction(self, text):
		self.instruction = text
		self.update()
	def __init__(self):
		super().__init__()
		self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
		self.setAttribute(Qt.WA_TranslucentBackground)
		self.setAttribute(Qt.WA_NoSystemBackground, True)
		self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
		self.setMouseTracking(True)
		self.start = None
		self.end = None
		self.drawing = False
		self.show_background = False  # Start with background off
		self.rectangle_finalized = False
		self.instruction = ""
		geometry = self.get_all_screens_geometry()
		self.setGeometry(geometry)
		self.showFullScreen()
		print(f"Overlay geometry: {geometry}")

	def get_all_screens_geometry(self):
		screens = QGuiApplication.screens()
		if not screens:
			return QApplication.primaryScreen().geometry()
		rect = screens[0].geometry()
		for screen in screens[1:]:
			rect = rect.united(screen.geometry())
		return rect

	def toggle_background(self):
		# Enable background and allow drawing
		self.show_background = True
		self.rectangle_finalized = False
		self.start = None
		self.end = None
		self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
		print("Background enabled, ready to draw (global hotkey).")
		self.update()

	def mousePressEvent(self, event):
		if event.button() == Qt.LeftButton and self.show_background:
			self.start = event.pos()
			self.end = event.pos()
			self.drawing = True
			self.rectangle_finalized = False
			self.update()

	def mouseMoveEvent(self, event):
		if self.drawing and self.show_background:
			self.end = event.pos()
			self.update()

	def mouseReleaseEvent(self, event):
		if event.button() == Qt.LeftButton and self.drawing and self.show_background:
			self.end = event.pos()
			self.drawing = False
			rect = QRect(self.start, self.end).normalized()
			print(f"Rectangle selected: x={rect.x()}, y={rect.y()}, w={rect.width()}, h={rect.height()}")
			self.rectangle_finalized = True
			self.show_background = False  # Hide background after drawing
			self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
			self.update()

	def paintEvent(self, event):
		painter = QPainter(self)
		painter.setRenderHint(QPainter.Antialiasing)
		# Show background only if enabled
		if self.show_background:
			painter.fillRect(self.rect(), QColor(100, 100, 100, 80))
		else:
			painter.fillRect(self.rect(), QColor(0, 0, 0, 0))
		# Draw rectangle if exists
		if self.start and self.end and (self.drawing or self.rectangle_finalized or self.start != self.end):
			rect = QRect(self.start, self.end).normalized()
			if self.show_background:
				painter.fillRect(rect, QColor(255, 0, 0, 60))
			pen = QPen(QColor(255, 0, 0), 3)
			painter.setPen(pen)
			painter.drawRect(rect)
		# Draw instruction text
		if self.instruction:
			painter.setPen(QColor(255,255,255))
			painter.setFont(QFont('Arial', 32, QFont.Bold))
			painter.drawText(self.rect(), Qt.AlignTop | Qt.AlignHCenter, self.instruction)


class CalibrationManager:
	def __init__(self, overlay, config_path):
		self.overlay = overlay
		self.config_path = config_path
		self.entries = []
		self.current = 0
		self.load_entries()
		self.running = False
		self.result_windows = []

	def load_entries(self):
		with open(self.config_path, 'r', encoding='utf-8') as f:
			data = json.load(f)
		self.entries = data['other']
		self.data = data

	def save_entries(self):
		self.data['other'] = self.entries
		with open(self.config_path, 'w', encoding='utf-8') as f:
			json.dump(self.data, f, indent=2)

	def start(self):
		self.running = True
		self.current = 0
		self.next_entry()

	def next_entry(self):
		if self.current >= len(self.entries):
			self.overlay.set_instruction("Calibration complete! All windows saved.")
			self.save_entries()
			return
		entry = self.entries[self.current]
		self.overlay.set_instruction(f"[{self.current+1}/{len(self.entries)}] F2: Draw region for '{entry['name']}'\nF3: Confirm selection")
		self.overlay.show_background = False
		self.overlay.rectangle_finalized = False
		self.overlay.start = None
		self.overlay.end = None
		self.overlay.setAttribute(Qt.WA_TransparentForMouseEvents, True)
		self.overlay.update()

	def confirm_entry(self):
		# Save only the top-left and bottom-right coordinates
		if self.overlay.start and self.overlay.end:
			rect = QRect(self.overlay.start, self.overlay.end).normalized()
			x1, y1 = rect.topLeft().x(), rect.topLeft().y()
			x2, y2 = rect.bottomRight().x(), rect.bottomRight().y()
			self.entries[self.current]['window'] = [x1, y1, x2, y2]
		self.current += 1
		self.next_entry()

def run_keyboard_listener(overlay, manager):
	# F2: Enable drawing, F3: Start/confirm
	keyboard.add_hotkey('f2', overlay.toggle_background)
	keyboard.add_hotkey('f3', lambda: manager.start() if not manager.running else manager.confirm_entry())
	keyboard.wait()


if __name__ == "__main__":
	config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'scan_windows.json')
	app = QApplication(sys.argv)
	overlay = TransparentOverlay()
	overlay.set_instruction("Press F3 to start calibration")
	overlay.show()
	manager = CalibrationManager(overlay, config_path)
	t = threading.Thread(target=run_keyboard_listener, args=(overlay, manager), daemon=True)
	t.start()
	sys.exit(app.exec_())

