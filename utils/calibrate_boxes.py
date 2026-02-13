
import os
import json
import time
import keyboard
from bot.base import BotState, PlayerInput

def prompt_user(message):
    print(f"{message} Press 'p' to confirm...")
    while True:
        if keyboard.is_pressed('p'):
            # Wait for key release to avoid double triggers
            while keyboard.is_pressed('p'):
                time.sleep(0.05)
            break

def calibrate_boxes():
    # Load gacha sets
    cfg_path = os.path.join(os.path.dirname(__file__), "..", "config", "gacha_sets.json")
    with open(cfg_path, "r") as f:
        data = json.load(f)
    sets = data.get("gacha_sets", [])

    # Prepare bot state and input
    bot_state = BotState()
    player_input = PlayerInput()
    time.sleep(4)  # Give user time to switch to Game

    for idx, box in enumerate(sets):
        box_name = box.get("name", f"box_{idx+1}")
        tp_box = box.get("tp_box")
        print(f"\nTeleporting to {box_name} ({tp_box})...")
        player_input.teleport_to(tp_box, bot_state)
        time.sleep(1)

        # Calibrate Gacha 1
        prompt_user(f"Look at Gacha 1 for {box_name}.")
        x1, y1, z1, yaw1, pitch1 = parse_ccc_clipboard(player_input)
        print(f"Gacha 1: x={x1}, y={y1}, z={z1}, yaw={yaw1}, pitch={pitch1}")
        box["gacha1_view_direction"] = {"yaw": yaw1, "pitch": pitch1, "x": x1, "y": y1, "z": z1}

        # Calibrate Gacha 2
        prompt_user(f"Look at Gacha 2 for {box_name}.")
        x2, y2, z2, yaw2, pitch2 = parse_ccc_clipboard(player_input)
        print(f"Gacha 2: x={x2}, y={y2}, z={z2}, yaw={yaw2}, pitch={pitch2}")
        box["gacha2_view_direction"] = {"yaw": yaw2, "pitch": pitch2, "x": x2, "y": y2, "z": z2}

        # Calibrate Pego
        prompt_user(f"Look at Pego for {box_name}.")
        xp, yp, zp, yawp, pitchp = parse_ccc_clipboard(player_input)
        print(f"Pego: x={xp}, y={yp}, z={zp}, yaw={yawp}, pitch={pitchp}")
        box["pego_view_direction"] = {"yaw": yawp, "pitch": pitchp, "x": xp, "y": yp, "z": zp}

    # Save updated config
    data["gacha_sets"] = sets
    with open(cfg_path, "w") as f:
        json.dump(data, f, indent=2)
    print("Calibration complete. Updated gacha_sets.json.")


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