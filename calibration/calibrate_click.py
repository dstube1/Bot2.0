import json
import os


import time
import keyboard
import mouse

CONFIG_PATH = os.path.join(os.path.dirname(__file__), '../config/click_positions.json')


def load_click_positions():
    with open(CONFIG_PATH, 'r') as f:
        data = json.load(f)
    return data.get('inventories', [])

def save_click_positions(inventories):
    with open(CONFIG_PATH, 'w') as f:
        json.dump({'inventories': inventories}, f, indent=2)



# --- Overlay for instructions ---
from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPainter, QColor, QFont

class CalibrationOverlay(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setGeometry(self.screenGeometry())
        self.instruction = ""
        self.showFullScreen()

    def set_instruction(self, text):
        self.instruction = text
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 0))
        if self.instruction:
            painter.setPen(QColor(255,255,255))
            painter.setFont(QFont('Arial', 32, QFont.Bold))
            painter.drawText(self.rect(), Qt.AlignTop | Qt.AlignHCenter, self.instruction)

    def screenGeometry(self):
        from PyQt5.QtGui import QGuiApplication
        screens = QGuiApplication.screens()
        if not screens:
            return QApplication.primaryScreen().geometry()
        rect = screens[0].geometry()
        for screen in screens[1:]:
            rect = rect.united(screen.geometry())
        return rect

def prompt_f3_overlay(message, overlay, app):
    overlay.set_instruction(message)
    overlay.show()
    confirmed = {'pressed': False}
    def on_f3():
        confirmed['pressed'] = True
        overlay.set_instruction("")
    keyboard.add_hotkey('f3', on_f3)
    while not confirmed['pressed']:
        app.processEvents()
        time.sleep(0.05)
    while keyboard.is_pressed('f3'):
        time.sleep(0.05)

def calibrate_clicks():
    inventories = load_click_positions()
    updated = []

    app = QApplication([])
    overlay = CalibrationOverlay()
    overlay.set_instruction("")
    overlay.show()

    for entry in inventories:
        name = entry['name']
        prompt_f3_overlay(f"Next: {name}\nPress F3 when ready to click.", overlay, app)
        overlay.set_instruction(f"Now click the '{name}' button with your mouse...")
        app.processEvents()
        pos = None
        def on_click():
            nonlocal pos
            pos = mouse.get_position()
        mouse.on_click(lambda: on_click())
        while pos is None:
            app.processEvents()
            time.sleep(0.01)
        mouse.unhook_all()
        entry['position'] = [int(pos[0]), int(pos[1])]
        updated.append(entry)

    save_click_positions(updated)
    overlay.set_instruction("All click positions have been calibrated and saved.\nYou may close this window.")
    app.processEvents()
    time.sleep(2)
    overlay.close()
    app.quit()

if __name__ == "__main__":
    calibrate_clicks()
