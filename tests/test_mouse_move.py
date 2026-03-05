import pyautogui
import keyboard
import ctypes

# 2K ultrawide: 2560x1080, so center is (1280, 540)
CENTER_X, CENTER_Y = 1720, 720
TARGET_X, TARGET_Y = 1910, 515

print("Press 'O' to move mouse to center (1720, 720) (absolute)")
print("Press 'P' to move mouse to (1910, 515) (absolute)")
print("Press 'ESC' to exit.")

def set_cursor_pos(x, y):
    ctypes.windll.user32.SetCursorPos(int(x), int(y))

while True:
    if keyboard.is_pressed('o'):
        set_cursor_pos(CENTER_X, CENTER_Y)
        print(f"Moved to center: ({CENTER_X}, {CENTER_Y}) [absolute]")
        while keyboard.is_pressed('o'):
            pass  # Wait for key release
    if keyboard.is_pressed('p'):
        set_cursor_pos(TARGET_X, TARGET_Y)
        print(f"Moved to: ({TARGET_X}, {TARGET_Y}) [absolute]")
        while keyboard.is_pressed('p'):
            pass  # Wait for key release
    if keyboard.is_pressed('esc'):
        print("Exiting.")
        break
