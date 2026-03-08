

import threading, time, os, sys, json, datetime, pyautogui, openpyxl
try:
    import keyboard
    KEYBOARD_AVAILABLE = True
except Exception:
    KEYBOARD_AVAILABLE = False

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from bot.base import BotState, PlayerInput, InventoryManager, RestartTask, info, warn
from bot.tasks import CollectAndCrackAllGachasTask, FeedAllGachasMajorTask



def watcher_stop_event(stop_event):
    if not KEYBOARD_AVAILABLE: return
    def _instant_exit():
        print("F1 pressed: immediate cancellation.")
        stop_event.set()
        os._exit(0)
    try:
        keyboard.add_hotkey('F1', _instant_exit)
        while not stop_event.is_set(): time.sleep(0.1)
    finally:
        try: keyboard.clear_all_hotkeys()
        except Exception: pass

def load_gacha_boxes(player_input):
    cfg = player_input.load_json('gacha_sets.json')
    sets = cfg.get('gacha_sets', [])
    def extract_view(raw):
        if raw is None: return None
        if isinstance(raw, (list, tuple)) and len(raw) == 2:
            return (float(raw[0]), float(raw[1]))
        if isinstance(raw, dict) and 'yaw' in raw and 'pitch' in raw:
            return (float(raw['yaw']), float(raw['pitch']))
        return None
    boxes = []
    for gset in sets:
        tp_box = gset.get('tp_box') or gset.get('teleporter') or ''
        pego_view = extract_view(gset.get('pego_view_direction'))
        gacha1_view = extract_view(gset.get('gacha1_view_direction'))
        gacha2_view = extract_view(gset.get('gacha2_view_direction'))
        if tp_box and (gacha1_view or gacha2_view):
            boxes.append({
                'name': gset.get('name') or 'unnamed_set',
                'tp_box': tp_box,
                'pego_view_direction': pego_view,
                'gacha1_view_direction': gacha1_view,
                'gacha2_view_direction': gacha2_view
            })
    return boxes

def load_grinder_info(player_input):
    grinder_view = (
        player_input.get_calibration_view_direction('grinder') or
        player_input.get_calibration_view_direction('grinder_view')
    )
    grinder_tp = 'grinder'
    if hasattr(player_input, 'teleporters') and 'grinder' not in player_input.teleporters:
        grinder_tp = player_input.teleporter_render
    return grinder_tp, grinder_view

def drop_all(inv):
    try:
        inv.open_own_inv(); inv.drop_all()
    finally:
        inv.close_inv()

def feed_player():
    pyautogui.press('2')
    time.sleep(0.5)
    pyautogui.press('3')
    time.sleep(0.5)

def run_with_retries(task, max_attempts=5, warn_prefix=None):
    attempt = 0
    while attempt < max_attempts:
        try:
            task()
            return
        except RestartTask as rt:
            attempt += 1
            if warn_prefix:
                warn(f"{warn_prefix} restart signaled: {rt}; will retry (attempt {attempt}/{max_attempts}).")
            if attempt >= max_attempts:
                warn(f"{warn_prefix}: reached max attempts; proceeding to next phase.")

def main():
    bot_state = BotState()
    player_input = PlayerInput()
    inv = InventoryManager()
    inv.bot_state = bot_state

    stop_event = threading.Event()
    t = threading.Thread(target=watcher_stop_event, args=(stop_event,), daemon=True)
    t.start()

    # Load gacha boxes and grinder info
    boxes = load_gacha_boxes(player_input)
    grinder_tp, grinder_view = load_grinder_info(player_input)
    if grinder_view is None or not boxes:
        warn('Grinder view or gacha boxes not configured; aborting.')
        return

    # Split boxes into 1-6 and 7-12
    boxes_1_6 = boxes[:6]
    boxes_7_12 = boxes[6:12]

    # Prepare gacha_boxes lists for CollectAndCrackAllGachasTask (must have 'teleporter' and 'pego_view_direction')
    boxes_1_6_cc = [
        {'teleporter': b['tp_box'], 'pego_view_direction': b['pego_view_direction']}
        for b in boxes_1_6 if b.get('tp_box') and b.get('pego_view_direction') is not None
    ]
    boxes_7_12_cc = [
        {'teleporter': b['tp_box'], 'pego_view_direction': b['pego_view_direction']}
        for b in boxes_7_12 if b.get('tp_box') and b.get('pego_view_direction') is not None
    ]



    info("Calibrating current view. Bring ARK to foreground; sending 'ccc' in 3s...")
    time.sleep(3)
    player_input.wake_up(bot_state)

    num_cycles = 20

    for cycle in range(num_cycles):
        info(f"=== Split Bot Cycle {cycle+1}/{num_cycles} ===")

        # Feed all boxes
        info("=== FeedAllGachasMajorTask (all boxes) ===")
        bot_state.major_checkpoint_idx = 0
        bot_state.major_checkpoint_stage = None
        run_with_retries(lambda: FeedAllGachasMajorTask(bot_state, player_input, inv, boxes).run(), warn_prefix="FeedAllGachasMajorTask")

        drop_all(inv)

        # Collect and crack for boxes 1-6
        info("=== CollectAndCrackAllGachasTask (boxes 1-6) ===")
        bot_state.collect_checkpoint_idx = 0
        bot_state.collect_checkpoint_stage = None
        if boxes_1_6_cc:
            run_with_retries(lambda: CollectAndCrackAllGachasTask(
                bot_state, player_input, inv, boxes_1_6_cc, grinder_tp, grinder_view, per_box_collect_count=1, per_box_crack_count=1
            ).run(), warn_prefix="CollectAndCrackAllGachasTask (1-6)")
        else:
            warn("No boxes 1-6 found for collect and crack.")

        drop_all(inv)

        # Feed all boxes again
        info("=== FeedAllGachasMajorTask (all boxes, between cracks) ===")
        bot_state.major_checkpoint_idx = 0
        bot_state.major_checkpoint_stage = None
        run_with_retries(lambda: FeedAllGachasMajorTask(bot_state, player_input, inv, boxes).run(), warn_prefix="FeedAllGachasMajorTask (between cracks)")

        drop_all(inv)

        # Collect and crack for boxes 7-12
        info("=== CollectAndCrackAllGachasTask (boxes 7-12) ===")
        bot_state.collect_checkpoint_idx = 0
        bot_state.collect_checkpoint_stage = None
        if boxes_7_12_cc:
            run_with_retries(lambda: CollectAndCrackAllGachasTask(
                bot_state, player_input, inv, boxes_7_12_cc, grinder_tp, grinder_view, per_box_collect_count=1, per_box_crack_count=1
            ).run(), warn_prefix="CollectAndCrackAllGachasTask (7-12)")
        else:
            warn("No boxes 7-12 found for collect and crack.")


        drop_all(inv)
        feed_player()

        info(f"=== Finished split bot cycle {cycle+1}/{num_cycles} ===")
        

    t.join(timeout=1.0)
    info('Split bot run finished.')

if __name__ == '__main__':
    main()

