
import time
import ctypes
import pyperclip
import keyboard  # To detect key presses
from pynput.keyboard import Key, Controller
import json
import os
import threading
from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPainter, QColor, QFont

keyboard_controller = Controller()


def move_mouse_relative(dx: int, dy: int) -> None:
    """
    Moves the mouse dx to the right/left and dy up/down from the current position.
    """
    ctypes.windll.user32.mouse_event(0x0001, dx, dy, 0, 0)  # 0x0001 = MOUSEEVENTF_MOVE


def press_key(key: str, hold_time=0):
    """
    Presses a key and holds it for hold_time
    """
    special_keys = {
        'backspace': Key.backspace,
        'enter': Key.enter,
        'esc': Key.esc,
        'space': Key.space,
        'left': Key.left,
        'up': Key.up,
        'right': Key.right,
        'down': Key.down,
        'tab': Key.tab
    }
    
    key_to_press = special_keys.get(key.lower(), key)
    
    keyboard_controller.press(key_to_press)
    if hold_time > 0:
        time.sleep(hold_time)
    keyboard_controller.release(key_to_press)


def get_roll_and_pitch():
    """
    Extracts the pitch and roll (yaw) values from the clipboard data.
    
    Returns:
        tuple: (roll, pitch) as floats.
    """
    press_key('tab')
    time.sleep(2)
    press_key('c')
    time.sleep(0.2)
    press_key('c')
    time.sleep(0.2)
    press_key('c')
    time.sleep(0.2)
    press_key('enter')
    time.sleep(1)
    
    try:
        # Get the clipboard data
        clipboard_data = pyperclip.paste()
        print(f"Clipboard data: {clipboard_data}")  # Debugging: Print the clipboard data
        
        # Extract roll and pitch from the clipboard data
        pitch_str = clipboard_data.split()[-1]
        roll_str = clipboard_data.split()[-2]
        
        # Convert strings to floats
        pitch = float(pitch_str)
        roll = float(roll_str)
        print(f"Roll: {roll}, Pitch: {pitch}")
        return roll, pitch
    
    except Exception as e:
        print(f"An error occurred: {e}")
        return None, None

def test_mouse_movement(dx: int, dy: int):
    """
    Tests how moving the mouse affects the roll and pitch in-game.
    
    Args:
        dx (int): The amount to move the mouse horizontally (right/left).
        dy (int): The amount to move the mouse vertically (up/down).
    """
    print("\nCapturing initial roll and pitch...")
    initial_roll, initial_pitch = get_roll_and_pitch()
    
    if initial_roll is None or initial_pitch is None:
        print("Failed to capture initial roll and pitch.")
        return

    print(f"Moving mouse by dx={dx}, dy={dy}...")
    move_mouse_relative(dx, dy)
    time.sleep(1)  # Wait for the game to process the view change

    print("Capturing new roll and pitch...")
    new_roll, new_pitch = get_roll_and_pitch()
    time.sleep(1)

    if new_roll is None or new_pitch is None:
        print("Failed to capture new roll and pitch.")
        return
    time.sleep(1)
    # Calculate the change
    roll_change = new_roll - initial_roll
    pitch_change = new_pitch - initial_pitch

    print(f"Roll change: {roll_change} degrees")
    print(f"Pitch change: {pitch_change} degrees")
    
    # Sensitivity estimation
    if dx != 0:
        yaw_sensitivity = abs(roll_change / dx)
        print(f"Estimated Yaw Sensitivity: {yaw_sensitivity} degrees per pixel")
        
    if dy != 0:
        pitch_sensitivity = abs(pitch_change / dy)
        print(f"Estimated Pitch Sensitivity: {pitch_sensitivity} degrees per pixel")

    return round(yaw_sensitivity, 5), round(-pitch_sensitivity, 5)


def save_config(sensitivity):
    yaw_sensitivity, pitch_sensitivity = sensitivity  # Unpack the tuple

    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.json')
    config_path = os.path.abspath(config_path)

    # Load existing config if it exists
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            try:
                config_data = json.load(f)
            except Exception:
                config_data = {}
    else:
        config_data = {}

    # Update degree_to_pixel_factor
    config_data['degree_to_pixel_factor'] = {
        'x': yaw_sensitivity,
        'y': pitch_sensitivity
    }

    # Preserve Logging if present, else default to INFO
    if 'Logging' not in config_data:
        config_data['Logging'] = 'INFO'

    with open(config_path, 'w') as f:
        json.dump(config_data, f, indent=2)

    print(f"Saved degree_to_pixel_factor to {config_path}")




class CalibrationOverlay(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.setMouseTracking(True)
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
        # Get the bounding rectangle of all screens
        from PyQt5.QtGui import QGuiApplication
        screens = QGuiApplication.screens()
        if not screens:
            return QApplication.primaryScreen().geometry()
        rect = screens[0].geometry()
        for screen in screens[1:]:
            rect = rect.united(screen.geometry())
        return rect

def main():
    dx = 500 # Horizontal mouse movement in pixels
    dy = 500  # Vertical mouse movement in pixels (negative to move up)

    app = QApplication([])
    overlay = CalibrationOverlay()
    overlay.set_instruction("Prepare for mouse calibration and press F3 to start")
    overlay.show()

    confirmed = {'pressed': False}
    def on_f3():
        confirmed['pressed'] = True
        overlay.set_instruction("")
    keyboard.add_hotkey('f3', on_f3)
    # Wait for F3
    while not confirmed['pressed']:
        app.processEvents()
        time.sleep(0.05)

    # Run calibration sequence once after F3
    overlay.set_instruction("Calibrating: moving mouse +dx, +dy...")
    app.processEvents()
    test_mouse_movement(dx, dy)
    overlay.set_instruction("Calibrating: moving mouse -dx, -dy...")
    app.processEvents()
    sensitivity = test_mouse_movement(-dx, -dy)
    overlay.set_instruction("Saving calibration results...")
    app.processEvents()
    save_config(sensitivity)
    time.sleep(1)
    overlay.set_instruction("Calibration complete. You may close this window.")
    app.processEvents()
    time.sleep(2)
    overlay.close()
    app.quit()

# Run the main loop
if __name__ == "__main__":
    main()

