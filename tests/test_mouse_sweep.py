
import pyautogui
import keyboard
import time

# Coordinates to jump between
y_coord = 370
x1 = 730
x2 = 1350

running = False

print("Press 'p' to start jumping, 'o' to stop.")

while True:
    if keyboard.is_pressed('p') and not running:
        print("Jumping started. Pressing 'e' at each position. Press 'o' to stop.")
        running = True
        while running:
            for x in (x1, x2):
                if keyboard.is_pressed('o'):
                    running = False
                    break
                pyautogui.moveTo(x, y_coord)
                pyautogui.press('e')
                time.sleep(0.02)
        print("Jumping stopped. Waiting for 'p' to start again.")
    time.sleep(0.1)
