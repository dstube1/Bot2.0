import sys
import threading
import time

# Ensure project can be imported when running directly
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from bot.base import BotState, PlayerInput, InventoryManager, RestartTask, info, warn
from bot.tasks import SortLootAndGrindTask

# Optional F1 abort via `keyboard` package; falls back gracefully if not available
def start_abort_listener():
    try:
        import keyboard  # pip install keyboard
    except Exception:
        warn("F1 abort disabled: 'keyboard' package not available. Install with 'pip install keyboard'.")
        return None

    def _listen():
        info("Press F1 at any time to abort the test script.")
        keyboard.wait('F1')
        warn("F1 pressed – aborting test script.")
        os._exit(0)
    t = threading.Thread(target=_listen, daemon=True)
    t.start()
    return t


def main():
    info("Starting sort_resources_from_grinding test...")
    time.sleep(3)
    # Minimal stubs – relies on your existing PlayerInput calibration/config files
    bot_state = BotState()
    player_input = PlayerInput()
    inventory_manager = InventoryManager()

    # Begin listening for F1 abort in background
    start_abort_listener()
    player_input.calibrate_current_view(bot_state)
    task = SortLootAndGrindTask(
        bot_state=bot_state,
        player_input=player_input,
        inventory_manager=inventory_manager,
    )
    try:
        # Directly invoke the method under test
        task.sort_resources_from_grinding()
        info("sort_resources_from_grinding completed.")
    except RestartTask as rt:
        warn(f"sort_resources_from_grinding requested restart: {rt}")
    except Exception as e:
        warn(f"Test encountered an error: {e}")

    # Keep process alive briefly to allow F1 abort (optional)
    time.sleep(1)


if __name__ == '__main__':
    main()
