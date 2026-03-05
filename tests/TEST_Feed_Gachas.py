"""
Simple test script for GetTrapsTask.

Flow:
1) Teleport to the teleporter for a set of 24 crop plots
2) Take traps from each of the 24 plots
3) Teleport to a follow-up teleporter (e.g., gacha box or safe spot)
4) Pause for manual inspection

Configure TELEPORTER names below to match your environment.
"""

import time
import json
import os
import sys
import datetime
try:
    import keyboard  # for global hotkey (F1)
    KEYBOARD_AVAILABLE = True
except Exception:
    KEYBOARD_AVAILABLE = False

# Ensure workspace root is on sys.path so imports work when running from scripts/
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bot.tasks import GetTrapsTask, FeedGachaTask
from bot.base import BotState, PlayerInput, InventoryManager, RestartTask


 # --- Configuration: set your teleporter names here ---
 # (No longer needed; teleporters are loaded from gacha_sets.json)

def load_gacha_views():
    """Load gacha view directions for up to two boxes from gacha_sets.json.
    Returns: ((g1_box1, g2_box1), (g1_box2, g2_box2)) where the second pair may be None if not configured.
    """
    cfg_path = os.path.join(os.path.dirname(__file__), "..", "config", "gacha_sets.json")
    with open(cfg_path, "r") as f:
        data = json.load(f)
    sets = data.get("gacha_sets", [])
    if not sets:
        raise RuntimeError("No gacha_sets found in config/gacha_sets.json")

    def extract_box_views(box):
        g1 = box.get("gacha1_view_direction") or box.get("gacha1", {}).get("view_direction")
        g2 = box.get("gacha2_view_direction") or box.get("gacha2", {}).get("view_direction")
        if g1 is None or g2 is None:
            raise RuntimeError("Missing gacha1/2 view directions in gacha_sets.json for a box entry")
        return g1, g2

    def as_tuple(v):
        if isinstance(v, dict):
            return (float(v.get("yaw", 0.0)), float(v.get("pitch", 0.0)))
        return tuple(v)

    # Box 1 (required)
    g1_b1, g2_b1 = extract_box_views(sets[0])
    g1_b1, g2_b1 = as_tuple(g1_b1), as_tuple(g2_b1)

    # Box 2 (optional)
    g1_b2 = g2_b2 = None
    if len(sets) > 1:
        g1_b2_raw, g2_b2_raw = extract_box_views(sets[1])
        g1_b2, g2_b2 = as_tuple(g1_b2_raw), as_tuple(g2_b2_raw)

    return (g1_b1, g2_b1), (g1_b2, g2_b2)

def load_gacha_teleporters():
    """Load per-gacha crop plot teleporters from gacha_sets.json for each box."""
    cfg_path = os.path.join(os.path.dirname(__file__), "..", "config", "gacha_sets.json")
    with open(cfg_path, "r") as f:
        data = json.load(f)
    sets = data.get("gacha_sets", [])
    if not sets:
        raise RuntimeError("No gacha_sets found in config/gacha_sets.json")
    # For each box, get tp_plots_gacha1 and tp_plots_gacha2
    teleporters = []
    for box in sets:
        tp1 = box.get("tp_plots_gacha1")
        tp2 = box.get("tp_plots_gacha2")
        teleporters.append((tp1, tp2))
    return teleporters

def load_crop_plot_targets():
    """Load the 24 crop plot look targets; returns list of dicts with view_direction and crouch.
    The script uses only view_direction for looking at plots, GetTrapsTask will call `take_item('trap')`.
    """
    cfg_path = os.path.join(os.path.dirname(__file__), "..", "config", "crop_plot_look_positions.json")
    with open(cfg_path, "r") as f:
        data = json.load(f)
    items = data.get("crop_plot_look_positions", [])
    if len(items) < 24:
        raise RuntimeError("Expected 24 crop plot look positions; found %d" % len(items))
    return items[:24]


