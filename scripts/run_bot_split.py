
import threading
import time
import os
import sys
import json
import datetime
import pyautogui
import openpyxl
try:
    import keyboard
    KEYBOARD_AVAILABLE = True
except Exception:
    KEYBOARD_AVAILABLE = False

# --- Runtime Tracker ---
RUNTIME_LOG = []
SCRIPT_START_TS = datetime.datetime.now()
SCRIPT_END_TS = None
def log_runtime(event, cycle=None, run=None):
    ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    RUNTIME_LOG.append({
        'timestamp': ts,
        'event': event,
        'cycle': cycle,
        'run': run
    })
def save_runtime_log():
    global SCRIPT_START_TS, SCRIPT_END_TS
    logs_dir = os.path.join(os.path.dirname(__file__), '..', 'logs')
    os.makedirs(logs_dir, exist_ok=True)
    xlsx_path = os.path.join(logs_dir, 'runtime.xlsx')
    # Create or load workbook
    if os.path.exists(xlsx_path):
        wb = openpyxl.load_workbook(xlsx_path)
        ws = wb.active
    else:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(['ScriptStart', 'ScriptEnd', 'Event', 'Cycle', 'Run', 'Timestamp'])
    for entry in RUNTIME_LOG:
        ws.append([
            SCRIPT_START_TS.strftime('%Y-%m-%d %H:%M:%S'),
            SCRIPT_END_TS.strftime('%Y-%m-%d %H:%M:%S') if SCRIPT_END_TS else '',
            entry['event'],
            entry['cycle'] if entry['cycle'] is not None else '',
            entry['run'] if entry['run'] is not None else '',
            entry['timestamp']
        ])
    wb.save(xlsx_path)

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from bot.base import BotState, PlayerInput, InventoryManager, RestartTask, info, debug, warn, error
from bot.tasks import CollectAndCrackAllGachasTask, FeedAllGachasMajorTask

def watcher_stop_event(stop_event):
    if not KEYBOARD_AVAILABLE:
        return
    def _instant_exit():
        global SCRIPT_END_TS
        print("F1 pressed: immediate cancellation.")
        try:
            stop_event.set()
        except Exception:
            pass
        SCRIPT_END_TS = datetime.datetime.now()
        log_runtime('script_end')
        save_runtime_log()
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

