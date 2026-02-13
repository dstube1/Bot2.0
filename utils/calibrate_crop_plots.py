import os
import json
import time
import keyboard
import pyautogui
import pyperclip
from bot.base import BotState, PlayerInput

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
    time.sleep(4)  # Give user time to switch to Game

    # Teleport to plots1
    print("Teleporting to plots1 teleporter...")
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
        prompt_user(f"Look at {target_name} and press 'p' after running ccc.")
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

    # Save updated config
    data["crop_plot_look_positions"] = new_plots
    with open(cfg_path, "w") as f:
        json.dump(data, f, indent=2)
    print("Calibration complete. Updated crop_plot_look_positions.json.")

if __name__ == "__main__":
    calibrate_crop_plots()
