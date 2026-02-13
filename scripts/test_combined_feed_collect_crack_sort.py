import threading
import time
import os
import sys
import json
import datetime
try:
    import keyboard  # for global hotkey
    KEYBOARD_AVAILABLE = True
except Exception:
    KEYBOARD_AVAILABLE = False

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from bot.base import BotState, PlayerInput, InventoryManager, RestartTask, info, debug, warn, error
from bot.tasks import GetTrapsTask, FeedGachaTask, CollectCrystalsTask, CrackCrystalsTask, SortLootAndGrindTask, CollectAndCrackAllGachasTask, FeedAllGachasMajorTask

def watcher_stop_event(stop_event):
    if not KEYBOARD_AVAILABLE:
        return
    def _instant_exit():
        print("F1 pressed: immediate cancellation.")
        try:
            stop_event.set()
        except Exception:
            pass
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
def setup():
    bot_state = BotState()
    player_input = PlayerInput()
    inv = InventoryManager()
    inv.bot_state = bot_state

    t = threading.Thread(target=watcher_stop_event, args=(threading.Event(),), daemon=True)
    t.start()

    info("Calibrating current view. Bring ARK to foreground; sending 'ccc' in 3s...")
    time.sleep(3)
    player_input.calibrate_current_view(bot_state)

    # Load gacha_sets.json once here
    cfg_path = os.path.join(os.path.dirname(__file__), "..", "config", "gacha_sets.json")
    with open(cfg_path, "r") as f:
        gacha_cfg = json.load(f)
    gacha_sets_raw = gacha_cfg.get("gacha_sets", [])
    # Log pego view directions for all boxes loaded from config
    info(f"Found {len(gacha_sets_raw)} gacha boxes in gacha_sets.json")
    for gs in gacha_sets_raw:
        name = gs.get("name") or "unnamed_set"
        tp = gs.get("tp_box") or gs.get("teleporter") or ""
        pv = gs.get("pego_view_direction")
        if isinstance(pv, dict) and "yaw" in pv and "pitch" in pv:
            info(f"Box '{name}' tp='{tp}' pego_view_direction: yaw={pv['yaw']}, pitch={pv['pitch']}")
        elif isinstance(pv, (list, tuple)) and len(pv) == 2:
            info(f"Box '{name}' tp='{tp}' pego_view_direction: yaw={pv[0]}, pitch={pv[1]}")
        else:
            warn(f"Box '{name}' tp='{tp}' missing pego_view_direction")

    # Load crop plots
    crop_plot_path = os.path.join(os.path.dirname(__file__), "..", "config", "crop_plot_look_positions.json")
    with open(crop_plot_path, "r") as f:
        crop_plot_cfg = json.load(f)
    crop_plots = crop_plot_cfg.get("crop_plot_look_positions", [])

    # Restructure gacha_sets to inject crop_plots and gacha1/gacha2 objects
    gacha_sets = []
    for gset in gacha_sets_raw:
        new_set = dict(gset)
        new_set["crop_plots"] = crop_plots[:24]
        g1_tp = gset.get("tp_box")
        g1_view = gset.get("gacha1_view_direction")
        if g1_tp and g1_view:
            new_set["gacha1"] = {"teleporter": g1_tp, "view_direction": g1_view}
        g2_tp = gset.get("tp_box")
        g2_view = gset.get("gacha2_view_direction")
        if g2_tp and g2_view:
            new_set["gacha2"] = {"teleporter": g2_tp, "view_direction": g2_view}
        gacha_sets.append(new_set)

    boxes = load_gacha_boxes(player_input)
    grinder_tp, grinder_view = load_grinder_info(player_input)
    if grinder_view is None:
        warn('Grinder view not configured; please calibrate grinder in look_positions.json')
        t.join(timeout=1.0)
        debug('Full combined test finished.')
        return bot_state, player_input, inv, t, gacha_sets, None, None, None

    debug(f"Loaded {len(boxes)} gacha box entries; grinder='{grinder_tp}', view={grinder_view}")
    if not boxes:
        warn("No gacha boxes found. Ensure gacha_sets.json has 'gacha_sets' entries with 'tp_box' and pego/gacha view directions.")
        info("Example entry: {\n  'name': 'box_1',\n  'tp_box': 'yourTeleporterName',\n  'pego1_view_direction': [yaw, pitch]\n}")
        t.join(timeout=1.0)
        debug('Full combined test finished.')
        return bot_state, player_input, inv, t, gacha_sets, None, None, None

    gacha_boxes = [
        { 'teleporter': b.get('teleporter'), 'pego_view_direction': b.get('pego_view_direction') }
        for b in boxes if b.get('teleporter') and b.get('pego_view_direction') is not None
    ]
    if not gacha_boxes:
        warn('No valid gacha boxes to process; aborting.')
        t.join(timeout=1.0)
        debug('Full combined test finished.')
        return bot_state, player_input, inv, t, gacha_sets, None, None, None

    return bot_state, player_input, inv, t, gacha_sets, gacha_boxes, grinder_tp, grinder_view