def main():
    # Initialize bot environment
    bot_state = BotState()
    player_input = PlayerInput()
    inventory_manager = InventoryManager()
    # Wire shared BotState into InventoryManager so OCR recovery has context
    inventory_manager.bot_state = bot_state
    start_time = time.time()
    cycles_done = 0

    def end_procedure(reason: str = "Requested stop"):
        """Stop script immediately and print diagnostics."""
        elapsed = time.time() - start_time
        # Prepare readable state summary
        state_summary = {
            "current_task": bot_state.current_task,
            "position": bot_state.position,
            "view_direction": bot_state.view_direction,
            "is_crouching": bot_state.is_crouching,
        }
        print("\n===== BOT RUN SUMMARY =====")
        print(f"Reason: {reason}")
        print(f"Cycles completed: {cycles_done}")
        print(f"Total recoveries: {bot_state.recovery_count}")
        print(f"Total restarts signaled: {bot_state.recovery_restarts}")
        print(f"Elapsed: {datetime.timedelta(seconds=int(elapsed))}")
        print(f"State: {state_summary}")
        print("==========================\n")
        # Ensure output is flushed before hard exit
        try:
            sys.stdout.flush()
            sys.stderr.flush()
        except Exception:
            pass
        # Immediate process termination (affects all threads)
        os._exit(0)

    # Global F1 watcher running in background to allow stop at any time
    if KEYBOARD_AVAILABLE:
        import threading
        def _f1_watcher():
            while True:
                try:
                    if keyboard.is_pressed('f1'):
                        end_procedure("F1 pressed")
                    time.sleep(0.05)
                except SystemExit:
                    # Process will exit via os._exit; ignore in watcher
                    pass
                except Exception:
                    # If keyboard fails, stop watcher silently
                    break
        watcher_thread = threading.Thread(target=_f1_watcher, daemon=True)
        watcher_thread.start()
    # Calibrate current view first so bot_state.view_direction is accuratef
    print("Calibrating current view. Bring ARK to foreground; sending 'ccc' in 2s...")
    time.sleep(2)
    player_input.calibrate_current_view(bot_state)

    # Build crop plots list in the shape GetTrapsTask expects: position optional, view_direction required
    plots = []
    for item in load_crop_plot_targets():
        plots.append({
            # position is optional per-plot; we already teleported to the area teleporter
            "view_direction": item.get("view_direction"),
            "crouch": bool(item.get("crouch", False)),  
        })

    # Load gacha view directions (per box)
    (g1_view_b1, g2_view_b1), (g1_view_b2, g2_view_b2) = load_gacha_views()

    # traps -> feed gacha1 -> get traps -> feed gacha2
    cycles = 50  # adjust as needed
    teleporters = load_gacha_teleporters()
    # Also load box teleporter names from gacha_sets.json
    cfg_path = os.path.join(os.path.dirname(__file__), "..", "config", "gacha_sets.json")
    with open(cfg_path, "r") as f:
        data = json.load(f)
    sets = data.get("gacha_sets", [])
    box_teleporters = [box.get("tp_box") for box in sets]
    try:
        for _ in range(cycles):
            # Iterate over each box in gacha_sets.json
            for idx, ((tp_plots_gacha1, tp_plots_gacha2), box_tp) in enumerate(zip(teleporters, box_teleporters)):
                # Select per-box gacha views
                if idx == 0:
                    g1_view, g2_view = g1_view_b1, g2_view_b1
                else:
                    g1_view = g1_view_b2 or g1_view_b1
                    g2_view = g2_view_b2 or g2_view_b1
                # Collect traps for gacha1 using tp_plots_gacha1
                player_input.teleport_to(tp_plots_gacha1, bot_state)
                try:
                    traps_task = GetTrapsTask(bot_state, player_input, inventory_manager, crop_plots=plots, indices=range(0, 24))
                    traps_task.run()
                except RestartTask:
                    if bot_state.restart_requested:
                        print("Driver: restarting GetTrapsTask after recovery")
                        bot_state.restart_requested = False
                        traps_task.run()
                # Feed gacha1
                try:
                    feed1 = FeedGachaTask(bot_state, player_input, inventory_manager, teleporter=box_tp, gacha_view_direction=g1_view)
                    feed1.run()
                except RestartTask:
                    if bot_state.restart_requested:
                        print("Driver: restarting FeedGachaTask(gacha1) after recovery")
                        bot_state.restart_requested = False
                        feed1.run()

                # Collect traps for gacha2 using tp_plots_gacha2
                player_input.teleport_to(tp_plots_gacha2, bot_state)
                try:
                    traps_task2 = GetTrapsTask(bot_state, player_input, inventory_manager, crop_plots=plots, indices=range(0, 24))
                    traps_task2.run()
                except RestartTask:
                    if bot_state.restart_requested:
                        print("Driver: restarting GetTrapsTask(second) after recovery")
                        bot_state.restart_requested = False
                        traps_task2.run()
                # Feed gacha2
                try:
                    feed2 = FeedGachaTask(bot_state, player_input, inventory_manager, teleporter=box_tp, gacha_view_direction=g2_view)
                    feed2.run()
                except RestartTask:
                    if bot_state.restart_requested:
                        print("Driver: restarting FeedGachaTask(gacha2) after recovery")
                        bot_state.restart_requested = False
                        feed2.run()
            cycles_done += 1
        end_procedure("Completed requested cycles")
    except KeyboardInterrupt:
        end_procedure("KeyboardInterrupt")
    except SystemExit:
        raise
    except Exception as e:
        end_procedure(f"Unhandled error: {e}")


if __name__ == "__main__":
    main()
