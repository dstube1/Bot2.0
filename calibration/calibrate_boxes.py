
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import json
import time
from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPainter, QColor, QFont
import pyautogui
try:
    import mouse
    mouse_installed = True
except ImportError:
    mouse_installed = False
from bot.base import BotState, PlayerInput


import threading
import keyboard


def prompt_user_overlay_f3(message, overlay):
    overlay.set_instruction(message)
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

def calibrate_boxes():
    # Load gacha sets
    cfg_path = os.path.join(os.path.dirname(__file__), "..", "config", "gacha_sets.json")
    with open(cfg_path, "r") as f:
        data = json.load(f)
    sets = data.get("gacha_sets", [])

    # Prepare bot state and input
    bot_state = BotState()
    player_input = PlayerInput()

    app = QApplication([])
    overlay = CalibrationOverlay()
    overlay.set_instruction("")
    overlay.show()

    # Initial prompt for user to stand on teleporter
    prompt_user_overlay_f3("Stand on teleporter and press F3 to start", overlay)

    # Only calibrate boxes 7 to 12 (indices 6 to 11)
    for idx in range(0, 12):
        if idx >= len(sets):
            overlay.set_instruction(f"Error: Box index {idx+1} does not exist in gacha_sets.json.")
            app.processEvents()
            time.sleep(2)
            continue
        box = sets[idx]
        box_name = box.get("name", f"box_{idx+1}")
        tp_box = box.get("tp_box")
        prompt_user_overlay_f3(f"Press F3 to teleport to {box_name} ({tp_box})...", overlay)
        player_input.teleport_to(tp_box, bot_state)
        time.sleep(1)

        # Calibrate Gacha 1
        prompt_user_overlay_f3(f"Look at Gacha 1 for {box_name}, then press F3 to capture.", overlay)
        x1, y1, z1, yaw1, pitch1 = parse_ccc_clipboard(player_input)
        box["gacha1_view_direction"] = {"yaw": yaw1, "pitch": pitch1, "x": x1, "y": y1, "z": z1}

        # Calibrate Gacha 2
        prompt_user_overlay_f3(f"Look at Gacha 2 for {box_name}, then press F3 to capture.", overlay)
        x2, y2, z2, yaw2, pitch2 = parse_ccc_clipboard(player_input)
        box["gacha2_view_direction"] = {"yaw": yaw2, "pitch": pitch2, "x": x2, "y": y2, "z": z2}

        # Calibrate Pego
        prompt_user_overlay_f3(f"Look at Pego for {box_name}, then press F3 to capture.", overlay)
        xp, yp, zp, yawp, pitchp = parse_ccc_clipboard(player_input)
        box["pego_view_direction"] = {"yaw": yawp, "pitch": pitchp, "x": xp, "y": yp, "z": zp}

    overlay.set_instruction("Calibration complete. Updated gacha_sets.json.\nYou may close this window.")
    app.processEvents()
    time.sleep(2)
    overlay.close()
    app.quit()


import pyperclip

def parse_ccc_clipboard(player_input):
    # Directly perform the ccc command, copy, and extract all values from clipboard
    import pyautogui
    import pyperclip
    time.sleep(0.5)
    # Open console, type ccc, press enter
    pyautogui.press('tab')
    pyautogui.typewrite('ccc')
    pyautogui.press('enter')
    time.sleep(0.5)  # Wait for clipboard to update
    # Read clipboard
    text = pyperclip.paste()
    parts = text.strip().split()
    if len(parts) < 5:
        raise ValueError(f"Unexpected ccc clipboard format: {text}")
    x, y, z = map(float, parts[:3])
    yaw, pitch = map(float, parts[3:5])
    return x, y, z, yaw, pitch

if __name__ == "__main__":
    calibrate_boxes()