# --- Helper functions moved to module level ---
def load_gacha_boxes(player_input):
    cfg = player_input.load_json('gacha_sets.json')
    sets = cfg.get('gacha_sets', [])
    boxes = []
    for gset in sets:
        name = gset.get('name') or 'unnamed_set'
        tp_box = gset.get('tp_box') or gset.get('teleporter') or ''
        def extract_view(raw):
            if raw is None:
                return None
            if isinstance(raw, (list, tuple)) and len(raw) == 2:
                return (float(raw[0]), float(raw[1]))
            if isinstance(raw, dict) and 'yaw' in raw and 'pitch' in raw:
                return (float(raw['yaw']), float(raw['pitch']))
            return None
        # Only use the generic pego_view_direction per box
        chosen_view = extract_view(gset.get('pego_view_direction'))
        if tp_box and chosen_view:
            boxes.append({'name': f"{name}", 'teleporter': tp_box, 'pego_view_direction': chosen_view})
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
    bot_state, player_input, inv, t, gacha_sets, gacha_boxes, grinder_tp, grinder_view = setup()

    # --- FEED GACHAS PHASE ---
    if not gacha_sets or not gacha_boxes or grinder_tp is None or grinder_view is None:
        warn("No gacha sets/boxes or grinder info available; aborting.")
        return

    total_cycles = 20
    feeds_per_cycle = 2
    for cycle in range(total_cycles):
        info(f"=== Procedure Cycle {cycle+1}/{total_cycles} ===")
        # Feed All 3 times per cycle
        for feed_run in range(feeds_per_cycle):
            info(f"Starting FeedAllGachasMajorTask run {feed_run+1}/{feeds_per_cycle} for {len(gacha_sets)} sets...")
            # Reset major-task checkpoints at the start of each feed run
            bot_state.major_checkpoint_idx = 0
            bot_state.major_checkpoint_stage = None
            max_attempts = 5
            attempt = 0
            while attempt < max_attempts:
                info(f"--- FeedAllGachasMajorTask Attempt {attempt+1}/{max_attempts} ---")
                try:
                    FeedAllGachasMajorTask(bot_state, player_input, inv, gacha_sets).run()
                    break
                except RestartTask as rt:
                    attempt += 1
                    warn(f"FeedAllGachasMajorTask restart signaled: {rt}; will retry (attempt {attempt}/{max_attempts}).")
                    if attempt >= max_attempts:
                        warn("FeedAllGachasMajorTask: reached max attempts; proceeding to next run.")
            info(f"Completed FeedAllGachasMajorTask run {feed_run+1}/{feeds_per_cycle}.")
        # Ensure player inventory is empty before collect/crack phase
        try:
            inv.open_own_inv()
            inv.drop_all()
        finally:
            inv.close_inv()
        # Optional: go to bed between phases to settle state (requires bot_state)
        #try:
        #    player_input.go_to_bed(bot_state)
        #    time.sleep(20)
        #    player_input.wake_up(bot_state, settle_seconds=0.7)
        #except Exception:
        #    pass

        info(f"Starting CollectAndCrackAllGachasTask for {len(gacha_boxes)} boxes...")

        # Reset collect/crack checkpoints at the start of each collect+crack phase
        bot_state.collect_checkpoint_idx = 0
        bot_state.collect_checkpoint_stage = None

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
        # Collect+Crack once per cycle, with capped retries
        max_attempts = 5
        attempt = 0
        while attempt < max_attempts:
            info(f"--- CollectAndCrackAllGachasTask Attempt {attempt+1}/{max_attempts} ---")
            try:
                task.run()
                break
            except RestartTask as rt:
                attempt += 1
                warn(f"CollectAndCrackAllGachasTask restart signaled: {rt}; will retry (attempt {attempt}/{max_attempts}).")
                if attempt >= max_attempts:
                    warn("CollectAndCrackAllGachasTask: reached max attempts; ending phase for this cycle.")
                    break
                # Log current resume checkpoint before retrying
                try:
                    warn(f"Resume checkpoint idx={bot_state.collect_checkpoint_idx}, stage={bot_state.collect_checkpoint_stage}")
                except Exception:
                    pass
                # Before retrying, ensure any crystals currently in inventory get cracked
                try:
                    info("Cracking any leftover crystals before retrying Collect+Crack...")
                    CrackCrystalsTask(
                        bot_state,
                        player_input,
                        inv,
                        grinder_tp,
                        grinder_view,
                        count=1
                    ).run()
                except Exception as e:
                    warn(f"Pre-retry CrackCrystalsTask failed or not applicable: {e}")

    t.join(timeout=1.0)
    info('Full combined test finished.')

if __name__ == '__main__':
    main()
