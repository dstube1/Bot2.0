
#USAGE: python -m utils.calibrate_crop_plots
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import json
import time
import threading
import keyboard
from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPainter, QColor, QFont
import pyautogui
import pyperclip
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

def prompt_user(message):
    print(f"{message} Press 'p' to confirm...")
    while True:
        if keyboard.is_pressed('p'):
            while keyboard.is_pressed('p'):
                time.sleep(0.05)
            break

def calibrate_crop_plots():
    # Load existing crop plot positions
    cfg_path = os.path.join(os.path.dirname(__file__), "..", "config", "crop_plot_look_positions.json")
    with open(cfg_path, "r") as f:
        data = json.load(f)
    plots = data.get("crop_plot_look_positions", [])


    # Prepare bot state and input
    bot_state = BotState()
    player_input = PlayerInput()


    app = QApplication(sys.argv)
    overlay = CalibrationOverlay()
    overlay.set_instruction("")
    overlay.show()

    # Initial prompt for user to stand on teleporter
    prompt_user_overlay_f3("Stand on teleporter and press F3 to start", overlay)

    # Teleport to plots1
    prompt_user_overlay_f3("Teleporting to plots1 teleporter... Press F3 to continue.", overlay)
    player_input.teleport_to("plots1", bot_state)
    time.sleep(1)

    new_plots = []
    for idx in range(1, 33):
        target_name = f"crop_plot_{idx}"
        crouch = False
        # If previous config exists, use crouch value
        for plot in plots:
            if plot.get("target_name") == target_name:
                crouch = plot.get("crouch", False)
                break
        overlay.set_instruction("")
        prompt_user_overlay_f3(f"Look at {target_name} and press F3 after running ccc.", overlay)
        # Run ccc command and extract yaw/pitch
        pyautogui.press('tab')
        pyautogui.typewrite('ccc')
        pyautogui.press('enter')
        time.sleep(0.5)
        text = pyperclip.paste()
        parts = text.strip().split()
        if len(parts) < 5:
            print(f"Warning: Unexpected ccc clipboard format for {target_name}: {text}")
            continue
        yaw, pitch = map(float, parts[3:5])
        new_plots.append({
            "target_name": target_name,
            "view_direction": [yaw, pitch],
            "crouch": crouch
        })
        print(f"{target_name}: yaw={yaw}, pitch={pitch}, crouch={crouch}")


    overlay.close()
    app.quit()

    # Save updated config
    data["crop_plot_look_positions"] = new_plots
    with open(cfg_path, "w") as f:
        json.dump(data, f, indent=2)
    print("Calibration complete. Updated crop_plot_look_positions.json.")

if __name__ == "__main__":
    calibrate_crop_plots()
