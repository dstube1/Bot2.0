

""" Teleporter calibration script for Bot2.0
    This script allows you to calibrate the coordinates of the teleporters added to config/teleporter.json.
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import time
import json
import threading
import keyboard
from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPainter, QColor, QFont
from bot.base import BotState, PlayerInput


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
        # Fully transparent background
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

def prompt_user_overlay_f3(message, overlay):
    overlay.set_instruction(message + "\n(Press F3 to confirm)")
    overlay.show()
    confirmed = {'pressed': False}
    def on_f3():
        confirmed['pressed'] = True
        overlay.set_instruction("")
    keyboard.add_hotkey('f3', on_f3)
    app = QApplication.instance()
    while not confirmed['pressed']:
        app.processEvents()
        time.sleep(0.05)



def main():
    app = QApplication(sys.argv)
    overlay = CalibrationOverlay()
    overlay.set_instruction("")
    overlay.show()

    bot_state = BotState()
    player_input = PlayerInput()

    # Initial prompt
    prompt_user_overlay_f3("Lay in sleeping pod and press F3 to start calibration", overlay)

    # Wake up and calibrate current view
    player_input.wake_up(bot_state)
    yaw, pitch, x, y, z = player_input.calibrate_current_view(bot_state)

    # Load teleporters
    tp_cfg_path = os.path.join(os.path.dirname(__file__), '../config/teleporter.json')
    with open(tp_cfg_path, 'r') as f:
        tp_data = json.load(f)
    teleporters = tp_data.get('teleporters', [])

    for idx, tp in enumerate(teleporters):
        name = tp.get('name')
        if not name:
            continue
        if idx == 0:
            overlay.set_instruction(f"Calibrating start teleporter: {name}", overlay)
            yaw, pitch, x, y, z = player_input.calibrate_current_view(bot_state)
        else:
            overlay.set_instruction(f"Calibrating... {name}")
            overlay.show()
            app.processEvents()
            player_input.teleport_to(name, bot_state)
            time.sleep(2)  # Wait for teleport to finish
            yaw, pitch, x, y, z = player_input.calibrate_current_view(bot_state)
            overlay.set_instruction("")
            app.processEvents()
        tp['position'] = [x, y, z]
        with open(tp_cfg_path, 'w') as f:
            json.dump(tp_data, f, indent=2)
        time.sleep(1)
    overlay.close()
    app.quit()
    print("Teleporter calibration complete!")

if __name__ == "__main__":
    main()
