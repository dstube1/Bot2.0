import threading
import time
import os
import sys

try:
    import keyboard  # for global hotkey
except Exception:
    keyboard = None

# Import bot components
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from bot.base import BotState, PlayerInput, InventoryManager, RestartTask
from bot.tasks import CollectCrystalsTask, CrackCrystalsTask, SortLootAndGrindTask, CollectAndCrackAllGachasTask


def watcher_stop_event(stop_event):
    """Watch for F1 key and immediately terminate process."""
    if keyboard is None:
        return
    def _instant_exit():
        print("F1 pressed: immediate cancellation.")
        try:
            stop_event.set()
        except Exception:
            pass
        # Hard exit to guarantee immediate stop
        os._exit(0)  # pylint: disable=protected-access
    try:
        keyboard.add_hotkey('F1', _instant_exit)
        while not stop_event.is_set():
            time.sleep(0.1)
    finally:
        try:
            keyboard.clear_all_hotkeys()
        except Exception:
            pass


def load_gacha_boxes(player_input):
    """Load gacha box entries from config/gacha_sets.json.

    Supports both new pego view keys (pego1_view_direction / pego2_view_direction)
    and legacy keys (gacha1_view_direction / gacha2_view_direction).

    Each entry returned: {
        'teleporter': <tp_box or teleporter name>,
        'pego_view_direction': (yaw, pitch)
    }
    """
    cfg = player_input.load_json('gacha_sets.json')
    sets = cfg.get('gacha_sets', [])
    boxes = []
    for gset in sets:
        name = gset.get('name') or 'unnamed_set'
        tp_box = gset.get('tp_box') or gset.get('teleporter') or ''
        # Normalize view extraction helper
        def extract_view(raw):
            if raw is None:
                return None
            if isinstance(raw, (list, tuple)) and len(raw) == 2:
                return (float(raw[0]), float(raw[1]))
            if isinstance(raw, dict) and 'yaw' in raw and 'pitch' in raw:
                return (float(raw['yaw']), float(raw['pitch']))
            return None
        # Only use pego view directions for collection; do NOT fallback to gacha views
        v1 = extract_view(gset.get('pego1_view_direction'))
        v2 = extract_view(gset.get('pego2_view_direction'))
        if tp_box and v1:
            boxes.append({'name': f"{name}:pego1", 'teleporter': tp_box, 'pego_view_direction': v1})
        if tp_box and v2:
            boxes.append({'name': f"{name}:pego2", 'teleporter': tp_box, 'pego_view_direction': v2})
    return boxes


def load_grinder_info(player_input):
    """Load grinder teleporter and view direction from look_positions.json.

    Expects a calibration named 'grinder' or fallback to 'grinder_view'.
    """
    grinder_view = (
        player_input.get_calibration_view_direction('grinder') or
        player_input.get_calibration_view_direction('grinder_view')
    )
    # Teleporter name for grinder area from teleporter.json, prefer 'grinder' else 'render'
    grinder_tp = 'grinder'
    if hasattr(player_input, 'teleporters') and 'grinder' not in player_input.teleporters:
        grinder_tp = player_input.teleporter_render
    return grinder_tp, grinder_view

def load_loot_storage(player_input, grinder_tp):
    """Loot storage is at grinder TP and uses 'poly_vault' view.

    Returns the grinder teleporter and the calibration view for 'poly_vault'.
    """ 
    loot_tp = grinder_tp
    loot_view = player_input.get_calibration_view_direction('poly_vault')
    return loot_tp, loot_view


def main():
    bot_state = BotState()
    player_input = PlayerInput()
    inv = InventoryManager()
    inv.bot_state = bot_state

    # F1 cancel watcher
    stop_event = threading.Event()
    t = threading.Thread(target=watcher_stop_event, args=(stop_event,), daemon=True)
    t.start()

    # Load gacha boxes and grinder info
    boxes = load_gacha_boxes(player_input)
    grinder_tp, grinder_view = load_grinder_info(player_input)
    loot_tp, loot_view = load_loot_storage(player_input, grinder_tp)
    if grinder_view is None:
        print('Grinder view not configured; please calibrate grinder in look_positions.json')
        return

    print(f"Loaded {len(boxes)} gacha box entries; grinder='{grinder_tp}', view={grinder_view}")
    if not boxes:
        print("No gacha boxes found. Ensure gacha_sets.json has 'gacha_sets' entries with 'tp_box' and pego/gacha view directions.")
        print("Example entry: {\n  'name': 'box_1',\n  'tp_box': 'yourTeleporterName',\n  'pego1_view_direction': [yaw, pitch]\n}")

    print("Calibrating current view. Bring ARK to foreground; sending 'ccc' in 3s...")
    time.sleep(3)
    player_input.calibrate_current_view(bot_state)

    # High-level combined workflow: collect & crack all gachas, then loot+grind sort
    try:
        if stop_event.is_set():
            print('Cancelled before start by F1')
            return
        # Build gacha_boxes in expected structure for CollectAndCrackAllGachasTask
        gacha_boxes = [
            { 'teleporter': b.get('teleporter'), 'pego_view_direction': b.get('pego_view_direction') }
            for b in boxes if b.get('teleporter') and b.get('pego_view_direction') is not None
        ]
        if not gacha_boxes:
            print('No valid gacha boxes to process; aborting.')
        else:
            print(f"Starting CollectAndCrackAllGachasTask for {len(gacha_boxes)} boxes, 5 times...")
            for i in range(5):
                print(f"--- Run {i+1}/5 ---")
                task = CollectAndCrackAllGachasTask(
                    bot_state,
                    player_input,
                    inv,
                    gacha_boxes,
                    grinder_tp,
                    grinder_view,
                    per_box_collect_count=1,
                    per_box_crack_count=1
                )
                try:
                    task.run()
                except RestartTask as rt:
                    print(f"Global restart signaled: {rt}; re-running task once...")
                    task.run()
        # SortLootAndGrindTask now invoked inside CollectAndCrackAllGachasTask; no external call needed.
    finally:
        stop_event.set()
        try:
            t.join(timeout=1.0)
        except Exception:
            pass
        print('Full test finished.')


if __name__ == '__main__':
    main()
