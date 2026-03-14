import time
from base import BotState, PlayerInput, InventoryManager
from tasks import CollectAndCrackAllGachasTask, FeedAllGachasMajorTask

def run_bot(selected, cycles=20, ui_callback=None, overlay_callback=None, start_with_crack=False, eat_twice=False):
    # F1 abort logic
    import threading
    try:
        import keyboard
        KEYBOARD_AVAILABLE = True
    except Exception:
        KEYBOARD_AVAILABLE = False

    stop_event = threading.Event()
    def watcher_stop_event(stop_event):
        if not KEYBOARD_AVAILABLE:
            return
        def _instant_exit():
            print("F1 pressed: immediate cancellation.")
            stop_event.set()
            os._exit(0)
        try:
            keyboard.add_hotkey('F1', _instant_exit)
            while not stop_event.is_set():
                time.sleep(0.1)
        finally:
            try:
                keyboard.clear_all_hotkeys()
            except Exception:
                pass
    watcher_thread = threading.Thread(target=watcher_stop_event, args=(stop_event,), daemon=True)
    watcher_thread.start()
    bot_state = BotState()
    player_input = PlayerInput()
    inventory = InventoryManager()
    inventory.bot_state = bot_state

    def drop_all(inv):
        try:
            inv.open_own_inv(); inv.drop_all()
        finally:
            inv.close_inv()

    def feed_player(eat_2_times=False):
        try:
            import pyautogui
        except ImportError:
            return
        if eat_2_times:
            pyautogui.press('4')
            time.sleep(0.5)
            pyautogui.press('5')
            time.sleep(0.5)
        else:
            pyautogui.press('2')
            time.sleep(0.5)
            pyautogui.press('3')
            time.sleep(0.5)

    def run_with_retries(task, max_attempts=5, warn_prefix=None, overlay_text=None):
        attempt = 0
        while attempt < max_attempts:
            try:
                if overlay_callback and overlay_text:
                    overlay_callback(overlay_text)
                task()
                return
            except Exception as rt:
                attempt += 1
                if warn_prefix:
                    print(f"{warn_prefix} restart signaled: {rt}; will retry (attempt {attempt}/{max_attempts}).")
                if attempt >= max_attempts:
                    print(f"{warn_prefix}: reached max attempts; proceeding to next phase.")

    # Load gacha boxes and grinder info (mimic run_bot_with_pause.py)
    import os, json
    def extract_view(raw):
        if raw is None: return None
        if isinstance(raw, (list, tuple)) and len(raw) == 2:
            return (float(raw[0]), float(raw[1]))
        if isinstance(raw, dict) and 'yaw' in raw and 'pitch' in raw:
            return (float(raw['yaw']), float(raw['pitch']))
        return None

    gacha_sets_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'config', 'gacha_sets.json'))
    with open(gacha_sets_path, 'r') as f:
        gacha_sets_cfg = json.load(f)
    sets = gacha_sets_cfg.get('gacha_sets', [])
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

    grinder_tp = 'grinder'
    grinder_view = None
    for gset in sets:
        if gset.get('grinder_teleporter'):
            grinder_tp = gset['grinder_teleporter']
        if gset.get('grinder_view_direction'):
            grinder_view = gset['grinder_view_direction']
    if grinder_view is None:
        grinder_view = [0, 0]

    if grinder_view is None or not boxes:
        print('Grinder view or gacha boxes not configured; aborting.')
        if ui_callback:
            ui_callback('error', 'Grinder view or gacha boxes not configured; aborting.')
        return

    boxes_1_6 = boxes[:6]
    boxes_7_12 = boxes[6:12]
    boxes_1_6_cc = [
        {'teleporter': b['tp_box'], 'pego_view_direction': b['pego_view_direction']}
        for b in boxes_1_6 if b.get('tp_box') and b.get('pego_view_direction') is not None
    ]
    boxes_7_12_cc = [
        {'teleporter': b['tp_box'], 'pego_view_direction': b['pego_view_direction']}
        for b in boxes_7_12 if b.get('tp_box') and b.get('pego_view_direction') is not None
    ]

    # Calibrate view (simulate)
    print("Calibrating current view. Bring ARK to foreground; sending 'ccc' in 3s...")
    time.sleep(3)
    if hasattr(player_input, 'wake_up'):
        player_input.wake_up(bot_state)

    cycle = 0
    while True:
        if stop_event.is_set():
            print("Abort signal received. Exiting bot loop.")
            break
        cycle += 1
        if cycles != 0 and cycle > cycles:
            break
        print(f"=== Split Bot Cycle {cycle}{f'/{cycles}' if cycles != 0 else ''} ===")

        skip_feed = start_with_crack and cycle == 1

        if 'feed' in selected and not skip_feed:
            print("=== FeedAllGachasMajorTask (all boxes) ===")
            bot_state.major_checkpoint_idx = 0
            bot_state.major_checkpoint_stage = None
            run_with_retries(
                lambda: FeedAllGachasMajorTask(bot_state, player_input, inventory, boxes, overlay_callback=overlay_callback).run(),
                warn_prefix="FeedAllGachasMajorTask",
                overlay_text=None
            )

        drop_all(inventory)

        if stop_event.is_set():
            print("Abort signal received. Exiting bot loop.")
            break

        if 'crack' in selected:
            print("=== CollectAndCrackAllGachasTask (boxes 1-6) ===")
            bot_state.collect_checkpoint_idx = 0
            bot_state.collect_checkpoint_stage = None
            if boxes_1_6_cc:
                run_with_retries(
                    lambda: CollectAndCrackAllGachasTask(
                        bot_state, player_input, inventory, boxes_1_6_cc, grinder_tp, grinder_view, per_box_collect_count=1, per_box_crack_count=1, idx_shift=0
                    ).run(),
                    warn_prefix="CollectAndCrackAllGachasTask (1-6)",
                    overlay_text="Cracking crystals (boxes 1-6)..."
                )
            else:
                print("No boxes 1-6 found for collect and crack.")

        drop_all(inventory)
        feed_player(eat_2_times=eat_twice)


        if stop_event.is_set():
            print("Abort signal received. Exiting bot loop.")
            break

        if 'feed' in selected and not skip_feed:
            print("=== FeedAllGachasMajorTask (all boxes, between cracks) ===")
            bot_state.major_checkpoint_idx = 0
            bot_state.major_checkpoint_stage = None
            run_with_retries(
                lambda: FeedAllGachasMajorTask(bot_state, player_input, inventory, boxes, overlay_callback=overlay_callback).run(),
                warn_prefix="FeedAllGachasMajorTask (between cracks)",
                overlay_text=None
            )

        drop_all(inventory)

        if stop_event.is_set():
            print("Abort signal received. Exiting bot loop.")
            break

        if 'crack' in selected:
            print("=== CollectAndCrackAllGachasTask (boxes 7-12) ===")
            bot_state.collect_checkpoint_idx = 0
            bot_state.collect_checkpoint_stage = None
            if boxes_7_12_cc:
                run_with_retries(
                    lambda: CollectAndCrackAllGachasTask(
                        bot_state, player_input, inventory, boxes_7_12_cc, grinder_tp, grinder_view, per_box_collect_count=1, per_box_crack_count=1, idx_shift=6
                    ).run(),
                    warn_prefix="CollectAndCrackAllGachasTask (7-12)",
                    overlay_text="Cracking crystals (boxes 7-12)..."
                )
            else:
                print("No boxes 7-12 found for collect and crack.")

        drop_all(inventory)
        feed_player()

        print(f"=== Finished split bot cycle {cycle}{f'/{cycles}' if cycles != 0 else ''} ===")

    if ui_callback:
        ui_callback('done', 'Selected tasks completed.')
