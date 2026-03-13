
""" Teleporter calibration script for Bot2.0
    This script allows you to calibrate the coordinates of the teleporters added to config/teleporter.json.
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import time
import json
import keyboard
from bot.base import BotState, PlayerInput


def main():
    print("--- Teleporter Calibration Script ---")
    bot_state = BotState()
    player_input = PlayerInput()

    # Wait for F to start
    print("Press F6 to start calibration...")
    keyboard.wait('f6')
    print("Starting calibration!")

    # Wake up and calibrate current view
    player_input.wake_up(bot_state)
    yaw, pitch, x, y, z = player_input.calibrate_current_view(bot_state)
    print(f"Initial position: x={x}, y={y}, z={z}, yaw={yaw}, pitch={pitch}")

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
            print(f"Calibrating start teleporter: {name}")
            yaw, pitch, x, y, z = player_input.calibrate_current_view(bot_state)
        else:
            print(f"Teleporting to: {name}")
            player_input.teleport_to(name, bot_state)
            time.sleep(2)  # Wait for teleport to finish
            yaw, pitch, x, y, z = player_input.calibrate_current_view(bot_state)
        print(f"Teleporter '{name}' position: x={x}, y={y}, z={z}")
        tp['position'] = [x, y, z]
        with open(tp_cfg_path, 'w') as f:
            json.dump(tp_data, f, indent=2)
        time.sleep(1)
    print("Calibration complete!")

if __name__ == "__main__":
    main()