def load_gacha_boxes(player_input):
    cfg = player_input.load_json('gacha_sets.json')
    sets = cfg.get('gacha_sets', [])
    boxes = []
    def extract_view(raw):
        if raw is None:
            return None
        if isinstance(raw, (list, tuple)) and len(raw) == 2:
            return (float(raw[0]), float(raw[1]))
        if isinstance(raw, dict) and 'yaw' in raw and 'pitch' in raw:
            return (float(raw['yaw']), float(raw['pitch']))
        return None
    for gset in sets:
        name = gset.get('name') or 'unnamed_set'
        tp_box = gset.get('tp_box') or gset.get('teleporter') or ''
        pego_view = extract_view(gset.get('pego_view_direction'))
        gacha1_view = extract_view(gset.get('gacha1_view_direction'))
        gacha2_view = extract_view(gset.get('gacha2_view_direction'))
        if tp_box and (gacha1_view or gacha2_view):
            boxes.append({
                'name': f"{name}",
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

def main():
    bot_state = BotState()
    player_input = PlayerInput()
    inv = InventoryManager()
    inv.bot_state = bot_state


    stop_event = threading.Event()
    t = threading.Thread(target=watcher_stop_event, args=(stop_event,), daemon=True)
    t.start()

    info("Calibrating current view. Bring ARK to foreground; sending 'ccc' in 3s...")
    time.sleep(3)
    player_input.calibrate_current_view(bot_state)

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

    log_runtime('script_start')

    num_cycles = 20
    try:
        if len(sys.argv) > 1:
            num_cycles = int(sys.argv[1])
    except Exception:
        warn("Invalid cycle count argument; defaulting to 1.")

    for cycle in range(num_cycles):
        info(f"=== Split Bot Cycle {cycle+1}/{num_cycles} ===")
        log_runtime('split_cycle_start', cycle=cycle+1)

        # Feed all boxes
        info("=== FeedAllGachasMajorTask (all boxes) ===")
        log_runtime('feedallgachas_start', cycle=cycle+1)
        bot_state.major_checkpoint_idx = 0
        bot_state.major_checkpoint_stage = None
        max_attempts = 5
        attempt = 0
        while attempt < max_attempts:
            try:
                FeedAllGachasMajorTask(bot_state, player_input, inv, boxes).run()
                break
            except RestartTask as rt:
                attempt += 1
                warn(f"FeedAllGachasMajorTask restart signaled: {rt}; will retry (attempt {attempt}/{max_attempts}).")
                if attempt >= max_attempts:
                    warn("FeedAllGachasMajorTask: reached max attempts; proceeding to next phase.")
        log_runtime('feedallgachas_end', cycle=cycle+1)

        try:
            inv.open_own_inv()
            inv.drop_all()
        finally:
            inv.close_inv()

        # Collect and crack for boxes 1-6
        info("=== CollectAndCrackAllGachasTask (boxes 1-6) ===")
        log_runtime('collectcrack_1_6_start', cycle=cycle+1)
        bot_state.collect_checkpoint_idx = 0
        bot_state.collect_checkpoint_stage = None
        if boxes_1_6_cc:
            task1 = CollectAndCrackAllGachasTask(
                bot_state,
                player_input,
                inv,
                boxes_1_6_cc,
                grinder_tp,
                grinder_view,
                per_box_collect_count=1,
                per_box_crack_count=1
            )
            max_attempts = 5
            attempt = 0
            while attempt < max_attempts:
                try:
                    task1.run()
                    break
                except RestartTask as rt:
                    attempt += 1
                    warn(f"CollectAndCrackAllGachasTask (1-6) restart signaled: {rt}; will retry (attempt {attempt}/{max_attempts}).")
                    if attempt >= max_attempts:
                        warn("CollectAndCrackAllGachasTask (1-6): reached max attempts; proceeding to next phase.")
        else:
            warn("No boxes 1-6 found for collect and crack.")
        log_runtime('collectcrack_1_6_end', cycle=cycle+1)

        # Feed all boxes again
        info("=== FeedAllGachasMajorTask (all boxes, between cracks) ===")
        log_runtime('feedallgachas_between_start', cycle=cycle+1)
        bot_state.major_checkpoint_idx = 0
        bot_state.major_checkpoint_stage = None
        max_attempts = 5
        attempt = 0
        while attempt < max_attempts:
            try:
                FeedAllGachasMajorTask(bot_state, player_input, inv, boxes).run()
                break
            except RestartTask as rt:
                attempt += 1
                warn(f"FeedAllGachasMajorTask (between cracks) restart signaled: {rt}; will retry (attempt {attempt}/{max_attempts}).")
                if attempt >= max_attempts:
                    warn("FeedAllGachasMajorTask (between cracks): reached max attempts; proceeding to next phase.")
        log_runtime('feedallgachas_between_end', cycle=cycle+1)

        try:
            inv.open_own_inv()
            inv.drop_all()
        finally:
            inv.close_inv()
            
        # Collect and crack for boxes 7-12
        info("=== CollectAndCrackAllGachasTask (boxes 7-12) ===")
        log_runtime('collectcrack_7_12_start', cycle=cycle+1)
        bot_state.collect_checkpoint_idx = 0
        bot_state.collect_checkpoint_stage = None
        if boxes_7_12_cc:
            task2 = CollectAndCrackAllGachasTask(
                bot_state,
                player_input,
                inv,
                boxes_7_12_cc,
                grinder_tp,
                grinder_view,
                per_box_collect_count=1,
                per_box_crack_count=1
            )
            max_attempts = 5
            attempt = 0
            while attempt < max_attempts:
                try:
                    task2.run()
                    break
                except RestartTask as rt:
                    attempt += 1
                    warn(f"CollectAndCrackAllGachasTask (7-12) restart signaled: {rt}; will retry (attempt {attempt}/{max_attempts}).")
                    if attempt >= max_attempts:
                        warn("CollectAndCrackAllGachasTask (7-12): reached max attempts; proceeding to next phase.")
        else:
            warn("No boxes 7-12 found for collect and crack.")
        log_runtime('collectcrack_7_12_end', cycle=cycle+1)

        info(f"=== Finished split bot cycle {cycle+1}/{num_cycles} ===")
        pyautogui.press('2')
        time.sleep(0.5)
        pyautogui.press('3')
        time.sleep(0.5)
        log_runtime('split_cycle_end', cycle=cycle+1)

    t.join(timeout=1.0)
    global SCRIPT_END_TS
    SCRIPT_END_TS = datetime.datetime.now()
    log_runtime('script_end')
    save_runtime_log()
    info('Split bot run finished.')

if __name__ == '__main__':
    main()
