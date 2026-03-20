import os
import sys
import time
import json
from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPainter, QColor, QFont
import pyautogui
import keyboard

def get_crystal_region():
    scan_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'scan_windows.json')
    if not os.path.exists(scan_path):
        print("scan_windows.json not found; provide region manually.")
        return None
    with open(scan_path, 'r') as f:
        scan_data = json.load(f)
    others = scan_data.get('other', [])
    entry = next((o for o in others if o.get('name') == 'first_slot_own'), None)
    if not entry:
        print("'first_slot_own' entry missing in scan_windows.json")
        return None
    reg = entry.get('window') or entry.get('region')
    if not (isinstance(reg, (list, tuple)) and len(reg) == 4):
        print("invalid region format for first_slot_own")
        return None
    return tuple(int(v) for v in reg)

class Overlay(QWidget):
    def __init__(self, message):
        super().__init__()
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setGeometry(self.screenGeometry())
        self.instruction = message
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

def main():
    app = QApplication([])
    overlay = Overlay("Press F3 to take screenshot")
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
    region = get_crystal_region()
    if not region:
        overlay.set_instruction("Region not found. Aborting.")
        app.processEvents()
        time.sleep(2)
        overlay.close()
        app.quit()
        return
    x1, y1, x2, y2 = region
    width = x2 - x1
    height = y2 - y1
    if width <= 0 or height <= 0:
        overlay.set_instruction("Invalid region size.")
        app.processEvents()
        time.sleep(2)
        overlay.close()
        app.quit()
        return
    output_path = os.path.join(os.path.dirname(__file__), '..', 'assets', 'Gacha_Crystal.png')
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    overlay.set_instruction("Capturing in 1 second...")
    app.processEvents()
    time.sleep(1)
    shot = pyautogui.screenshot(region=(x1, y1, width, height))
    shot.save(output_path)
    overlay.set_instruction("Screenshot saved!\nassets/Gacha_Crystal.png")
    app.processEvents()
    time.sleep(2)
    overlay.close()
    app.quit()

if __name__ == "__main__":
    main()
